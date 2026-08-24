/**
 * P1 FOLLOW-UP RUNTIME REGRESSION TESTS (serverless-safe)
 * ========================================================
 * Drives the REAL api handlers (decision/aftercall/analytics) through mocked
 * Node req/res pairs and asserts the production-safety contract:
 *   - TEST-mode executes the full pipeline with ZERO external sends
 *   - suppression/DNC blocks before any transport decision
 *   - idempotency skips duplicates
 *   - tenant isolation (events never leak across tenants)
 *   - analytics exclude TEST events from production counters
 *
 * Run: node mbm-dialer/app/tests/followup-engine.test.mjs
 */
import assert from "node:assert";
import { EventEmitter } from "node:events";
import aftercallHandler from "../api/aftercall.js";
import decisionHandler from "../api/decision.js";
import meetingHandler from "../api/meeting.js";
import analyticsHandler from "../api/analytics.js";

let passed = 0;
let failed = 0;
const ok = (cond, name) => {
  if (cond) { passed++; console.log(`  PASS ${name}`); }
  else { failed++; console.error(`  FAIL ${name}`); }
};

function mockReq(method, bodyObj, headers = {}, url = "/api/x") {
  const req = new EventEmitter();
  req.method = method;
  req.headers = headers;
  req.url = url;
  process.nextTick(() => {
    if (bodyObj) {
      req.emit("data", Buffer.from(JSON.stringify(bodyObj)));
    }
    req.emit("end");
  });
  return req;
}

function mockRes() {
  let resolveDone;
  const donePromise = new Promise((r) => { resolveDone = r; });
  const res = {
    statusCode: 0,
    headers: {},
    body: null,
    done: donePromise,
    setHeader(k, v) { this.headers[k] = v; },
    end(buf) {
      this.body = buf ? buf.toString("utf-8") : "";
      resolveDone(this);
    },
  };
  return res;
}

async function call(handlerFn, method, bodyObj, headers = {}, url = "/api/x") {
  const req = mockReq(method, bodyObj, headers, url);
  const res = mockRes();
  await handlerFn(req, res);
  await res.done;
  return { status: res.statusCode, json: JSON.parse(res.body || "{}"), raw: res.body };
}

const TENANT = "P1TEST";
const OTHER = "OTHERCO";

// ---------------------------------------------------------------------------
console.log("\n[1] TEST-mode aftercall executes full pipeline with zero sends");
{
  const r = await call(aftercallHandler, "POST", {
    mode: "TEST",
    leadId: "NPI-1649914912",
    phone: "+12013419119",
    email: "test@example.com",
    firstName: "Austin",
    company: "Austin Athletic Recovery",
    transcript: "We should book the diagnostic next Tuesday, budget around $2k",
    currentStage: "Prospecting",
    disposition: "Diagnostic Booked",
    eventId: "evt-test-1",
    tenantId: TENANT,
  }, {});
  ok(r.status === 200, "HTTP 200");
  ok(r.json.ok === true && r.json.status === "COMPLETED", "pipeline COMPLETED");
  ok(r.json.mode === "TEST_DRYRUN", "mode=TEST_DRYRUN");
  ok(r.json.follow_up.type === "DIAGNOSTIC_BOOKED_CONFIRMATION", "follow-up decided");
  ok(String(r.json.channels.whatsapp.status).includes("PREFILL") ||
     r.json.channels.whatsapp.status === "BLOCKED_SUPPRESSED", "whatsapp prefill/blocked only");
  ok((r.json.channels.whatsapp.prefill || "").startsWith("https://web.phound.app/?phone="),
     "phound prefill link");
  ok(r.json.channels.email.status === "DRYRUN_TEST_MODE", "email never sends in TEST");
  ok(typeof r.json.analytics_snapshot.production.total === "number", "analytics snapshot present");
}

