# Clipping Factory — Production Audit (M-022, Phase 0)

- **Date:** 2026-08-25
- **Scope:** `clipping-factory/MBM-Social/` (package `mbm_social/`, root scripts, registries) + touchpoints into `clipping-factory/backend/`
- **Method:** Read-only inspection of architecture docs, runtime modules, publishers, gates, queues, tests. No code was changed during this audit.
- **Verdict:** The real system (`mbm_social/` package) is substantially production-shaped. One root-level script fabricates results and pollutes shared metrics; several real bugs silently disable core capabilities (local LLM generation, paced publishing). LinkedIn/X publishing does not exist anywhere.

---

## 1. Current pipeline (what actually runs today)

Two real orchestrators exist:

| Orchestrator | Path | Shape |
|---|---|---|
| `pipeline.run_end_to_end` | `mbm_social/pipeline.py` | Function flow: acquire → analyze → clip → edit → QC → route → package → queue |
| `autonomous_runtime.run_autonomous_campaign` | `mbm_social/autonomous_runtime.py` | 14 named stages (source discovery → rights → acquisition → speech → visual → hook → ranking → captions → thumbnail → QC → publish queue → publisher → analytics → learning) |

Publishing: `post_orchestrator.publish_package` is the single authoritative status writer (`draft → published | publish_blocked | publish_pending_verification`). YouTube: OAuth Data API v3 → native-Chrome CDP → per-brand Playwright profile. Instagram/TikTok: Playwright browser automation only.

Supporting systems: state machine (`state_machine.py`), quality gates (`video_gate.py`, `audio_gate.py`, `caption_gate.py`, `platform_gate.py`, `creative_gate.py`, `visual_qa.py`), brand config/router (`brand_config.py`, `brand_router.py`), learning (`learning_engine.py`), analytics ledger (`youtube_analytics.py`), night ops (`night_operations.py`, 10 missions), pacing (`paced_publish.py`), rewards/economics ledgers (`content_rewards.py`, `agent_economics.py`, `asset_lineage.py`, `profit_engine.py`, `jarvis_decision.py`).

## 2. Duplicate systems

1. **Four "pipelines":** `pipeline.run_end_to_end`, `autonomous_runtime` (real), `ROOT/mbm_social_autonomous_runtime.py` (fake, §3), `multi_agent_workflow.py` queue chain (partially dead code — checks `audit_result["approved"]` but `clipping_quality_agent` returns `gatekeeper_status`).
2. **YouTube upload ×4:** `youtube_api_publisher.py`, `youtube_cdp_publisher.py`, `publisher.py`, plus the status logic in `post_orchestrator`. Three separate `mark_published()` implementations.
3. **Learning/memory writers ×3:** `learning_engine.py`, `autonomous_runtime.stage_learning`, fake root script's `LearningEngine`.
4. **Night ops ×2:** real `mbm_social/night_operations.py` vs fake root `NightOperationsDaemon`.
5. **Anti-detection helpers:** `human_behavior.py` duplicated inline in `shortform_publisher.py:32–75`, `youtube_cdp_publisher.py:92–100`, `account_creator.py:74–79`.
6. **Chrome profile conventions ×3** (`youtube_profile_<brand>/`, `youtube_profiles/<slug>/`, package-relative profiles).
7. `TOPICS` constant defined twice in `social_account_discovery.py` (:49, :108).

## 3. Fake / placeholder implementations (integrity risks)

| Item | Location | Problem |
|---|---|---|
| **Fabricated campaign runtime** | `MBM-Social/mbm_social_autonomous_runtime.py` | Hardcodes 16 steps as `"PASSED"` without executing anything; writes **fabricated analytics** (`views=100000, ctr=0.092, revenue_usd=1850`) into `ChannelMetrics.json`; advertises LinkedIn/Twitter auth that has no implementation; night-ops returns canned SUCCESS. **This is the highest-severity finding — it poisons the same metrics file the learning engine consumes.** |
| Broken model generation | `mbm_social/model_registry.generate()` (:82–103) | Calls `AIService.generate(...)` — method does not exist (backend has `complete/complete_structured/embed`). Every call raises → returns canned JSON blob `'{"title": "Viral Short", ...}'`. Local Ollama generation never runs despite module docstring claiming local-only inference; also ignores resolved task model / temperature / max_tokens. |
| Paced publisher never publishes | `mbm_social/paced_publish.py:149` | Calls `orch.publish_package(filepath, package, dry_run=False)` omitting `mode=` which defaults to `"dry_run"` → forced back to dry-run forever. Docstring says 5/day @120 min; constants are `MAX_DAILY=25`, `GAP_MINUTES=15`. |
| Rights check rubber stamp | `mbm_social/autonomous_runtime.stage_rights_check` (:108–118) | Always returns `rights_verified: True`, `rights_holder="approved_source"`. No source approval lifecycle exists at runtime. |
| Ranking seed | `stage_ranking` seeds `score: 0.6`; `brand_router` uses `visual_fit=0.7 # placeholder` and fixed `past_performance=0.5`. |
| Partially-fake quality gates | `creative_gate.py:174–227` hardcodes 9 of 13 dimension scores to 7.0/8.0; `audio_gate.validate_audio` hardcodes silence/loudness checks `True` while real LUFS/silence helpers sit unused (:212–215). |
| Fabricated virality score | `high_reach_virality_agent.py:53` → `random.randint(96,99)`. |
| Mock trend sources | `social_trend_jack_agent.py` hardcoded trend list; `trend_hijack_runtime.py` self-admitted mock fetch. |

