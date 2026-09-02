import pytest
from mbm_social.models.source import NormalizedSource, ProvenanceConfidence
from mbm_social.moment_discovery import CandidateMoment, MomentConfidence, DiscoveryMethod
from mbm_social.clip_planner import ClipPlan, Platform
from mbm_social.models.campaign import NormalizedCampaign, CampaignType, CampaignStatus
from mbm_social.economics import EconomicAssumptions
from mbm_social.campaign_ranking import Recommendation
from mbm_social.qa_gates import run_qa_gates

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

@pytest.fixture
def valid_plan(valid_source, valid_moment):
    return ClipPlan(
        clip_id="c", moment_id=valid_moment.moment_id, source_id=valid_source.source_id,
        target_platforms=[Platform.TIKTOK], aspect_ratio="9:16", target_duration=30,
        hook_treatment="", caption_subtitle_strategy="", intro_outro_treatment="", cta_strategy="",
        title_caption_suggestions=[], editorial_notes="", estimated_editing_effort_hours=1.0,
        ai_generation_cost_estimate=1.0, human_review_cost_estimate=1.0, expected_quality_score=1.0,
        campaign_id="test", provenance_chain={"source": valid_source.source_id, "moment": valid_moment.moment_id},
        qa_requirements=[]
    )

@pytest.fixture
def valid_campaign():
    return NormalizedCampaign(
        id="test", provider_id="test", provider_campaign_id="1", brand="b", topic="t", title="title",
        campaign_type=CampaignType.RETAINER, status=CampaignStatus.ACTIVE, budget_total=1000.0,
        budget_remaining=1000.0, payout_rate=100.0
    )

@pytest.fixture
def valid_assumptions():
    return EconomicAssumptions(human_hourly_rate_usd=0.0, ai_generation_cost_usd=0.0) # Ensure profit

def test_qa_all_pass(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.PRODUCE
    assert len(result.gate_failures) == 0

def test_qa_gate_a_failure(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_source.duration_seconds = -10
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REJECT
    assert any("Gate A" in f for f in result.gate_failures)

def test_qa_gate_b_failure(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_moment.end_seconds = 200 # Exceeds source duration of 120
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REJECT
    assert any("Gate B" in f for f in result.gate_failures)
    
def test_qa_gate_b_confidence_failure(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_moment.confidence = MomentConfidence.LOW
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REVIEW_REQUIRED
    assert any("Gate B: Insufficient confidence" in f for f in result.reasons)

def test_qa_gate_c_failure(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_plan.provenance_chain = {}
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REJECT
    assert any("Gate C: Missing provenance chain" in f for f in result.gate_failures)

def test_qa_gate_e_campaign_paused(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_campaign.status = CampaignStatus.PAUSED
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REJECT
    assert any("Gate E: Campaign is paused" in f for f in result.gate_failures)

def test_qa_gate_e_negative_profit(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    valid_assumptions.human_hourly_rate_usd = 1000.0 # Make profit negative
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REJECT
    assert any("Gate E: Expected profit is negative" in f for f in result.gate_failures)

def test_qa_review_required_margin(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions):
    # Set profit > 0 but < 20/hr
    valid_campaign.payout_rate = 10.0
    valid_assumptions.human_hourly_rate_usd = 5.0 
    # 10hrs * 5/hr = 50 cost + 0.5 ai = 50.5. Wait, default human hours = 1.
    # Cost = 1hr * 5 = 5.0. AI = 0. Profit = 10 - 5 = 5. 5/hr is < 20/hr
    
    result = run_qa_gates(valid_source, valid_moment, valid_plan, valid_campaign, valid_assumptions)
    assert result.recommendation == Recommendation.REVIEW_REQUIRED
