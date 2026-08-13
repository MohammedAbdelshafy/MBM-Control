import { z } from 'zod';

const E164 = /^\+[1-9]\d{7,14}$/;

const ConfigSchema = z.object({
  enabled: z.boolean().default(false),
  endpoint: z.string().url().optional(),
  token: z.string().min(1).optional(),
  timeoutMs: z.number().int().min(1000).max(30000).default(8000),
  authHeader: z.string().min(1).max(100).default('Authorization'),
}).superRefine((cfg, ctx) => {
  if (cfg.enabled && (!cfg.endpoint || !cfg.token)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Phound provider requires both endpoint and token when enabled.' });
  }
});

export function getPhoundConfig(env = process.env) {
  const parsed = ConfigSchema.safeParse({
    enabled: String(env.PHOUND_ENABLED || 'false').toLowerCase() === 'true',
    endpoint: env.PHOUND_CALL_ENDPOINT || undefined,
    token: env.PHOUND_API_TOKEN || undefined,
    timeoutMs: env.PHOUND_TIMEOUT_MS ? Number(env.PHOUND_TIMEOUT_MS) : 8000,
    authHeader: env.PHOUND_AUTH_HEADER || 'Authorization',
  });

  if (!parsed.success) {
    return { enabled: false, configured: false, error: parsed.error.issues[0]?.message || 'Invalid Phound configuration' };
  }

  return { ...parsed.data, configured: Boolean(parsed.data.endpoint && parsed.data.token) };
}

export function normalizeE164(value) {
  const raw = String(value || '').trim();
  if (!raw) throw new Error('Phone number is required');
  const digits = raw.replace(/[^\d+]/g, '');
  const normalized = digits.startsWith('+') ? digits : `+1${digits.replace(/^1/, '')}`;
  if (!E164.test(normalized)) throw new Error('Invalid phone number. Expected E.164 format, e.g. +12125551234.');
  return normalized;
}

function redact(value) {
  if (!value) return '';
  return `${value.slice(0, 4)}…${value.slice(-3)}`;
}

export function getPhoundStatus(env = process.env) {
  const cfg = getPhoundConfig(env);
  return {
    provider: 'phound',
    mode: cfg.enabled && cfg.configured ? 'api' : 'native_app',
    configured: cfg.configured,
    enabled: cfg.enabled,
    endpoint: cfg.endpoint || null,
    token_preview: redact(cfg.token),
    message: cfg.enabled && cfg.configured
      ? 'Phound API adapter configured. Calling stays behind the server boundary.'
      : 'Phound native-app mode. No credentials are exposed to the browser.',
  };
}

/**
 * Sends a normalized call request to an endpoint explicitly supplied by the
 * Phound account/integration configuration. No undocumented Phound endpoint
 * or payload is assumed here.
 */
export async function placePhoundCall({ to, prospectName, leadId, notes } = {}, env = process.env) {
  const cfg = getPhoundConfig(env);
  if (!cfg.enabled || !cfg.configured) {
    return { status: 'native_app', provider: 'phound', to: normalizeE164(to), prospect_name: prospectName || 'Prospect' };
  }

  const phone = normalizeE164(to);
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
        prospect_name: prospectName || 'Prospect',
        lead_id: leadId || null,
        notes: notes || null,
      }),
      signal: controller.signal,
    });

    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text.slice(0, 1000) }; }

    if (!response.ok) {
      return { status: 'error', provider: 'phound', http_status: response.status, error: data?.error || 'Phound call request failed' };
    }

    return { status: 'accepted', provider: 'phound', response: data };
  } catch (error) {
    return {
      status: 'error',
      provider: 'phound',
      error: error.name === 'AbortError' ? 'Phound request timed out' : 'Phound provider unavailable',
    };
  } finally {
    clearTimeout(timeout);
  }
}
