/**
 * MBM Dialer — Production Follow-Up Engine (serverless-safe core)
 * ================================================================
 * Implements the pipeline:
 *   DISPOSITION -> AFTERCALL (extraction) -> FOLLOW-UP DECISION ->
 *   WHATSAPP -> EMAIL FALLBACK -> EVENT -> ANALYTICS
 *
 * Production-safety contract:
 *   - ZERO hard-coded localhost/hosts. Same-origin API functions only.
 *   - FAIL-CLOSED transports: every provider mode is derived purely from
 *     environment presence; with no credentials nothing external is sent.
 *       WhatsApp  : Phound native-app prefill link (no credentials needed).
 *                   API mode ONLY when PHOUND_CALL_ENDPOINT + PHOUND_API_TOKEN.
 *       Email     : mailto fallback (operator-initiated, no credentials);
 *                   relay webhook ONLY when FOLLOWUP_EMAIL_RELAY_URL is set.
 *       Durable   : Supabase REST ONLY when SUPABASE_URL +
 *                   SUPABASE_SERVICE_ROLE_KEY are set; else in-memory.
 *   - TEST-mode events NEVER perform a network send of any kind and are
 *     excluded from production analytics counters.
 *   - Idempotency: per-tenant event + lead/type keys; duplicates SKIPPED.
 *   - Tenant isolation: every event/analytics query is namespaced by tenant.
 */

const WHATSAPP_PREFILL_BASE = "https://web.phound.app/";
const MAX_EVENTS = 5000;

// ---------------------------------------------------------------------------
// Normalization helpers
// ---------------------------------------------------------------------------

export function normalizePhoneE164(raw) {
  const digits = String(raw || "").replace(/\D/g, "");
  if (digits.length === 10 && !digits.startsWith("0") && !digits.startsWith("1")) {
    return `+1${digits}`;
  }
  if (digits.length === 11 && digits.startsWith("1")) return `+${digits}`;
  if (digits.length > 6 && raw && String(raw).trim().startsWith("+")) return `+${digits}`;
  return "";
}

export function sanitizeTenantId(raw) {
  const t = String(raw || "").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64);
  return t || "DEFAULT_TENANT";
}

export function normalizeEmail(email) {
  return String(email || "").toLowerCase().trim();
}

// ---------------------------------------------------------------------------
// Follow-up decision (mirrors server/dialer/emailRuleEngine.js semantics)
// ---------------------------------------------------------------------------

const BLOCKED_DISPOSITION_PATTERNS = [
  "dnc", "do not call", "unsubscribe", "unsubscribed",
  "not interested", "wrong number", "bad number", "opted out",
];

export function determineFollowUp(disposition, recommendedStage) {
  const disp = String(disposition || "").toLowerCase();
  if (!disp) return null;
  for (const p of BLOCKED_DISPOSITION_PATTERNS) {
    if (disp.includes(p)) return null; // hard block
  }
  const stage = String(recommendedStage || "").toUpperCase().replace(/ /g, "_");
  if (disp.includes("diagnostic") || stage === "DIAGNOSTIC_BOOKED") {
    return "DIAGNOSTIC_BOOKED_CONFIRMATION";
  }
  if (stage === "PROPOSAL_SENT" || disp.includes("proposal")) return "PROPOSAL_FOLLOW_UP";
  if (stage === "QUALIFIED" || disp.includes("qualified")) return "QUALIFICATION_FOLLOW_UP";
  if (stage === "NEEDS_MORE_INFO" || disp.includes("more info") || disp.includes("send info")) {
    return "NEEDS_MORE_INFO";
  }
  if (stage === "FOLLOW_UP_REQUIRED" || disp.includes("follow up") || disp.includes("call back")) {
    return "FOLLOW_UP_AFTER_CALL";
  }
  if (stage === "NOT_NOW" || disp.includes("not now") || disp.includes("timing")) {
    return "REACTIVATION";
  }
  if (disp.includes("success") || disp.includes("positive")) return "THANK_YOU";
  return null;
}

// ---------------------------------------------------------------------------
// AFTERCALL extraction (deterministic heuristic — fail-closed, no network)
// ---------------------------------------------------------------------------

export function extractFromTranscript(transcript, currentStage) {
  const text = String(transcript || "").toLowerCase();
  if (!text.trim()) {
    return {
      Pain_Points: "unknown",
      Budget: "unknown",
      Next_Steps: "needs_review",
      Recommended_Stage: currentStage || "needs_review",
      is_fallback: true,
    };
  }
  const budgetMatch = text.match(/\$\s?\d[\d,.]*\s?[kK]?/);
  let stage = "";
  if (/(book|schedule|set up|diagnostic)/.test(text)) stage = "DIAGNOSTIC_BOOKED";
  else if (/proposal|quote/.test(text)) stage = "PROPOSAL_SENT";
  else if (/(qualified|budget confirmed)/.test(text)) stage = "QUALIFIED";
  else if (/(more info|send information|email me)/.test(text)) stage = "NEEDS_MORE_INFO";
  else if (/(call back|follow up|next week|later)/.test(text)) stage = "FOLLOW_UP_REQUIRED";
  else if (/(not now|bad timing|revisit)/.test(text)) stage = "NOT_NOW";

  return {
    Pain_Points: /pain|problem|struggle|bottleneck|missed/.test(text)
      ? "mentioned_in_transcript" : "unknown",
    Budget: budgetMatch ? budgetMatch[0] : "unknown",
    Next_Steps: stage ? `${stage.replace(/_/g, " ").toLowerCase()}` : "needs_review",
    Recommended_Stage: stage || currentStage || "needs_review",
    is_fallback: !stage,
  };
}

