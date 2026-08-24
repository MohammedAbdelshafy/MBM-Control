/**
 * POST /api/meeting — record a booked discovery meeting (follow-up event).
 * Body: { lead_id, company, contact, phone, scheduled_time, meeting_type,
 *         ai_fit, notes, tenantId?, mode? }
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
  const eventId = `mtg-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  const test = body.mode === "TEST";

  if (alreadyProcessedEvent(tenantId, eventId)) {
    return jsonRes(res, 200, { ok: true, event_id: eventId, status: "SKIPPED_DUPLICATE" });
  }
  markEventProcessed(tenantId, eventId);

  // Telegram notification ONLY when explicitly configured and NOT test mode.
  let telegram = { status: "SKIPPED_NO_PROVIDER", reason: "TELEGRAM_* env missing" };
  if (!test && process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID) {
    try {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 8000);
      const tRes = await fetch(
        `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            chat_id: process.env.TELEGRAM_CHAT_ID,
            text: `[${tenantId}] Meeting booked: ${body.company} / ${body.contact} @ ${body.scheduled_time}`,
          }),
          signal: controller.signal,
        }
      );
      clearTimeout(t);
      telegram = { status: tRes.ok ? "SENT" : `HTTP_${tRes.status}` };
    } catch (err) {
      telegram = { status: "FAILED", reason: String(err).slice(0, 100) };
    }
  }

  const event = {
    event_id: eventId,
    tenant_id: tenantId,
    type: "meeting",
    lead_id: leadId,
    disposition: "Meeting Booked",
    scheduled_time: String(body.scheduled_time || "").slice(0, 64),
    meeting_type: String(body.meeting_type || "").slice(0, 96),
    company: String(body.company || "").slice(0, 120),
    contact: String(body.contact || "").slice(0, 96),
    test,
    channels: { telegram },
    created_at: new Date().toISOString(),
  };
  recordEvent(event);

  return jsonRes(res, 200, {
    ok: true,
    event_id: eventId,
    status: "MEETING_RECORDED",
    tenant_id: tenantId,
    mode: test ? "TEST" : "PRODUCTION",
    meeting_brief: {
      lead_id: leadId,
      company: event.company,
      scheduled_time: event.scheduled_time,
      meeting_type: event.meeting_type,
    },
    channels: event.channels,
    providers: providerSnapshot(),
    analytics_snapshot: analyticsFor(tenantId),
  });
}
