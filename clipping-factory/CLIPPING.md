# CLIPPING.md — Clipping Factory

## Pipeline Overview

Python/FastAPI video clipping pipeline with Celery task queue. AI assistants connect via an MCP server (fastmcp, SSE, port 8001) and orchestrate 9+ agents through `backend/app/agents/`. The pipeline stages are: Discovery -> Acquisition -> Analysis -> Production -> Quality -> Delivery -> Publishing.

PostgreSQL for state, Redis for broker/result backend/caching, MinIO for video/blob storage. Celery workers consume from named queues (campaigns, acquisition, analysis, video, delivery, publish, health, default, dlq).

Key source files:
- `backend/app/main.py` — FastAPI app factory
- `backend/app/core/celery_app.py` — Celery app, queues, routing, beat schedule
- `backend/app/core/config.py` — All settings from env vars
- `backend/app/api/routes/` — Route modules

## Docker Stack

| Container | Role | Port(s) |
|---|---|---|
| `postgres` | PostgreSQL 16 (primary DB) | 5432 |
| `redis` | Redis 7 (cache + broker) | 6379 |
| `minio` | S3-compatible object storage | 9000, 9001 |
| `api` | FastAPI Uvicorn server | 8000 |
| `worker-campaigns` | Celery worker (campaigns,default queues) | — |
| `worker-video` | Celery worker (acquisition,analysis,video queues) | — |
| `worker-delivery` | Celery worker (delivery,publish,health queues) | — |
| `celery-beat` | Celery beat scheduler | — |
| `mcp-server` | fastmcp SSE server (AI assistant gateway) | 8001 |
| `frontend` | Next.js admin dashboard | 3000 |
| `prometheus` | Metrics collection | 9090 |
| `grafana` | Dashboards | 3001 |

Defined in `docker-compose.yml`. Run with: `docker compose up --build`

## Agent Roster

All agents in `backend/app/agents/`:

| Agent | File | Role |
|---|---|---|
| Campaign Hunter | `campaign_hunter.py` | Scans Clipping.com for new campaigns |
| Campaign Intelligence | `campaign_intelligence.py` | Scores and analyzes campaigns |
| Content Acquisition | `content_acquisition.py` | Downloads video/audio source content |
| Content Analysis | `content_analysis.py` | Transcribes and analyzes clips |
| Clip Generation | `clip_generation.py` | Cuts raw clips to specifications |
| Editing Agent | `editing_agent.py` | Applies post-production effects |
| Enhancement Agent | `enhancement_agent.py` | FFmpeg filter pipeline (sharpen, color, denoise, upscale) |
| Quality Control | `quality_control.py` | Automated quality review |
| Clip Editor Quality | `clip_editor_quality.py` | Editor-level quality checks |
| Delivery Agent | `delivery_agent.py` | Submits clips to Clipping.com |
| Multi-Platform Delivery | `multi_platform_delivery.py` | Distributes clips to multiple platforms |
| Publishing Agent | `publishing.py` | Manages social publishing workflows |
| Health Monitor | `health_monitor.py` | System health checks |
| Lead Ingestion | `lead_ingestion.py` | Ingests leads from MBM packs |
| Monetization Agent | `monetization_agent.py` | Revenue monitoring and alerts |

Base class: `base_agent.py`

## Celery Beat Schedule

Defined in `backend/app/core/celery_app.py`:

| Task | Schedule | Queue |
|---|---|---|
| `campaign_tasks.scan_for_campaigns` | `clipping_scan_interval_seconds` (default 300s) | campaigns |
| `health_tasks.run_health_check` | 60s | health |
| `video_tasks.cleanup_temp_files` | 3600s (1h) | default |
| `video_tasks.requeue_stuck_clips` | 600s (10m) | default |
| `ingestion_tasks.ingest_lead_packs` | 21600s (6h) | campaigns |
| `ingestion_tasks.ingest_mbm_social_leads` | 43200s (12h) | campaigns |
| `monetization_tasks.run_monetization_check` | `monetization_check_interval_seconds` (default 600s) | health |
| `analytics_tasks.sync_post_metrics` | 3600s (1h) | default |

Workers map to queues: `worker-campaigns` (campaigns,default), `worker-video` (acquisition,analysis,video), `worker-delivery` (delivery,publish,health).

## Key Commands

From root `package.json`:

```bash
npm run clip:server           # Start FastAPI dev server (port 8000)
npm run clip:build            # Run build_one_clip.py
npm run clip:seed             # Run seed_campaigns.py
npm run clip:monitor          # Run MonetizationAgent
npm run clip:quality          # Verify quality tooling (edge-tts, whisperx)
npm run clip:analytics        # Run sync_post_metrics
npm run clip:report           # Print analytics report
npm run clip:multi-deliver    # Multi-platform delivery for a clip_id
docker compose up --build     # Full stack (all containers)
```

## API Routes Overview

All routes under `/api/v1/` (prefix defined in `backend/app/main.py`). Auth via basic auth or session.

| Prefix | File | Purpose |
|---|---|---|
| `/health` | `routes/health.py` | System status, queue depths, recent jobs, SSE stream |
| `/campaigns` | `routes/campaigns.py` | CRUD, pause/resume/reprocess |
| `/clips` | `routes/clips.py` | List, download URL, approve/reject |
| `/commands` | `routes/commands.py` | Natural-language command execution |
| `/publish` | `routes/publishing.py` | Publish clips to social platforms |
| `/analytics` | `routes/analytics.py` | Dashboard summary, revenue chart, audit log |
| `/transcribe` | `routes/transcribe.py` | Speech-to-text via local Whisper |
| `/thumbnail` | `routes/thumbnail.py` | Generate thumbnail prompt + optional image |
| `/script` | `routes/script.py` | Generate YouTube script + hook |
| `/research` | `routes/research.py` | Trend-aware topic research |
| `/workflows` | `routes/workflows.py` | Langflow flow listing and execution |
| `/models` | `routes/models.py` | Ollama model availability |
| `/pages` | `routes/pages.py` | Clipping.com account/page management |
| `/mbm` | `routes/mbm.py` | MBM lead data, runs, outputs, ingest trigger |

## Output Contract

Every agent run and workflow step emits:

```
status: success | failure | skipped
inputs: { ... }
outputs: { ... }
errors: [ ... ]
next_action: string
owner: "system" | "human"
timestamp: ISO8601
```
