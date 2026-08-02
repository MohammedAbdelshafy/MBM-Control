"""
Unit tests for agent logic — scoring, parsing, candidate generation.
Tests focus on pure logic without external dependencies.
"""
import pytest


def test_opportunity_score_high_pay():
    from app.agents.campaign_intelligence import CampaignIntelligenceAgent
    agent = CampaignIntelligenceAgent(db=None)
    score = agent._score_opportunity({
        "payment_per_clip": 50,
        "difficulty": "easy",
        "platform": "TikTok",
        "duration_max": 60,
    })
    assert score > 0.7


def test_opportunity_score_low_pay():
    from app.agents.campaign_intelligence import CampaignIntelligenceAgent
    agent = CampaignIntelligenceAgent(db=None)
    score = agent._score_opportunity({
        "payment_per_clip": 0,
        "difficulty": "hard",
    })
    assert score < 0.5


def test_opportunity_score_expired():
    from app.agents.campaign_intelligence import CampaignIntelligenceAgent
    agent = CampaignIntelligenceAgent(db=None)
    score = agent._score_opportunity({
        "payment_per_clip": 100,
        "due_date": "2020-01-01",  # Past date
    })
    assert score < 0.4


def test_detect_source_type_youtube():
    from app.agents.content_acquisition import ContentAcquisitionAgent
    agent = ContentAcquisitionAgent(db=None)
    assert agent._detect_source_type("https://www.youtube.com/watch?v=abc123") == "youtube"
    assert agent._detect_source_type("https://youtu.be/abc123") == "youtube"


def test_detect_source_type_gdrive():
    from app.agents.content_acquisition import ContentAcquisitionAgent
    agent = ContentAcquisitionAgent(db=None)
    assert agent._detect_source_type("https://drive.google.com/file/d/abc/view") == "gdrive"


def test_detect_source_type_dropbox():
    from app.agents.content_acquisition import ContentAcquisitionAgent
    agent = ContentAcquisitionAgent(db=None)
    assert agent._detect_source_type("https://www.dropbox.com/s/abc/video.mp4?dl=0") == "dropbox"


def test_detect_source_type_direct():
    from app.agents.content_acquisition import ContentAcquisitionAgent
    agent = ContentAcquisitionAgent(db=None)
    assert agent._detect_source_type("https://example.com/video.mp4") == "direct"


def test_candidate_deduplication():
    from app.agents.content_analysis import ContentAnalysisAgent
    agent = ContentAnalysisAgent(db=None)
    candidates = [
        {"start": 10.0, "end": 70.0, "duration": 60.0, "score": 0.9, "type": "hook", "reason": ""},
        {"start": 12.0, "end": 68.0, "duration": 56.0, "score": 0.7, "type": "hook", "reason": ""},  # overlaps 90%
        {"start": 200.0, "end": 260.0, "duration": 60.0, "score": 0.8, "type": "story_arc", "reason": ""},
    ]
    deduped = agent._deduplicate_candidates(candidates)
    assert len(deduped) == 2
    # Higher score should survive
    assert deduped[0]["score"] == 0.9


def test_srt_timestamp_format():
    from app.agents.editing_agent import EditingAgent
    agent = EditingAgent(db=None)
    assert agent._ts(0.0) == "00:00:00,000"
    assert agent._ts(61.5) == "00:01:01,500"
    assert agent._ts(3661.123) == "01:01:01,123"


def test_caption_style_string():
    from app.agents.editing_agent import EditingAgent
    agent = EditingAgent(db=None)
    style = agent._caption_style_string("bold_white")
    assert "FontName" in style
    assert "Bold=1" in style


def test_views_likes_milestones_logic():
    from app.agents.views_likes_milestones_agent import ViewsLikesMilestonesAgent
    agent = ViewsLikesMilestonesAgent(db=None)
    assert len(agent.VIEW_MILESTONES) == 10
    assert len(agent.LIKE_MILESTONES) == 7
    assert agent.VIEW_MILESTONES[0]["threshold"] == 1000
    assert agent.LIKE_MILESTONES[2]["label"] == "1K Likes"

