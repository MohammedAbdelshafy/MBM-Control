# AI Voice Calls — human-like AI voice calls for sales/support

**VibeFounder power #10** (2026-10-11): "Run human-like AI voice calls for
support/sales at scale" — from the reel about Giga's voice AI (millions of
calls/mo, DoorDash-scale case study).

This package wires AI voice calling into the founder's stack as a named,
documented capability: **Wholesaler Lead Engine gains AI-voice lead
follow-up**, and **AI Front Desk gains an AI-voice receptionist lane**.
See `WIRING.md` for the product mapping.

## Status: BUILT + TESTED — activation BLOCKED_ON_KEY

Everything here is real and runnable (21/21 hermetic tests pass), but **live
calls need a paid voice-AI account the founder does not have yet** —
dry-run mode needs no key and costs nothing.

Provider note: Giga (the reel's vendor) is an enterprise platform with no
public self-serve API verified from here. The concrete adapter below targets
**Vapi** (`api.vapi.ai`), whose REST API is publicly documented, so the
integration is real code against real endpoints — not a Giga stub.

## What this is

- `voice_calls.py` — stdlib-only client + campaign layer: Vapi REST adapter
  (assistant create/get, call start/get/list/end, wait-until-terminal),
  E.164 validation, DNC suppression list, AI-disclosure compliance gate,
  CSV lead intake (number,name,consent), campaign runner with pacing +
  JSONL outcome log, parameterized USD cost estimator. No deps.
- `mcp_server.py` — stdlib-only MCP stdio server (8 tools) for Claude Code /
  Cursor agents. No `mcp` package needed.
- `test_smoke.py` — 21 hermetic tests against a fake in-process Vapi
  server: no network beyond loopback, no key, no charge, no real calls.
- `SKILL.md` — reusable agent skill.
- `WIRING.md` — how this plugs into Wholesaler Lead Engine, AI Front Desk,
  and the existing mbm-dialer.

## Activate (founder)

1. Create a Vapi account at dashboard.vapi.ai (paid; card required —
   platform $0.05/min, realistic all-in ~$0.07–$0.25/min per 2026 estimates).
2. Create an assistant + provision a phone number; note both IDs.
3. Export credentials — **environment only, never commit**:
   ```bash
   export VAPI_API_KEY='...' VAPI_ASSISTANT_ID='...' VAPI_PHONE_NUMBER_ID='...'
   ```
4. Compliance before any live campaign (non-negotiable, enforced in code):
   - lead list has recorded consent (`consent=true` per row);
   - the assistant's first message discloses it is AI
     (enforced by `ensure_ai_disclosure`, waiver only with human sign-off);
   - DNC suppression list loaded (`--dnc-csv` / `dnc_csv` tool arg).
5. Always dry-run first, then estimate, then go live on explicit approval.

## Agent use (MCP)

```json
{"mcpServers": {"ai-voice-calls": {
  "command": "python3",
  "args": ["<abs path>/mcp_server.py"],
  "env": {"VAPI_API_KEY": "..."}}}}
```

Mandatory order: `voice_config_check` → `voice_cost_estimate` → `voice_call_start`
/ `voice_campaign_run` with `dry_run=true` → explicit user go-ahead → live run.

## Test evidence

`python3 test_smoke.py` — 21/21 pass, hermetic. Full log in `TEST_EVIDENCE.md`.

## Branch

Built on `night-shift/vibefounder-powers` in MohammedAbdelshafy/MBM-Control
(never master). Mirror of this folder: `integrations/ai-voice-calls/`.
