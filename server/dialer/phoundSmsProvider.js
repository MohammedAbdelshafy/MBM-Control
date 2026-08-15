import { z } from 'zod';

/**
 * phoundSmsProvider.js — Secure Phound SMS boundary (enterprise).
 *
 * Mirrors phoundProviderSecure.js but for outbound SMS campaign dispatch.
 * Two modes, selected by config:
 *
 *   native_app (default)
 *     No API call is made. Returns a per-recipient `https://web.phound.app/?phone=...`
 *     prefill link + the prepared message so the operator sends from the Phound app.
 *     This is the only mode valid until Phound provisions an official SMS endpoint.
 *
 *   api
 *     POSTs { to, message, campaign, lead_id } to PHOUND_SMS_ENDPOINT with the
 *     configured auth header + token. Only reachable when endpoint AND token are set.
 *
 * Hard rules (from README.md):
 *   - The browser never receives tokens; this module runs server-side only.
 *   - No undocumented Phound endpoint is assumed — api mode stays disabled until
 *     an official endpoint is configured via env.
 *   - Numbers are normalized to E.164 before any dispatch.
 *   - Responses are reduced to bounded payloads; errors never expose secrets.
 */

const E164 = /^\+[1-9]\d{7,14}$/;
const SMS_SEGMENT = 160;

const SmsConfigSchema = z.object({
  enabled: z.boolean().default(false),
  endpoint: z.string().url().optional(),
  token: z.string().min(1).optional(),
  timeoutMs: z.number().int().min(1000).max(30000).default(8000),
  authHeader: z.string().min(1).max(100).default('Authorization'),
}).superRefine((cfg, ctx) => {
  if (cfg.endpoint) {
    try {
      if (new URL(cfg.endpoint).protocol !== 'https:') {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Phound SMS endpoint must use HTTPS.' });
      }
    } catch {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Invalid Phound SMS endpoint.' });
    }
  }
  if (cfg.enabled && (!cfg.endpoint || !cfg.token)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Enabled Phound SMS API mode requires endpoint and token.' });
  }
});

export function normalizeE164Sms(value) {
  const raw = String(value || '').trim();
  if (!raw) throw new Error('Phone number is required');
  const digits = raw.replace(/[^\d+]/g, '');
  const normalized = digits.startsWith('+') ? digits : `+1${digits.replace(/^1/, '')}`;
  if (!E164.test(normalized)) throw new Error('Invalid phone number. Expected E.164 format.');
  return normalized;
}

export function getSmsConfig(env = process.env) {
  const parsed = SmsConfigSchema.safeParse({
    enabled: String(env.PHOUND_ENABLED || 'false').toLowerCase() === 'true',
    endpoint: env.PHOUND_SMS_ENDPOINT || undefined,
    token: env.PHOUND_API_TOKEN || undefined,
    timeoutMs: env.PHOUND_TIMEOUT_MS ? Number(env.PHOUND_TIMEOUT_MS) : 8000,
    authHeader: env.PHOUND_AUTH_HEADER || 'Authorization',
  });
  if (!parsed.success) return { enabled: false, configured: false, error: parsed.error.issues[0]?.message || 'Invalid Phound SMS configuration' };
  return { ...parsed.data, configured: Boolean(parsed.data.endpoint && parsed.data.token) };
}

export function getSmsStatus(env = process.env) {
  const cfg = getSmsConfig(env);
  return {
    provider: 'phound_sms',
    mode: cfg.enabled && cfg.configured ? 'api' : 'native_app',
    enabled: cfg.enabled,
    configured: cfg.configured,
    error: cfg.error || null,
  };
}

export function smsSegmentCount(message = '') {
  return Math.max(1, Math.ceil(String(message).length / SMS_SEGMENT));
}

export function buildPhoundPrefillLink(phone, message) {
  const normalized = normalizeE164Sms(phone);
  const base = `https://web.phound.app/?phone=${encodeURIComponent(normalized)}`;
  return message ? `${base}&body=${encodeURIComponent(message)}` : base;
}

export async function sendPhoundSms({ to, message, campaign, leadId } = {}, env = process.env) {
  const cfg = getSmsConfig(env);
  const phone = normalizeE164Sms(to);

  if (!cfg.enabled || !cfg.configured) {
    return {
      status: 'native_app',
      provider: 'phound_sms',
      to: phone,
      campaign: campaign || null,
      prefill: buildPhoundPrefillLink(phone, message),
      segments: smsSegmentCount(message),
    };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), cfg.timeoutMs);
  try {
    const response = await fetch(cfg.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [cfg.authHeader]: cfg.authHeader.toLowerCase() === 'authorization' ? `Bearer ${cfg.token}` : cfg.token,
      },
      body: JSON.stringify({
        to: phone,
        message,
        campaign: campaign || null,
        lead_id: leadId || null,
      }),
      signal: controller.signal,
    });

    const body = await response.text();
    let data = null;
    try { data = body ? JSON.parse(body) : null; } catch { data = { raw: body.slice(0, 1000) }; }
    if (!response.ok) return { status: 'error', provider: 'phound_sms', http_status: response.status, error: data?.error || 'Provider request failed' };
    return { status: 'accepted', provider: 'phound_sms', response: data };
  } catch (error) {
    return { status: 'error', provider: 'phound_sms', error: error?.name === 'AbortError' ? 'Provider request timed out' : 'Provider unavailable' };
  } finally {
    clearTimeout(timeout);
  }
}