// ---------------------------------------------------------------------------
// Suppression / DNC
// ---------------------------------------------------------------------------

function parseListEnv(name) {
  try {
    const raw = process.env[name];
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return new Set(parsed.map((v) => String(v).toLowerCase().trim()));
    if (typeof parsed === "string") {
      return new Set(parsed.split(/[,\s]+/).filter(Boolean).map((v) => v.toLowerCase().trim()));
    }
  } catch { /* fail-closed to empty */ }
  return new Set();
}

function suppressionSets() {
  return {
    emails: parseListEnv("FOLLOWUP_SUPPRESSED_EMAILS"),
    phones: parseListEnv("FOLLOWUP_SUPPRESSED_PHONES"),
  };
}

export function isSuppressedEmail(email, extraSet) {
  const e = normalizeEmail(email);
  if (!e || !e.includes("@") || e.length < 5) return true;
  if (extraSet && extraSet.has(e)) return true;
  return suppressionSets().emails.has(e);
}

export function isSuppressedPhone(phone, extraSet) {
  const p = normalizePhoneE164(phone);
  if (!p) return true;
  if (extraSet && extraSet.has(p)) return true;
  return suppressionSets().phones.has(p);
}

// ---------------------------------------------------------------------------
// Transports (fail-closed; provider modes derived from env presence only)
// ---------------------------------------------------------------------------

export function providerSnapshot() {
  return {
    whatsapp: {
      mode: process.env.PHOUND_ENABLED === "true" &&
            process.env.PHOUND_CALL_ENDPOINT && process.env.PHOUND_API_TOKEN
        ? "api"
        : "prefill",
      configured_api: Boolean(process.env.PHOUND_ENABLED === "true" &&
        process.env.PHOUND_CALL_ENDPOINT && process.env.PHOUND_API_TOKEN),
    },
    email: {
      mode: process.env.FOLLOWUP_EMAIL_RELAY_URL ? "relay" : "mailto_fallback",
      relay_configured: Boolean(process.env.FOLLOWUP_EMAIL_RELAY_URL),
    },
    durable: {
      mode: process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY
        ? "supabase"
        : "memory",
      configured: Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY),
    },
    ai_extraction: {
      mode: process.env.FOLLOWUP_AI_ENDPOINT ? "remote" : "heuristic",
      configured: Boolean(process.env.FOLLOWUP_AI_ENDPOINT),
    },
  };
}

export function buildWhatsAppPrefill(phone, message) {
  const p = normalizePhoneE164(phone);
  const text = encodeURIComponent(String(message || "").slice(0, 800));
  return `${WHATSAPP_PREFILL_BASE}?phone=${encodeURIComponent(p)}&text=${text}`;
}

export async function sendWhatsAppApiMode(payload) {
  // Only reachable when provider snapshot says api mode. Fail-closed on error.
  const endpoint = process.env.PHOUND_CALL_ENDPOINT;
  const token = process.env.PHOUND_API_TOKEN;
  if (!endpoint || !token) {
    return { status: "SKIPPED_NO_PROVIDER", reason: "phound api not configured" };
  }
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        [process.env.PHOUND_AUTH_HEADER || "Authorization"]: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(t);
    return { status: res.ok ? "SENT" : `HTTP_${res.status}`, http_status: res.status };
  } catch (err) {
    return { status: "FAILED", reason: String(err).slice(0, 120) };
  }
}

const SUBJECTS = {
  DIAGNOSTIC_BOOKED_CONFIRMATION: "Confirming your MBM AI diagnostic",
  PROPOSAL_FOLLOW_UP: "Your MBM proposal — next step",
  QUALIFICATION_FOLLOW_UP: "Quick follow-up from MBM",
  NEEDS_MORE_INFO: "The information you asked for",
  FOLLOW_UP_AFTER_CALL: "Following up on our call",
  REACTIVATION: "Reconnecting at a better time",
  THANK_YOU: "Thank you from MBM",
};

export function buildEmailContent(type, ctx) {
  const first = ctx.first_name || "there";
  const company = ctx.company || "your team";
  const text =
    `Hi ${first},\n\nThanks for the conversation about ${company}. ` +
    `This is a ${String(type).replace(/_/g, " ").toLowerCase()} follow-up from MBM.\n\n` +
    `— Mohammed, MBM Automation\n`;
  return {
    subject: SUBJECTS[type] || "Follow-up from MBM",
    text,
  };
}

