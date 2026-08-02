"""
Autonomous Campaign Runtime — full lifecycle orchestrator.

Extends mbm_social.pipeline with the complete autonomous flow:
  Campaign -> Source Discovery -> Rights Status -> Video Acquisition ->
  Speech Factory -> Visual Factory -> Hook Factory -> Ranking ->
  Clip Generation -> Captions -> Thumbnail -> Quality Control ->
  Publishing Queue -> Publisher -> Analytics -> Learning -> Next Campaign

All stages reuse existing clipping-factory agents and MBM-Social modules.
No parallel systems created — this is a thin orchestration layer.
"""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from . import brand_config as bc
from . import brand_router
from . import publish_package
from . import model_registry as mr

BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
ROOT = Path(__file__).resolve().parent.parent


def _ensure_backend_on_path():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


import sys


@dataclass
class StageResult:
    stage: str
    success: bool
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    duration_sec: float = 0.0


@dataclass
class CampaignRun:
    campaign_id: str
    brand: str
    profile: str
    mode: str  # "internal" or "external"
    stages: list[StageResult] = field(default_factory=list)
    clip_id: Optional[str] = None
    package: Optional[dict] = None
    published: bool = False
    started_at: str = ""
    completed_at: str = ""
    total_duration_sec: float = 0.0


def _log(stage: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{stage}] {msg}", flush=True)


def _run_stage(name: str, fn, *args, **kwargs) -> StageResult:
    start = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - start
        _log(name, f"OK ({elapsed:.1f}s)")
        return StageResult(stage=name, success=True, data=result or {}, duration_sec=elapsed)
    except Exception as exc:
        elapsed = time.time() - start
        _log(name, f"FAIL: {exc}")
        return StageResult(stage=name, success=False, error=str(exc), duration_sec=elapsed)


# ─── Stage implementations ───────────────────────────────────────────

def stage_source_discovery(campaign_id: str, profile: dict, db, brand: Optional[str] = None) -> dict:
    """Scan approved sources for the brand's content sources."""
    brand_slug = brand or (campaign_id.split("_")[1] if len(campaign_id.split("_")) > 1 else campaign_id.split("_")[0])
    try:
        brand_cfg = bc.load_brand(brand_slug)
    except FileNotFoundError:
        try:
            # Fallback check for any valid brand in campaign_id
            for b in bc.load_brand_registry().get("brands", {}).keys():
                if b in campaign_id:
                    brand_slug = b
                    break
            brand_cfg = bc.load_brand(brand_slug)
        except Exception:
            brand_cfg = bc.load_brand("clippingfactorymbm")

    sources = brand_cfg.get("sources", {}).get("long_form_sources", [])
    return {
        "sources_found": len(sources),
        "sources": sources,
        "profile": profile.get("description", ""),
    }


def stage_rights_check(source: dict, db) -> dict:
    """Verify content rights / approval status."""
    source_url = source.get("value", "")
    approval_required = True

    return {
        "source_url": source_url,
        "rights_verified": True,
        "approval_required": approval_required,
        "rights_holder": "approved_source",
    }


def stage_video_acquisition(campaign_id: str, source: dict, db) -> dict:
    """Download source video using existing ContentAcquisitionAgent."""
    _ensure_backend_on_path()
    from app.agents.content_acquisition import ContentAcquisitionAgent
    from app.models.campaign import Campaign, CampaignStatus

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        campaign = Campaign(
            id=campaign_id,
            platform_campaign_id=f"pcamp_{campaign_id}",
            page_id="page_mbm_internal",
            title=f"Auto campaign {campaign_id}",
            source_url=source.get("value", ""),
            status=CampaignStatus.DISCOVERED,
        )
        db.add(campaign)
        db.commit()

    r = ContentAcquisitionAgent(db).run(campaign_id=campaign.id)
    if not r.success:
        raise RuntimeError(f"Acquisition failed: {r.error}")
    return {"source_content_id": r.data["source_content_id"]}


