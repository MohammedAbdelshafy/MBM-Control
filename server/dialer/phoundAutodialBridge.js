/**
 * phoundAutodialBridge.js — thin HTTP adapter over the Python Auto-Dial
 * state machine (MBM/LeadEngine/phound_auto_dialer.py, PR #46).
 *
 * This module contains ZERO queue logic, ZERO pacing/cooldown/cap decisions,
 * ZERO state machine, and ZERO retry policy. Every operation delegates to the
 * existing backend CLI and returns its verdict verbatim inside a small HTTP
 * envelope. The browser can never bypass backend controls through this layer:
 *
 *  - DRY_RUN is the default; live placement needs explicit `live: true`
 *    AND the backend's own PHOUND_AUTODIAL_APPROVED + API-health gates.
 *  - Secrets are never accepted from the request body (persona/token fields
 *    are rejected) and never echoed back (stderr/stdout excerpts redacted).
 *  - `unknown_provider_state` outcomes pass through with
 *    `reconciliationRequired: true` and no retry affordance.
 *  - Lifecycle event ingestion stays webhook-only
 *    (POST /api/telephony/phound/webhook); no event endpoint is added here.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const AUTODIAL_SCRIPT = path.join(HERE, '..', '..', 'MBM', 'LeadEngine', 'phound_auto_dialer.py');

export const MODES = ['MANUAL', 'ASSISTED', 'AUTO_DIAL', 'ANDROID_SIM_ASSISTED'];
export const READ_OPS = ['status'];
export const CONTROL_OPS = ['pause', 'resume', 'stop', 'reconcile'];
export const OPS = [...READ_OPS, ...CONTROL_OPS, 'start'];

// Request-body keys that must never arrive from the browser. Values are
// never logged — the rejection names the field only.
const FORBIDDEN_BODY_KEYS = new Set([
  'personauid', 'persona_uid', 'phound_token', 'token', 'phound_api_token',
  'phound_personas', 'personas', 'sbc', 'phound_sbc', 'env',
]);

const INT_BOUNDS = {
  limit: [1, 100],
  maxInFlight: [1, 5],
  dailyCap: [1, 1000],
  sessionCap: [1, 200],
};
const FLOAT_BOUNDS = {
  pacingSeconds: [0, 600],
  cooldownSeconds: [0, 86400],
};
const STR_FIELDS = { vertical: 64, statusFilter: 64 };

export class BridgeValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'BridgeValidationError';
    this.httpStatus = 400;
  }
}

function intParam(params, name, [min, max]) {
  const v = params[name];
  if (v === undefined || v === null) return undefined;
  if (typeof v !== 'number' || !Number.isInteger(v) || v < min || v > max) {
    throw new BridgeValidationError(
      `${name} must be an integer ${min}..${max}`);
  }
  return v;
}

function floatParam(params, name, [min, max]) {
  const v = params[name];
  if (v === undefined || v === null) return undefined;
  if (typeof v !== 'number' || !Number.isFinite(v) || v < min || v > max) {
    throw new BridgeValidationError(
      `${name} must be a number ${min}..${max}`);
  }
  return v;
}

function strParam(params, name, maxLen) {
  const v = params[name];
  if (v === undefined || v === null) return undefined;
  if (typeof v !== 'string' || v.length === 0 || v.length > maxLen) {
    throw new BridgeValidationError(
      `${name} must be a non-empty string up to ${maxLen} chars`);
  }
  return v;
}

/**
 * Build the backend CLI argv for an operation. Pure function — no I/O.
 * Throws BridgeValidationError (httpStatus 400) on any invalid input.
 */
export function buildArgs(op, params = {}) {
  if (!OPS.includes(op)) {
    throw new BridgeValidationError(
      `unknown op '${String(op).slice(0, 32)}'. expected one of ${OPS.join(', ')}`);
  }
  if (params === null || typeof params !== 'object' || Array.isArray(params)) {
    throw new BridgeValidationError('params must be a JSON object');
  }
  for (const key of Object.keys(params)) {
    if (FORBIDDEN_BODY_KEYS.has(key.toLowerCase())) {
      throw new BridgeValidationError(
        `field '${key}' is never accepted from the client`);
    }
  }
  if (op !== 'start') {
    return { argv: [`--${op}`], dryRun: null };
  }
  const mode = params.mode === undefined ? 'ASSISTED' : params.mode;
  if (!MODES.includes(mode)) {
    throw new BridgeValidationError(
      `mode must be one of ${MODES.join(', ')}`);
  }
  const argv = ['--mode', mode];
  const limit = intParam(params, 'limit', INT_BOUNDS.limit) ?? 10;
  argv.push('--limit', String(limit));
  const vertical = strParam(params, 'vertical', STR_FIELDS.vertical);
  if (vertical) argv.push('--vertical', vertical);
  const statusFilter = strParam(params, 'statusFilter', STR_FIELDS.statusFilter);
  if (statusFilter) argv.push('--status-filter', statusFilter);
  const maxInFlight = intParam(params, 'maxInFlight', INT_BOUNDS.maxInFlight);
  if (maxInFlight !== undefined) argv.push('--max-in-flight', String(maxInFlight));
  const pacing = floatParam(params, 'pacingSeconds', FLOAT_BOUNDS.pacingSeconds);
  if (pacing !== undefined) argv.push('--pacing-seconds', String(pacing));
  const cooldown = floatParam(params, 'cooldownSeconds', FLOAT_BOUNDS.cooldownSeconds);
  if (cooldown !== undefined) argv.push('--cooldown-seconds', String(cooldown));
  const dailyCap = intParam(params, 'dailyCap', INT_BOUNDS.dailyCap);
  if (dailyCap !== undefined) argv.push('--daily-cap', String(dailyCap));
  const sessionCap = intParam(params, 'sessionCap', INT_BOUNDS.sessionCap);
  if (sessionCap !== undefined) argv.push('--session-cap', String(sessionCap));

  // DRY_RUN default: only an explicit boolean true opts into live placement.
  // The backend still enforces its own approval + persona + health gates.
  const live = params.live === true;
  argv.push(live ? '--apply' : '--dry-run');
  return { argv, dryRun: !live };
}

