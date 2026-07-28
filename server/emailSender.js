import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';

const nodemailer = await import('nodemailer').then(m => m.default);

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co';

// Parse sender pool: "email:password,email:password,..."
// Falls back to single-account mode with SMTP_USER/SMTP_PASS
const senderPoolRaw = process.env.SMTP_SENDER_POOL || '';
const senderAccounts = [];

if (senderPoolRaw.includes(':')) {
  // Multi-account mode: email:password pairs
  for (const entry of senderPoolRaw.split(',').map(e => e.trim()).filter(Boolean)) {
    const [email, ...passParts] = entry.split(':');
    senderAccounts.push({ email: email.trim(), pass: passParts.join(':').trim() });
  }
} else {
  // Single-account fallback
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
  });
}

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function sendOne(transporter, supabase, email, fromAddress, fromName) {
  try {
    await transporter.sendMail({
      from: `"${fromName}" <${fromAddress}>`,
      to: email.recipient_email,
      subject: email.subject,
      text: email.body,
      html: email.body.includes('<') ? email.body : undefined,
    });
    await supabase
      .from('email_queue')
      .update({ status: 'sent', sent_at: new Date().toISOString(), updated_at: new Date().toISOString() })
      .eq('id', email.id);
    return { id: email.id, status: 'sent', sender: fromAddress };
  } catch (err) {
    await supabase
      .from('email_queue')
      .update({ status: 'failed', error: err.message, updated_at: new Date().toISOString() })
      .eq('id', email.id);
    return { id: email.id, status: 'failed', error: err.message };
  }
}

export async function sendEmailQueue({ supabase, batchSize = 5000, continuous = false } = {}) {
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabase) {
    if (!serviceRoleKey) {
      throw new Error('SUPABASE_SERVICE_ROLE_KEY env var required');
    }
    supabase = createClient(supabaseUrl, serviceRoleKey);
  }

  // Build transporter pool with per-account credentials
  const poolTransporters = senderAccounts.map(acct => ({
    address: acct.email,
    transporter: getTransporter(acct.email, acct.pass)
  }));

  console.log(`[emailSender] Multi-Account Pool: ${poolTransporters.length} accounts`);
  poolTransporters.forEach(p => console.log(`  - ${p.address}`));

  const fromName = process.env.SMTP_FROM_NAME || 'Contech AI Agentic Teamz';
  const sendDelay = parseInt(process.env.EMAIL_SEND_DELAY_MS || '100');
  const concurrency = parseInt(process.env.EMAIL_CONCURRENCY || '5');

  let totalSent = 0;
  let totalFailed = 0;
  let iterations = 0;

  while (true) {
    const { data: emails, error } = await supabase
      .from('email_queue')
      .select('*')
      .eq('status', 'qued')
      .limit(batchSize)
      .order('created_at', { ascending: true });

    if (error) throw new Error(`Failed to fetch queue: ${error.message}`);
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

    // Send in parallel batches with round-robin pool rotation
    for (let i = 0; i < emails.length; i += concurrency) {
      const batch = emails.slice(i, i + concurrency);
      const results = await Promise.allSettled(
        batch.map((email, idx) => {
          const poolObj = poolTransporters[(i + idx) % poolTransporters.length];
          return sendOne(poolObj.transporter, supabase, email, poolObj.address, fromName);
        })
      );

      for (const r of results) {
        if (r.status === 'fulfilled' && r.value.status === 'sent') sent++;
        else failed++;
      }

      if (sendDelay > 0 && i + concurrency < emails.length) {
        await delay(sendDelay);
      }
    }

    totalSent += sent;
    totalFailed += failed;
    console.log(`[emailSender] Batch sent ${sent}, failed ${failed} (total: ${totalSent} sent, ${totalFailed} failed)`);

    if (!continuous) break;
  }

  return { sent: totalSent, failed: totalFailed, total: totalSent + totalFailed };
}

if (process.argv[1]?.endsWith('emailSender.js')) {
  const continuous = process.argv.includes('--continuous');
  const batchSizeArg = process.argv.find(arg => arg.startsWith('--batchSize='));
  const batchSize = batchSizeArg ? parseInt(batchSizeArg.split('=')[1], 10) : 5000;
  const result = await sendEmailQueue({ batchSize, continuous });
  console.log('FINAL:', JSON.stringify(result));
}