## 4. Incomplete stages

- **No event bus** — stages communicate only via return values/files; no observable event stream (closest: `content_rewards.economics_event`, unconsumed).
- **No checkpoint/resume between runtime stages** — a crash mid-run restarts from stage 1; `state_machine.py` exists but `autonomous_runtime` never drives it.
- **No dead-letter queue, no circuit breaker** anywhere in the tree.
- **No verify-publish step** after upload (status flips to published on API response; CDP RSS diffing exists but isn't wired into verification loop); analytics verification exists separately in `youtube_analytics.verify_analytics`.
- **Thumbnail stage generates text/prompt only** — no image variants, no scoring (Phase 6 requirement).
- **Per-platform metadata not differentiated** — one title/description/hashtags for all platforms (`publish_package.build_package`), violating Phase 5.
- `asset_lineage.RenderJob.enqueue_render/retry_backoff` — retry descriptors exist but **nothing dequeues or executes them**.

## 5. Missing credentials / capabilities

| Capability | Status |
|---|---|
| YouTube OAuth tokens | Present for some brands in `youtube_tokens.json` (gitignored); reauth tooling exists. |
| Instagram Graph API | Absent — Playwright UI automation only. |
| TikTok Content Posting API | Absent — Playwright UI automation only; requires audited app for direct-post. |
| LinkedIn | **No implementation at all.** |
| Twitter/X | **No implementation at all.** |
| Analytics APIs | `youtube_analytics.py` provider-less (docstring records revoked scopes honestly); IG/TikTok analytics absent. |
| Whisper/transcription | Runs via backend agents (faster-whisper vendored under `video_repos/`). |

## 6. Broken assumptions

- `model_registry` assumes `AIService.generate()` exists (§3) and that backend import inside a hot function is safe.
- `publisher.upload_to_youtube` headless=True path waits for an interactive login that can never happen headless (:112–121); returns bare `True` without video id (:277).
- `run_from_queue()` marks packages `published` when `published=True` even when `video_id=None` (`autonomous_runtime.py:505–510`) — contradicts post_orchestrator's pending-verification contract.
- `bc.list_brands()` called by `social_account_discovery.py:319` but not defined → silent AttributeError → hardcoded brand list.
- `night_operations.mission_platform_health` probes token path `BACKEND.parent/youtube_tokens.json` but actual tokens live at MBM-Social ROOT.
- `mission_queue_optimization` deletes drafts >7 days with **no backup** (:308–316); `clean_publish_queue.py` deletes every queue JSON unconditionally.
- Campaign profiles list `"twitter"`/`"linkedin"` platforms with zero backing implementation.

## 7. Unsafe automation

- Live-mode gate is good (`PUBLISH_MODE=live` env required) — keep.
- Queue purge without backup (above) is the main destructive risk.
- `account_creator.py` prints predictable password patterns.
- Browser profiles containing live session cookies sit inside the repo tree (gitignored, but drift-prone; three conventions).

## 8. Performance bottlenecks

- Embedding calls per candidate per brand (2 HTTP calls each) in `brand_router.route_clip` — fine for 5 brands, quadratic at scale.
- `model_registry.generate` imports the whole FastAPI backend per call.
- Night ops backup copies whole `Brands/` tree nightly without retention pruning.
- Headless Playwright Studio flows are slow and fragile vs the working OAuth path (correctly ordered last).

## 9. Exact production blockers

1. **P0 — quarantine the fake root runtime** (`mbm_social_autonomous_runtime.py`) and purge its fabricated rows from `ChannelMetrics.json` (backup first).
2. **P0 — fix `model_registry.generate`**: route through Ollama `/api/generate` (task-resolved model), fall back to `AIService.complete()`, never return fabricated content.
3. **P0 — fix `paced_publish` mode passthrough** so scheduled pacing can actually publish.
4. **P0 — source rights lifecycle**: enforce DISCOVERED→APPROVED gate before acquisition (replace rubber stamp).
5. **P1 — checkpoint/resume + events + DLQ/circuit breaker** in the runtime (Phases 1/13).
6. **P1 — per-platform metadata + thumbnail variants/scoring** (Phases 5/6).
7. **P1 — configurable quality-gate thresholds with measured-vs-assumed provenance** (Phase 7).
8. **P2 — LinkedIn/X honest BLOCKED/MANUAL_REQUIRED surface + GitHub issue hook** (Phase 8).
9. **P2 — website contract, client-campaign mode, analytics→ranking feedback loop** (Phases 10/11/14).

## 10. Test coverage snapshot

Strong offline suites already exist: `tests/test_production_safety.py` (31), `test_production_qa.py` (50), `test_hardening.py` (47). Uncovered: publishers (CDP/shortform/legacy), night ops, paced_publish, social_account_discovery, the new modules required by Phases 1–15.

---

**Decision:** extend `mbm_social/` (no parallel architecture): fix P0 bugs in place, add event bus / checkpoints / source registry / viral intelligence / platform registry / circuit breaker+DLQ / GitHub App control plane / website contract as new focused modules consumed by the existing runtime, and wire learning→routing feedback. All changes covered by hermetic pytest suites.