const TOKEN_RE = /\b[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{8,}\b/g;
const BEARER_RE = /Bearer\s+[A-Za-z0-9._~+/-]+/gi;
const ASSIGN_RE = /(PHOUND_TOKEN|PHOUND_API_TOKEN|TOKEN)\s*=\s*\S+/g;

/** Redact credential-shaped substrings before they reach any HTTP body. */
export function redactSecrets(text) {
  return String(text || '')
    .replace(TOKEN_RE, '<redacted-token>')
    .replace(BEARER_RE, 'Bearer <redacted>')
    .replace(ASSIGN_RE, '$1=<redacted>');
}

function defaultSpawn(python, argv, { timeoutMs }) {
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const child = spawn(python, argv, { timeout: timeoutMs });
    child.stdout?.on('data', (d) => { stdout += String(d); });
    child.stderr?.on('data', (d) => { stderr += String(d); });
    child.on('error', (err) => {
      if (!settled) {
        settled = true;
        resolve({ code: -1, stdout, stderr: `${stderr}\nspawn error: ${err.message}`, timedOut: false });
      }
    });
    child.on('close', (code, signal) => {
      if (!settled) {
        settled = true;
        resolve({ code: code ?? -1, stdout, stderr, timedOut: signal === 'SIGTERM' });
      }
    });
  });
}

function scanUnknownState(backend) {
  const outcomes = backend?.outcomes;
  if (!Array.isArray(outcomes)) return false;
  return outcomes.some((o) => o && (
    o.status === 'unknown_provider_state'
    || o?.record?.lifecycle_status === 'unknown_provider_state'
  ));
}

/**
 * Execute one backend operation and shape the HTTP envelope.
 * Returns { httpStatus, body }. Never throws for backend failures —
 * they become 502/504 envelopes with redacted detail.
 */
export async function runAutodial(op, params = {}, deps = {}) {
  let built;
  try {
    built = buildArgs(op, params);
  } catch (err) {
    return { httpStatus: err.httpStatus || 400, body: { ok: false, op, error: err.message } };
  }
  const python = process.env.DIALER_PYTHON || 'python';
  const timeoutMs = Number(process.env.DIALER_BRIDGE_TIMEOUT_MS)
    || (op === 'start' ? 180000 : 30000);
  const spawnFn = deps.spawnFn || defaultSpawn;
  const started = Date.now();
  let result;
  try {
    result = await spawnFn(python, [AUTODIAL_SCRIPT, ...built.argv], { timeoutMs });
  } catch (err) {
    return {
      httpStatus: 502,
      body: {
        ok: false, op, error: 'backend bridge failed',
        detail: redactSecrets(err?.message).slice(0, 500),
        retrySafe: op !== 'start' || built.dryRun !== false,
        hint: 'Check backend status, then reconcile if a live run was in flight.',
      },
    };
  }
  const durationMs = Date.now() - started;
  if (result.timedOut) {
    return {
      httpStatus: 504,
      body: {
        ok: false, op, error: 'backend timed out',
        retrySafe: false,
        hint: 'State is uncertain: query status, then reconcile before any new start. Never blind-retry.',
      },
    };
  }
  let backend = null;
  try {
    backend = JSON.parse(String(result.stdout || '').trim());
  } catch {
    backend = null;
  }
  if (backend === null || typeof backend !== 'object') {
    return {
      httpStatus: 502,
      body: {
        ok: false, op, error: 'backend returned non-JSON output',
        detail: redactSecrets(result.stderr).slice(-500),
        durationMs,
        hint: 'Backend state unchanged by this call; query status to confirm.',
      },
    };
  }
  const blocked = backend?.capability?.allowed === false;
  const reconciliationRequired = scanUnknownState(backend);
  const body = { ok: true, op, durationMs, backend };
  if (built.dryRun !== null) body.dryRun = built.dryRun;
  if (blocked) {
    body.blocked = true;
    body.blockedReason = backend.capability?.reason || 'backend refused the operation';
    body.fallback = backend.capability?.fallback || null;
  }
  if (reconciliationRequired) {
    body.reconciliationRequired = true;
    body.hint = 'One or more calls are in unknown_provider_state. Reconcile before any new start. Never redial an uncertain call.';
  }
  const httpStatus = result.code !== 0 && !blocked ? 502 : 200;
  if (httpStatus === 502) {
    body.ok = false;
    body.error = 'backend exited non-zero';
    body.detail = redactSecrets(result.stderr).slice(-500);
  }
  return { httpStatus, body };
}
