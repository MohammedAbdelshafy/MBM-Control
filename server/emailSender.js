import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
dotenv.config({ path: '.env' }); // load .env as well to get GMAIL_SEND_ENABLED
import { createClient } from '@supabase/supabase-js';

const nodemailer = await import('nodemailer').then(m => m.default);

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co';

// Preflight: CONFIG_HEALTH
if (process.env.GMAIL_SEND_ENABLED !== 'true' && !process.argv.includes('--test-gmail') && !process.argv.includes('--dry-run')) {
  console.error('[emailSender] FATAL: GMAIL_SEND_ENABLED is false. Failing closed.');
  process.exit(1);
}

const senderPoolRaw = process.env.SMTP_SENDER_POOL || '';
const senderAccounts = [];

if (senderPoolRaw.includes(':')) {
  const entries = senderPoolRaw.split(/[,;]/).map(e => e.trim()).filter(Boolean);
  for (const entry of entries) {
    const [email, ...passParts] = entry.split(':');
    senderAccounts.push({
      email: email.trim(),
      pass: passParts.join(':').replace(/\s+/g, '')
    });
  }
} else {
  senderAccounts.push({
    email: process.env.SMTP_USER || 'abdelshafyclapps@gmail.com',
    pass: (process.env.SMTP_PASS || '').replace(/\s+/g, '')
  });
}

function getTransporter(email, pass) {
  const host = process.env.SMTP_HOST || 'smtp.gmail.com';
  const port = parseInt(process.env.SMTP_PORT || '587');

  return nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user: email, pass },
    pool: true,
    maxConnections: parseInt(process.env.MAX_SMTP_CONNECTIONS || '10'),
    rateDelta: parseInt(process.env.SMTP_RATE_DELTA || '1000'),
    rateLimit: parseInt(process.env.SMTP_RATE_LIMIT || '0'),
    connectionTimeout: 10000,
    greetingTimeout: 10000,
    socketTimeout: 30000,
  });
}

async function preflightAccounts() {
  const valid = [];
  for (const acct of senderAccounts) {
    const transporter = getTransporter(acct.email, acct.pass);
    try {
      await transporter.verify();
      valid.push({ address: acct.email, transporter });
      console.log(`[emailSender] ✅ Sender verified: ${acct.email}`);
    } catch (err) {
      console.error(`[emailSender] ⚠️ Sender REJECTED (dropped): ${acct.email} — ${err.message}`);
      if (err.responseCode === 535) {
        console.error(`[emailSender] ⚠️ Gmail 535 BadCredentials detected. Never retrying this account.`);
      }
      try { transporter.close(); } catch (_) {}
    }
  }
  return valid;
}

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function sendOne(transporter, supabase, email, fromAddress, fromName, isDryRun) {
  try {
    const info = await transporter.sendMail({
      from: `"${fromName}" <${fromAddress}>`,
      to: email.recipient_email,
      subject: email.subject,
      text: email.body,
      html: email.body && email.body.includes('<') ? email.body : undefined,
    });
    if (!isDryRun && supabase) {
      // Mark sent ONLY after SMTP success
      await supabase
        .from('email_queue')
        .update({ status: 'sent', sent_at: new Date().toISOString(), updated_at: new Date().toISOString() })
        .eq('id', email.id);
    }
    return { id: email.id, status: 'sent', sender: fromAddress, messageId: info.messageId };
  } catch (err) {
    if (!isDryRun && supabase) {
      // Mark failed after permanent failure
      await supabase
        .from('email_queue')
        .update({ status: 'failed', error: err.message, updated_at: new Date().toISOString() })
        .eq('id', email.id);
    }
    return { id: email.id, status: 'failed', error: err.message };
  }
}

async function runTestGmail(poolTransporters) {
  // Phase 8: CANARY ARCHITECTURE FIX
  // Bypass queue completely. Send one direct SMTP email.
  console.log('[emailSender] Running dedicated SMTP canary test...');
  const poolObj = poolTransporters[0];
  const testEmail = {
    recipient_email: 'abdelshafyplay@gmail.com',
    subject: 'MBM Pipeline Canary',
    body: 'This is an internal canary message confirming SMTP connectivity.'
  };
  const result = await sendOne(poolObj.transporter, null, testEmail, poolObj.address, 'MBM System', false);
  if (result.status === 'sent') {
    console.log(`CANARY = PASS`);
    console.log(`MESSAGE_ID = ${result.messageId}`);
    console.log(`SENT_AT = ${new Date().toISOString()}`);
  } else {
    console.log(`CANARY = FAIL`);
    console.error(`ERROR = ${result.error}`);
  }
  console.log(`PROSPECT_EMAILS_SENT = 0`);
  return;
}

