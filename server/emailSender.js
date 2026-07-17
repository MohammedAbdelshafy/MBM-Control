import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';

const nodemailer = await import('nodemailer').then(m => m.default);

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co';

function getTransporter() {
  const pass = (process.env.SMTP_PASS || '').replace(/\s+/g, '');
  const host = process.env.SMTP_HOST || 'smtp.gmail.com';
  const port = parseInt(process.env.SMTP_PORT || '587');
  return nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user: process.env.SMTP_USER, pass },
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
    return { id: email.id, status: 'sent' };
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

  const transporter = getTransporter();
  const fromAddress = process.env.SMTP_FROM || 'noreply@contechai.com';
  const fromName = process.env.SMTP_FROM_NAME || 'Contech AI Agentic teamz';
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

    // Send in parallel batches with concurrency limit
    for (let i = 0; i < emails.length; i += concurrency) {
      const batch = emails.slice(i, i + concurrency);
      const results = await Promise.allSettled(
        batch.map(email => sendOne(transporter, supabase, email, fromAddress, fromName))
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
