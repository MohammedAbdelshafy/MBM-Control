import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from .models.source import NormalizedSource
from .models.campaign import NormalizedCampaign
from .moment_discovery import CandidateMoment, MomentConfidence

class Platform(Enum):
    YOUTUBE_SHORTS = "YOUTUBE_SHORTS"
    TIKTOK = "TIKTOK"
    INSTAGRAM_REELS = "INSTAGRAM_REELS"
    X = "X"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass
class ClipPlan:
    clip_id: str
    moment_id: str
    source_id: str
    
    target_platforms: List[Platform]
    aspect_ratio: str  # e.g., "9:16", "1:1"
    target_duration: int
    
    hook_treatment: str
    caption_subtitle_strategy: str
    intro_outro_treatment: str
    cta_strategy: str
    
    title_caption_suggestions: List[str]
    editorial_notes: str
    
    estimated_editing_effort_hours: float
    ai_generation_cost_estimate: float
    human_review_cost_estimate: float
    
    expected_quality_score: float # 0.0 - 1.0
    
    # Expected reward economics linkage
    campaign_id: Optional[str]
    
    # Provenance chain
    provenance_chain: Dict[str, Any]
    qa_requirements: List[str]
    
    def __post_init__(self):
        if not self.target_platforms:
            raise ValueError("At least one target platform is required")
            
        if Platform.UNSUPPORTED in self.target_platforms:
            raise ValueError("Cannot plan for unsupported platforms")

        # Validate duration limits based on platforms
        if Platform.YOUTUBE_SHORTS in self.target_platforms and self.target_duration > 60:
            raise ValueError("YouTube Shorts cannot exceed 60 seconds")
            
        if Platform.INSTAGRAM_REELS in self.target_platforms and self.target_duration > 90:
            raise ValueError("Instagram Reels cannot exceed 90 seconds")
            
        # Ensure we have a complete provenance chain
        if not self.provenance_chain or "source" not in self.provenance_chain or "moment" not in self.provenance_chain:
            raise ValueError("Incomplete provenance chain")

def normalize_platform(platform_str: str) -> Platform:
    platform_str = platform_str.upper().replace(" ", "_")
    if "YOUTUBE" in platform_str and "SHORT" in platform_str:
        return Platform.YOUTUBE_SHORTS
    if "TIKTOK" in platform_str:
        return Platform.TIKTOK
    if "INSTAGRAM" in platform_str or "REEL" in platform_str:
        return Platform.INSTAGRAM_REELS
    if platform_str == "X" or platform_str == "TWITTER":
        return Platform.X
    return Platform.UNSUPPORTED

def generate_clip_id(moment_id: str, platform: Platform) -> str:
    raw = f"{moment_id}_{platform.value}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]

def plan_clip(
    source: NormalizedSource, 
    moment: CandidateMoment, 
    campaign: Optional[NormalizedCampaign],
    target_platforms_str: List[str]
) -> List[ClipPlan]:
    """
    Transforms discovered moments into production-ready plans.
    """
    if moment.confidence in (MomentConfidence.LOW, MomentConfidence.UNKNOWN):
        raise ValueError("Cannot plan clip for low confidence moment")
        
    plans = []
    seen_ids = set()
    
    for p_str in target_platforms_str:
        platform = normalize_platform(p_str)
        
        if platform == Platform.UNSUPPORTED:
            # We explicitly ignore unsupported platforms instead of failing entirely,
            # or we could log it. For now, we skip generating a plan for it.
            continue
            
        target_duration = moment.duration_seconds
        
        # Enforce platform constraints during planning
        if platform == Platform.YOUTUBE_SHORTS and target_duration > 60:
            # We would need to edit it down. For this prototype, we'll cap it at 60.
            target_duration = 60
        elif platform == Platform.INSTAGRAM_REELS and target_duration > 90:
            target_duration = 90
            
        clip_id = generate_clip_id(moment.moment_id, platform)
        
        if clip_id in seen_ids:
            continue
            
        seen_ids.add(clip_id)
        
        plan = ClipPlan(
            clip_id=clip_id,
            moment_id=moment.moment_id,
            source_id=source.source_id,
            target_platforms=[platform],
            aspect_ratio="9:16",
            target_duration=target_duration,
            hook_treatment="Fast-paced visual hook",
            caption_subtitle_strategy="Dynamic bold center captions",
            intro_outro_treatment="No intro, strong CTA outro",
            cta_strategy="Link in bio" if platform != Platform.YOUTUBE_SHORTS else "Pinned comment",
            title_caption_suggestions=["Check this out!", "You won't believe this..."],
            editorial_notes="Ensure high energy.",
            estimated_editing_effort_hours=1.5,
            ai_generation_cost_estimate=0.50,
            human_review_cost_estimate=15.0, # 0.5 hours * 30/hr
            expected_quality_score=moment.total_score,
            campaign_id=campaign.id if campaign else None,
            provenance_chain={
                "source": {
                    "id": source.source_id,
                    "url": source.source_url,
                    "hash": source.raw_metadata_hash
                },
                "moment": {
                    "id": moment.moment_id,
                    "start": moment.start_seconds,
                    "end": moment.end_seconds,
                    "confidence": moment.confidence.value
                }
            },
            qa_requirements=[
                "Verify hook lands in first 3 seconds",
                "Ensure text is within safe zones for " + platform.value
            ]
        )
        
        plans.append(plan)
        
    return plans
