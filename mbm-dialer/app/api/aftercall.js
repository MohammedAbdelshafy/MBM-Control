/**
 * POST /api/aftercall — the production follow-up pipeline.
 *
 *   DISPOSITION -> AFTERCALL (extraction) -> FOLLOW-UP DECISION ->
 *   WHATSAPP -> EMAIL FALLBACK -> EVENT -> ANALYTICS
 *
 * Body: { leadId, phone, email?, firstName?, company?, transcript,
 *         currentStage, disposition?, tenantId?, mode? }
 *
 * mode:"TEST" executes the ENTIRE pipeline through the production runtime but
 * forces every transport into DRYRUN/prefill mode — nothing is ever sent.
 */
import {
  sanitizeTenantId,
  normalizePhoneE164,
  readJsonBody,
  jsonRes,
  determineFollowUp,
  extractFromTranscript,
  isSuppressedEmail,
  isSuppressedPhone,
  buildWhatsAppPrefill,
  sendWhatsAppApiMode,
  buildEmailContent,
  buildMailto,
  relayEmail,
  alreadyProcessedEvent,
  markEventProcessed,
  alreadyProcessedEmailKey,
  markEmailKey,
  persistDurable,
  recordEvent,
  analyticsFor,
  providerSnapshot,
} from "../lib/followup/core.js";

export const config = { runtime: "nodejs", maxDuration: 20 };

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return jsonRes(res, 405, { ok: false, error: "POST only" });
  }
  const body = await readJsonBody(req);
  if (body === null) return jsonRes(res, 413, { ok: false, error: "payload too large" });
  if (body === undefined) return jsonRes(res, 400, { ok: false, error: "invalid JSON" });

  const leadId = String(body.leadId || body.lead_id || "").slice(0, 128);
  const transcript = String(body.transcript || "").slice(0, 8000);
  const disposition = String(body.disposition || body.currentStage || "").slice(0, 64);
  if (!leadId || !transcript.trim()) {
    return jsonRes(res, 400, { ok: false, error: "leadId and transcript are required" });
  }

  const tenantId = sanitizeTenantId(req.headers["x-tenant-id"] || body.tenantId);
  const eventId = String(body.eventId || "").slice(0, 64) ||
    `afc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  const test = body.mode === "TEST";
  const phone = normalizePhoneE164(body.phone);
  const email = String(body.email || "").trim();

  // ---- idempotency gate ----------------------------------------------------
  if (alreadyProcessedEvent(tenantId, eventId)) {
    return jsonRes(res, 200, {
      ok: true, event_id: eventId, status: "SKIPPED_DUPLICATE",
      tenant_id: tenantId, analytics_snapshot: analyticsFor(tenantId),
    });
  }
  markEventProcessed(tenantId, eventId);

  // ---- stage 2: AFTERCALL extraction (fail-closed heuristic) ----------------
  const extractedData = extractFromTranscript(transcript, body.currentStage);

  // ---- stage 3: FOLLOW-UP DECISION ------------------------------------------
  const followupType = determineFollowUp(disposition, extractedData.Recommended_Stage);

  const channels = { whatsapp: { status: "NO_ACTION" }, email: { status: "NO_ACTION" } };

  if (!followupType) {
    channels.whatsapp.status = "BLOCKED_DISPOSITION";
    channels.email.status = "BLOCKED_DISPOSITION";
  } else {
    // ---- stage 4: WHATSAPP --------------------------------------------------
    const waMessage =
      `Hi ${String(body.firstName || "there")}, this is Mohammed from MBM ` +
      `following up on our call about ${String(body.company || "your team")}. ` +
      `Happy to share the details we discussed.`;
    if (isSuppressedPhone(phone)) {
      channels.whatsapp.status = "BLOCKED_SUPPRESSED";
    } else if (providerSnapshot().whatsapp.mode === "api" && !test) {
      const apiRes = await sendWhatsAppApiMode({
        to: phone, lead_id: leadId, notes: waMessage.slice(0, 200),
      });
      channels.whatsapp = { mode: "api", ...apiRes };
    } else {
      channels.whatsapp = {
        mode: test ? "prefill_dryrun" : "prefill",
        status: "PREFILL_READY",
        prefill: buildWhatsAppPrefill(phone, waMessage),
        message_preview: waMessage.slice(0, 140),
      };
    }

    // ---- stage 5: EMAIL FALLBACK --------------------------------------------
    const emailKey = `${leadId}:${followupType}:${email}`;
    if (!email && !(body.allow_mailto_without_address === true)) {
      channels.email.status = "NO_ADDRESS";
    } else if (alreadyProcessedEmailKey(tenantId, emailKey)) {
      channels.email.status = "SKIPPED_DUPLICATE";
    } else if (isSuppressedEmail(email)) {
      channels.email.status = "BLOCKED_SUPPRESSED";
    } else {
      markEmailKey(tenantId, emailKey);
      const content = buildEmailContent(followupType, {
        first_name: body.firstName, company: body.company,
        tenantId, lead_id: leadId,
      });
      const mailto = buildMailto(email || "", content.subject, content.text);
      let relay;
      if (test) {
        relay = { status: "DRYRUN_TEST_MODE", reason: "test events never send" };
      } else {
        relay = await relayEmail({
          to: email, subject: content.subject, text: content.text,
          tenantId, lead_id: leadId, event_id: eventId, followup_type: followupType,
          test,
        });
      }
      channels.email = {
        mode: process.env.FOLLOWUP_EMAIL_RELAY_URL ? "relay" : "mailto_fallback",
        status: relay.status === "RELAYED" ? "RELAYED"
          : relay.status === "FAILED" ? "FAILED"
          : relay.status.startsWith("HTTP_") ? relay.status
          : relay.status === "MAILTO_FALLBACK" ? "MAILTO_READY"
          : relay.status,
        reason: relay.reason,
        subject: content.subject,
        mailto,
      };
    }
  }

  // ---- stage 6: EVENT ---------------------------------------------------------
  const event = {
    event_id: eventId,
    tenant_id: tenantId,
    type: "aftercall",
    lead_id: leadId,
    disposition,
    recommended_stage: extractedData.Recommended_Stage,
    followup_type: followupType || "NONE",
    extraction_fallback: Boolean(extractedData.is_fallback),
    phone_last4: phone ? phone.slice(-4) : "",
    test,
    channels,
    created_at: new Date().toISOString(),
  };
  recordEvent(event);
  const durability = await persistDurable(event);

  // ---- stage 7: ANALYTICS -------------------------------------------------------
  const analytics = analyticsFor(tenantId);

  return jsonRes(res, 200, {
    ok: true,
    event_id: eventId,
    status: "COMPLETED",
    tenant_id: tenantId,
    mode: test ? "TEST_DRYRUN" : "PRODUCTION",
    extractedData,
    follow_up: { type: followupType || "NONE", decision: followupType ? "TRIGGERED" : "NO_ACTION" },
    channels,
    persistence: durability,
    analytics_snapshot: analytics,
    providers: providerSnapshot(),
  });
}
