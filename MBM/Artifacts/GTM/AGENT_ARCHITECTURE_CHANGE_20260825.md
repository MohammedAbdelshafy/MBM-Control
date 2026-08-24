# AGENT ARCHITECTURE CHANGE — 2026-08-25

## OX ALPHA 2 RETIRED (JARVIS directive)

Effective immediately, the swarm has EXACTLY THREE active agents:

| Agent | Role |
|---|---|
| **OX1** | Master intelligence: research, strategy, governance, orchestration, learning. SOLE research authority (absorbs all former OX2 functions). |
| **OX3** | Commercial intelligence: scoring, pain/offer selection, contact qualification. Owns CALL_READY / EMAIL_READY gates. |
| **ANTIGRAVITY** | Execution: email sends, follow-up cadence, reply triage, telemetry, suppression. |

## Rules
- Never dispatch to OX2 / wait on OX2 / create OX2 missions.
- Historical OX2 artifacts (`dental_gold_batch_001/DENTAL-GOLD-001..002.*`, earlier research batches) are marked
  **LEGACY_RESEARCH_ARTIFACT** — preserved for institutional memory, readable as evidence only.
- OX1 research output must carry the full evidence schema (identity, sources, timestamps,
  confidence, conflicts) but NEVER sets commercial gates.
- Pipeline law: OX1 (discover→verify→enrich→understand→evidence) → OX3 (score→qualify→rank)
  → Antigravity (execute→listen) → OX1 (learn→adjust).

## Registry status
- agent registry: OX2 removed from active set this date.
- handoff contracts: OX1 is the sole upstream of OX3.
- dashboard/scheduler/dependency graphs: show OX1 / OX3 / ANTIGRAVITY only.

Owner: system · Authority: JARVIS v7 · Timestamp: 2026-08-25T00:00Z+ (local session)
