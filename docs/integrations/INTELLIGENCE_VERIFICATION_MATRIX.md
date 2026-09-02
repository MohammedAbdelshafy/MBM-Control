# Intelligence Verification Matrix
Generated: 2026-09-02T Airlock Reconciliation
Baseline: leads 4953, rev 91, checksum 43b3d167…

## Status Legend

- VERIFIED_LOCAL — code exists, unit-tested locally
- VERIFIED_REMOTE — committed + exists on origin (GitHub)
- LIVE_VERIFIED — read-only live contract proved with real credentials (bounded, non-prod)
- UNVERIFIED — no live proof yet
- BLOCKED / GATED / LOCAL_ONLY — policy states (see provider section)

> Unit tests ≠ live verification. A green suite does not prove endpoint correctness, ToS, or commercial rights.

## Component Matrix

| Component | Local | Remote | Live | Security | License | Status |
|---|---|---|---|---|---|---|
| Provider policy (`provider_policy.py`) | VERIFIED_LOCAL — allow/allow_pending_verification/gated/research_only/blocked enforced via `assert_allowed()`, unknown->BLOCKED, tested 6 cases | UNVERIFIED (intelligence dir untracked, not on origin) | N/A | Pass — fail-closed, env bypass only in tests | N/A | VERIFIED_LOCAL |
| World Monitor adapter (`world_monitor_adapter.py`) | VERIFIED_LOCAL — MCP + REST fallback, Bearer, timeout 12s, 3 retries, rate-limit, payload 2MB, SSRF allowlist (worldmonitor.app), tool discovery dynamic+cache, normalize -> IntelligenceEvent[] | UNVERIFIED | UNVERIFIED — no `WORLDMONITOR_API_KEY` set, no live call in CI | Pass — SSRF, size, content-type, timeout, redacted audit | AGPL-3.0 consumed via API/MCP only (no vendored code) — needs human legal sign-off | VERIFIED_LOCAL |
| Intelligence normalization (`intelligence_engine.py`) | VERIFIED_LOCAL — schema gate, dedupe by sha, 5 tests | UNVERIFIED | N/A | Pass — rejects untitled, preserves provenance, no injection exec | N/A | VERIFIED_LOCAL |
| Provenance (`types.py:Provenance`) | VERIFIED_LOCAL — provider/object/url/type/captured/hash/content/lineage/confidence mandatory, `is_provenance_complete()` | UNVERIFIED | N/A | Pass — stored rawReference hash, transformation lineage | N/A | VERIFIED_LOCAL |
| Opportunity engine (`opportunity_engine.py`) | VERIFIED_LOCAL — weights configurable via env, bounded 0..1, risk always subtracted, provenance failure overrides | UNVERIFIED | N/A | Pass — policy failure overrides score (not implemented as score, but queue blocks APPROVED) | N/A | VERIFIED_LOCAL |
| Opportunity queue/airlock (`opportunity_queue.py`) | VERIFIED_LOCAL — states DISCOVERED..CONSUMED, allowed map fail-closed, write downgrades APPROVED/CONSUMED to REVIEW_REQUIRED, provenance mandatory, audit jsonl, isolated namespace | UNVERIFIED | N/A | Pass — no silent APPROVED, no lead DB write | N/A | VERIFIED_LOCAL |
| Anderro adapter | VERIFIED_LOCAL — no hardcoded rates, live-data only, NOT_VERIFIED/BLOCKED on no key | UNVERIFIED | UNVERIFIED — `ANDERRO_API_KEY` not set, live contract is `test_live_contracts.py:anderro` (skipped) | Pass — never invents `commissionRate` | Proprietary, ToS pending | UNVERIFIED |
| Topview adapter | VERIFIED_LOCAL — idempotent `input_hash`, GenerationJob QUEUED/BLOCKED (no mock video) | UNVERIFIED | UNVERIFIED — `TOPVIEW_API_KEY` not set | Pass — allowlist `api.topview.ai`, timeout 15s | Proprietary, pending verify | UNVERIFIED |
| SkySnail adapter | VERIFIED_LOCAL — 3-5 variants, experimentId, persist + `record_result()`, empty on no key | UNVERIFIED | UNVERIFIED — `SKYSNAIL_API_KEY` not set | Pass — same allowlist pattern | Proprietary, pending | UNVERIFIED |
| VoxCPM gate (`voxcpm_gate.py`) | VERIFIED_LOCAL — `VOXCPM_ENABLED=false` default, `voice_clone_allowed()` requires consent+authz+provenance, bans impersonation, kill switch | UNVERIFIED | UNVERIFIED — self-host not provisioned | Pass — gated, auditable | OSS license TBD, misuse warning | GATED |
| Content orchestrator (`content_orchestrator.py`) | VERIFIED_LOCAL — dry-run never calls Topview, queues opportunities as REVIEW_REQUIRED, no `DialerSingleWriter` import | UNVERIFIED | N/A | Pass — no-publish invariant proven | N/A | VERIFIED_LOCAL |
| Human approval (`human_approval.py`) | VERIFIED_LOCAL — `approve_opportunity()` requires REVIEW_REQUIRED + actor + reason≥5 + correlation_id, audit trail | UNVERIFIED | N/A | Pass — no implicit approval from score | N/A | VERIFIED_LOCAL |
| Observability (`observability.py`) | VERIFIED_LOCAL — counters/latency + redacted AuditLog | UNVERIFIED | N/A | Pass — secrets redacted | N/A | VERIFIED_LOCAL |
| Generation jobs (`jobs.py`) | VERIFIED_LOCAL — QUEUED/RUNNING/SUCCEEDED/FAILED/BLOCKED/RETRYING/CANCELLED, input_hash, idempotencyKey, bounded retries, timestamps | UNVERIFIED | N/A | Pass | N/A | VERIFIED_LOCAL |
| Reward Clipping integration | VERIFIED_LOCAL — reposited reuse: `crayo_engine.py` (candidate_pool->routing_decision->content_intelligence->video_editing->publishing DLQ->revenue_attribution->learning_feedback), 24 crayo tests passed in `clipping-factory/MBM-Social/tests/test_crayo_engine.py`, + hardening modules | UNVERIFIED (clipping-factory on origin) | UNVERIFIED — no live publish test run | Pass | Check clipping-factory licenses | VERIFIED_LOCAL (phases 3-11 code exists) |
| Lead safety | VERIFIED_LOCAL — 6 isolation tests: timeout/malformed/blocked cannot break leads, opportunity cannot reach leads without approval, no second writer, count 4953 unchanged | UNVERIFIED | N/A | Pass | N/A | VERIFIED_LOCAL |
| Prompt injection defense (`security.py`) | VERIFIED_LOCAL — 5 tests: injection flagged as DATA, sanitize, `assert_no_instruction_override`, engine treats injection as title not instruction | UNVERIFIED | N/A | Pass | N/A | VERIFIED_LOCAL |

