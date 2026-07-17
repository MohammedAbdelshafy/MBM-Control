# SOCIAL.md -- MBM Social

Brand management, publishing, and analytics for the MBM multi-channel YouTube network.

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
  BrandRegistry.json        - Brand metadata (source of truth)
  ChannelRegistry.json      - YouTube channel auth + ownership
  CampaignRouter.json       - Brand-fit scoring weights + routing rules
  ChannelMetrics.json       - Per-channel rolling analytics (zeroed until first publish)
  MasterAccount.json        - Master Gmail + auth policy
  Brands/                   - Per-brand config (one folder per brand)
    <brand>/
      brand.yaml            - Identity, voice, keywords
      sources.yaml          - Long-form content sources
      posting_schedule.yaml - Cadence, time windows, timezone
      kpis.yaml             - Targets per channel
      style_guide.md        - Voice, visual, hook style
      thumbnail_rules.md    - Thumbnail overlay rules
      title_rules.md        - Title format rules
      caption_rules.md      - Caption format rules
  BrandTemplates/
    publish_package.schema.json - JSON schema for publish-ready packages
  mbm_social/               - Python package
    brand_config.py         - Registry + brand YAML loader
    brand_router.py         - Brand-fit scoring and channel selection
    model_registry.py       - Local LLM routing (Ollama, all local)
    pipeline.py             - End-to-end publish flow
    publish_package.py      - Build brand-aware title/desc/hashtags/thumb text
  tools/
    gen_brand_configs.py    - Brand config generator (canonical defaults)
  publish_queue/            - Output directory for publish-ready packages
```

## Publishing Pipeline

1. **Source** -- ContentAcquisitionAgent pulls approved long-form content.
2. **Analysis + Clip** -- ContentAnalysis, ClipGeneration, Editing, QualityControl agents produce a clip.
3. **Brand Router** -- `brand_router.route_clip()` scores clip against every active brand using weighted criteria (topic match 40%, hook style 20%, visual fit 15%, keyword overlap 15%, past performance 10%). Routing uses local embeddings (nomic-embed-text) + optional LLM classification (qwen2.5-coder). Scores below 0.65 require manual review.
4. **Package** -- `publish_package.build_package()` generates brand-aware title, description, hashtags, thumbnail overlay text via local LLMs. Output matches `BrandTemplates/publish_package.schema.json`.
5. **Queue** -- Package saved as JSON to `publish_queue/` with status `draft`.
6. **Publish** -- (TBD) Publisher pushes to YouTube via session auth.

All inference is local (Ollama). No data leaves the machine. Model routing is data-driven per task, not hardcoded.

## Analytics & Metrics

`ChannelMetrics.json` tracks per-channel rolling 30-day metrics, zeroed until first publish:
- views_30d, ctr, avg_view_pct, subs_gain, posts
- Network-level rollup

Each brand defines KPIs in `kpis.yaml`: target_views_30d, target_ctr, target_avg_view_pct, target_subs_per_post, priority_metric. Analytics module (TBD) will pull from YouTube API + clipping-factory SocialPost data.

## Key Commands

```bash
# Regenerate all brand configs from canonical defaults
python tools/gen_brand_configs.py

# Run end-to-end pipeline for a campaign
# (via pipeline.py run_end_to_end)

# Route an already-built clip
# (via pipeline.py route_existing_clip)

# Ensure Ollama is running locally with required models
ollama pull qwen2.5-coder:7b qwen2.5-coder:14b nomic-embed-text:latest
```
