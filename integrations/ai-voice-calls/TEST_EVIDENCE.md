# TEST EVIDENCE — ai-voice-calls

**Date:** 2026-10-11 (night-shift run)
**Method:** `python3 test_smoke.py` — hermetic. All provider traffic goes to
an in-process fake Vapi HTTP server on 127.0.0.1 (in-memory store; no key,
no charge, no real calls). MCP tools are exercised via stdio round-trips.

## Result: 21/21 pass

```
== ai-voice-calls smoke tests (hermetic) ==
  PASS missing key raises ConfigError
  PASS E.164 validation
  PASS create/get assistant
  PASS assistant requires model
  PASS start call posts correct payload
  PASS start call needs assistant+number ids
  PASS wait_call polls to ended
  PASS end_call PATCH
  PASS list calls
  PASS 401 raises ApiError
  PASS AI disclosure enforced
  PASS DNC suppression
  PASS leads CSV loading
  PASS campaign dry-run (zero HTTP)
  PASS cost estimation
  PASS MCP initialize + tools/list
  PASS MCP config check (no secrets)
  PASS MCP call start dry-run validation
  PASS MCP assistant disclosure gate
  PASS MCP cost estimate
  PASS CLI --estimate

21 passed, 0 failed
```

## What the tests actually verify

- Config: missing `VAPI_API_KEY` raises `ConfigError` (never a silent call);
  `voice_config_check` reports `blocked_on_key` without echoing secrets.
- Validation: E.164 rejects 6 malformed shapes, accepts `+14155551234`;
  unparseable numbers are treated as DNC-suppressed (never dialed).
- Provider flow (fake server): assistant create/get round-trip; call start
  sends `assistantId`/`phoneNumberId`/`customer.number` with a Bearer auth
  header; `wait_call` polls `queued → in-progress → ended`; `end_call`
  PATCH sets status; `list_calls` returns the store; wrong key → 401
  → `ApiError`.
- Campaign: CSV intake skips bad rows (no-consent, invalid, duplicate);
  DNC-suppressed lead is never dispatched; dry-run makes **zero HTTP calls**
  (asserted against the fake server's request log); JSONL outcome log has
  one record per lead.
- Compliance: non-disclosing first messages are rejected by
  `ensure_ai_disclosure` and by the `voice_assistant_create` MCP tool, even
  in dry-run.
- MCP: initialize + tools/list expose 8 tools; notifications/initialized
  handled as a true notification; dry-run call start returns validation +
  cost estimate with no network.

## Honest limits

- One fixture bug caught by the tests: the fake server did not strip query
  strings on `GET /call?limit=...` (fixed; 21/21 after).
- Live Vapi behavior (real billing, real latency, webhook end-of-call
  reports, recording URLs) is NOT exercised here — activation needs a paid
  `VAPI_API_KEY` the founder does not have yet (BLOCKED_ON_KEY).
- Pricing defaults ($0.05/min platform; $0.07–$0.25/min all-in) are 2026
  third-party estimates, re-check the vendor page before quoting clients.
