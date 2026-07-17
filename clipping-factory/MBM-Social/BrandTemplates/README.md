# BrandTemplates

Reusable templates for the MBM-Social multi-channel engine.

- `publish_package.schema.json` — schema for the publish-ready package that
  `mbm_social.publish_package` emits for every clip. This is the contract
  between the clipping pipeline and the YouTube publisher.

A publish-ready package always contains, per brand:

| field | source |
|---|---|
| `title` | local LLM, brand `title_rules.md`, `BrandRouter` selection |
| `description` | local LLM, brand `caption_rules.md` |
| `hashtags` | local LLM + brand `keywords` |
| `thumbnail_prompt` / `thumbnail_text` | local LLM, brand `thumbnail_rules.md` |
| `hook_text` | clipping-factory `EditingAgent` A/B hook variants |
| `publish_time` | brand `posting_schedule.yaml` windows |
| `target_channel` | `ChannelRegistry.json` (brand -> channel id) |
| `source_reference` | originating long-form source |
| `clip_file_path` | clipping-factory `Clip.storage_key` |
| `brand_fit_score` | `BrandRouter` scoring |
| `quality_gate` | clipping-factory `QualityControlAgent` |

To add a brand: drop a brand folder (see `tools/gen_brand_configs.py`) and a
`ChannelRegistry` + `CampaignRouter` entry. No engine code changes.
