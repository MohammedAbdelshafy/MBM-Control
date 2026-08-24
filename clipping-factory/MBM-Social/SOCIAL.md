# SOCIAL.md -- MBM Social

Brand management, publishing, and analytics for the MBM multi-channel YouTube network.

## Architecture

Single autonomous clipping business — 5 internal brands + unlimited external client campaigns — all running through one pipeline backend.

```
Campaign Input
  -> Source Discovery
  -> Rights Status
  -> Video Acquisition (ContentAcquisitionAgent)
  -> Speech Factory (ContentAnalysisAgent)
  -> Visual Factory (ClipGenerationAgent)
  -> Hook Factory (EditingAgent)
  -> Brand Ranking (BrandRouter)
  -> Captions (publish_package)
  -> Thumbnail generation
  -> Quality Control (QualityControlAgent)
  -> Publishing Queue
  -> Publisher (YouTube API / Playwright)
  -> Analytics recording
  -> Learning Engine update
  -> Next Campaign
```

## Brand Registry

`BrandRegistry.json` is the single source of truth. Five active brands, all owned by one master Gmail (`abdelshafyclapps@gmail.com`) as Google brand accounts:

| Brand | Handle | Theme |
|---|---|---|
| Don't Watch This | @DONTWATCHTHIS1 | Dark stories, mystery, suspense |
| Goal Machinez | @Goalmachinez | Football/soccer highlights |
| Cute Dosage | @CuteDosage | Cute, wholesome, family |
| ClippingFactoryMBM | @ClippingFactoryMBM | Build-in-public, MBM ops |
| Twists Revealed | @TwistsRevealed | Plot twists, reveals, suspense |

Adding a brand: add entry to `tools/gen_brand_configs.py` BRANDS list, rerun it, add BrandRegistry + ChannelRegistry entries, add CampaignRouter rule if needed. No framework code changes.

## Directory Structure

```
MBM-Social/
  BrandRegistry.json          - Brand metadata (source of truth)
  ChannelRegistry.json        - YouTube channel auth + ownership
  CampaignRouter.json         - Brand-fit scoring + routing rules + campaign profiles + client mode
  ChannelMetrics.json         - Per-channel rolling analytics + KPI tracking
  MasterAccount.json          - Master Gmail + auth policy
  LearningMemory.json         - Learning engine memory (auto-generated)
  Brands/                     - Per-brand config (one folder per brand)
    <brand>/
      brand.yaml              - Identity, voice, keywords
      sources.yaml            - Long-form content sources
      posting_schedule.yaml   - Cadence, time windows, timezone
      kpis.yaml               - Targets per channel
      style_guide.md          - Voice, visual, hook style
      thumbnail_rules.md      - Thumbnail overlay rules
      title_rules.md          - Title format rules
      caption_rules.md        - Caption format rules
  BrandTemplates/
    publish_package.schema.json - JSON schema for publish-ready packages
  mbm_social/                 - Python package
    __init__.py               - Module exports
    brand_config.py           - Registry + brand YAML loader
    brand_router.py           - Brand-fit scoring and channel selection
    model_registry.py         - Local LLM routing (Ollama)
    pipeline.py               - End-to-end publish flow (manual trigger)
    autonomous_runtime.py     - Full autonomous campaign lifecycle
    learning_engine.py        - Self-improving analytics memory
    night_operations.py       - Automated overnight missions
    publish_package.py        - Build brand-aware title/desc/hashtags/thumb
    publisher.py              - Playwright YouTube Studio publisher
    youtube_api_publisher.py  - YouTube Data API v3 publisher
    social_daemon.py          - Background publish daemon
    prompt_evaluator.py       - Content quality scoring
    prompt_router.py          - Content prompt routing
  tools/
    gen_brand_configs.py      - Brand config generator
  publish_queue/              - Output directory for publish-ready packages
  night_reports/              - Night operations reports (auto-generated)
  backups/                    - Config backups (auto-generated)
```

## Campaign Profiles

`CampaignRouter.json` supports unlimited campaign profiles:

| Profile | Description | Target Brands |
|---|---|---|
| dark_stories | Mystery, true crime lite, paranormal | dontwatchthis, twistsrevealed |
| football_highlights | Football/soccer highlights, goals | goalmachinez |
| cute_wholesome | Cute animals, babies, family | cutedosage |
| plot_twists | Plot twists, reveals, shocking endings | twistsrevealed |
| tech_automation | AI, automation, build-in-public | clippingfactorymbm |
| movie_recaps | Movie/TV recaps, analysis | dontwatchthis, twistsrevealed |
| business_finance | Business insights, finance tips | clippingfactorymbm |
| history_documentary | Historical events, documentary | dontwatchthis |
| islamic_content | Islamic reminders, spiritual | cutedosage |
| construction_real_estate | Construction, property development | clippingfactorymbm |

## Client Mode

Two execution modes via `CampaignRouter.json > client_mode`:

- **Internal** — MBM owned brands, auto-publish, quality gate 0.65
- **External** — Client campaigns, approval required, quality gate 0.70, per-clip billing

Same pipeline. Different configuration.

## Publishing Pipeline

