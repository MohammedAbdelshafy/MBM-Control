"""
pipeline — end-to-end MBM-Social flow, reusing clipping-factory agents.

Stages (per mission):
  Source -> Speech -> Visual -> Hook -> Ranking -> Clip -> Caption
  -> Thumbnail -> Quality Gate -> Brand Router -> Publisher -> Analytics -> Learning

Upstream stages (Source..Quality Gate) call the existing clipping-factory
agents. MBM-Social contributes Ranking (brand fit), Caption/Thumbnail
(brand-aware), Brand Router, Publisher (per-channel YouTube), Analytics and
Learning. The backend is imported lazily so the routing/LLM modules stay
testable without a database.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from . import brand_router, publish_package, brand_config

BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"


def _ensure_backend_on_path():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def run_end_to_end(campaign_id: str, clip_id: Optional[str] = None) -> dict:
    """Build a clip with existing agents, then route + package it for MBM.

    Returns the publish-ready package (saved to MBM-Social/publish_queue/).
    """
    _ensure_backend_on_path()
    from app.core.database import SyncSessionLocal
    from app.models.campaign import Campaign
    from app.agents.content_acquisition import ContentAcquisitionAgent
    from app.agents.content_analysis import ContentAnalysisAgent
    from app.agents.clip_generation import ClipGenerationAgent
    from app.agents.editing_agent import EditingAgent
    from app.agents.quality_control import QualityControlAgent

    db = SyncSessionLocal()
    try:
        if not clip_id:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                raise ValueError(f"campaign {campaign_id} not found")
            r1 = ContentAcquisitionAgent(db).run(campaign_id=campaign_id)
            if not r1.success:
                raise RuntimeError(f"acquire failed: {r1.error}")
            src_id = r1.data["source_content_id"]
            r2 = ContentAnalysisAgent(db).run(source_content_id=src_id)
            r3 = ClipGenerationAgent(db).run(source_content_id=src_id)
            if not r3.success or not r3.data.get("clips_created"):
                raise RuntimeError("no clips generated")
            clip_id = r3.data["clips_created"][0]
            r4 = EditingAgent(db).run(clip_id=clip_id)
            r5 = QualityControlAgent(db).run(clip_id=clip_id)
            qc = r5.data
        else:
            r5 = None
            qc = {"passed": True, "note": "prebuilt"}

        from app.models.clip import Clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        # pick best candidate for routing
        candidate = _best_candidate(clip)
        route = brand_router.route_clip_dict(candidate)
        clip_dict = {
            "storage_key": clip.storage_key,
            "hook_text": clip.hook_text or candidate.get("reason", ""),
            "campaign_id": campaign_id,
            "source_reference": campaign_id,
        }
        package = publish_package.build_package(clip_dict, candidate, route, qc)
        path = publish_package.save_package(package)
        package["_saved_to"] = str(path)
        return package
    finally:
        db.close()


def _best_candidate(clip) -> dict:
    """Pull the strongest clip candidate from the clip's transcript."""
    try:
        src = clip.source_content
        cand = (src.transcript.clip_candidates or []) if src and src.transcript else []
        if cand:
            return max(cand, key=lambda c: c.get("score", 0))
    except Exception:
        pass
    return {
        "transcript_window": (clip.hook_text or "")[:500],
        "tags": [],
        "reason": clip.hook_text or "",
        "score": 0.6,
    }


def route_existing_clip(clip_id: str) -> dict:
    """Route + package an already-built clip (no upstream rebuild)."""
    _ensure_backend_on_path()
    from app.core.database import SyncSessionLocal
    from app.models.clip import Clip

    db = SyncSessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise ValueError(f"clip {clip_id} not found")
        candidate = _best_candidate(clip)
        route = brand_router.route_clip_dict(candidate)
        clip_dict = {
            "storage_key": clip.storage_key,
            "hook_text": clip.hook_text or candidate.get("reason", ""),
            "source_reference": str(getattr(clip, "campaign_id", "") or ""),
        }
        package = publish_package.build_package(clip_dict, candidate, route)
        path = publish_package.save_package(package)
        package["_saved_to"] = str(path)
        return package
    finally:
        db.close()
