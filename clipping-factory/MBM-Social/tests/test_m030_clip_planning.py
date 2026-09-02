import pytest
from mbm_social.models.source import NormalizedSource, ProvenanceConfidence
from mbm_social.moment_discovery import CandidateMoment, MomentConfidence, DiscoveryMethod
from mbm_social.clip_planner import (
    ClipPlan, Platform, normalize_platform, plan_clip, generate_clip_id
)

@pytest.fixture
def valid_source():
    payload = {
        "source_url": "https://youtube.com/watch?v=123",
        "source_type": "video",
        "title": "Test Video",
        "duration_seconds": 120,
    }
    return NormalizedSource.from_provider_payload("youtube", "123", payload)

@pytest.fixture
def valid_moment():
    return CandidateMoment(
        moment_id="m1", source_id="youtube_123", start_seconds=10, end_seconds=40, duration_seconds=30,
        moment_type="t", hook_score=1.0, payoff_score=1.0, standalone_score=1.0, context_score=1.0, relevance_score=1.0,
        confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
    )

def test_platform_normalization():
    assert normalize_platform("YouTube Shorts") == Platform.YOUTUBE_SHORTS
    assert normalize_platform("tiktok") == Platform.TIKTOK
    assert normalize_platform("Instagram Reels") == Platform.INSTAGRAM_REELS
    assert normalize_platform("Twitter") == Platform.X
    assert normalize_platform("random_platform") == Platform.UNSUPPORTED

def test_duration_constraints(valid_source, valid_moment):
    # Valid moment is 30s. Let's make it 100s to test constraints.
    long_moment = CandidateMoment(
        moment_id="m2", source_id="youtube_123", start_seconds=0, end_seconds=100, duration_seconds=100,
        moment_type="t", hook_score=1.0, payoff_score=1.0, standalone_score=1.0, context_score=1.0, relevance_score=1.0,
        confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
    )
    
    plans = plan_clip(valid_source, long_moment, None, ["YouTube Shorts", "Instagram Reels", "TikTok"])
    assert len(plans) == 3
    
    yt_plan = next(p for p in plans if Platform.YOUTUBE_SHORTS in p.target_platforms)
    ig_plan = next(p for p in plans if Platform.INSTAGRAM_REELS in p.target_platforms)
    tk_plan = next(p for p in plans if Platform.TIKTOK in p.target_platforms)
    
    assert yt_plan.target_duration == 60 # Capped
    assert ig_plan.target_duration == 90 # Capped
    assert tk_plan.target_duration == 100 # Uncapped

def test_unsupported_platform_handling(valid_source, valid_moment):
    plans = plan_clip(valid_source, valid_moment, None, ["YouTube Shorts", "MySpace"])
    assert len(plans) == 1
    assert plans[0].target_platforms == [Platform.YOUTUBE_SHORTS]
    
def test_clip_plan_incompatible_platform_init():
    with pytest.raises(ValueError, match="Cannot plan for unsupported platforms"):
        ClipPlan(
            clip_id="c", moment_id="m", source_id="s", target_platforms=[Platform.UNSUPPORTED],
            aspect_ratio="1", target_duration=10, hook_treatment="", caption_subtitle_strategy="",
            intro_outro_treatment="", cta_strategy="", title_caption_suggestions=[], editorial_notes="",
            estimated_editing_effort_hours=1.0, ai_generation_cost_estimate=1.0, human_review_cost_estimate=1.0,
            expected_quality_score=1.0, campaign_id=None, provenance_chain={"source": "a", "moment": "b"}, qa_requirements=[]
        )

def test_provenance_retention(valid_source, valid_moment):
    plans = plan_clip(valid_source, valid_moment, None, ["TikTok"])
    assert len(plans) == 1
    plan = plans[0]
    
    assert plan.provenance_chain["source"]["id"] == valid_source.source_id
    assert plan.provenance_chain["moment"]["id"] == valid_moment.moment_id

def test_duplicate_plan_prevention(valid_source, valid_moment):
    # Asking for "TikTok" and "tiktok" should only produce one plan
    plans = plan_clip(valid_source, valid_moment, None, ["TikTok", "tiktok"])
    assert len(plans) == 1

def test_invalid_moment_rejection(valid_source, valid_moment):
    valid_moment.confidence = MomentConfidence.LOW
    with pytest.raises(ValueError, match="Cannot plan clip for low confidence moment"):
        plan_clip(valid_source, valid_moment, None, ["TikTok"])
