"""
Video pipeline Celery tasks — acquisition → analysis → generation → editing → QC.
Each task delegates to the matching agent and chains to the next stage.
"""
from celery.exceptions import MaxRetriesExceededError

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.workers.campaign_tasks import JobTrackedTask

logger = get_logger("workers.video")


@celery_app.task(
    name="app.workers.video_tasks.acquire_content",
    base=JobTrackedTask,
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue="acquisition",
    soft_time_limit=1800,
)
def acquire_content(self, campaign_id: str):
    from app.core.database import SyncSessionLocal
    from app.agents.content_acquisition import ContentAcquisitionAgent

    db = SyncSessionLocal()
    try:
        agent = ContentAcquisitionAgent(db=db)
        result = agent._safe_run(campaign_id=campaign_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Content acquisition failed for {campaign_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            _mark_campaign_failed(campaign_id, str(exc))
            return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.analyze_content",
    base=JobTrackedTask,
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="analysis",
    soft_time_limit=3600,
)
def analyze_content(self, source_content_id: str):
    from app.core.database import SyncSessionLocal
    from app.agents.content_analysis import ContentAnalysisAgent

    db = SyncSessionLocal()
    try:
        agent = ContentAnalysisAgent(db=db)
        result = agent._safe_run(source_content_id=source_content_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Content analysis failed for {source_content_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.generate_clips",
    base=JobTrackedTask,
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="video",
    soft_time_limit=1800,
)
def generate_clips(self, source_content_id: str):
    from app.core.database import SyncSessionLocal
    from app.agents.clip_generation import ClipGenerationAgent

    db = SyncSessionLocal()
    try:
        agent = ClipGenerationAgent(db=db)
        result = agent._safe_run(source_content_id=source_content_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Clip generation failed for {source_content_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.edit_clip",
    base=JobTrackedTask,
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="video",
    soft_time_limit=1800,
)
def edit_clip(self, clip_id: str):
    from app.core.database import SyncSessionLocal
    from app.agents.editing_agent import EditingAgent

    db = SyncSessionLocal()
    try:
        agent = EditingAgent(db=db)
        result = agent._safe_run(clip_id=clip_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Editing failed for clip {clip_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            _mark_clip_failed(clip_id, str(exc))
            return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.enhance_clip",
    base=JobTrackedTask,
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="video",
    soft_time_limit=3600,
)
def enhance_clip(self, clip_id: str):
    """Apply quality enhancement (sharpen, color grade, denoise, upscale) to a clip."""
    from app.core.database import SyncSessionLocal
    from app.agents.enhancement_agent import EnhancementAgent

    db = SyncSessionLocal()
    try:
        agent = EnhancementAgent(db=db)
        result = agent._safe_run(clip_id=clip_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Enhancement failed for clip {clip_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            _mark_clip_failed(clip_id, str(exc))
            return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.quality_check_clip",
    base=JobTrackedTask,
    bind=True,
    max_retries=1,
    queue="video",
)
def quality_check_clip(self, clip_id: str):
    from app.core.database import SyncSessionLocal
    from app.agents.quality_control import QualityControlAgent

    db = SyncSessionLocal()
    try:
        agent = QualityControlAgent(db=db)
        result = agent._safe_run(clip_id=clip_id)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"QC failed for clip {clip_id}: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.editor_quality_check",
    base=JobTrackedTask,
    bind=True,
    max_retries=1,
    queue="video",
    soft_time_limit=600,
)
def editor_quality_check(self, clip_id: str, auto_fix: bool = False):
    """Run the professional clip editor quality agent — validates every detail."""
    from app.core.database import SyncSessionLocal
    from app.agents.clip_editor_quality import ClipEditorQualityAgent

    db = SyncSessionLocal()
    try:
        agent = ClipEditorQualityAgent(db=db)
        result = agent._safe_run(clip_id=clip_id, auto_fix=auto_fix)
        if not result.success:
            raise ValueError(result.error)
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Editor QA failed for clip {clip_id}: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.video_tasks.cleanup_temp_files",
    queue="default",
)
def cleanup_temp_files():
    """Remove temp directories older than 4 hours."""
    import os
    import shutil
    import time

    temp_base = "/tmp"
    cutoff = time.time() - 4 * 3600
    cleaned = 0

    for entry in os.scandir(temp_base):
        if entry.name.startswith(("clip_acquire_", "clip_analysis_", "clip_gen_", "clip_edit_", "clip_qc_", "clip_deliver_")):
            if entry.stat().st_mtime < cutoff:
                try:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    cleaned += 1
                except Exception:
                    pass

    logger.info(f"Cleanup: removed {cleaned} temp directories")
    return {"cleaned": cleaned}


@celery_app.task(
    name="app.workers.video_tasks.requeue_stuck_clips",
    queue="default",
    soft_time_limit=120,
)
def requeue_stuck_clips():
    """Detect clips stuck in editing/generating for >30 min and re-queue them."""
    from datetime import datetime, timezone, timedelta
    from app.core.database import SyncSessionLocal
    from app.models.clip import Clip, ClipStatus

    db = SyncSessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        stuck = db.query(Clip).filter(
            Clip.status.in_([ClipStatus.EDITING, ClipStatus.GENERATING]),
            Clip.created_at < cutoff,
        ).all()

        if not stuck:
            return {"requeued": 0}

        requeued = 0
        for clip in stuck:
            if clip.status == ClipStatus.EDITING and (clip.edits_applied and len(clip.edits_applied) > 0):
                clip.status = ClipStatus.QC_PENDING
                editor_quality_check.apply_async(args=[clip.id, True], queue="video")
            else:
                clip.status = ClipStatus.GENERATING
                edit_clip.apply_async(args=[clip.id], queue="video")
            requeued += 1

        db.commit()
        logger.warning(f"Requeued {requeued} stuck clips")
        return {"requeued": requeued}
    except Exception as exc:
        db.rollback()
        logger.error(f"Requeue stuck clips failed: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _mark_campaign_failed(campaign_id: str, error: str) -> None:
    from app.core.database import SyncSessionLocal
    from app.models.campaign import Campaign, CampaignStatus
    db = SyncSessionLocal()
    try:
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if c:
            c.status = CampaignStatus.FAILED
            c.error_message = error
            db.commit()
    finally:
        db.close()


def _mark_clip_failed(clip_id: str, error: str) -> None:
    from app.core.database import SyncSessionLocal
    from app.models.clip import Clip, ClipStatus
    db = SyncSessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip:
            clip.status = ClipStatus.QC_FAIL
            clip.qc_notes = error
            db.commit()
    finally:
        db.close()