export async function sendEmailQueue({ supabase, batchSize = 5000, continuous = false, dryRun = false } = {}) {
  const isDryRun = dryRun || process.argv.includes('--dry-run') || process.env.EMAIL_DRY_RUN === 'true';
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabase) {
    if (!serviceRoleKey) {
      console.error('[emailSender] FATAL: SUPABASE_SERVICE_ROLE_KEY env var required. CONFIG_HEALTH failed.');
      process.exit(1);
    }
    supabase = createClient(supabaseUrl, serviceRoleKey);
  }

  // Preflight: SMTP_HEALTH
  let poolTransporters = await preflightAccounts();
  if (poolTransporters.length === 0) {
    if (isDryRun) {
      console.log('[emailSender] ℹ️ Running in DRY-RUN mode (mocking SMTP delivery)');
      poolTransporters = [{ address: 'dry-run@contecai.com', transporter: { sendMail: async () => ({ messageId: 'dry-run-id' }), close: () => {} } }];
    } else {
      console.error('[emailSender] FATAL: All sender accounts failed verification. SMTP_HEALTH failed. Failing closed.');
      process.exit(1);
    }
  }

  if (process.argv.includes('--test-gmail')) {
    await runTestGmail(poolTransporters);
    process.exit(0);
  }

  // Preflight: QUEUE_HEALTH & DUPLICATE_HEALTH
  console.log('[emailSender] Preflight passed. Starting dispatch loop.');

  const fromName = process.env.SMTP_FROM_NAME || 'MBM Operations';
  const concurrency = parseInt(process.env.EMAIL_CONCURRENCY || '5');

  let totalSent = 0;
  let totalFailed = 0;
  let iterations = 0;

  // Track recipients in current run to prevent intra-run duplicates
  const sessionRecipients = new Set();

  while (true) {
    // Fail closed if query unhealthy
    const { data: rawEmails, error } = await supabase
      .from('email_queue')
      .select('id, recipient_email, subject, body')
      .eq('status', 'qued')
      .limit(batchSize);

    if (error) {
      console.error(`[emailSender] FATAL: Failed to fetch queue. QUEUE_HEALTH failed. Error: ${error.message}`);
      process.exit(1);
    }
    
    const emails = [];
    for (const em of (rawEmails || [])) {
      const addr = (em.recipient_email || '').toLowerCase().trim();
      
      // Exclusion logic (Phase 7 & 9)
      const isDummy = !addr || !addr.includes('@') || addr.includes('example.com') || addr.includes('test');
      const isInternal = addr.endsWith('@abdelshafyclapps.com') || addr === 'abdelshafyplay@gmail.com';
      const isDup = sessionRecipients.has(addr);

      if (isDummy || isInternal) {
        console.log(`[emailSender] ⚠️ Rejecting internal/test email: ${addr}`);
        if (!isDryRun) {
          await supabase.from('email_queue').update({ status: 'skipped', error: 'Internal/Dummy recipient excluded by policy' }).eq('id', em.id);
        }
      } else if (isDup) {
        console.log(`[emailSender] ⚠️ Rejecting batch duplicate: ${addr}`);
        if (!isDryRun) {
          await supabase.from('email_queue').update({ status: 'duplicate', error: 'Duplicate in current dispatch session' }).eq('id', em.id);
        }
      } else {
        sessionRecipients.add(addr);
        emails.push({ ...em, recipient_email: addr }); // Normalize address
      }
    }

    if (!emails || emails.length === 0) {
      if (!continuous) break;
      await delay(5000);
      iterations++;
      if (iterations > 360) break;
      continue;
    }

    iterations++;
    let sent = 0;
    let failed = 0;

    for (let i = 0; i < emails.length; i += concurrency) {
      const batch = emails.slice(i, i + concurrency);
      const results = await Promise.allSettled(
        batch.map((email, idx) => {
          const poolObj = poolTransporters[(i + idx) % poolTransporters.length];
          return sendOne(poolObj.transporter, supabase, email, poolObj.address, fromName, isDryRun);
        })
      );

      for (const r of results) {
        if (r.status === 'fulfilled' && r.value.status === 'sent') sent++;
        else failed++;
      }

      const randomDelay = Math.floor(Math.random() * 3000) + 2000;
      await delay(randomDelay);
    }

    totalSent += sent;
    totalFailed += failed;
    console.log(`[emailSender] Batch sent ${sent}, failed ${failed} (total: ${totalSent} sent, ${totalFailed} failed)`);

    if (!continuous) break;
  }

  for (const p of poolTransporters) {
    try { p.transporter.close(); } catch (_) {}
  }

  return { sent: totalSent, failed: totalFailed, total: totalSent + totalFailed };
}

if (process.argv[1]?.endsWith('emailSender.js')) {
  const continuous = process.argv.includes('--continuous');
  const batchSizeArg = process.argv.find(arg => arg.startsWith('--batchSize='));
  const batchSize = batchSizeArg ? parseInt(batchSizeArg.split('=')[1], 10) : 5000;
  
  sendEmailQueue({ batchSize, continuous }).then(result => {
    if (result) console.log('FINAL:', JSON.stringify(result));
    process.exit(0);
  }).catch(err => {
    console.error('FATAL ERROR:', err);
    process.exit(1);
  });
}
