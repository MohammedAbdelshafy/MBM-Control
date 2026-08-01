# Clipping Factory MCP Server v2.0 — Claude Code Integration

The Clipping Factory exposes **34 MCP tools** covering all agents, pipelines,
queries, infrastructure introspection, and direct service access.

## Quick Start

### 1. Start the system
```bash
docker compose up --build
```

### 2. Verify MCP server is ready
**Windows (PowerShell):**
```powershell
.\verify-mcp-setup.ps1
```

**macOS/Linux (Bash):**
```bash
bash verify-mcp-setup.sh
```

### 3. Configure Claude Code

Merge the MCP server config into your Claude Code settings:

**Option A: Automatic (recommended)**
- Open `claude-mcp-config.json` in this directory
- Copy the `mcpServers` section
- Paste into `~/.claude/settings.json` under the `mcpServers` key

**Option B: Manual**
Edit `~/.claude/settings.json` and add:
```json
{
  "mcpServers": {
    "clipping-factory": {
      "type": "sse",
      "url": "http://localhost:8001/sse"
    }
  }
}
```

### 4. Restart Claude Code
Close and reopen Claude Code. The MCP server should now be connected.

## Available Tools (34 total)

### Agent Control (15 tools)
- **`scan_campaigns(page_id?)`** — Scan Clipping.com for new campaigns
- **`analyze_campaign(campaign_id)`** — Score and analyze a campaign
- **`acquire_content(campaign_id)`** — Download source video
- **`analyze_content(source_content_id)`** — Transcribe and score clips
- **`generate_clips(source_content_id)`** — Cut raw clips
- **`edit_clip(clip_id)`** — Apply post-production
- **`enhance_clip(clip_id)`** — Sharpen, color grade, denoise, upscale
- **`quality_check(clip_id)`** — Automated QC review
- **`deliver_clip(clip_id)`** — Submit to Clipping.com
- **`publish_clip(clip_id, platforms?)`** — Publish to social platforms
- **`system_health()`** — Check all system components
- **`monetization_check()`** — Pipeline health + earnings recovery
- **`multi_platform_deliver(clip_id, platforms?)`** — Deliver to all platforms simultaneously
- **`ingest_leads(source?, date_str?, max_campaigns?)`** — Ingest leads from MBM/Social
- **`editor_quality_check(clip_id, auto_fix?)`** — Professional-grade quality gate
- **`poll_outcomes()`** — Check delivery acceptance/rejection status

### Pipeline Control (5 tools)
- **`run_full_pipeline(campaign_id)`** — End-to-end processing
- **`approve_clip(clip_id, notes?)`** — Manual approval workflow
- **`reject_clip(clip_id, reason?)`** — Manual rejection
- **`run_youtube_pipeline(topic, niche?)`** — Full 10-stage YouTube pipeline
- **`list_pipeline_stages()`** — View pipeline stage order

### Analytics (1 tool)
- **`get_analytics(days?)`** — Performance summary for last N days

### Queries (8 tools)
- **`list_campaigns(status?, limit?)`** — Query campaigns
- **`list_clips(campaign_id?, limit?)`** — Query clips
- **`get_campaign(campaign_id)`** — Full campaign details
- **`list_audit_log(entity_type?, actor?, limit?)`** — Query audit log
- **`list_jobs(status?, task_name?, limit?)`** — Query job records
- **`get_job_status(job_id)`** — Full job details
- **`get_submission(clip_id)`** — Submission details for a clip

### Infrastructure (3 tools)
- **`list_celery_queues()`** — Queue depths across all 9 queues
- **`list_celery_tasks(queue?, limit?)`** — Active/reserved/scheduled tasks
- **`retry_failed_task(task_id)`** — Re-queue failed task from DLQ

### Services (2 tools)
- **`send_telegram(message, category?)`** — Direct Telegram notification
- **`get_storage_stats()`** — MinIO bucket statistics

## Example Usage in Claude Code

```
User: Scan for new campaigns
Claude Code: I'll scan Clipping.com for new campaigns.
[calls scan_campaigns()]
Result: Found 5 new campaigns

User: Check the health of the system
Claude Code: Let me check all system components...
[calls system_health()]
Result: PostgreSQL ✓ Redis ✓ MinIO ✓ Celery workers ✓

User: How many tasks are queued?
Claude Code: Let me check the Celery queue depths...
[calls list_celery_queues()]
Result: campaigns=2, video=1, delivery=0, total=3

User: Run quality check on clip abc-123
Claude Code: I'll run the professional quality gate...
[calls editor_quality_check("abc-123")]
Result: Score 0.91 — visual=0.95, audio=0.88, hook=0.90, platform=1.0

User: Deliver to all platforms
Claude Code: Delivering to Whop, Clipping.com, Vyro, and more...
[calls multi_platform_deliver("abc-123")]
Result: whop=success, clipping_com=success, vyro=pending
```

## Troubleshooting

### MCP server not connecting

**Health endpoint:**
```bash
curl http://localhost:8001/health
```

**Check Docker logs:**
```bash
docker logs clipping-factory-mcp-server-1
```

**Run startup validation:**
```bash
python backend/app/mcp_server.py --check
```

### Tool calls failing

**Check system health:**
```
Claude Code: Check system health
[calls system_health()]
```

**Check Celery queues:**
```
Claude Code: Check queue depths
[calls list_celery_queues()]
```

**Check database:**
```bash
docker exec clipping-factory-postgres-1 psql -U clipuser -d clipping_factory -c "SELECT COUNT(*) FROM campaigns;"
```

### Port 8001 already in use

Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8002:8001"  # Use 8002 instead
```

Then update `claude-mcp-config.json`:
```json
"url": "http://localhost:8002/sse"
```

## Architecture

```
Claude Code / Cursor / Any MCP Client
         ↓ (SSE over HTTP)
MCP Server v2.0 (fastmcp) — Port 8001
         ↓
┌────────────────────────────────────────┐
│  15 Agents         │  5 Pipeline Tools │
│  8 Query Tools     │  3 Infra Tools    │
│  2 Service Tools   │  1 Analytics Tool │
└────────────────────────────────────────┘
         ↓
┌──────────┬──────────┬──────────┐
│ Postgres │  Redis   │  MinIO   │
│ (data)   │ (queues) │ (storage)│
└──────────┴──────────┴──────────┘
         ↓
Celery Workers (3 pools, 8 queues)
```

## Files

- `app/mcp_server.py` — MCP server implementation (34 tools)
- `docker-compose.yml` — MCP service definition with /health endpoint
- `claude-mcp-config.json` — Claude Code MCP config
- `verify-mcp-setup.ps1` — Windows verification script
- `verify-mcp-setup.sh` — Unix/Mac verification script
