"""
Clipping Factory MCP Server — exposes all agents as MCP tools.

Compatible with Claude Code, Cursor, any MCP-capable AI assistant.
Agents: scan_campaigns, analyze_campaign, acquire_content, analyze_content,
        generate_clips, edit_clip, quality_check, deliver_clip, publish_clip,
        system_health
Queries: list_campaigns, list_clips, get_campaign

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

mcp = FastMCP("Clipping Factory", version="1.0.0")


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


# ── Agent tools ───────────────────────────────────────────────────────────────

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
    from app.agents.content_acquisition import ContentAcquisitionAgent
    with _db() as db:
        return _wrap(ContentAcquisitionAgent(db)._safe_run(campaign_id=campaign_id))


@mcp.tool()
def analyze_content(source_content_id: str) -> dict:
    """
    Transcribe source audio with Whisper then use Claude to score and rank
    clip candidates by engagement potential.
    """
    from app.agents.content_analysis import ContentAnalysisAgent
    with _db() as db:
        return _wrap(ContentAnalysisAgent(db)._safe_run(source_content_id=source_content_id))


@mcp.tool()
def generate_clips(source_content_id: str) -> dict:
    """
    Cut raw clip segments from source video using ffmpeg.
    Produces multiple versions per candidate for quality selection downstream.
    """
    from app.agents.clip_generation import ClipGenerationAgent
    with _db() as db:
        return _wrap(ClipGenerationAgent(db)._safe_run(source_content_id=source_content_id))


@mcp.tool()
def edit_clip(clip_id: str) -> dict:
    """
    Apply AI-directed post-production to a raw clip: captions, color grade,
    transitions, background music. Produces a polished deliverable.
    """
    from app.agents.editing_agent import EditingAgent
    with _db() as db:
        return _wrap(EditingAgent(db)._safe_run(clip_id=clip_id))


@mcp.tool()
def enhance_clip(clip_id: str) -> dict:
    """
    Apply quality enhancement to a clip: sharpen, color grade, denoise,
    and optional Real-ESRGAN upscaling. Uses campaign requirements config.
    """
    from app.agents.enhancement_agent import EnhancementAgent
    with _db() as db:
        return _wrap(EnhancementAgent(db)._safe_run(clip_id=clip_id))


@mcp.tool()
def quality_check(clip_id: str) -> dict:
    """
    Run automated QC: technical specs, campaign requirement compliance,
    content quality scoring. Approves or rejects the clip for delivery.
    """
    from app.agents.quality_control import QualityControlAgent
    with _db() as db:
        return _wrap(QualityControlAgent(db)._safe_run(clip_id=clip_id))


@mcp.tool()
def deliver_clip(clip_id: str) -> dict:
    """
    Submit an approved clip to Clipping.com via browser automation.
    Records submission metadata and updates delivery status.
    """
    from app.agents.delivery_agent import DeliveryAgent
    with _db() as db:
        return _wrap(DeliveryAgent(db)._safe_run(clip_id=clip_id))


@mcp.tool()
def publish_clip(clip_id: str, platforms: list[str] | None = None) -> dict:
    """
    Publish a finished clip to social platforms (tiktok, instagram, youtube)
    via browser automation. Pass `platforms` to override the configured default
    (PUBLISH_PLATFORMS). Falls back to a simulated post when no logged-in session
    is configured for a platform. Records one SocialPost row per platform.
    """
    from app.agents.publishing import PublishingAgent
    with _db() as db:
        return _wrap(PublishingAgent(db)._safe_run(clip_id=clip_id, platforms=platforms))


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


# ── Pipeline tools ────────────────────────────────────────────────────────────

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


@mcp.tool()
def approve_clip(clip_id: str, notes: str = "") -> dict:
    """
    Manually approve a clip that is awaiting review (status: awaiting_approval).
    Triggers delivery pipeline automatically if auto_submit is disabled.
    """
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


@mcp.tool()
def reject_clip(clip_id: str, reason: str = "") -> dict:
    """
    Manually reject a clip. Marks it as QC_FAIL and records the reason.
    """
    from app.models.clip import Clip, ClipStatus
    with _db() as db:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return {"success": False, "error": f"Clip {clip_id} not found"}
        clip.status = ClipStatus.QC_FAIL
        clip.qc_notes = (clip.qc_notes or "") + f" | Rejected: {reason}"
        db.flush()
        return {"success": True, "clip_id": clip_id, "status": "rejected", "reason": reason}


@mcp.tool()
def get_analytics(days: int = 7) -> dict:
    """
    Return a high-level performance summary for the last N days.
    Includes: campaigns processed, clips generated, clips delivered,
    average quality score, estimated earnings.
    """
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


# ── Query tools ───────────────────────────────────────────────────────────────

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


@mcp.tool()
def get_campaign(campaign_id: str) -> dict | None:
    """
    Retrieve full details for a single campaign by ID, including requirements
    and current processing status.
    """
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


# ── Entrypoint ────────────────────────────────────────────────────────────────

def _validate_startup() -> tuple[bool, str]:
    """
    Validate that the MCP server can start successfully.
    Returns (success, message).
    """
    errors = []

    # Check database connectivity
    try:
        with _db() as db:
            db.execute("SELECT 1")
        print("✓ Database: OK")
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
    ]
    for agent in agents:
        try:
            __import__(f"app.agents.{agent}")
            print(f"✓ Agent {agent}: OK")
        except Exception as exc:
            errors.append(f"Agent {agent} import failed: {exc}")

    # Check models exist
    try:
        from app.models.campaign import Campaign
        from app.models.clip import Clip
        print("✓ Models: OK")
    except Exception as exc:
        errors.append(f"Model import failed: {exc}")

    if errors:
        return False, "\n".join(errors)
    return True, "All checks passed — MCP server ready for Claude Code"


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
            print(f"Starting MCP server (SSE) on port {args.port}...")
            mcp.run(transport="sse", host="0.0.0.0", port=args.port)
        else:
            print("Starting MCP server (stdio for Claude Code)...")
            mcp.run()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    except Exception as exc:
        print(f"ERROR: MCP server failed to start: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
