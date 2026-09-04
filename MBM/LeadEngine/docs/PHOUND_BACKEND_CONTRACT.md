# Phound Backend Contract (for Antigravity frontend)

Owner: backend/data (MBM-Control). Frontend must consume this contract.
Do not build frontend-side telephony, token handling, or queue mutation.
Scope: Issues #42 (provider), #43 (auto-dial), #44 (Android/SIM-assisted).

Modules:

- `MBM/LeadEngine/phound_provider.py` — provider bridge (CLI + importable API)
- `MBM/LeadEngine/phound_auto_dialer.py` — auto-dial state machine (CLI)
- `MBM/LeadEngine/ad_dialer_adapter.py` — the ONLY lead read/write path
  (single-writer lock; no second lead database, ever)

## 1. Provider status

Command: `python MBM/LeadEngine/phound_provider.py --status`

Response (UI-safe; token never echoed, preview only):

```json
{
  "ok": false,
  "provider": "phound",
  "mode": "native_app",
  "enabled": false,
  "configured": false,
  "token_preview": "uid1...456",
  "error": null,
  "message": "Phound native-app mode. Manual fallback available; no credentials exposed.",
  "checked_at": "2026-09-03T23:41:29+00:00"
}
```

- `mode: "api"` only when `PHOUND_ENABLED=true` AND `PHOUND_TOKEN`
  (`<uid>.<api_key>`) AND `PHOUND_DEFAULT_PERSONA_UID` are set.
  Otherwise `mode: "native_app"` (manual fallback; frontend shows handoff).
- `ok: true` iff `mode == "api"`.

## 2. Provider capabilities

| Capability | API mode | Native-app mode |
|---|---|---|
| `place_call` (server-side) | yes | no → `handoff` URL returned |
| `send_sms` (server-side) | yes | no → `prefill` URL returned |
| `ingest_event` (lifecycle) | yes | yes (manual dispositions) |
| `health` | yes | yes |

`place_call` response statuses: `dry_run_simulated` | `native_app`
(`to` + `handoff: https://web.phound.app/?phone=...`) | `accepted`
| `duplicate_suppressed` | `error_transient_no_call_placed` (safe to retry)
| `unknown_provider_state` (+ `reconciliation_required: true` — never blind-retry).

`send_sms` mirrors this (`prefill` instead of `handoff`).
Every response carries the persisted provider-call `record`:

```json
{
  "provider": "phound", "provider_call_id": null, "lead_id": "NPI-…",
  "persona_uid": "P1", "kind": "call",
  "normalized_phone": "+18176561215", "request_id": "NPI-…_worker_…",
  "dry_run": true, "lifecycle_status": "dry_run_simulated",
  "disposition": null, "transcript": null, "recording_url": null,
  "error": null, "created_at": "…", "updated_at": "…"
}
```

## 3. Modes

`MANUAL` | `ASSISTED` | `AUTO_DIAL` | `ANDROID_SIM_ASSISTED`
(pass `--mode`; default `ASSISTED`).

- `AUTO_DIAL` is capability-gated: requires `PHOUND_AUTODIAL_APPROVED=1`
  AND healthy API mode. Otherwise the backend refuses and falls back to
  `ASSISTED` (`capability: {allowed: false, reason, fallback: "ASSISTED"}`).
