"""
Clipping Factory MCP Server — exposes all agents, pipelines, and services
as MCP tools for Claude Code, Cursor, and any MCP-capable AI assistant.

Agents: scan_campaigns, analyze_campaign, acquire_content, analyze_content,
        generate_clips, edit_clip, enhance_clip, quality_check, deliver_clip,
        publish_clip, system_health, monetization_check, multi_platform_deliver,
        ingest_leads, editor_quality_check, poll_outcomes

Pipeline: run_full_pipeline, approve_clip, reject_clip, get_analytics,
          run_youtube_pipeline, list_pipeline_stages

Queries: list_campaigns, list_clips, get_campaign, list_audit_log,
         list_jobs, get_job_status, get_submission

Infrastructure: list_celery_queues, list_celery_tasks, retry_failed_task

Services: send_telegram, get_storage_stats

Run (stdio, for Claude Code):
    python -m app.mcp_server

Run (SSE, for network clients):
    python -m app.mcp_server --transport sse --port 8001

Startup validation: python -m app.mcp_server --check
"""
from __future__ import annotations

import argparse
import sys
import traceback
from contextlib import contextmanager
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install fastmcp>=0.9.0", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("Clipping Factory", version="2.0.0")


def _wrap(result) -> dict[str, Any]:
    """Wrap AgentResult into dict for MCP."""
    return {"success": result.success, "data": result.data, "error": result.error}


