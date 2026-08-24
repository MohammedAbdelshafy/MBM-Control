# CRAYO_REPLACEMENT_REPORT (M-023)

Reference issue: GitHub #22 (per brief) · tracking #17 · follow-ups #18–#22.

## 1. What was already present (reused, not rebuilt)
- `viral_intelligence.score_clip` — the ClipScorer brain (multi-factor ranking, deterministic).
- `content_rewards` — honest economics pipeline (ESTIMATED/verified/actual, routing reuse).
- `routing` — fail-closed destination resolver (brand→account→platform).
- `platform_registry` (M-022) — honest YouTube=SUPPORTED, IG/TikTok=MANUAL, LI/X=BLOCKED.
- `circuit_breaker` + `checkpoint` + `event_bus` (M-022) — resilience primitives.
- `asset_lineage` — simhash near-duplicate detection.
- `learning_engine` — Enterprise Memory (winning hooks/titles/performance).
- `brand_router`, `brand_config`, `publish_package`, `quality_gate_policy` (M-022).
- Publishers: `youtube_api_publisher`, `youtube_cdp_publisher`, `shortform_publisher`, `publisher`.
- QA gates: `creative_gate`, `clipping_quality_agent`, `video_gate`, `caption_gate`, `audio_gate`, `visual_qa`.

## 2. What was added (new modules, `mbm_social/`)
- `candidate_pool` — Phase 1: pool sizes 10/25/50/100/250, 8-axis scoring, selection.
- `video_editing` — Phase 2: ffmpeg reframe (9:16/16:9/1:1), caption burn-in, safe-zone.
- `content_intelligence` — Phase 3: hook/title/desc/caption/hashtags/CTA via Model Registry.
- `distribution_optimizer` — Phase 5: volume controls + performance-driven auto-scaling.
- `routing_decision` — Phase 4: WHERE/WHEN/SHOULD/variant decision.
- `publishing` — Phase 6: retry/backoff/idempotency/duplicate/DLQ resilience layer.
- `revenue_attribution` — Phase 7: configurable RPM, ESTIMATED vs ACTUAL, ROI.
- `observability` — Phase 11: metrics aggregator.
- `learning_feedback` — Phase 8: Enterprise Memory loop wrapper.
- `crayo_engine` — canonical orchestrator wiring the full loop.
- `night_operations.mission_revenue_analysis` — Phase 10 night mission.

## 3. What was reused (not duplicated)
Every new module calls an existing one: scoring→`viral_intelligence`; economics→
`content_rewards`+`revenue_attribution`; routing→`routing`+`platform_registry`;
dup-detect→`asset_lineage`; learning→`learning_engine`; metadata→`publish_package`
pattern + `model_registry`. No parallel factory architecture was created.

## 4. What is fully automated
Given one authorized source + a fake/real transcription provider + a publisher:
ingest→candidate pool→scoring→selection→routing decision→metadata→editing
command build→resilient publish→economics→learning→metrics. Verified end-to-end
in `tests/test_crayo_engine.py::test_crayo_e2e_publishes_and_learns` (24 tests
total, all green).

## 5. What still requires credentials / external services
- Ollama local models for real hook/title/CTA generation (else honest templates).
- YouTube OAuth refresh tokens for live public publish.
- Instagram Graph API app + token (or keep MANUAL).
- TikTok Content Posting API app (or keep MANUAL).
- LinkedIn API app + publisher (currently BLOCKED, #20).
- X API v2 write + publisher (currently BLOCKED, #20).
- YouTube Analytics API scopes for real `verify_analytics` (revoked).
- Verified reward rates from official program sources (#22).
- Real ASR (faster-whisper) wiring into the pool (#19).
- Real active-speaker/face detector for reframe (#18).

## 6. Tests passed
45 total in `clipping-factory/MBM-Social/tests/`: 21 (M-022) + 24 (M-023). All green.

## 7. Throughput achieved (logic layer, hermetic)
The metrics aggregator reports clips/hour, publish throughput, queue depth,
failure/retry rate, cost/clip, views/clip, ROI. Under test the loop processes a
25-candidate pool and publishes the selected subset with 0 failures. Real
throughput is bounded by: Ollama generation latency (per clip), FFmpeg render
time (per clip), and platform API rate limits (enforced by `distribution_optimizer`
caps). No media was rendered in tests, so wall-clock throughput is unmeasured;
the control plane is proven correct.

## 8. Cost per clip
`revenue_attribution` + `agent_economics` track cost. Default amortized editorial
+ render cost is $0.10/production-minute (configurable). With Ollama local models,
generation is effectively free; only render compute (FFmpeg/GPU) and any paid API
(e.g. YouTube) incur cost. `observability.cost_per_clip_usd` surfaces this.

## 9. Current blockers
1. LinkedIn/X publishers absent (BLOCKED).
2. IG/TikTok auto-publish absent (MANUAL).
3. Unverified reward rates (#22).
4. No real ASR wiring into the pool (#19).
5. No real speaker/face detector for reframe (#18).
6. YouTube Analytics scopes revoked.

## 10. Highest-ROI next mission
**Verify reward rates + wire real YouTube Analytics** (#22): it unlocks ACTUAL
revenue/ROI reporting (currently ESTIMATED-only) with the least engineering, and
directly improves the learning loop's priors. Second priority: **ASR wiring (#19)**
so the candidate pool scores on real speech/hook signals instead of synthetic
defaults — this lifts selection quality across every brand.
