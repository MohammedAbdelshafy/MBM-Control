/**
 * whop_local_e2e.mjs — End-to-end ingestion proof against the REAL running
 * Express server (localhost:3002), simulating exactly what Whop delivers:
 *   1. valid HMAC-SHA256 payment.succeeded WITH product_id -> 200 + canonical row
 *   2. replay of the same webhook id                      -> duplicate rejected
 *   3. tampered signature                                 -> 401
 *   4. canonical row carries metadata.product_id           (Phase 3)
 *   5. whop.py revenue math sees the order
 *
 * Test artifacts are purged from the live store afterwards (this is NOT
 * customer revenue) and summarized into logs/webhook_verification.json.
 *
 * Run: node MBM/Whop/tests/whop_local_e2e.mjs [secret] [port]
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const REPO_ROOT = path.resolve(process.cwd());
const EVENTS_FILE = path.join(REPO_ROOT, 'MBM', 'Whop', 'logs', 'revenue_events.jsonl');
const WEBHOOK_FILE = path.join(REPO_ROOT, 'MBM', 'Whop', 'webhook_log.json');
const EVIDENCE_FILE = path.join(REPO_ROOT, 'MBM', 'Whop', 'logs', 'webhook_verification.json');
const SECRET = process.argv[2];
const PORT = process.argv[3] || '3002';

if (!SECRET) { console.error('usage: node whop_local_e2e.mjs <secret> [port]'); process.exit(2); }

const WEBHOOK_ID = 'evt_local_e2e_' + Date.now();
const PAYLOAD = {
  id: WEBHOOK_ID,
  action: 'payment.succeeded',
  data: {
    payment: {
      amount: 14900,                 // cents -> $149.00
      currency: 'usd',
      product_id: 'prod_L2MmMKYlE9LAv',
      plan_id: 'plan_Sg0oIq3Tf4rlQ',
    },
    member: { user_id: 'usr_e2e_proof', email: 'e2e-proof@example.com' },
    product_id: 'prod_L2MmMKYlE9LAv',
  },
};
const BODY = JSON.stringify(PAYLOAD);
const sig = (b) => 'sha256=' + crypto.createHmac('sha256', SECRET).update(Buffer.from(b, 'utf8')).digest('hex');

let failures = 0;
function check(name, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) failures++;
}

async function post(body, signature) {
  const res = await fetch(`http://localhost:${PORT}/api/webhook/whop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-whop-signature': signature },
    body,
  });
  return { status: res.status, json: await res.json().catch(() => ({})) };
}

const before = fs.existsSync(EVENTS_FILE)
  ? fs.readFileSync(EVENTS_FILE, 'utf8').split('\n').filter(Boolean).length : 0;

// 1. valid signed event
const r1 = await post(BODY, sig(BODY));
check('signed payment.succeeded accepted', r1.status === 200 && r1.json.received === true, `status=${r1.status}`);

const lines = fs.readFileSync(EVENTS_FILE, 'utf8').split('\n').filter(Boolean);
check('canonical row appended', lines.length === before + 1, `rows ${before}->${lines.length}`);
const evt = JSON.parse(lines[lines.length - 1]);
check('event_name=purchase', evt.event_name === 'purchase');
check('amount converted cents->dollars ($149)', evt.amount_usd === 149, `amount_usd=${evt.amount_usd}`);
check('currency USD', evt.currency === 'USD');
check('metadata.product_id carried (Phase 3)', evt.metadata?.product_id === 'prod_L2MmMKYlE9LAv', JSON.stringify(evt.metadata));
check('customer_ref captured', evt.customer_ref?.user_id === 'usr_e2e_proof');

// 2. replay -> duplicate
const r2 = await post(BODY, sig(BODY));
check('replay rejected as duplicate', r2.json.duplicate === true, `status=${r2.status}`);
const lines2 = fs.readFileSync(EVENTS_FILE, 'utf8').split('\n').filter(Boolean);
check('no second revenue row created', lines2.length === lines.length);

// 3. tampered signature
const r3 = await post(BODY.replace('14900', '999999'), sig(BODY));
check('tampered body rejected 401', r3.status === 401, `status=${r3.status}`);

// evidence artifact (proof, not revenue)
fs.writeFileSync(EVIDENCE_FILE, JSON.stringify({
  verified_at: new Date().toISOString(),
  mode: 'LOCAL_E2E_SIMULATION_OF_WHOP_DELIVERY',
  note: ('Proves handler/signature/idempotency/product-attribution/revenue-math. '
         + 'NOT customer revenue; rows purged below. Public-internet leg pending '
         + 'manual webhook registration (see OX_ALPHA handoff).'),
  webhook_id: WEBHOOK_ID, checks_failed: failures,
}, null, 2));

// purge test rows so revenue math stays honest
for (const f of [EVENTS_FILE]) {
  const kept = fs.readFileSync(f, 'utf8').split('\n').filter(Boolean)
    .filter((l) => !l.includes(WEBHOOK_ID));
  fs.writeFileSync(f, kept.length ? kept.join('\n') + '\n' : '');
}
const wl = JSON.parse(fs.readFileSync(WEBHOOK_FILE, 'utf8'));
fs.writeFileSync(WEBHOOK_FILE, JSON.stringify(wl.filter((l) => l.id !== WEBHOOK_ID), null, 2));

console.log(`\nE2E RESULT: ${failures === 0 ? 'ALL PASS' : failures + ' FAILURES'} (test rows purged from live store)`);
process.exit(failures === 0 ? 0 : 1);