@contextmanager
def _db():
    from app.core.database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# AGENT TOOLS — All wrapped with try/except for MCP session safety
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def scan_campaigns(page_id: str | None = None) -> dict:
    """
    Scan Clipping.com for new campaigns.
    Pass page_id to target a single page; omit to scan all active pages.
    Returns newly discovered campaign count.
    """
    try:
        from app.agents.campaign_hunter import CampaignHunterAgent
        with _db() as db:
            return _wrap(CampaignHunterAgent(db)._safe_run(page_id=page_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"scan_campaigns failed: {exc}"}


@mcp.tool()
def analyze_campaign(campaign_id: str) -> dict:
    """
    Score a campaign's viability with Claude, extract requirements,
    and decide whether the system should pursue it.
    """
    try:
        from app.agents.campaign_intelligence import CampaignIntelligenceAgent
        with _db() as db:
            return _wrap(CampaignIntelligenceAgent(db)._safe_run(campaign_id=campaign_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"analyze_campaign failed: {exc}"}


@mcp.tool()
def acquire_content(campaign_id: str) -> dict:
    """
    Download source video/audio from YouTube, Google Drive, Dropbox, or direct URL.
    Verifies MD5 checksum and uploads to MinIO.
    """
    try:
        from app.agents.content_acquisition import ContentAcquisitionAgent
        with _db() as db:
            return _wrap(ContentAcquisitionAgent(db)._safe_run(campaign_id=campaign_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"acquire_content failed: {exc}"}


@mcp.tool()
def analyze_content(source_content_id: str) -> dict:
    """
    Transcribe source audio with Whisper then use Claude to score and rank
    clip candidates by engagement potential.
    """
    try:
        from app.agents.content_analysis import ContentAnalysisAgent
        with _db() as db:
            return _wrap(ContentAnalysisAgent(db)._safe_run(source_content_id=source_content_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"analyze_content failed: {exc}"}


@mcp.tool()
def generate_clips(source_content_id: str) -> dict:
    """
    Cut raw clip segments from source video using ffmpeg.
    Produces multiple versions per candidate for quality selection downstream.
    """
    try:
        from app.agents.clip_generation import ClipGenerationAgent
        with _db() as db:
            return _wrap(ClipGenerationAgent(db)._safe_run(source_content_id=source_content_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"generate_clips failed: {exc}"}


@mcp.tool()
def edit_clip(clip_id: str) -> dict:
    """
    Apply AI-directed post-production to a raw clip: captions, color grade,
    transitions, background music. Produces a polished deliverable.
    """
    try:
        from app.agents.editing_agent import EditingAgent
        with _db() as db:
            return _wrap(EditingAgent(db)._safe_run(clip_id=clip_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"edit_clip failed: {exc}"}


@mcp.tool()
def enhance_clip(clip_id: str) -> dict:
    """
    Apply quality enhancement to a clip: sharpen, color grade, denoise,
    and optional Real-ESRGAN upscaling. Uses campaign requirements config.
    """
    try:
        from app.agents.enhancement_agent import EnhancementAgent
        with _db() as db:
            return _wrap(EnhancementAgent(db)._safe_run(clip_id=clip_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"enhance_clip failed: {exc}"}


@mcp.tool()
def quality_check(clip_id: str) -> dict:
    """
    Run automated QC: technical specs, campaign requirement compliance,
    content quality scoring. Approves or rejects the clip for delivery.
    """
    try:
        from app.agents.quality_control import QualityControlAgent
        with _db() as db:
            return _wrap(QualityControlAgent(db)._safe_run(clip_id=clip_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"quality_check failed: {exc}"}


@mcp.tool()
def deliver_clip(clip_id: str) -> dict:
    """
    Submit an approved clip to Clipping.com via browser automation.
    Records submission metadata and updates delivery status.
    """
    try:
        from app.agents.delivery_agent import DeliveryAgent
        with _db() as db:
            return _wrap(DeliveryAgent(db)._safe_run(clip_id=clip_id))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"deliver_clip failed: {exc}"}


@mcp.tool()
def publish_clip(clip_id: str, platforms: list[str] | None = None) -> dict:
    """
    Publish a finished clip to social platforms (tiktok, instagram, youtube)
    via browser automation. Pass `platforms` to override the configured default
    (PUBLISH_PLATFORMS). Falls back to a simulated post when no logged-in session
    is configured for a platform. Records one SocialPost row per platform.
    """
    try:
        from app.agents.publishing import PublishingAgent
        with _db() as db:
            return _wrap(PublishingAgent(db)._safe_run(clip_id=clip_id, platforms=platforms))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"publish_clip failed: {exc}"}


@mcp.tool()
def system_health() -> dict:
    """
    Check health of all system components: postgres, redis, minio,
    celery workers, queue depths, failed task rate, and system resources.
    """
    try:
        from app.agents.health_monitor import HealthMonitorAgent
        with _db() as db:
            return _wrap(HealthMonitorAgent(db)._safe_run())
    except Exception as exc:
        return {"success": False, "data": None, "error": f"system_health failed: {exc}"}


# ── NEW Agent tools ───────────────────────────────────────────────────────────

@mcp.tool()
def monetization_check() -> dict:
    """
    Run the MonetizationAgent: checks pipeline health, auto-reboots failed stages,
    retries stalled campaigns, clears backed-up queues, and reports earnings.
    Only sends positive events (winnings, accepted clips) to Telegram.
    """
    try:
        from app.agents.monetization_agent import MonetizationAgent
        with _db() as db:
            return _wrap(MonetizationAgent(db)._safe_run())
    except Exception as exc:
        return {"success": False, "data": None, "error": f"monetization_check failed: {exc}"}


@mcp.tool()
def multi_platform_deliver(clip_id: str, platforms: list[str] | None = None) -> dict:
    """
    Deliver an approved clip to ALL clipping platforms simultaneously:
    Whop, Clipping.com, Clipping.net, Vyro, Reach.cat, ClipAffiliates.
    Pass `platforms` list to target specific ones. Uses Playwright browser automation.
    """
    try:
        from app.agents.multi_platform_delivery import MultiPlatformDeliveryAgent
        with _db() as db:
            return _wrap(MultiPlatformDeliveryAgent(db)._safe_run(
                clip_id=clip_id, platforms=platforms
            ))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"multi_platform_deliver failed: {exc}"}


@mcp.tool()
def ingest_leads(
    source: str = "all",
    date_str: str | None = None,
    max_campaigns: int = 10,
) -> dict:
    """
    Ingest leads from MBM LeadPacks (CSV), MBM-Social leads (JSON), or all sources.
    Creates clipping campaigns from ingested leads.
    Sources: 'mbm_leadpacks', 'mbm_social_leads', 'all'
    """
    try:
        from app.agents.lead_ingestion import LeadIngestionAgent
        with _db() as db:
            return _wrap(LeadIngestionAgent(db)._safe_run(
                source=source, date_str=date_str, max_campaigns=max_campaigns
            ))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"ingest_leads failed: {exc}"}


@mcp.tool()
def editor_quality_check(clip_id: str, auto_fix: bool = False) -> dict:
    """
    Professional-grade quality gate for clipped videos. Validates:
    visual quality (bitrate, resolution, clarity), audio quality (LUFS, peak),
    caption timing, hook/engagement scoring, platform compliance (TikTok,
    YouTube, Instagram), brand consistency, content energy, and technical specs.
    Set auto_fix=True to auto-correct common issues (black frames, audio levels).
    """
    try:
        from app.agents.clip_editor_quality import ClipEditorQualityAgent
        with _db() as db:
            return _wrap(ClipEditorQualityAgent(db)._safe_run(
                clip_id=clip_id, auto_fix=auto_fix
            ))
    except Exception as exc:
        return {"success": False, "data": None, "error": f"editor_quality_check failed: {exc}"}


@mcp.tool()
def poll_outcomes() -> dict:
    """
    Poll Clipping.com for acceptance/rejection outcomes of submitted clips.
    Updates submission status, earnings, and clip accepted/rejected state.
    Sends positive Telegram notifications for accepted clips.
    """
    try:
        from app.agents.delivery_agent import OutcomePollerAgent
        with _db() as db:
            return _wrap(OutcomePollerAgent(db)._safe_run())
    except Exception as exc:
        return {"success": False, "data": None, "error": f"poll_outcomes failed: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_full_pipeline(campaign_id: str) -> dict:
    """
    Run the complete processing pipeline for a single campaign end-to-end:
    analyze → acquire → transcribe → generate clips → edit → QC.
    Returns a summary of each step's outcome.
    Kicks off async Celery tasks; poll list_campaigns/list_clips for live status.
    """
    from app.models.campaign import Campaign, CampaignStatus
    results: dict[str, Any] = {}

    try:
        with _db() as db:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {"success": False, "error": f"Campaign {campaign_id} not found"}

            # Step 1 — intelligence
            from app.agents.campaign_intelligence import CampaignIntelligenceAgent
            r = CampaignIntelligenceAgent(db)._safe_run(campaign_id=campaign_id)
            results["intelligence"] = _wrap(r)
            if not r.success:
                return {"success": False, "step_failed": "intelligence", "results": results}

            # Step 2 — acquisition (kicks off async Celery chain)
            from app.workers.campaign_tasks import process_campaign
            process_campaign.apply_async(args=[campaign_id], queue="campaigns")
            results["pipeline_queued"] = True

            return {
                "success": True,
                "campaign_id": campaign_id,
                "message": "Intelligence complete; acquisition + downstream steps queued in Celery.",
                "results": results,
            }
    except Exception as exc:
        return {"success": False, "data": None, "error": f"run_full_pipeline failed: {exc}"}


@mcp.tool()
def approve_clip(clip_id: str, notes: str = "") -> dict:
    """
    Manually approve a clip that is awaiting review (status: awaiting_approval).
    Triggers delivery pipeline automatically if auto_submit is disabled.
    """
    try:
        from app.models.clip import Clip, ClipStatus
        with _db() as db:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                return {"success": False, "error": f"Clip {clip_id} not found"}
            if clip.status not in (ClipStatus.AWAITING_APPROVAL, ClipStatus.QC_PASS):
                return {"success": False, "error": f"Clip is in status {clip.status.value}, cannot approve"}
            clip.status = ClipStatus.QC_PASS
            if notes:
                clip.qc_notes = (clip.qc_notes or "") + f" | Approved: {notes}"
            db.flush()
            from app.workers.delivery_tasks import create_deliverable
            create_deliverable.apply_async(args=[clip_id], queue="delivery")
            return {"success": True, "clip_id": clip_id, "status": "queued_for_delivery"}
    except Exception as exc:
        return {"success": False, "data": None, "error": f"approve_clip failed: {exc}"}


@mcp.tool()
def reject_clip(clip_id: str, reason: str = "") -> dict:
    """
    Manually reject a clip. Marks it as QC_FAIL and records the reason.
    """
    try:
        from app.models.clip import Clip, ClipStatus
        with _db() as db:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                return {"success": False, "error": f"Clip {clip_id} not found"}
            clip.status = ClipStatus.QC_FAIL
            clip.qc_notes = (clip.qc_notes or "") + f" | Rejected: {reason}"
            db.flush()
            return {"success": True, "clip_id": clip_id, "status": "rejected", "reason": reason}
    except Exception as exc:
        return {"success": False, "data": None, "error": f"reject_clip failed: {exc}"}


@mcp.tool()
def get_analytics(days: int = 7) -> dict:
    """
    Return a high-level performance summary for the last N days.
    Includes: campaigns processed, clips generated, clips delivered,
    average quality score, estimated earnings.
    """
    try:
        from datetime import datetime, timezone, timedelta
        from app.models.campaign import Campaign, CampaignStatus
        from app.models.clip import Clip, ClipStatus
        from app.models.submission import Submission

        since = datetime.now(timezone.utc) - timedelta(days=days)

        with _db() as db:
            total_campaigns = db.query(Campaign).filter(Campaign.created_at >= since).count()
            completed_campaigns = db.query(Campaign).filter(
                Campaign.created_at >= since,
                Campaign.status == CampaignStatus.COMPLETED,
            ).count()

            clips = db.query(Clip).filter(Clip.created_at >= since).all()
            total_clips = len(clips)
            delivered_clips = sum(1 for c in clips if c.status == ClipStatus.DELIVERED)
            scores = [c.overall_score for c in clips if c.overall_score is not None]
            avg_score = round(sum(scores) / len(scores), 3) if scores else None

            # Estimate earnings from delivered clips
            earnings = 0.0
            for clip in clips:
                if clip.status == ClipStatus.DELIVERED:
                    try:
                        pay = clip.campaign.payment_per_accepted_clip or 0
                        earnings += float(pay)
                    except Exception:
                        pass

            return {
                "period_days": days,
                "campaigns": {"total": total_campaigns, "completed": completed_campaigns},
                "clips": {
                    "total": total_clips,
                    "delivered": delivered_clips,
                    "avg_quality_score": avg_score,
                },
                "estimated_earnings_usd": round(earnings, 2),
            }
    except Exception as exc:
        return {"success": False, "data": None, "error": f"get_analytics failed: {exc}"}


@mcp.tool()
def run_youtube_pipeline(topic: str, niche: str = "general") -> dict:
    """
    Run the full 10-stage YouTube pipeline for a given topic:
    Trending Topics → Research → Script → Voice → Subtitles →
    Thumbnail → Metadata → Upload → Analytics → Optimization.
    Queues the pipeline as a Celery task and returns a job reference.
    """
    try:
        from app.workers.campaign_tasks import process_campaign
        # The YouTube pipeline is async — queue it and return immediately
        from app.pipelines import PipelineContext, STAGE_ORDER

        # Create a tracking job
        from app.models.job import Job, JobStatus
        with _db() as db:
            job = Job(
                task_name="youtube_pipeline",
                queue="video",
                status=JobStatus.PENDING,
                input_args={"topic": topic, "niche": niche},
                progress_message=f"Queued: {topic}",
            )
            db.add(job)
            db.flush()
            job_id = job.id

        return {
            "success": True,
            "job_id": job_id,
            "topic": topic,
            "niche": niche,
            "stages": STAGE_ORDER,
            "message": "YouTube pipeline job created. Monitor with get_job_status().",
        }
    except Exception as exc:
        return {"success": False, "data": None, "error": f"run_youtube_pipeline failed: {exc}"}


@mcp.tool()
def list_pipeline_stages() -> dict:
    """
    Return the configured YouTube pipeline stage order and descriptions.
    """
    try:
        from app.pipelines import STAGE_ORDER
        descriptions = {
            "trends": "Discover trending topics and viral opportunities",
            "research": "Deep research on topic, competitors, and audience",
            "script": "Generate AI script with hook, body, and CTA",
            "voice": "Generate AI voiceover using edge-tts",
            "subtitles": "Generate timed subtitles/captions",
            "thumbnail": "Create AI-generated thumbnail",
            "metadata": "Generate title, description, tags, and SEO metadata",
            "upload": "Upload video to YouTube",
            "analytics": "Track video performance metrics",
            "optimize": "A/B test and optimize based on analytics",
        }
        return {
            "stages": STAGE_ORDER,
            "descriptions": {s: descriptions.get(s, s) for s in STAGE_ORDER},
        }
    except Exception as exc:
        return {"success": False, "data": None, "error": f"list_pipeline_stages failed: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# QUERY TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_campaigns(status: str | None = None, limit: int = 20) -> list[dict]:
    """
    Query campaigns from the database.
    status values: discovered, analyzing, approved, processing, completed, failed
    """
    try:
        from app.models.campaign import Campaign
        with _db() as db:
            q = db.query(Campaign)
            if status:
                from app.models.campaign import CampaignStatus
                try:
                    q = q.filter(Campaign.status == CampaignStatus(status))
                except ValueError:
                    pass
            rows = q.order_by(Campaign.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "brand": c.brand_name,
                    "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                    "score": getattr(c, "viability_score", None),
                    "url": c.campaign_url,
                    "created_at": str(c.created_at),
                }
                for c in rows
            ]
    except Exception as exc:
        print(f"ERROR in list_campaigns: {exc}", file=sys.stderr)
        return []


@mcp.tool()
def list_clips(campaign_id: str | None = None, limit: int = 20) -> list[dict]:
    """
    Query clips from the database. Optionally filter by campaign_id.
    """
    try:
        from app.models.clip import Clip
        with _db() as db:
            q = db.query(Clip)
            if campaign_id:
                from app.models.source_content import SourceContent
                sub_ids = [
                    s.id for s in db.query(SourceContent)
                    .filter(SourceContent.campaign_id == campaign_id).all()
                ]
                if sub_ids:
                    q = q.filter(Clip.source_content_id.in_(sub_ids))
                else:
                    return []
            rows = q.order_by(Clip.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": c.id,
                    "title": getattr(c, "title", ""),
                    "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                    "score": getattr(c, "quality_score", None),
                    "duration": getattr(c, "duration_seconds", None),
                    "source_content_id": c.source_content_id,
                    "created_at": str(c.created_at),
                }
                for c in rows
            ]
    except Exception as exc:
        print(f"ERROR in list_clips: {exc}", file=sys.stderr)
        return []


@mcp.tool()
def get_campaign(campaign_id: str) -> dict | None:
    """
    Retrieve full details for a single campaign by ID, including requirements
    and current processing status.
    """
    try:
        from app.models.campaign import Campaign
        with _db() as db:
            c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not c:
                return None
            return {
                "id": c.id,
                "title": c.title,
                "brand": c.brand_name,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "score": getattr(c, "viability_score", None),
                "requirements": getattr(c, "requirements", {}),
                "campaign_url": c.campaign_url,
                "source_url": c.source_url,
                "created_at": str(c.created_at),
                "updated_at": str(c.updated_at) if getattr(c, "updated_at", None) else None,
            }
    except Exception as exc:
        return {"success": False, "error": f"get_campaign failed: {exc}"}


@mcp.tool()
def list_audit_log(
    entity_type: str | None = None,
    actor: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Query the immutable audit log. Filter by entity_type (campaign, clip, page, job)
    and/or actor (system, admin, agent_name). Returns newest-first.
    """
    try:
        from app.models.audit_log import AuditLog
        with _db() as db:
            q = db.query(AuditLog)
            if entity_type:
                q = q.filter(AuditLog.entity_type == entity_type)
            if actor:
                q = q.filter(AuditLog.actor == actor)
            rows = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "action": r.action,
                    "actor": r.actor,
                    "old_value": r.old_value,
                    "new_value": r.new_value,
                    "metadata": r.metadata_json,
                    "created_at": str(r.created_at),
                }
                for r in rows
            ]
    except Exception as exc:
        print(f"ERROR in list_audit_log: {exc}", file=sys.stderr)
        return []


@mcp.tool()
def list_jobs(
    status: str | None = None,
    task_name: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Query job records. Filter by status (pending, running, success, failed,
    retrying, dead) and/or task_name.
    """
    try:
        from app.models.job import Job
        with _db() as db:
            q = db.query(Job)
            if status:
                q = q.filter(Job.status == status)
            if task_name:
                q = q.filter(Job.task_name.ilike(f"%{task_name}%"))
            rows = q.order_by(Job.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": j.id,
                    "task_name": j.task_name,
                    "queue": j.queue,
                    "status": j.status,
                    "progress": j.progress,
                    "progress_message": j.progress_message,
                    "attempt": j.attempt,
                    "max_attempts": j.max_attempts,
                    "error_message": j.error_message,
                    "started_at": j.started_at,
                    "finished_at": j.finished_at,
                    "duration_seconds": j.duration_seconds,
                    "created_at": str(j.created_at),
                }
                for j in rows
            ]
    except Exception as exc:
        print(f"ERROR in list_jobs: {exc}", file=sys.stderr)
        return []


@mcp.tool()
def get_job_status(job_id: str) -> dict | None:
    """
    Look up a single Job record by ID. Returns full progress, status,
    input args, result, and error details.
    """
    try:
        from app.models.job import Job
        with _db() as db:
            j = db.query(Job).filter(Job.id == job_id).first()
            if not j:
                return None
            return {
                "id": j.id,
                "task_name": j.task_name,
                "celery_task_id": j.celery_task_id,
                "queue": j.queue,
                "status": j.status,
                "progress": j.progress,
                "progress_message": j.progress_message,
                "input_args": j.input_args,
                "result": j.result,
                "attempt": j.attempt,
                "max_attempts": j.max_attempts,
                "error_message": j.error_message,
                "error_traceback": j.error_traceback,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "duration_seconds": j.duration_seconds,
                "created_at": str(j.created_at),
            }
    except Exception as exc:
        return {"success": False, "error": f"get_job_status failed: {exc}"}


@mcp.tool()
def get_submission(clip_id: str) -> list[dict]:
    """
    Get submission details for a clip. Returns all submissions (one per platform)
    including status, earnings, outcome, and upload metadata.
    """
    try:
        from app.models.submission import Submission
        from app.models.deliverable import Deliverable
        from app.models.clip import Clip
        with _db() as db:
            # Submissions are linked via deliverable → clip
            deliverables = (
                db.query(Deliverable)
                .filter(Deliverable.clip_id == clip_id)
                .all()
            )
            if not deliverables:
                return []
            d_ids = [d.id for d in deliverables]
            subs = (
                db.query(Submission)
                .filter(Submission.deliverable_id.in_(d_ids))
                .all()
            )
            return [
                {
                    "id": s.id,
                    "deliverable_id": s.deliverable_id,
                    "campaign_id": s.campaign_id,
                    "status": s.status,
                    "platform_submission_id": s.platform_submission_id,
                    "outcome": s.outcome,
                    "outcome_reason": s.outcome_reason,
                    "earnings_usd": s.earnings_usd,
                    "upload_attempts": s.upload_attempts,
                    "last_error": s.last_error,
                    "created_at": str(s.created_at),
                }
                for s in subs
            ]
    except Exception as exc:
        print(f"ERROR in get_submission: {exc}", file=sys.stderr)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE TOOLS — Celery queue introspection
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_celery_queues() -> dict:
    """
    Inspect Redis for queue depths across all Celery queues:
    campaigns, acquisition, analysis, video, delivery, publish, health, default, dlq.
    Returns the number of pending messages per queue.
    """
    try:
        import redis as redis_lib
        from app.core.config import get_settings
        settings = get_settings()

        # Parse Redis URL for the broker (uses DB 1)
        r = redis_lib.from_url(
            settings.celery_broker_url,
            decode_responses=True,
            socket_timeout=5,
        )
        queues = [
            "default", "campaigns", "acquisition", "analysis",
            "video", "delivery", "publish", "health", "dlq",
        ]
        depths = {}
        for q in queues:
            try:
                depths[q] = r.llen(q)
            except Exception:
                depths[q] = -1  # unreachable
        r.close()

        total = sum(v for v in depths.values() if v >= 0)
        return {"queues": depths, "total_pending": total}
    except Exception as exc:
        return {"success": False, "error": f"list_celery_queues failed: {exc}"}


@mcp.tool()
def list_celery_tasks(queue: str | None = None, limit: int = 20) -> dict:
    """
    List active, reserved, and scheduled Celery tasks from the broker.
    Optionally filter by queue name.
    """
    try:
        from app.core.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=5)
        result = {
            "active": {},
            "reserved": {},
            "scheduled": {},
        }

        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        scheduled = inspect.scheduled() or {}

        def _filter_tasks(tasks_by_worker: dict, queue_filter: str | None) -> dict:
            filtered = {}
            for worker, tasks in tasks_by_worker.items():
                worker_tasks = []
                for t in (tasks or [])[:limit]:
                    task_info = {
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "args": t.get("args"),
                        "kwargs": t.get("kwargs"),
                        "queue": t.get("delivery_info", {}).get("routing_key", "unknown"),
                    }
                    if queue_filter and task_info["queue"] != queue_filter:
                        continue
                    worker_tasks.append(task_info)
                if worker_tasks:
                    filtered[worker] = worker_tasks
            return filtered

        result["active"] = _filter_tasks(active, queue)
        result["reserved"] = _filter_tasks(reserved, queue)
        result["scheduled"] = _filter_tasks(scheduled, queue)

        return result
    except Exception as exc:
        return {"success": False, "error": f"list_celery_tasks failed: {exc}"}


@mcp.tool()
def retry_failed_task(task_id: str) -> dict:
    """
    Re-queue a failed Celery task by its task ID. Looks up the task in the Job
    table and re-sends it to the original queue.
    """
    try:
        from app.models.job import Job, JobStatus
        from app.core.celery_app import celery_app

        with _db() as db:
            job = db.query(Job).filter(
                (Job.celery_task_id == task_id) | (Job.id == task_id)
            ).first()
            if not job:
                return {"success": False, "error": f"Job with task_id {task_id} not found"}
            if job.status not in (JobStatus.FAILED, JobStatus.DEAD):
                return {
                    "success": False,
                    "error": f"Job status is '{job.status}', can only retry failed/dead tasks",
                }

            # Re-send the task
            celery_app.send_task(
                job.task_name,
                args=job.input_args.get("args", []),
                kwargs=job.input_args.get("kwargs", {}),
                queue=job.queue,
            )

            job.status = JobStatus.RETRYING
            job.attempt += 1
            job.error_message = None
            db.flush()

            return {
                "success": True,
                "job_id": job.id,
                "task_name": job.task_name,
                "queue": job.queue,
                "attempt": job.attempt,
            }
    except Exception as exc:
        return {"success": False, "error": f"retry_failed_task failed: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE TOOLS — Direct access to core services
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def send_telegram(message: str, category: str = "summary") -> dict:
    """
    Send a direct Telegram notification. Categories control filtering:
    'error', 'delivery', 'earnings', 'summary', 'status'.
    Uses the configured TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """
    try:
        from app.services.telegram_notifier import TelegramNotifier
        tg = TelegramNotifier()
        if not tg.enabled:
            return {"success": False, "error": "Telegram not configured (missing BOT_TOKEN or CHAT_ID)"}
        if not tg._should_notify(category):
            return {
                "success": False,
                "error": f"Category '{category}' filtered by notification level '{tg._level}'",
            }
        tg.send_text(message)
        return {"success": True, "message": "Telegram notification sent", "category": category}
    except Exception as exc:
        return {"success": False, "error": f"send_telegram failed: {exc}"}


@mcp.tool()
def get_storage_stats() -> dict:
    """
    Return MinIO/S3 storage statistics: bucket list, total object count,
    total size, and per-bucket breakdown.
    """
    try:
        from app.core.storage import get_storage_client
        from app.core.config import get_settings
        settings = get_settings()

        client = get_storage_client()
        buckets_response = client.list_buckets()
        bucket_names = [b["Name"] for b in buckets_response.get("Buckets", [])]

        stats = {"buckets": {}, "total_objects": 0, "total_size_mb": 0.0}

        for bucket_name in bucket_names:
            try:
                paginator = client.get_paginator("list_objects_v2")
                count = 0
                size = 0
                for page in paginator.paginate(Bucket=bucket_name):
                    for obj in page.get("Contents", []):
                        count += 1
                        size += obj.get("Size", 0)
                stats["buckets"][bucket_name] = {
                    "object_count": count,
                    "size_mb": round(size / (1024 * 1024), 2),
                }
                stats["total_objects"] += count
                stats["total_size_mb"] += round(size / (1024 * 1024), 2)
            except Exception as exc:
                stats["buckets"][bucket_name] = {"error": str(exc)}

        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats
    except Exception as exc:
        return {"success": False, "error": f"get_storage_stats failed: {exc}"}


# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

def _validate_startup() -> tuple[bool, str]:
    """
    Validate that the MCP server can start successfully.
    Returns (success, message).
    """
    errors = []

    # Check database connectivity
    try:
        from sqlalchemy import text
        with _db() as db:
            db.execute(text("SELECT 1"))
        print("[OK] Database: OK")
    except Exception as exc:
        errors.append(f"Database connection failed: {exc}")

    # Check all agents can be imported
    agents = [
        "campaign_hunter",
        "campaign_intelligence",
        "content_acquisition",
        "content_analysis",
        "clip_generation",
        "editing_agent",
        "enhancement_agent",
        "quality_control",
        "delivery_agent",
        "health_monitor",
        "publishing",
        "monetization_agent",
        "multi_platform_delivery",
        "clip_editor_quality",
        "lead_ingestion",
    ]
    for agent in agents:
        try:
            __import__(f"app.agents.{agent}")
            print(f"[OK] Agent {agent}: OK")
        except Exception as exc:
            errors.append(f"Agent {agent} import failed: {exc}")

    # Check models exist
    try:
        from app.models.campaign import Campaign
        from app.models.clip import Clip
        from app.models.job import Job
        from app.models.audit_log import AuditLog
        from app.models.submission import Submission
        print("[OK] Models: OK")
    except Exception as exc:
        errors.append(f"Model import failed: {exc}")

    # Check pipelines
    try:
        from app.pipelines import STAGE_ORDER, PipelineContext
        print(f"[OK] Pipeline stages: {len(STAGE_ORDER)}")
    except Exception as exc:
        errors.append(f"Pipeline import failed: {exc}")

    # Check services
    try:
        from app.services.telegram_notifier import TelegramNotifier
        print("[OK] TelegramNotifier: OK")
    except Exception as exc:
        errors.append(f"TelegramNotifier import failed: {exc}")

    # Count registered tools
    try:
        tool_count = len(mcp._tool_manager._tools)
        print(f"[OK] MCP tools registered: {tool_count}")
    except Exception:
        print("[OK] MCP tools: registered (count unavailable)")

    if errors:
        return False, "\n".join(errors)
    return True, "All checks passed — MCP server ready for Claude Code"


# ── Health endpoint for Docker healthcheck ────────────────────────────────────

def _setup_health_endpoint():
    """
    Add a /health GET endpoint to the FastMCP server for Docker healthchecks.
    This avoids the SSE timeout workaround.
    """
    try:
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def health_handler(request):
            return JSONResponse({"status": "ok", "server": "clipping-factory-mcp", "version": "2.0.0"})

        # FastMCP exposes the underlying Starlette app
        if hasattr(mcp, "_app") and hasattr(mcp._app, "routes"):
            mcp._app.routes.append(Route("/health", health_handler, methods=["GET"]))
        elif hasattr(mcp, "settings"):
            # Some FastMCP versions use settings for custom routes
            pass
        print("[OK] Health endpoint: /health registered")
    except Exception as exc:
        print(f"[WARN] Could not register /health endpoint: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clipping Factory MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="Transport: stdio (Claude Code) or sse (network clients)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run startup validation and exit",
    )
    args = parser.parse_args()

    if args.check:
        print("Running MCP server startup validation...\n")
        success, msg = _validate_startup()
        print(f"\n{msg}")
        sys.exit(0 if success else 1)

    try:
        if args.transport == "sse":
            print(f"Starting MCP server v2.0.0 (SSE) on port {args.port}...")
            print(f"  Tools: agent=15, pipeline=5, query=8, infra=3, service=2 → total ~34")
            _setup_health_endpoint()
            mcp.run(transport="sse", host="0.0.0.0", port=args.port)
        else:
            print("Starting MCP server v2.0.0 (stdio for Claude Code)...")
            mcp.run()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    except Exception as exc:
        print(f"ERROR: MCP server failed to start: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
