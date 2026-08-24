/**
 * whop_webhook_smoke.mjs — integration smoke for the REAL Express server.
 * =========================================================================
 * Boots server/index.js with WHOP_WEBHOOK_SECRET set, then proves:
 *   1. valid HMAC-SHA256 signature  -> 200 {received:true} + canonical event row
 *   2. tampered signature           -> 401
 *   3. missing secret header path   -> 401
 *   4. analytics beacon accepted    -> {success:true}
 *   5. duplicate beacon within 60s  -> {deduplicated:true}
 *
 * Run:  node MBM/Whop/tests/whop_webhook_smoke.mjs
 * Exit code 0 = all assertions passed.
 */

import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const EVENTS_FILE = path.join(REPO_ROOT, 'MBM', 'Whop', 'logs', 'revenue_events.jsonl');
const ANALYTICS_FILE = path.join(REPO_ROOT, 'MBM', 'Whop', 'analytics_log.json');
const PORT = 3937;
const SECRET = 'smoke_test_secret_only';

function loadEnvMinimal(file) {
  // Parse only what the server needs to boot; never log values.
  const needed = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY'];
  const env = {};
  if (!fs.existsSync(file)) return env;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && needed.includes(m[1])) {
      env[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  }
  return env;
}

async function waitForServer(url, tries = 240) {
  // NOTE: server/index.js performs heavy boot work (env injection, lead
  // pipeline) BEFORE app.listen() — allow up to ~2 minutes.
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url.replace('/api/webhook/whop', '/api/webhook/whop'), { method: 'GET' });
      if (res.status < 500) return true;   // 404 on GET == route table live
    } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

function sign(body) {
  return crypto.createHmac('sha256', SECRET).update(Buffer.from(body, 'utf8')).digest('hex');
}

let failures = 0;
function check(name, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) failures++;
}

const server = spawn(process.platform === 'win32' ? 'node' : 'node',
  [path.join(REPO_ROOT, 'server', 'index.js')], {
    cwd: REPO_ROOT,
    env: { ...process.env, ...loadEnvMinimal(path.join(REPO_ROOT, '.env')),
           WHOP_WEBHOOK_SECRET: SECRET, PORT: String(PORT) },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
let serverLog = '';
server.stdout.on('data', d => { serverLog += d; });
server.stderr.on('data', d => { serverLog += d; });
server.on('error', e => { serverLog += `\n[spawn error] ${e.message}`; });

try {
  const base = `http://127.0.0.1:${PORT}`;
  const up = await waitForServer(`${base}/api/webhook/whop`);
  check('server booted', up);
  if (!up) throw new Error(serverLog.slice(-800));

  const eventsBefore = fs.existsSync(EVENTS_FILE)
    ? fs.readFileSync(EVENTS_FILE, 'utf8').split('\n').filter(Boolean).length : 0;

  // 1) valid signed webhook
  const payload = JSON.stringify({ id: `smoke_${Date.now()}`, action: 'payment.succeeded',
    data: { payment: { amount: 29700 }, member: { user_id: 'usr_smoke' } } });
  const good = await fetch(`${base}/api/webhook/whop`, {
    method: 'POST', headers: { 'Content-Type': 'application/json',
      'x-whop-signature': sign(payload) }, body: payload });
  check('signed webhook -> 200', good.status === 200, `status=${good.status}`);

  const lines = fs.readFileSync(EVENTS_FILE, 'utf8').split('\n').filter(Boolean);
  check('canonical event stored', lines.length === eventsBefore + 1,
    `rows ${eventsBefore}->${lines.length}`);
  const evt = JSON.parse(lines[lines.length - 1]);
  check('canonical event normalized', evt.event_name === 'purchase'
    && evt.amount_usd === 297.0 && evt.customer_ref.user_id === 'usr_smoke');

  // idempotency: same webhook id replayed
  const replay = await fetch(`${base}/api/webhook/whop`, {
    method: 'POST', headers: { 'Content-Type': 'application/json',
      'x-whop-signature': sign(payload) }, body: payload });
  const replayBody = await replay.json();
  check('webhook replay deduplicated', replayBody.duplicate === true);

  // 2) tampered signature
  const bad = await fetch(`${base}/api/webhook/whop`, {
    method: 'POST', headers: { 'Content-Type': 'application/json',
      'x-whop-signature': 'deadbeef'.repeat(8) },
    body: JSON.stringify({ id: `evil_${Date.now()}`, action: 'payment.succeeded' }) });
  check('tampered signature -> 401', bad.status === 401, `status=${bad.status}`);

  // 3) missing signature
  const noSig = await fetch(`${base}/api/webhook/whop`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: '{"id":"nosig"}' });
  check('missing signature -> 401', noSig.status === 401, `status=${noSig.status}`);

  // 4+5) analytics beacon + dedupe window
  const beaconBody = { event: 'landing_view', session_id: 'smoke_sess',
    utm_source: 'smoke', landing_variant: 'A', props: { landing_variant: 'A' } };
  const b1 = await fetch(`${base}/api/analytics/track`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(beaconBody) });
  check('analytics beacon accepted', b1.status === 200);
  const b2 = await fetch(`${base}/api/analytics/track`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(beaconBody) });
  const b2j = await b2.json();
  check('duplicate beacon deduplicated within 60s', b2j.deduplicated === true);

  const rejected = await fetch(`${base}/api/analytics/track`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event: '<script>' }) });
  check('unknown event rejected 400', rejected.status === 400, `status=${rejected.status}`);
} catch (e) {
  check('smoke run completed', false, String(e).slice(0, 300));
} finally {
  server.kill('SIGTERM');
}

console.log(failures === 0 ? '\nSMOKE RESULT: ALL PASS' : `\nSMOKE RESULT: ${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