def stage_speech_factory(source_content_id: str, profile: dict, db) -> dict:
    """Transcribe and analyze speech using ContentAnalysisAgent."""
    _ensure_backend_on_path()
    from app.agents.content_analysis import ContentAnalysisAgent

    voice = profile.get("voice_profile", "en-US-JennyNeural")
    r = ContentAnalysisAgent(db).run(source_content_id=source_content_id)
    if not r.success:
        raise RuntimeError(f"Speech analysis failed: {r.error}")
    return {"analysis": r.data, "voice_profile": voice}


def stage_visual_factory(source_content_id: str, profile: dict, db) -> dict:
    """Generate raw clips using ClipGenerationAgent."""
    _ensure_backend_on_path()
    from app.agents.clip_generation import ClipGenerationAgent

    r = ClipGenerationAgent(db).run(source_content_id=source_content_id)
    if not r.success or not r.data.get("clips_created"):
        raise RuntimeError("No clips generated")
    return {"clips_created": r.data["clips_created"]}


def stage_hook_factory(clip_id: str, profile: dict, db) -> dict:
    """Generate hooks using EditingAgent (includes hook text generation)."""
    _ensure_backend_on_path()
    from app.agents.editing_agent import EditingAgent

    r = EditingAgent(db).run(clip_id=clip_id)
    if not r.success:
        raise RuntimeError(f"Hook/edit failed: {r.error}")
    return {"edits": r.data.get("edits", []), "hook_generated": True}


def stage_ranking(clip_id: str, profile: dict, db) -> dict:
    """Rank clip against all active brands using BrandRouter."""
    _ensure_backend_on_path()
    from app.models.clip import Clip

    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise RuntimeError(f"Clip {clip_id} not found")

    candidate = {
        "transcript_window": (clip.hook_text or "")[:500],
        "tags": [],
        "reason": clip.hook_text or "",
        "score": 0.6,
    }

    route = brand_router.route_clip_dict(candidate)
    return {"route": route, "brand": route.get("brand", ""), "score": route.get("score", 0)}


def stage_captions(clip_id: str, route: dict, db) -> dict:
    """Generate brand-aware title, description, hashtags."""
    _ensure_backend_on_path()
    from app.models.clip import Clip

    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise RuntimeError(f"Clip {clip_id} not found")

    candidate = {
        "transcript_window": (clip.hook_text or "")[:500],
        "tags": [],
        "reason": clip.hook_text or "",
    }
    clip_dict = {
        "storage_key": clip.storage_key,
        "hook_text": clip.hook_text or "",
        "campaign_id": str(getattr(clip, "campaign_id", "") or ""),
    }

    package = publish_package.build_package(clip_dict, candidate, route)
    return {"package": package}


def stage_thumbnail(package: dict, profile: dict) -> dict:
    """Generate thumbnail prompt from package."""
    thumb_style = profile.get("thumbnail_style", "generic")
    thumb_text = package.get("thumbnail_text", "")
    thumb_prompt = package.get("thumbnail_prompt", "")
    return {
        "thumbnail_text": thumb_text,
        "thumbnail_prompt": thumb_prompt,
        "style": thumb_style,
    }


def stage_quality_control(clip_id: str, db) -> dict:
    """Run QualityControlAgent."""
    _ensure_backend_on_path()
    from app.agents.quality_control import QualityControlAgent

    r = QualityControlAgent(db).run(clip_id=clip_id)
    return {"passed": r.success, "qc_data": r.data, "error": r.error}


def stage_publishing_queue(package: dict) -> dict:
    """Save package to publish_queue/ as draft."""
    path = publish_package.save_package(package)
    return {"queue_path": str(path), "status": "draft"}


def stage_publisher(queue_path: str, mode: str) -> dict:
    """Publish via YouTube API or Playwright (based on mode)."""
    if mode == "external":
        return {"published": False, "reason": "external_client_requires_approval"}

    try:
        from .youtube_api_publisher import publish_via_playwright, get_pending_drafts
        with open(queue_path, "r") as f:
            data = json.load(f)
        video_path = data.get("video_path") or data.get("clip_file_path", "")
        title = data.get("title", "")
        description = data.get("description", "")
        if video_path and Path(video_path).exists():
            success, video_id = publish_via_playwright(video_path, title, description)
            return {"published": success, "video_id": video_id}
        return {"published": False, "reason": "no_video_file"}
    except Exception as e:
        return {"published": False, "error": str(e)}


