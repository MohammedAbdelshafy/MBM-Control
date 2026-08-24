# Mission M-023 — Crayo-Class Autonomous Clipping + Distribution + Revenue Engine

- **Status:** COMPLETE (control plane) · CONDITIONAL GO (YouTube-first)
- **Tracking issue:** #17 · **Brief linkage:** #22 · **Deferred:** #18–#22
- **Date:** 2026-08-25
- **Subsystem:** `clipping-factory/MBM-Social/mbm_social/`

## Objective
Turn the existing MBM-Social clipping factory into a fully automated, high-volume,
Crayo-class content production + distribution + revenue engine: one authorized
long-form source → candidate pool → multi-factor scoring → auto-edit →
content intelligence → brand/channel routing → high-volume distribution →
resilient publishing → analytics → revenue attribution → Enterprise Memory →
learning → better next batch.

## What was done
- **Audit first.** Mapped the brief's "Factory" names to the real modules
  (ClipFactory→`viral_intelligence`, PublishFactory→`routing`/`publishers`,
  Enterprise Memory→`learning_engine`, etc.). Extended those; did NOT duplicate.
- **Phase 1** `candidate_pool` — pool sizes 10/25/50/100/250; 8-axis scoring;
  selection with quality + retention gates and a publishable cap.
- **Phase 2** `video_editing` — ffmpeg reframe (9:16/16:9/1:1), word-level
  caption burn-in, safe-zone, center-crop fallback (honest: no fabricated detection).
- **Phase 3** `content_intelligence` — hook/title/desc/caption/hashtags/CTA via
  Model Registry (Ollama-first), template fallback when model offline.
- **Phase 4** `routing_decision` — WHERE/WHEN/SHOULD/variant; fails closed→manual.
- **Phase 5** `distribution_optimizer` — all required volume controls + performance
  auto-scaling + daily caps + queue backpressure.
- **Phase 6** `publishing` — retry/backoff, idempotency, near-duplicate detection
  (reuses `asset_lineage`), dead-letter preservation; blocked platforms → DLQ.
- **Phase 7** `revenue_attribution` — configurable RPM registry (UNVERIFIED
  placeholders), strict ESTIMATED vs ACTUAL, revenue/1K, /1M, cost/clip, profit, ROI.
- **Phase 8** `learning_feedback` — Enterprise Memory loop (record + analytics feed).
- **Phase 9** `Reports/Crayo_Replacement_Gap_Analysis.md` — honest capability matrix.
- **Phase 10** `night_operations.mission_revenue_analysis`.
- **Phase 11** `observability` — metrics aggregator.
- **Phase 12** rights/safety — reused `source_registry`, `asset_lineage`, human gates.
- **Phase 13** model orchestration — reused `model_registry` (no hardcoded models).
- **Phase 14** tests — `tests/test_crayo_engine.py` (24 hermetic, incl. E2E loop).
- **Phase 15** governance — `AGENTS.md` registry updated; this file; GitHub
  issues #17–#22; reports committed.

## Honesty invariants preserved
- No fabricated analytics, views, or revenue.
- No platform marked Published without a real publisher result.
- Blocked (LinkedIn/X) and manual (IG/TikTok) packages preserved in dead-letter,
  never silently dropped.
- Reward rates flagged UNVERIFIED until sourced from official programs (#22).

## Deliverables
- `clipping-factory/MBM-Social/mbm_social/{candidate_pool,video_editing,content_intelligence,distribution_optimizer,routing_decision,publishing,revenue_attribution,observability,learning_feedback,crayo_engine}.py`
- `tests/test_crayo_engine.py` (24 passed)
- `Reports/{Crayo_Replacement_Gap_Analysis,CRAYO_REPLACEMENT_REPORT,PRODUCTION_READINESS,NEXT_SPRINT}.md`

## Open blockers (see issues)
#18 real speaker/face detection · #19 ASR wiring · #20 LinkedIn/X publishers ·
#21 IG/TikTok auto-publish · #22 verify reward rates.
