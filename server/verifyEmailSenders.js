// Verify every SMTP sender account currently in SMTP_SENDER_POOL / SMTP_USER.
// Usage:  node server/verifyEmailSenders.js
// Prints a PASS/FAIL per account so you can update .env.local quickly.
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

const nodemailer = await import('nodemailer').then(m => m.default);

const poolRaw = process.env.SMTP_SENDER_POOL || '';
const accounts = [];

if (poolRaw.includes(':')) {
  for (const entry of poolRaw.split(/[,;]/).map(e => e.trim()).filter(Boolean)) {
    const [email, ...passParts] = entry.split(':');
    accounts.push({ email: email.trim(), pass: passParts.join(':').replace(/\s+/g, '') });
  }
} else {
  accounts.push({
    email: process.env.SMTP_USER || 'abdelshafyclapps@gmail.com',
    pass: (process.env.SMTP_PASS || '').replace(/\s+/g, ''),
  });
}

const host = process.env.SMTP_HOST || 'smtp.gmail.com';
const port = parseInt(process.env.SMTP_PORT || '587');
const results = [];

for (const acct of accounts) {
  if (!acct.pass || /^[xX*]{4,}/.test(acct.pass) || acct.pass === 'REPLACE_WITH_NEW_APP_PASSWORD') {
    results.push({ email: acct.email, status: 'NEEDS_APP_PASSWORD', reason: 'password empty or still a placeholder' });
    continue;
  }
  const t = nodemailer.createTransport({ host, port, secure: port === 465, auth: { user: acct.email, pass: acct.pass } });
  try {
    await t.verify();
    results.push({ email: acct.email, status: 'PASS' });
  } catch (err) {
    results.push({ email: acct.email, status: 'FAIL', reason: err.response || err.message });
  } finally {
    t.close();
  }
}

console.log('\n===== SENDER VERIFICATION =====');
for (const r of results) {
  console.log(`${r.status === 'PASS' ? '✅ PASS ' : r.status === 'NEEDS_APP_PASSWORD' ? '🔑 ' + r.status.padEnd(8) : '❌ FAIL '} ${r.email}`);
  if (r.reason) console.log(`      ${r.reason}`);
}
const ok = results.filter(r => r.status === 'PASS').length;
console.log(`\n${ok}/${results.length} senders usable.`);
process.exit(ok > 0 ? 0 : 1);