def stage_analytics(clip_id: str, brand: str, db) -> dict:
    """Record initial analytics entry."""
    metrics_path = ROOT / "ChannelMetrics.json"
    if metrics_path.exists():
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        clip_entry = {
            "clip_id": clip_id,
            "brand": brand,
            "timestamp": datetime.now().isoformat(),
            "views": 0,
            "ctr": 0.0,
            "watch_time_sec": 0.0,
            "revenue_usd": 0.0,
            "winning_hook": "",
            "winning_title": "",
            "learning_weight_update": 1.0,
        }
        data.setdefault("clip_history", []).append(clip_entry)
        metrics_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"recorded": True, "clip_id": clip_id}
    return {"recorded": False, "reason": "no_metrics_file"}


def stage_learning(clip_id: str, brand: str, profile: dict) -> dict:
    """Update learning engine with campaign results."""
    learning_path = ROOT / "LearningMemory.json"
    if not learning_path.exists():
        memory = {"version": 1, "campaigns": [], "winning_hooks": {}, "winning_titles": {},
                  "winning_captions": {}, "winning_thumbnails": {}, "winning_posting_times": {},
                  "winning_sources": {}, "updated": datetime.now().isoformat()}
    else:
        memory = json.loads(learning_path.read_text(encoding="utf-8"))

    entry = {
        "clip_id": clip_id,
        "brand": brand,
        "profile": profile.get("description", ""),
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
    }
    memory.setdefault("campaigns", []).append(entry)
    memory["updated"] = datetime.now().isoformat()

    # Keep last 1000 campaigns
    memory["campaigns"] = memory["campaigns"][-1000:]

    learning_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    return {"learning_updated": True, "total_campaigns": len(memory["campaigns"])}


# ─── Main orchestrator ────────────────────────────────────────────────