export function buildMailto(email, subject, text) {
  return `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
}

export async function relayEmail(payload) {
  const url = process.env.FOLLOWUP_EMAIL_RELAY_URL;
  if (!url) return { status: "MAILTO_FALLBACK", reason: "no relay configured" };
  if (payload.test) return { status: "DRYRUN_TEST_MODE", reason: "test events never send" };
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(process.env.FOLLOWUP_EMAIL_RELAY_TOKEN
          ? { authorization: `Bearer ${process.env.FOLLOWUP_EMAIL_RELAY_TOKEN}` }
          : {}),
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(t);
    return { status: res.ok ? "RELAYED" : `HTTP_${res.status}`, http_status: res.status };
  } catch (err) {
    return { status: "FAILED", reason: String(err).slice(0, 120) };
  }
}

// ---------------------------------------------------------------------------
// Event store: in-memory ring (per instance) + optional Supabase persistence
// ---------------------------------------------------------------------------

/** Global across invocations within one lambda instance. */
globalThis.__MBM_FOLLOWUP_STORE__ = globalThis.__MBM_FOLLOWUP_STORE__ || {
  byTenant: new Map(),   // tenant -> event[]
  idempotentEvents: new Set(), // `${tenant}:${eventId}`
  idempotentEmails: new Set(), // `${tenant}:${leadId}:${type}`
};

const STORE = globalThis.__MBM_FOLLOWUP_STORE__;

export function alreadyProcessedEvent(tenantId, eventId) {
  return STORE.idempotentEvents.has(`${tenantId}:${eventId}`);
}
export function markEventProcessed(tenantId, eventId) {
  STORE.idempotentEvents.add(`${tenantId}:${eventId}`);
  if (STORE.idempotentEvents.size > MAX_EVENTS) STORE.idempotentEvents.clear();
}
export function alreadyProcessedEmailKey(tenantId, key) {
  return STORE.idempotentEmails.has(`${tenantId}:${key}`);
}
export function markEmailKey(tenantId, key) {
  STORE.idempotentEmails.add(`${tenantId}:${key}`);
  if (STORE.idempotentEmails.size > MAX_EVENTS) STORE.idempotentEmails.clear();
}

export async function persistDurable(event) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return { durable: false, reason: "SUPABASE env missing (memory-only)" };
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${url.replace(/\/$/, "")}/rest/v1/followup_events`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        apikey: key,
        authorization: `Bearer ${key}`,
        prefer: "return=minimal",
      },
      body: JSON.stringify(event),
      signal: controller.signal,
    });
    clearTimeout(t);
    return res.ok || res.status === 201
      ? { durable: true }
      : { durable: false, reason: `HTTP_${res.status}` };
  } catch (err) {
    return { durable: false, reason: String(err).slice(0, 100) };
  }
}

export function recordEvent(event) {
  const list = STORE.byTenant.get(event.tenant_id) || [];
  list.push(event);
  while (list.length > MAX_EVENTS) list.shift();
  STORE.byTenant.set(event.tenant_id, list);
  return event;
}

export function getEvents(tenantId) {
  return STORE.byTenant.get(tenantId) || [];
}

// ---------------------------------------------------------------------------
// Analytics (production metrics exclude TEST-mode events)
// ---------------------------------------------------------------------------

export function analyticsFor(tenantId) {
  const events = getEvents(tenantId);
  const prod = events.filter((e) => !e.test);
  const tests = events.filter((e) => e.test);
  const summarize = (list) => ({
    total: list.length,
    decisions: list.filter((e) => e.type === "decision").length,
    aftercalls: list.filter((e) => e.type === "aftercall").length,
    meetings: list.filter((e) => e.type === "meeting").length,
    followups_sent_or_prefilled: list.filter(
      (e) =>
        e.channels?.whatsapp?.status === "PREFILL_READY" ||
        e.channels?.whatsapp?.status === "SENT" ||
        e.channels?.email?.status === "RELAYED"
    ).length,
    blocked_suppressed: list.filter(
      (e) =>
        e.channels?.whatsapp?.status === "BLOCKED_SUPPRESSED" ||
        e.channels?.email?.status === "BLOCKED_SUPPRESSED"
    ).length,
    duplicates_skipped: list.filter(
      (e) =>
        String(e.channels?.whatsapp?.status || "").includes("DUPLICATE") ||
        String(e.channels?.email?.status || "").includes("DUPLICATE")
    ).length,
    last_event_at: list.length ? list[list.length - 1].created_at : null,
  });
  return {
    tenant_id: tenantId,
    production: summarize(prod),
    test: summarize(tests),
    providers: providerSnapshot(),
  };
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

export function jsonRes(res, status, payload) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("x-mbm-followup-engine", "1");
  res.end(JSON.stringify(payload));
}

export async function readJsonBody(req, limitBytes = 32768) {
  return new Promise((resolve) => {
    const chunks = [];
    let size = 0;
    req.on("data", (c) => {
      size += c.length;
      if (size > limitBytes) {
        resolve(null); // too large -> reject upstream
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8") || "{}"));
      } catch {
        resolve(undefined); // invalid JSON
      }
    });
    req.on("error", () => resolve(undefined));
  });
}