1. **Source** — ContentAcquisitionAgent pulls approved long-form content.
2. **Analysis + Clip** — ContentAnalysis, ClipGeneration, Editing, QualityControl agents produce a clip.
3. **Brand Router** — `brand_router.route_clip()` scores clip against every active brand using weighted criteria (topic match 40%, hook style 20%, visual fit 15%, keyword overlap 15%, past performance 10%). Routing uses local embeddings (nomic-embed-text) + optional LLM classification. Scores below 0.65 require manual review.
4. **Package** — `publish_package.build_package()` generates brand-aware title, description, hashtags, thumbnail overlay text via local LLMs. Output matches `BrandTemplates/publish_package.schema.json`.
5. **Queue** — Package saved as JSON to `publish_queue/` with status `draft`.
6. **Publish** — YouTube API (preferred) or Playwright automation pushes to YouTube.

All inference is local (Ollama). No data leaves the machine.

## Analytics & KPIs

`ChannelMetrics.json` tracks per-channel rolling 30-day metrics + network KPIs:

- Revenue, RPM, Subscribers, Views, Watch Time, CTR
- Publishing Success Rate, Clip Success Rate, Hook Score
- Campaign ROI, Processing Time, Queue Length, Platform Health

Each brand defines KPIs in `kpis.yaml`: target_views_30d, target_ctr, target_avg_view_pct, target_subs_per_post, priority_metric.

## Learning Engine

`learning_engine.py` tracks:
- Winning hooks, titles, captions, thumbnails, posting times, sources
- Per-brand and per-profile performance
- Auto-updates CampaignRouter.json scoring weights based on actual performance

Data stored in `LearningMemory.json` — no database writes for learning.

## Production Revision (M-022)

The pipeline was revised (2026-08-25) to eliminate fabricated outputs and add
operational resilience. Key facts:

- **Canonical runtime:** `mbm_social/campaign_runner.py::run_campaign` is the single
  entry point for a resilient campaign. It wires every `autonomous_runtime` stage,
  emits an append-only event log (`event_bus.py`), writes checkpoints for resume
  (`checkpoint.py`), enforces the rights gate (`source_registry.py`) and quality gate
  (`quality_gate_policy.py`), and routes publishes through an honest platform matrix
  (`platform_registry.py`) with a circuit breaker + dead-letter queue
  (`circuit_breaker.py`).
- **Honest platform status:** YouTube = fully supported; Instagram/TikTok =
  MANUAL_REQUIRED (Playwright, no auto-verify); LinkedIn/X = BLOCKED (no publisher).
  Blocked/manual packages are preserved in `publish_queue/dead_letter/` and a GitHub
  issue is opened when a repo is configured (`github_app.py`). No platform is ever
  marked Published without a real success id.
- **Real inference:** `model_registry.generate()` is Ollama-first (or backend fallback)
  and raises on total failure — it never returns canned JSON.
- **Fake removed:** the old root `mbm_social_autonomous_runtime.py` fabricated analytics
  and is quarantined to `.QUARANTINED`; a delegating shim now uses the real package.
- **Quality gates:** 10 configurable gates (see `quality_gate_policy.DEFAULT_THRESHIERS`);
  failures carry exact reasons (`rights_blocked`, `quality_failed`, `manual_required`,
  `publish_failed`, `publish_blocked`).
- **Client mode:** `client_campaign.py` distinguishes INTERNAL_BRAND vs CLIENT_CAMPAIGN
  with validation. **Websites:** `app_websites.py` generates config-driven static sites.
- **Tested:** `tests/test_m022_modules.py` — 21 hermetic tests (units + E2E resume, quality
  fail, rights block, dead-letter, blocked platform).
- See `Reports/ClippingFactory_Production_Readiness.md` and
  `Reports/Platform_Capability_Matrix.md`.

## Night Operations

`night_operations.py` runs automated overnight missions:
1. Repository Audit — check file integrity
2. Campaign Health Check — queue depth, stuck clips
3. Analytics Collection — aggregate metrics
4. Model Health — Ollama model availability
5. Learning Update — auto-adjust scoring weights
6. Queue Optimization — clean stale drafts
7. Platform Health — session and API checks
8. Executive Report — compile all results
9. Opportunity Scan — discover new campaign profiles
10. Repository Backup — backup critical configs

## Key Commands

```bash
# Regenerate all brand configs from canonical defaults
python tools/gen_brand_configs.py

# Run end-to-end pipeline for a campaign
python -m mbm_social.pipeline

# Run autonomous campaign (full lifecycle)
python -c "from mbm_social.autonomous_runtime import run_autonomous_campaign; print(run_autonomous_campaign('campaign_001', profile_name='dark_stories'))"

# Run night operations
python -m mbm_social.night_operations

# Run the canonical resilient campaign runtime (dry-run by default)
python -c "from mbm_social.campaign_runner import run_campaign, CampaignContext; print(run_campaign(CampaignContext(campaign_id='demo', brand='dontwatchthis', profile='dark_stories'), queue_dir=None))"

# Inspect the honest platform matrix
python -c "from mbm_social.platform_registry import PlatformRegistry as P; print(P.all_capabilities())"

# Evaluate a quality gate
python -c "from mbm_social.quality_gate_policy import GatePolicy; print(GatePolicy().evaluate({'hook_score':0.9,'brand_fit':0.8,'visual_score':0.5},['youtube']))"

# Run learning engine update
python -c "from mbm_social.learning_engine import auto_update_scoring_weights; print(auto_update_scoring_weights())"

# Route an existing clip
python -c "from mbm_social.pipeline import route_existing_clip; print(route_existing_clip('clip_id_here'))"

# Ensure Ollama is running locally with required models
ollama pull qwen2.5-coder:7b qwen2.5-coder:14b nomic-embed-text:latest
```
