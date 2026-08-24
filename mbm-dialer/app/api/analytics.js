/**
 * GET /api/analytics?tenant=<id> — per-tenant follow-up analytics.
 * Production metrics exclude TEST-mode events; test metrics are separate.
 */
import {
  sanitizeTenantId,
  jsonRes,
  analyticsFor,
} from "../lib/followup/core.js";

export const config = { runtime: "nodejs", maxDuration: 15 };

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return jsonRes(res, 405, { ok: false, error: "GET only" });
  }
  const url = new URL(req.url, "http://same-origin");
  const tenantId = sanitizeTenantId(
    req.headers["x-tenant-id"] || url.searchParams.get("tenant")
  );
  return jsonRes(res, 200, {
    ok: true,
    ...analyticsFor(tenantId),
    note: "in-memory window is per serverless instance; set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY for durable aggregation",
  });
}