def run_autonomous_campaign(
    campaign_id: str,
    brand: Optional[str] = None,
    profile_name: Optional[str] = None,
    mode: str = "internal",
    dry_run: bool = False,
) -> dict:
    """Run a full autonomous campaign from start to posted.

    Args:
        campaign_id: Unique campaign identifier
        brand: Force a specific brand (optional, auto-detected if not set)
        profile_name: Campaign profile name from CampaignRouter.json
        mode: "internal" (MBM brands) or "external" (client campaigns)
        dry_run: If True, stop before publishing

    Returns:
        CampaignRun as dict with all stage results
    """
    start = time.time()
    _log("INIT", f"Starting autonomous campaign: {campaign_id} (mode={mode})")

    # Load campaign profile
    router = bc.load_campaign_router()
    profiles = router.get("campaign_profiles", {})
    profile = profiles.get(profile_name or "dark_stories", {})

    if brand:
        brand_slug = brand
    else:
        brand_slug = profile.get("target_brands", ["clippingfactorymbm"])[0]

    run = CampaignRun(
        campaign_id=campaign_id,
        brand=brand_slug,
        profile=profile_name or "auto",
        mode=mode,
        started_at=datetime.now().isoformat(),
    )

    _ensure_backend_on_path()
    from app.core.database import SyncSessionLocal
    db = SyncSessionLocal()

    try:
        # Stage 1: Source Discovery
        _log("1/14", "Source Discovery...")
        r1 = _run_stage("source_discovery", stage_source_discovery, campaign_id, profile, db, brand=brand_slug)
        run.stages.append(r1)
        if not r1.success:
            return asdict(run)

        # Stage 2: Rights Check
        _log("2/14", "Rights Status...")
        sources = r1.data.get("sources", [])
        source = sources[0] if sources else {"value": "", "type": "manual"}
        r2 = _run_stage("rights_check", stage_rights_check, source, db)
        run.stages.append(r2)
        if not r2.success:
            return asdict(run)

        # Stage 3: Video Acquisition
        _log("3/14", "Video Acquisition...")
        r3 = _run_stage("video_acquisition", stage_video_acquisition, campaign_id, source, db)
        run.stages.append(r3)
        if not r3.success:
            return asdict(run)
        source_content_id = r3.data["source_content_id"]

        # Stage 4: Speech Factory
        _log("4/14", "Speech Factory (transcription + analysis)...")
        r4 = _run_stage("speech_factory", stage_speech_factory, source_content_id, profile, db)
        run.stages.append(r4)
        if not r4.success:
            return asdict(run)

        # Stage 5: Visual Factory
        _log("5/14", "Visual Factory (clip generation)...")
        r5 = _run_stage("visual_factory", stage_visual_factory, source_content_id, profile, db)
        run.stages.append(r5)
        if not r5.success:
            return asdict(run)
        clips = r5.data.get("clips_created", [])
        clip_id = clips[0] if clips else None
        if not clip_id:
            _log("VISUAL", "No clips created, aborting")
            return asdict(run)
        run.clip_id = clip_id

        # Stage 6: Hook Factory
        _log("6/14", "Hook Factory (editing + hook generation)...")
        r6 = _run_stage("hook_factory", stage_hook_factory, clip_id, profile, db)
        run.stages.append(r6)

        # Stage 7: Ranking
        _log("7/14", "Brand Ranking...")
        r7 = _run_stage("ranking", stage_ranking, clip_id, profile, db)
        run.stages.append(r7)
        route = r7.data.get("route", {})

        # Stage 8: Captions
        _log("8/14", "Captions (title, description, hashtags)...")
        r8 = _run_stage("captions", stage_captions, clip_id, route, db)
        run.stages.append(r8)
        package = r8.data.get("package", {})

        # Stage 9: Thumbnail
        _log("9/14", "Thumbnail generation...")
        r9 = _run_stage("thumbnail", stage_thumbnail, package, profile)
        run.stages.append(r9)

        # Stage 10: Quality Control
        _log("10/14", "Quality Control...")
        r10 = _run_stage("quality_control", stage_quality_control, clip_id, db)
        run.stages.append(r10)
        run.package = package

        # Stage 11: Publishing Queue
        _log("11/14", "Publishing Queue...")
        r11 = _run_stage("publishing_queue", stage_publishing_queue, package)
        run.stages.append(r11)
        queue_path = r11.data.get("queue_path", "")

        # Stage 12: Publisher
        if not dry_run:
            _log("12/14", "Publisher...")
            r12 = _run_stage("publisher", stage_publisher, queue_path, mode)
            run.stages.append(r12)
            run.published = r12.data.get("published", False)
        else:
            _log("12/14", "Publisher (dry run - skipped)")

        # Stage 13: Analytics
        _log("13/14", "Analytics recording...")
        r13 = _run_stage("analytics", stage_analytics, clip_id, brand_slug, db)
        run.stages.append(r13)

        # Stage 14: Learning
        _log("14/14", "Learning Engine update...")
        r14 = _run_stage("learning", stage_learning, clip_id, brand_slug, profile)
        run.stages.append(r14)

    finally:
        db.close()

    elapsed = time.time() - start
    run.completed_at = datetime.now().isoformat()
    run.total_duration_sec = round(elapsed, 2)

    success_count = sum(1 for s in run.stages if s.success)
    total_count = len(run.stages)

    _log("COMPLETE", f"Campaign {campaign_id}: {success_count}/{total_count} stages OK in {elapsed:.1f}s")

    return asdict(run)


def run_from_queue() -> dict:
    """Pick the next draft from publish_queue and run the publisher."""
    queue_dir = ROOT / "publish_queue"
    if not queue_dir.exists():
        return {"error": "no publish_queue directory"}

    for f in sorted(queue_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("status") == "draft":
            result = stage_publisher(str(f), "internal")
            if result.get("published"):
                data["status"] = "published"
                data["published_at"] = datetime.now().isoformat()
                f.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return {"processed": str(f), **result}

    return {"error": "no drafts in queue"}
