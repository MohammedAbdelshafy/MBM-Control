# jarvis_control_plane — Scoped Agent Instructions

Governed multi-agent substrate. JARVIS (`MBM/GLM/orchestrator.py`) remains the
top-level decider; this package is the workflow/control layer underneath it.

## Ownership

| Module | Owns | Delegates to |
|---|---|---|
| `workflow.py` | 7-phase run state, deterministic transitions, resume | — |
| `policy.py` | classification, approvals, redaction, retry/timeout | — |
| `registry.py` | machine-readable agent contract | `MBM/GLM/agent_registry.py` (roles) |
| `record_replay.py` | redacted run ledger, LIVE/MOCK/REPLAY/DRY_RUN | — |
| `evaluation.py` | trajectory verdicts (result+trajectory+policy+transitions) | `workflow.py`, `policy.py` |
| `state.py` | scope isolation; canonical adapter | `MBM/GLM/single_writer_lock.py`, `dialer_verification_gate.py` |
| `mcp_a2a.py` | filtered tool bus, A2A contract | `registry.py` |
| `deploy.py` | readiness probes, safe-default specs | — |

## Canonical sources of truth (do NOT duplicate)

- Lead/dialer state → `mbm-dialer/app/public/leads_database.json` via `DialerSingleWriter` only
- Dial eligibility → `MBM/LeadEngine/dialer_verification_gate.py`
- Call lifecycle → `MBM/LeadEngine/dialer_call_engine.py`
- Email suppression → `server/dialer/emailSuppression.js`
- Agent roles → `MBM/GLM/agent_registry.py`

## Safe operations (no approval)

Read-only inspection, draft generation, DRY_RUN/MOCK/REPLAY execution,
`python -m pytest jarvis_control_plane/tests -q`.

## Gated operations (policy.evaluate + approval)

Canonical lead writes, after-call persistence, outbound email/SMS/calls,
money movement, production deploys. Live outbound actions additionally
require their domain gate (verification/suppression/provider) — never bypass.

## Forbidden

Second lead DB / dialer FSM / orchestration engine / suppression / approval /
audit systems. Credentials in code, logs, JSON, reports, or fixtures.
Real outbound calls/SMS/email during control-plane work (DRY_RUN default).
`git commit` / `push` unless explicitly requested.

## Validation

```bash
python -m pytest jarvis_control_plane/tests -q
npm run lint && npm run typecheck && npm test
```
