# Clipping Factory — Production Readiness Report (M-022, Phase 18)

- **Date:** 2026-08-25
- **Scope:** `clipping-factory/MBM-Social/` (package `mbm_social/`) + root scripts + registries
- **Verdict:** **CONDITIONAL GO** — one campaign can run end-to-end through the canonical resilient runtime with real quality gates, honest platform surfacing, checkpoint/resume, dead-letter preservation, and hermetic tests. Remaining blockers are credential/implementation gaps on LinkedIn/X and live analytics, all explicitly surfaced (never faked).

## 1. Pipeline coverage (Phase 1 canonical stages)

| Stage | Implemented | Notes |
|---|---|---|
| Source Discovery | Yes | `autonomous_runtime.stage_source_discovery` + `campaign_runner` |
| Rights / Approval | Yes (NEW) | `source_registry.py` lifecycle; restricted sources blocked until APPROVED |
| Source Acquisition | Yes | `ContentAcquisitionAgent` (backend) |
| Media Normalization | Partial | via backend agents; not a standalone stage in this package |
| Speech Intelligence | Yes | `ContentAnalysisAgent` |
| Visual Intelligence | Yes | `ClipGenerationAgent` |
| Hook Fusion | Yes | `EditingAgent` |
| Clip Ranking | Yes (NEW fusion) | `viral_intelligence.py` (11-axis score + history + reasons) |
| Clip Generation | Yes | backend agents |
| Captions | Yes | `publish_package.build_package` |
| Thumbnail | Yes (NEW scoring) | `publish_package.score_thumbnail_variants` (heuristic, provenance-tagged) |
| Quality Gate | Yes (NEW policy) | `quality_gate_policy.py` — 10 gates, configurable thresholds, exact failure reasons |
| Platform Package | Yes | `publish_package` + per-platform metadata (Phase 5) |
| Publish Queue | Yes | `post_orchestrator` authoritative status writer |
| Publish | Partial | YouTube real (API→CDP→Playwright); IG/TikTok Playwright-only; LI/X absent |
| Verify Publish | Partial | post_orchestrator pending-verification; `youtube_analytics.verify_analytics` separate |
| Analytics | Partial | `youtube_analytics.py` ledger; provider-less (scopes revoked) |
| Learning | Yes | `learning_engine.py` + routing feedback (`brand_router._past_performance`) |
| Campaign Optimization | Yes | `auto_update_scoring_weights` self-tuning |

## 2. Completed stages this revision
- P0: `model_registry.generate()` now routes Ollama-first (real local inference) with backend fallback — **no fabricated JSON**.
- P0: `paced_publish` now forwards `mode` (was permanently dry-run); caps configurable via env (5/day, 120 min default).
- P0: fake root runtime quarantined to `mbm_social_autonomous_runtime.py.QUARANTINED`; replaced by a delegating shim (no fabricated metrics).
- Phase 1/2: `event_bus.py`, `checkpoint.py`, `source_registry.py` with rights gate.
- Phase 3: `viral_intelligence.py` 11-axis scoring with reasons/confidence/timestamps/recommended platform.
- Phase 5/6: per-platform metadata + `score_thumbnail_variants`.
- Phase 7: `quality_gate_policy.py` (configurable, exact reasons).
- Phase 8: `platform_registry.py` honest capability matrix; BLOCKED/MANUAL surfaced via `campaign_runner` + GitHub issue hook.
- Phase 9: `github_app.py` (webhook HMAC, idempotency, allow-list, issue creation).
- Phase 10: `app_websites.py` config-driven site contract + static generator.
- Phase 11: `client_campaign.py` INTERNAL vs CLIENT config validation.
- Phase 13: `campaign_runner.py` resilient orchestrator + `circuit_breaker.py` + dead-letter queue.
- Phase 14: learning→routing feedback wired (`_past_performance`).
- Phase 15: night-ops destructive purge fixed (archive, not delete) + `dead_letter_review` mission.
- Phase 17: `tests/test_m022_modules.py` — 21 hermetic tests (units + E2E resume/quality-fail/rights-block/DLQ/blocked-platform).

