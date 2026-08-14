# ADR: Durable execution substrate for MBM workloads (jarvis-mbm#17 deliverable D)

Date: 2026-08-14
Status: PROPOSED (decision: ADOPT-for-selected-workloads, keep EventBus as control plane)

## Context

MBM runs several long-running, crash-prone workloads:
- MBM-Social 15-minute publish cycle (render + QA + routing + publish)
- Asset lineage render jobs with retries/backoff (asset_lineage.enqueue_render)
- Lead pipeline refresh (MoneyBeast, NPI callsheet, skip-trace)
- Email/outreach queues

Current reliability primitives are bespoke: JSONL ledgers (append-only), queue
JSON files, in-process retries, and the EventBus as the communication layer.
There is no unified durability substrate: a process crash mid-cycle leaves
ledger rows without a resume point.

## Gap (measured, not guessed)

| Capability | Current | Gap |
|---|---|---|
| Crash recovery | None (state is in flat files; no replay) | **Missing** |
| Retries w/ backoff | In-code per job (render job) | Partial |
| Durable job queue | publish_queue/*.json + status flags | Partial |
| Idempotent resume | No checkpoint/replay | **Missing** |
| History/visibility | JSONL ledgers | Partial |
| Distributed workers | None | Missing |

Evidence: `asset_lineage.py` has `RenderJob` with `queued/rendering/retry/failed`
and `next_run_after_iso` backoff — a hand-rolled durability attempt. MBM-Social
routing dry-run showed 1303 queued packages processed without a crash-safe
worker boundary.

## Candidates

### Temporal (MIT)
- Proven durable workflows, retries, crash recovery, activity heartbeats.
- Operational cost: server stack (Postgres/MySQL + worker). License MIT,
  commercial suitable.
- Fits: render pipeline, lead refresh, outreach queues.
- Migration path: wrap existing pipeline entry points as Temporal activities;
  keep ledgers as the source of truth (Temporal becomes the executor).
- Rollback: activity boundary keeps pipeline functions intact; workers can
  stop and existing scripts resume running directly.

### LangGraph checkpointing (MIT)
- State-machine/checkpoint pattern, human-in-loop. Simpler than Temporal.
- Less operational overhead (embeds in-process with checkpoint stores).
- Fits: single-process agent workflows; NOT a distributed executor.
- Risk: becomes a second orchestrator if layered on top of EventBus carelessly.

### n8n (Sustainable Use License — fair-code, not OSI)
- Great UX + human approvals, but commercial reuse restrictions.
- Decision: REFERENCE only; catalog existing MBM/n8n patterns, do not embed.

## Decision

**ADOPT Temporal for the two highest-risk workloads** (render/QA/publish cycle
and lead-refresh pipeline) as an execution substrate ONLY — the EventBus and
existing pipeline modules remain the control plane and source of truth.
**REFERENCE LangGraph** checkpoint concepts without importing the framework.
**REJECT n8n embedding** (license + second-orchestrator risk).

## Migration path (smallest useful slice)

1. Wrap `asset_lineage.enqueue_render -> mark_rendering -> (success|retry_backoff)`
   as Temporal activities. No schema change: RenderJob JSONL stays authoritative.
2. Wrap the 15-min cycle entry as a Temporal workflow with heartbeats; on crash,
   workflow replays from the last completed activity (ledger row idempotency
   via submission/asset IDs already present).
3. Run a dry-run parity test: Temporal execution vs current runner must produce
   identical ledger rows and routing decisions.

## Rollback

Temporal workers are additive. Stop workers => existing scripts/daemon resume
operating on the same JSONL/queue files unchanged. No data migration required
because ledgers remain the system of record.

## Open items

- Self-hosting operational cost (Temporal server) vs Temporal Cloud.
- Concurrency controls across multiple workers touching the same publish_queue.
- Cost/benefit of wrapping the EventBus bus itself (rejected for now).
