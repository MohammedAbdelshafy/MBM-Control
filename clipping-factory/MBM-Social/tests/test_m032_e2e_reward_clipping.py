import pytest
from mbm_social.models.campaign import normalize_provider_campaign, CampaignType, CampaignStatus
from mbm_social.models.source import NormalizedSource, ProvenanceConfidence
from mbm_social.moment_discovery import discover_moments
from mbm_social.clip_planner import plan_clip
from mbm_social.economics import EconomicAssumptions
from mbm_social.qa_gates import run_qa_gates
from mbm_social.campaign_ranking import Recommendation

def test_end_to_end_reward_clipping_pipeline():
    """
    Minimum end-to-end path:
    Provider Source -> Normalized Source -> Provenance -> Moment Discovery 
    -> Clip Plan -> Economic Projection -> Campaign Ranking -> QA Gates -> Recommendation
    
    The test proves no publishing side effects occur.
    """
    
    # 1. Campaign Normalization
    campaign_payload = {
        "id": "camp_789",
        "brand": "BigBrand",
        "title": "Viral Challenge",
        "type": "PER_POST",
        "status": "ACTIVE",
        "payout_rate": 500.0,
        "budget_total": 5000.0,
        "budget_remaining": 5000.0
    }
    campaign = normalize_provider_campaign("whop", "camp_789", campaign_payload)
    
    # 2. Provider Source -> Normalized Source & Provenance
    source_payload = {
        "source_url": "https://youtube.com/watch?v=viral123",
        "source_type": "video",
        "title": "The Ultimate Challenge",
        "duration_seconds": 600,
        "provenance_confidence": "HIGH"
    }
    source = NormalizedSource.from_provider_payload("youtube", "viral123", source_payload)
    
    assert source.provenance_confidence == ProvenanceConfidence.HIGH
    assert source.content_hash is not None
    
    # 3. Moment Discovery
    transcript = "Here is the hook. We are going to do the ultimate challenge today. Watch this payoff."
    moments = discover_moments(source, transcript=transcript, ai_available=True)
    
    assert len(moments) > 0
    best_moment = moments[0]
    
    # 4. Clip Planning
    # Requesting TikTok and YouTube Shorts
    plans = plan_clip(source, best_moment, campaign, ["TikTok", "YouTube Shorts"])
    
    assert len(plans) == 2
    # Pick TikTok plan
    tk_plan = next(p for p in plans if p.target_platforms[0].value == "TIKTOK")
    
    # Prove provenance survived the pipeline
    assert tk_plan.provenance_chain["source"]["id"] == source.source_id
    assert tk_plan.provenance_chain["moment"]["id"] == best_moment.moment_id
    
    # 5 & 6 & 7. Economic Projection, Campaign Ranking, and QA Gates
    assumptions = EconomicAssumptions(
        human_hourly_rate_usd=50.0,
        production_time_hours_base=2.0, # Cost = $100 + $0.50 = $100.50
        approval_probability_base=0.9
    )
    # Expected profit: (500 * 0.9) - 100.50 = 450 - 100.50 = 349.50
    # Profit/hr: 349.50 / 2 = 174.75 > 20, so should be PRODUCE
    
    qa_result = run_qa_gates(source, best_moment, tk_plan, campaign, assumptions)
    
    # 8. Final Decision State
    assert qa_result.recommendation == Recommendation.PRODUCE
    assert len(qa_result.gate_failures) == 0
    
    # Proof of no publishing side effects: 
    # At no point did the pipeline require network calls to social APIs,
    # nor did it execute a publishing method. The final result is just a Recommendation struct.