- `ANDROID_SIM_ASSISTED` (#44): MBM is the queue/intelligence layer only.
  Each lead returns `{status: "handoff_presented", to, handoff: "tel:…",
  script_context: {contact, score, notes}}` and the queue NEVER auto-advances.
- `MANUAL`/`ASSISTED` in live mode return `awaiting_operator_confirm` per lead.

## 4. Queue pull (gated)

Auto-dial consumes ONLY leads passing
`dialer_verification_gate.filter_for_dialer` + optional campaign filters
(`--vertical`, `--status-filter`). Hard exclusions: invalid/malformed/
synthetic-555 phones, failed names, unverified, DNC, opt-out, suppressed
(`MBM/Artifacts/suppressed_bad_phones.json`), closed dispositions
(CLOSED/DEAD/LOST/DNC/OPTED_OUT/STOP/WRONG_PERSON/NON_OWNER/BAD_NUMBER),
in-flight, cooldown, duplicates, missing contact info.

`queue_qa` in every run response (exact counts):

```json
{"ingested": 29561, "gate_passed": 4892, "gate_rejected": 24669,
 "optout_closed_inflight_skipped": 0, "callable": 5}
```

## 5. Run / current call / controls

Start (DRY_RUN is the default; NOTHING is placed without `--apply`):

```bash
python MBM/LeadEngine/phound_auto_dialer.py --mode ASSISTED --dry-run --limit 10
python MBM/LeadEngine/phound_auto_dialer.py --mode AUTO_DIAL --apply --limit 25 \
  --max-in-flight 1 --pacing-seconds 30 --cooldown-seconds 3600 \
  --daily-cap 100 --session-cap 50 --persona-uid P1
```

Run response: `{status, mode (effective), capability, dry_run,
outcomes: [{status, lead_id, …}], state, queue_qa}`.

Status: `--status` → `{paused, stopped, in_flight: {lead_id:
{request_id, started_at, mode}}, in_flight_count,
session_counts: {attempted, completed, failed, skipped},
daily_counts: {date, attempted}, dial_attempts_logged}`.

Controls: `--pause` / `--resume` / `--stop`. Stop conditions also fire on
`max_in_flight | session_cap | daily_cap | max_failed(5) | max_skipped(50)`
(defaults shown). `in_flight` is the current call set (max 1 by default).

Locking/idempotency: `dial_attempt` intent (`lead_id` + `request_id`) is
persisted BEFORE placement; a second worker placing the same lead gets
`duplicate_suppressed`. The provider call is placed exactly once per request.

## 6. Lifecycle state / disposition / aftercall

Ingest one provider event:

```bash
python MBM/LeadEngine/phound_auto_dialer.py \
  --event-json '{"lead_id":"L1","lifecycle_status":"completed","provider_call_id":"pc_1","disposition":"CONNECTED","transcript":"…"}'
```

Terminal lifecycles (`completed|ended|done|call_completed|call_ended|
finished`) clear in-flight AND persist via the existing
`DialerAdapter.record_aftercall(lead_id, transcript≤2000 chars,
disposition, notes, phone)` path (same store as
`mbm-dialer/app/api/aftercall.js`). Non-terminal events are recorded only.

Response: `{status: "event_recorded", handed_to_aftercall: bool, aftercall:
{ok, lead}}`.

Ambiguous provider state → `unknown_provider_state` (never auto-retried).
Restart recovery: `--reconcile` flags every in-flight lead without a
terminal event as `unknown_provider_state` for human review and clears the
lock: `{reconciled: N, flagged: [{lead_id, …, action}]}`.

## 7. Manual fallback

Always available: native-app mode returns `handoff` /
`prefill` (`https://web.phound.app/?phone=…`) and `tel:` links in
`ANDROID_SIM_ASSISTED`. Frontend must keep the manual action visible
whenever `mode != "api"`.

## 8. State files (backend-owned, gitignored `MBM/LeadEngine/logs/`)

- `phound_autodial_state.json` — lock, in-flight, counters, pause/stop flags
- `phound_dial_attempts.jsonl` — durable dial intents
- `phound_provider_calls.jsonl` — provider-call records
- Secrets NEVER appear in these files, lead JSON, browser storage, or logs.

## 9. Credential / live-call status (2026-09-04)

No `PHOUND_TOKEN`, no persona UID configured in any committed file.
DRY_RUN verified end-to-end (29,561 ingested → 4,892 gated → callable queue;
zero real calls, zero real SMS). Live placement is impossible until
credentials + `PHOUND_AUTODIAL_APPROVED=1` are set in the runtime
environment (never in source).