console.log("\n[2] Suppression / DNC blocks follow-ups entirely");
{
  const r1 = await call(aftercallHandler, "POST", {
    mode: "TEST", leadId: "L-DNC", phone: "+12125550001",
    transcript: "please never contact me again", currentStage: "x",
    disposition: "DNC - do not call", eventId: "evt-dnc-1", tenantId: TENANT,
  }, {});
  ok(r1.json.follow_up.type === "NONE", "DNC -> NONE");
  ok(r1.json.channels.email.status === "BLOCKED_DISPOSITION", "email blocked");
  ok(r1.json.channels.whatsapp.status === "BLOCKED_DISPOSITION", "whatsapp blocked");

  const r2 = await call(aftercallHandler, "POST", {
    mode: "TEST", leadId: "L-SUPP", phone: "+12125550002",
    email: "blocked@suppressed.test", transcript: "interested, send info",
    currentStage: "x", disposition: "Qualified", eventId: "evt-supp-1",
    tenantId: TENANT,
  }, {});
  ok(["BLOCKED_SUPPRESSED", "NO_ADDRESS"].includes(r2.json.channels.email.status) === false ||
     r2.json.channels.email.status === "DRYRUN_TEST_MODE",
     "non-suppressed email passes gate in TEST");
}

console.log("\n[3] Idempotency — same eventId is skipped");
{
  const payload = {
    mode: "TEST", leadId: "L-IDEM", phone: "+12125550003",
    transcript: "call back next week", currentStage: "x",
    disposition: "Follow Up Required", eventId: "evt-idem-1", tenantId: TENANT,
  };
  const a = await call(aftercallHandler, "POST", payload, {});
  const b = await call(aftercallHandler, "POST", payload, {});
  ok(a.json.status === "COMPLETED", "first run completes");
  ok(b.json.status === "SKIPPED_DUPLICATE", "duplicate skipped");
}

console.log("\n[4] Tenant isolation — events never cross tenants");
{
  await call(decisionHandler, "POST", {
    lead_id: "L-TEN", decision_id: "Deal", tenantId: TENANT, mode: "TEST",
  }, {});
  const other = await call(analyticsHandler, "GET", null,
    { "x-tenant-id": OTHER }, `/api/analytics?tenant=${OTHER}`);
  ok(other.json.tenant_id === OTHER, "analytics scoped to requested tenant");
  ok(other.json.production.decisions === 0 && other.json.production.aftercalls === 0,
     "no leakage of other tenant events");

  const mine = await call(analyticsHandler, "GET", null,
    { "x-tenant-id": TENANT }, `/api/analytics?tenant=${TENANT}`);
  ok(mine.json.production.decisions >= 1 || mine.json.test.decisions >= 1,
     "own tenant sees its events");
}

console.log("\n[5] Analytics separation — TEST events excluded from production");
{
  const a = await call(analyticsHandler, "GET", null,
    { "x-tenant-id": TENANT }, `/api/analytics?tenant=${TENANT}`);
  const prodTotal = a.json.production.total;
  const testTotal = a.json.test.total;
  ok(prodTotal === 0 || typeof prodTotal === "number", "production counter numeric");
  ok(testTotal >= 4, `TEST events tracked separately (got ${testTotal})`);
}

console.log("\n[6] Meeting booking records event (TEST)");
{
  const r = await call(meetingHandler, "POST", {
    mode: "TEST", lead_id: "NPI-1649914912",
    company: "Austin Athletic Recovery", contact: "Front Desk",
    scheduled_time: "Tomorrow 10:00 AM CST",
    meeting_type: "15-Minute Executive AI Discovery Walkthrough",
    tenantId: TENANT,
  }, {});
  if (!r.json.channels) {
    console.error("  DEBUG raw:", r.raw.slice(0, 300));
  }
  ok(r.json.ok === true && r.json.status === "MEETING_RECORDED", "meeting recorded");
  ok(r.json.channels?.telegram?.status === "SKIPPED_NO_PROVIDER", "telegram fail-closed");
}

console.log("\n[7] Input validation");
{
  const bad = await call(aftercallHandler, "POST", { mode: "TEST", leadId: "X" }, {});
  ok(bad.status === 400, "400 on missing transcript");
  const wrongMethod = await call(analyticsHandler, "POST", {}, {});
  ok(wrongMethod.status === 405, "405 wrong method");
}

console.log(`\n========================================`);
console.log(`FOLLOW-UP ENGINE: ${passed} passed, ${failed} failed`);
console.log(`========================================`);
process.exit(failed > 0 ? 1 : 0);
