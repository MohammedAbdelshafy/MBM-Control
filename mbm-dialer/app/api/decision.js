/**
 * POST /api/decision — record a call decision and emit a follow-up event.
 * Body: { lead_id, decision_id, decision_label, lane, amount, note, tenantId?, mode? }
 */
import {
  sanitizeTenantId,
  readJsonBody,
  jsonRes,
  recordEvent,
  alreadyProcessedEvent,
  markEventProcessed,
  analyticsFor,
  providerSnapshot,
} from "../lib/followup/core.js";

export const config = { runtime: "nodejs", maxDuration: 15 };

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return jsonRes(res, 405, { ok: false, error: "POST only" });
  }
  const body = await readJsonBody(req);
  if (body === null) return jsonRes(res, 413, { ok: false, error: "payload too large" });
  if (body === undefined) return jsonRes(res, 400, { ok: false, error: "invalid JSON" });

  const leadId = String(body.lead_id || body.leadId || "").slice(0, 128);
  if (!leadId) return jsonRes(res, 400, { ok: false, error: "lead_id required" });

  const tenantId = sanitizeTenantId(req.headers["x-tenant-id"] || body.tenantId);
  const eventId = `dec-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  const test = body.mode === "TEST";

  if (alreadyProcessedEvent(tenantId, eventId)) {
    return jsonRes(res, 200, { ok: true, event_id: eventId, status: "SKIPPED_DUPLICATE" });
  }

  const event = {
    event_id: eventId,
    tenant_id: tenantId,
    type: "decision",
    lead_id: leadId,
    disposition: String(body.decision_label || body.decision_id || "").slice(0, 64),
    lane: String(body.lane || "").slice(0, 64),
    amount: String(body.amount || "").slice(0, 32),
    note_present: Boolean(body.note),
    test,
    channels: {},
    created_at: new Date().toISOString(),
  };
  markEventProcessed(tenantId, eventId);
  recordEvent(event);

  return jsonRes(res, 200, {
    ok: true,
    event_id: eventId,
    status: "RECORDED",
    tenant_id: tenantId,
    mode: test ? "TEST" : "PRODUCTION",
    providers: providerSnapshot(),
    analytics_snapshot: analyticsFor(tenantId).production.total,
  });
}
