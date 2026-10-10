# Skill: ai-voice-calls

Run human-like AI voice calls for sales/support through a documented
voice-AI REST API (Vapi adapter), for **Wholesaler Lead Engine** outbound
lead follow-up and **AI Front Desk** voice-receptionist lanes.

## When to use

- A Wholesaler Lead Engine lead needs an AI follow-up call (motivation /
  cash-offer qualification from the 100-record call-now list).
- An AI Front Desk client wants a voice receptionist (inbound-capable
  assistant config; outbound appointment reminders).
- NEVER use when: no `VAPI_API_KEY` is configured — offer the dry-run path
  instead; never invent a key, a call ID, or a transcript.

## Setup

```bash
export VAPI_API_KEY='...' VAPI_ASSISTANT_ID='...' VAPI_PHONE_NUMBER_ID='...'
# keyless check (validates + estimates, zero network):
python3 voice_calls.py --config-check
python3 voice_calls.py --estimate 50 --avg-minutes 2.5
```

## Agent workflow (mandatory order)

1. **Config check** — `voice_config_check`. If `VAPI_API_KEY` is MISSING,
   stop: dry-run only.
2. **Estimate first** — `voice_cost_estimate(num_calls, avg_minutes)`.
   State the USD range to the user before anything live.
3. **Compliance** — for any live call/campaign:
   - leads CSV has `consent=true` per row (`load_leads_csv` drops the rest);
   - DNC CSV loaded and applied (`voice_dnc_check`);
   - assistant's first message discloses the caller is AI
     (enforced automatically; waiver needs human sign-off).
4. **Dry-run** — `voice_call_start(..., dry_run=true)` or
   `voice_campaign_run(..., dry_run=true)` to validate E.164, DNC,
   disclosure, and payloads. Zero network, zero charge.
5. **Live only on explicit user go-ahead** — `dry_run=false`; then
   `voice_call_status(call_id)` / JSONL outcome log for campaigns.
6. **Report** — calls placed, statuses, minutes, estimated spend, log path.

## Budgets

No global spend cap is enforced by the client. If the user sets a cap,
track estimates locally and refuse live starts that exceed it. Estimates
can differ from final charges; the Vapi dashboard analytics are ground truth.

## Failure modes

- `401/403` → key wrong or missing. Do not retry with variations.
- Call stuck non-terminal → `wait_call` raises after timeout; the call_id is
  preserved — resume with `voice_call_status(call_id)`.
- Compliance validation error (bad number, DNC hit, no disclosure) → fix the
  input; do not bypass the gate.