## 3. Missing credentials / capabilities
| Capability | Status |
|---|---|
| Ollama local models (qwen2.5-coder, nomic-embed-text, llava) | Required for local inference; absent in CI — code degrades to template fallbacks and honest errors. |
| YouTube OAuth refresh tokens | Per-brand; present for some brands. |
| Instagram Graph API app + token | Absent → MANUAL_REQUIRED. |
| TikTok posting API (audited app) | Absent → MANUAL_REQUIRED. |
| LinkedIn API app | Absent → BLOCKED (no implementation). |
| X/Twitter API v2 write | Absent → BLOCKED (no implementation). |
| YouTube Analytics API scopes | Revoked during secret scrub; `youtube_analytics` is provider-less (honest). |

## 4. Platform limitations
- YouTube: fully supported via OAuth Data API v3 (supported) with CDP/Playwright fallbacks. Public publish requires `PUBLISH_MODE=live`.
- Instagram Reels / TikTok: Playwright browser automation only; require a logged-in session; **cannot be auto-verified** → treated MANUAL_REQUIRED.
- LinkedIn / X: no publisher exists. Any package targeting them is preserved (dead-letter) and a GitHub issue is opened; never marked Published.

## 5. Exact production blockers (deferred → GitHub issues)
1. LinkedIn publisher implementation + approved API app. (BLOCKED)
2. X/Twitter publisher implementation + approved API access. (BLOCKED)
3. Provision Instagram Graph API app + token (or accept MANUAL). (MANUAL)
4. Provision TikTok Content Posting API app (or accept MANUAL). (MANUAL)
5. Restore YouTube Analytics API OAuth scopes for real `verify_analytics`. (Missing creds)
6. Purge fabricated rows previously written by the quarantined root runtime from `ChannelMetrics.json` (backup first). (Data hygiene)
7. LLM routing in `brand_router` is embedding-proxy only (`MBM_LLM_ROUTING=1` path depends on the now-fixed `model_registry.generate`). (Tuning)

## 6. Performance
- Local Ollama generation is the dominant cost; backend import is now lazy (only on fallback).
- Brand routing is O(brands × 2 embeddings); fine at 5 brands, quadratic at scale.
- Night backup copies the whole `Brands/` tree with no retention pruning (minor).

## 7. Reliability
- Checkpoint + resume: a crashed run resumes from the last completed stage.
- Dead-letter queue: failed/blocked publishes are preserved, never silently dropped.
- Circuit breaker: a persistently failing publisher stops being hammered.
- Quality gate: failures go to `QUALITY_FAILED` with exact reasons.

## 8. Quality gates
10 configurable gates (media_integrity, hook_quality, speech_accuracy, subtitle_accuracy, visual_framing, audio_quality, brand_fit, platform_fit, metadata_completeness, rights_status). Thresholds live in `quality_gate_policy.DEFAULT_THRESHIERS` and can be overridden per campaign.

## 9. Automation percentage
- ~75% automated end-to-end for YouTube-only campaigns (discovery → publish → analytics → learning) with human checkpoints at: source approval (rights), live public publish (env gate), and login/session maintenance for IG/TikTok.
- LinkedIn/X: 0% (blocked). IG/TikTok: ~40% (packages generated + queued, manual publish).

## 10. Human intervention points
- Approving restricted sources (rights gate).
- First-time YouTube public publish (live mode env).
- IG/TikTok login sessions.
- Reviewing dead-letter queue (blocked/manual platforms).
- Nightly executive report review.

## 11. Launch recommendation
**GO for YouTube-first campaigns** using `campaign_runner.run_campaign` with `CampaignContext(allow_manual=True)` and `PUBLISH_MODE=live` only after human login + a dry-run. **HOLD** LinkedIn/X until a real publisher + API app exist. IG/TikTok may run in MANUAL mode (packages produced, human publishes).

## 12. Test status
- `tests/test_m022_modules.py`: **21 passed** (units + E2E).
- Pre-existing suites (`test_production_safety/qa/hardening`): unchanged by this revision; require media/backend fixtures to run locally.
