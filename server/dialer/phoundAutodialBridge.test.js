/**
 * phoundAutodialBridge.test.js — HTTP control-surface tests.
 *
 * Proves the bridge delegates without deciding: validation, DRY_RUN default,
 * approval-gate passthrough, unknown-state surfacing (no retry path),
 * duplicate-worker passthrough, provider-failure envelopes, secret redaction.
 * The Python state machine itself is covered by
 * MBM/LeadEngine/tests/test_phound_auto_dialer.py (run via pytest).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

const bridge = await import('./phoundAutodialBridge.js');
const { buildArgs, runAutodial, redactSecrets, BridgeValidationError } = bridge;

// ── arg building: control ops ────────────────────────────────────────────

test('control ops map to single backend flags', () => {
  for (const op of ['status', 'pause', 'resume', 'stop', 'reconcile']) {
    assert.deepEqual(buildArgs(op), { argv: [`--${op}`], dryRun: null });
  }
});

test('unknown op rejected', () => {
  assert.throws(() => buildArgs('launch'), BridgeValidationError);
});

test('non-object params rejected', () => {
  assert.throws(() => buildArgs('start', [1]), BridgeValidationError);
  assert.throws(() => buildArgs('start', 'x'), BridgeValidationError);
});

// ── arg building: start validation ───────────────────────────────────────

test('start defaults to ASSISTED dry-run', () => {
  const { argv, dryRun } = buildArgs('start', {});
  assert.ok(argv.includes('--mode') && argv.includes('ASSISTED'));
  assert.ok(argv.includes('--dry-run') && !argv.includes('--apply'));
  assert.equal(dryRun, true);
});

test('start caps and filters map to backend flags', () => {
  const { argv } = buildArgs('start', {
    mode: 'AUTO_DIAL', limit: 25, vertical: 'Clinics', statusFilter: 'QUEUED',
    maxInFlight: 2, pacingSeconds: 30, cooldownSeconds: 60,
    dailyCap: 50, sessionCap: 20, live: true,
  });
  for (const flag of ['--mode', 'AUTO_DIAL', '--limit', '25', '--vertical', 'Clinics',
    '--status-filter', 'QUEUED', '--max-in-flight', '2', '--pacing-seconds', '30',
    '--cooldown-seconds', '60', '--daily-cap', '50', '--session-cap', '20', '--apply']) {
    assert.ok(argv.includes(flag), `missing ${flag}`);
  }
});

test('live must be explicit boolean true', () => {
  assert.ok(buildArgs('start', { live: 'true' }).argv.includes('--dry-run'));
  assert.ok(buildArgs('start', { live: 1 }).argv.includes('--dry-run'));
  assert.ok(buildArgs('start', { live: true }).argv.includes('--apply'));
});

test('invalid mode rejected', () => {
  assert.throws(() => buildArgs('start', { mode: 'TURBO' }), BridgeValidationError);
});

test('out-of-range numerics rejected', () => {
  assert.throws(() => buildArgs('start', { limit: 0 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { limit: 101 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { limit: 2.5 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { maxInFlight: 0 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { maxInFlight: 6 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { pacingSeconds: -1 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { cooldownSeconds: 90000 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { dailyCap: 0 }), BridgeValidationError);
  assert.throws(() => buildArgs('start', { sessionCap: 201 }), BridgeValidationError);
});

test('overlong strings rejected', () => {
  assert.throws(() => buildArgs('start', { vertical: 'x'.repeat(65) }), BridgeValidationError);
});

// ── secret rejection ─────────────────────────────────────────────────────

test('credential-shaped body fields rejected without echo', () => {
  for (const key of ['personaUid', 'persona_uid', 'PHOUND_TOKEN', 'token',
    'personas', 'sbc', 'env']) {
    let msg = '';
    try {
      buildArgs('start', { [key]: 'anything' });
    } catch (err) {
      msg = err.message;
    }
    assert.match(msg, /never accepted/, key);
    assert.ok(!msg.includes('anything'), `value leaked for ${key}`);
  }
});

test('redactSecrets scrubs token shapes', () => {
  const dirty = 'failed with uid12345.abcdef123456 and Bearer abcDEF123 and PHOUND_TOKEN=uid1.secretkey9';
  const clean = redactSecrets(dirty);
  assert.ok(!clean.includes('abcdef123456'));
  assert.ok(!clean.includes('abcDEF123'));
  assert.ok(!clean.includes('secretkey9'));
  assert.ok(clean.includes('<redacted'));
});

// ── runAutodial delegation (injected spawn) ──────────────────────────────

const okSpawn = (payload, code = 0) => async () => ({
  code, stdout: JSON.stringify(payload), stderr: '', timedOut: false,
});

test('status delegates and returns backend verbatim', async () => {
  const backend = { status: 'success', paused: false, in_flight_count: 0 };
  const seen = [];
  const spawnFn = async (python, argv) => {
    seen.push([python, argv]);
    return { code: 0, stdout: JSON.stringify(backend), stderr: '', timedOut: false };
  };
  const { httpStatus, body } = await runAutodial('status', {}, { spawnFn });
  assert.equal(httpStatus, 200);
  assert.equal(body.ok, true);
  assert.deepEqual(body.backend, backend);
  assert.ok(seen[0][1].some((a) => String(a).includes('phound_auto_dialer.py')));
  assert.ok(seen[0][1].includes('--status'));
});

test('missing approval surfaces as blocked, not error', async () => {
  const backend = {
    status: 'success', mode: 'ASSISTED',
    capability: { allowed: false, reason: 'AUTO_DIAL requires PHOUND_AUTODIAL_APPROVED=1', fallback: 'ASSISTED' },
    outcomes: [],
  };
  const { httpStatus, body } = await runAutodial(
    'start', { mode: 'AUTO_DIAL' }, { spawnFn: okSpawn(backend) });
  assert.equal(httpStatus, 200);
  assert.equal(body.ok, true);
  assert.equal(body.blocked, true);
  assert.match(body.blockedReason, /PHOUND_AUTODIAL_APPROVED/);
  assert.equal(body.fallback, 'ASSISTED');
  assert.equal(body.dryRun, true);
});

test('unknown provider state surfaces reconciliation, no retry', async () => {
  const backend = {
    status: 'success', mode: 'ASSISTED', dry_run: false,
    outcomes: [{ status: 'unknown_provider_state', lead_id: 'L1', reconciliation_required: true }],
  };
  const { httpStatus, body } = await runAutodial(
    'start', { live: true }, { spawnFn: okSpawn(backend) });
  assert.equal(httpStatus, 200);
  assert.equal(body.reconciliationRequired, true);
  assert.match(body.hint, /Never redial/);
  assert.ok(!('retry' in body) || body.retry !== true);
});

test('duplicate worker outcome passes through untouched', async () => {
  const backend = { status: 'success', outcomes: [{ status: 'duplicate_suppressed', lead_id: 'D1' }] };
  const { body } = await runAutodial('start', {}, { spawnFn: okSpawn(backend) });
  assert.equal(body.backend.outcomes[0].status, 'duplicate_suppressed');
  assert.equal(body.reconciliationRequired, undefined);
});

test('provider unavailable (non-zero exit) becomes 502 with redacted detail', async () => {
  const spawnFn = async () => ({
    code: 2, stdout: '', stderr: 'boom TOKEN=uid9.supersecretvalue here', timedOut: false,
  });
  const { httpStatus, body } = await runAutodial('status', {}, { spawnFn });
  assert.equal(httpStatus, 502);
  assert.equal(body.ok, false);
  assert.ok(!JSON.stringify(body).includes('supersecretvalue'));
});

test('non-JSON backend output becomes 502', async () => {
  const spawnFn = async () => ({ code: 0, stdout: 'traceback...', stderr: 'x', timedOut: false });
  const { httpStatus, body } = await runAutodial('status', {}, { spawnFn });
  assert.equal(httpStatus, 502);
  assert.match(body.error, /non-JSON/);
});

test('spawn timeout becomes 504 with no-retry guidance', async () => {
  const spawnFn = async () => ({ code: -1, stdout: '', stderr: '', timedOut: true });
  const { httpStatus, body } = await runAutodial('start', { live: true }, { spawnFn });
  assert.equal(httpStatus, 504);
  assert.equal(body.retrySafe, false);
  assert.match(body.hint, /reconcile/i);
});

test('validation failure returns 400 without spawning', async () => {
  let spawned = false;
  const spawnFn = async () => { spawned = true; return { code: 0, stdout: '{}', stderr: '', timedOut: false }; };
  const { httpStatus, body } = await runAutodial('start', { mode: 'NOPE' }, { spawnFn });
  assert.equal(httpStatus, 400);
  assert.equal(body.ok, false);
  assert.equal(spawned, false);
});
