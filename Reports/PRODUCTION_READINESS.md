# PRODUCTION_READINESS (M-023)

- **Date:** 2026-08-25
- **Scope:** `clipping-factory/MBM-Social/mbm_social/` Crayo-class engine
- **Linked issues:** #17 (tracking), #22 (per brief), #18–#22 (deferred)

## Verdict: CONDITIONAL GO (YouTube-first)

The control plane for a Crayo-class loop is implemented, tested (45 hermetic
tests), and honest. A single authorized source can flow through ingest →
candidate pool → scoring → selection → routing → metadata → editing → resilient
publish → economics → learning with no fabrication. Live public publishing is
gated behind `PUBLISH_MODE=live` + real credentials, and LinkedIn/X are BLOCKED
(not faked).

## What is production-ready
- Candidate pool generation with configurable 10/25/50/100/250 sizes.
- 8-axis per-candidate scoring (reuses `viral_intelligence` ClipScorer).
- Quality gates (`quality_gate_policy` + creative/visual/audio/caption/video gates).
- Routing decision (WHERE/WHEN/SHOULD/variant) with fail-closed fallback.
- Resilient publishing: retry/backoff, idempotency, near-duplicate detection,
  dead-letter preservation.
- Revenue attribution with strict ESTIMATED vs ACTUAL separation + ROI.
- Enterprise Memory learning loop.
- Observability metrics aggregator.
- Night-ops revenue analysis mission.

## What is NOT production-ready (honest gaps)
- LinkedIn/X publish (BLOCKED — no adapter).
- Instagram/TikTok automated publish (MANUAL — Playwright only).
- Reward rates (UNVERIFIED placeholders).
- Real ASR + speaker/face detection feeding the pool/reframe.
- Actual rendered throughput (unmeasured without media in CI).

## Launch recommendation
- **GO** for YouTube-first campaigns via `crayo_engine.run_crayo_loop` with a
  real publisher + `PUBLISH_MODE=live` after a dry-run.
- **HOLD** LinkedIn/X until #20 resolved.
- Keep IG/TikTok in MANUAL until #21 resolved.
- Verify reward rates (#22) before trusting ACTUAL ROI numbers.

## Test status
`tests/test_m022_modules.py` (21) + `tests/test_crayo_engine.py` (24) = **45 passed**.
