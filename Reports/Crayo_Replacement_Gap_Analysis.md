# Crayo Replacement — Gap Analysis (M-023, Phase 9)

Benchmark the MBM-Social clipping capability against a Crayo-class automated
clipping platform. Crayo is treated as a *reference point*, NOT a dependency.
We never clone proprietary code; we extend existing MBM modules or implement the
capability in the correct layer.

Legend: S = Supported/Automated · M = Manual (package produced, human finishes) ·
B = Blocked (no implementation) · L = Local (free) · P = Paid/External.

| Capability | MBM implementation | Provider | Local/Paid | Automation | Remaining gap |
|---|---|---|---|---|---|
| Long-form ingest | `autonomous_runtime.stage_video_acquisition` + `pipeline` | backend agents | L | S | needs authorized source list |
| Transcription | backend `ContentAnalysisAgent` (faster-whisper capable) | local/Ollama | L | S* | wiring into `candidate_pool` is injected, not yet auto |
| Speech/speaker analysis | `viral_intelligence` signals + `audio_gate` | local | L | S | no diarization; single-speaker assumed |
| Visual analysis | `visual_qa`, `video_gate`, `creative_gate` | ffmpeg/local | L | S | face/speaker detection not wired to reframe |
| Large candidate pool (10/25/50/100/250) | `candidate_pool.generate_candidates` | stdlib | L | S | synthetic segment planning; real segmentation injected |
| Hook detection | `viral_intelligence.hook` + `content_rewards.hook_score` | Ollama | L | S | depends on model availability |
| Multi-factor scoring (8 axes) | `candidate_pool` + `viral_intelligence.score_clip` | stdlib | L | S | speech_score/caption_quality are heuristics without real ASR |
| Auto crop / 9:16 / 16:9 / 1:1 | `video_editing` (ffmpeg cmd builder) | ffmpeg | L | S (command) | actual render run deferred to media pipeline |
| Active-speaker / face reframe | `video_editing.choose_reframe_filter` (center fallback) | — | L | M | real detector not integrated (#18) |
| Word-level captions | `video_editing.build_caption_command` | ffmpeg drawtext | L | S (command) | needs word timings from ASR (#19) |
| Title/desc/hashtags/CTA | `content_intelligence` + `publish_package` | Ollama | L | S* | template fallback when model offline |
| Quality control | `quality_gate_policy`, `creative_gate`, `clipping_quality_agent`, `video_gate`, `caption_gate`, `audio_gate` | local | L | S | comprehensive gate set |
| Brand/channel routing | `routing.resolve_destination`, `brand_router`, `routing_decision` | stdlib | L | S | fails closed (manual) when registry incomplete |
| High-volume distribution | `distribution_optimizer` + `adaptive_velocity_agent` | stdlib | L | S | auto-scaling logic present; needs live perf feed |
| Publishing (YT/TikTok/IG/X/LI) | `platform_registry` + `youtube_api_publisher`/`youtube_cdp_publisher`/`shortform_publisher`/`publisher` | API/browser | P | YT=S, IG/TikTok=M, X/LI=B | LinkedIn/X blocked (#20); IG/TikTok manual (#21) |
| Retry/backoff/idempotency/DLQ | `publishing` + `circuit_breaker` + `asset_lineage` | stdlib | L | S | new, tested |
| Analytics | `youtube_analytics`, `content_rewards` ledger | API | P | YT partial | scopes revoked; others absent |
| Revenue attribution | `revenue_attribution` + `content_rewards` | stdlib | L | S | rates UNVERIFIED placeholders (#22) |
| Enterprise Memory / learning | `learning_engine`, `learning_feedback` | local file | L | S | active |
| Night operations | `night_operations` (+revenue_analysis mission) | stdlib | L | S | active |
| Observability | `observability` | stdlib | L | S | metrics aggregator; dashboard wiring pending |
| Rights / safety | `source_registry`, `asset_lineage`, human approval gates | stdlib | L | S | active |

\* Runs fully when Ollama/local models are present; degrades to honest templates
otherwise (never fabricates).

## Verdict
MBM already covers ~70% of a Crayo-class loop through real, non-duplicated
modules. The Crayo-class M-023 work added the missing orchestration +
high-volume + resilience + economics + observability layers and tied them
together in `crayo_engine.run_crayo_loop`. No feature parity is claimed where
credentials or models are absent — those are explicit gaps (#18–#22).