## Provider Summary (final report enum only)

| Provider | Domain | Status | Reason |
|---|---|---|---|
| World Monitor | worldmonitor.app | LOCAL_ONLY | Code + unit tests verified locally; live contract not run (no key). License AGPL-3.0 via API/MCP only. |
| Anderro | anderro.com | UNVERIFIED | Adapter exists, live contract `test_anderro_live_contract` exists but skipped (no key). Rates never hardcoded. |
| Topview | api.topview.ai | UNVERIFIED | Adapter exists, `allow_pending_verification`; live contract skipped. |
| SkySnail | api.skysnail.ai | UNVERIFIED | Same. |
| VoxCPM | canonical OSS (find org) | GATED | `VOXCPM_ENABLED=false`, consent gate + voxcpm.net BLOCKED. |
| Famelack | — | RESEARCH_ONLY | Never from production. |
| AnkerGames | — | BLOCKED | Policy hard block. |
| Vidbox.dev | — | BLOCKED | Policy hard block. |
| voxcpm.net | voxcpm.net | BLOCKED | Unverified domain ≠ canonical. |

## Remotes

- Intelligence dir `MBM/LeadEngine/intelligence/` is currently **untracked** (`git status ?? MBM/LeadEngine/intelligence/`). Therefore **VERIFIED_REMOTE = false** for all intelligence components — requires commit + push + GitHub verification.
- Lead DB, AD engine, clipping-factory are on `origin/master` at `393cea8`.
- Previous agent claim "ahead by 3" is **stale** — current `HEAD == origin/master == 393cea8`, working tree dirty with many untracked files, no divergence. No commits were pushed for intelligence layer.

## Live Contract Tests

Located `MBM/LeadEngine/intelligence/tests/test_live_contracts.py` (marked `@pytest.mark.live`, excluded from normal CI). Each requires env var, bounded timeout, read-only where possible, secrets never printed. Currently all 4 are **skipped** (no env). Never reported as passed unless actually run.
