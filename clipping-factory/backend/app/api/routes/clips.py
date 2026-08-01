"""
Clip API routes — list, inspect, approve/reject, get presigned download URL.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.clip import Clip, ClipStatus

router = APIRouter(prefix="/clips", tags=["clips"])


@router.get("")
async def list_clips(
    campaign_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(Clip)
    if campaign_id:
        q = q.where(Clip.campaign_id == campaign_id)
    if status:
        q = q.where(Clip.status == status)
    q = q.order_by(Clip.overall_score.desc(), Clip.created_at.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    clips = result.scalars().all()

    total_q = select(func.count(Clip.id))
    if campaign_id:
        total_q = total_q.where(Clip.campaign_id == campaign_id)
    if status:
        total_q = total_q.where(Clip.status == status)
    total = (await db.execute(total_q)).scalar() or 0

    return {
        "items": [
            {
                "id": c.id,
                "campaign_id": c.campaign_id,
                "status": c.status,
                "overall_score": c.overall_score,
                "scores": c.scores,
                "duration_seconds": c.duration_seconds,
                "width": c.width,
                "height": c.height,
                "hook_text": c.hook_text,
                "qc_notes": c.qc_notes,
                "rejection_reason": c.rejection_reason,
                "edits_applied": c.edits_applied,
                "viral_benchmark": c.viral_benchmark,
                "enhanced_tags": c.enhanced_tags,
                "platform_metadata": c.platform_metadata,
                "version": c.version,
                "created_at": c.created_at.isoformat(),
            }
            for c in clips
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{clip_id}/download-url")
async def get_download_url(
    clip_id: str,
    expiry: int = Query(3600, ge=60, le=86400),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip or not clip.storage_key:
        raise HTTPException(404, "Clip not found or not yet processed")

    from app.core.storage import get_presigned_url
    url = get_presigned_url(clip.storage_bucket, clip.storage_key, expiry)
    return {"url": url, "expires_in": expiry}


_APPROVABLE = {ClipStatus.AWAITING_APPROVAL, ClipStatus.QC_PASS, ClipStatus.QC_FAIL}
_REJECTABLE = {ClipStatus.AWAITING_APPROVAL, ClipStatus.QC_PASS, ClipStatus.QC_FAIL, ClipStatus.APPROVED}


@router.post("/{clip_id}/approve")
async def approve_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found")
    if clip.status not in _APPROVABLE:
        raise HTTPException(400, f"Cannot approve clip in status: {clip.status}")
    clip.status = ClipStatus.APPROVED
    clip.reviewed_by = user
    await db.flush()
    from app.workers.delivery_tasks import create_deliverable
    create_deliverable.apply_async(args=[clip_id], queue="delivery")
    return {"status": "approved", "clip_id": clip_id}


@router.post("/{clip_id}/reject")
async def reject_clip(
    clip_id: str,
    reason: str = Query("Rejected by operator", max_length=512),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found")
    if clip.status not in _REJECTABLE:
        raise HTTPException(400, f"Cannot reject clip in status: {clip.status}")
    clip.status = ClipStatus.REJECTED_HUMAN
    clip.rejection_reason = reason.strip()
    clip.reviewed_by = user
    await db.flush()
    return {"status": "rejected", "clip_id": clip_id}


@router.get("/{clip_id}/viral-report")
async def get_viral_report(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Retrieve full viral video comparison report and enhanced tags for clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found")
    return {
        "clip_id": clip.id,
        "viral_benchmark": clip.viral_benchmark or {},
        "enhanced_tags": clip.enhanced_tags or [],
        "platform_metadata": clip.platform_metadata or {},
        "scores": clip.scores or {},
    }


@router.post("/{clip_id}/viral-compare")
async def run_viral_comparison(
    clip_id: str,
    niche: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Trigger background or immediate viral video comparison."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found")

    from app.workers.video_tasks import run_viral_benchmark
    task = run_viral_benchmark.apply_async(args=[clip_id, niche], queue="video")
    return {"status": "queued", "task_id": task.id, "clip_id": clip_id}


@router.post("/{clip_id}/enhance-viral")
async def enhance_viral(
    clip_id: str,
    niche: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Run inline viral video benchmark comparison and return updated tags & metadata."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found")

    from app.services.viral_comparison_service import ViralComparisonService
    service = ViralComparisonService()

    # Obtain transcript segment text
    window_transcript = clip.hook_text or ""
    if clip.source_content and clip.source_content.transcript:
        segments = clip.source_content.transcript.segments or []
        wt = [
            s.get("text", "") for s in segments
            if s.get("start", 0) >= clip.source_start_seconds and s.get("end", 0) <= clip.source_end_seconds + 2
        ]
        if wt:
            window_transcript = " ".join(wt)

    target_niche = niche or "general_viral"
    comp = service.compare_clip_to_viral(
        transcript_text=window_transcript,
        hook_text=clip.hook_text,
        current_tags=clip.enhanced_tags or [],
        duration_seconds=clip.duration_seconds or 30.0,
        niche=target_niche,
    )
    enh = service.generate_viral_enhancements(
        transcript_text=window_transcript,
        hook_text=clip.hook_text,
        current_tags=clip.enhanced_tags or [],
        niche=target_niche,
    )

    clip.viral_benchmark = comp
    clip.enhanced_tags = enh["enhanced_tags"]
    clip.platform_metadata = enh["platform_metadata"]
    scores = dict(clip.scores or {})
    scores["viral_alignment"] = comp["overall_viral_score"] / 100.0
    clip.scores = scores
    await db.flush()

    return {
        "status": "success",
        "clip_id": clip.id,
        "overall_viral_score": comp["overall_viral_score"],
        "tier": comp["tier"],
        "enhanced_tags": clip.enhanced_tags,
        "platform_metadata": clip.platform_metadata,
        "viral_benchmark": comp,
    }

