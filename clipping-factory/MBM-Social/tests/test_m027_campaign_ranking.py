import pytest
from datetime import datetime, timezone, timedelta
from mbm_social.models.campaign import NormalizedCampaign, CampaignType, CampaignStatus
from mbm_social.economics import EconomicAssumptions
from mbm_social.campaign_ranking import rank_campaign, Recommendation, RiskLevel

def test_ranking_high_budget_vs_cpm():
    camp = NormalizedCampaign(
        id="test_1",
        provider_id="test",
        provider_campaign_id="1",
        brand="BrandA",
        topic="t",
        title="High Budget",
        campaign_type=CampaignType.CPM,
        status=CampaignStatus.ACTIVE,
        budget_total=20000.0,
        budget_remaining=20000.0,
        payout_rate=2.0 # $2 CPM
    )
    
    assumptions = EconomicAssumptions(
        estimated_views_base=100000.0, # 100k views * 2 CPM = $200
        approval_probability_base=0.9
    )
    
    res = rank_campaign(camp, assumptions)
    assert res.recommendation in [Recommendation.PRODUCE, Recommendation.REVIEW_REQUIRED]
    assert "Strong remaining budget" in res.reasons

def test_ranking_high_profit_per_hour():
    camp = NormalizedCampaign(
        id="test_2",
        provider_id="test",
        provider_campaign_id="2",
        brand="BrandB",
        topic="t",
        title="High Profit",
        campaign_type=CampaignType.PER_POST,
        status=CampaignStatus.ACTIVE,
        budget_total=1000.0,
        budget_remaining=1000.0,
        payout_rate=500.0 # $500 per post
    )
    
    assumptions = EconomicAssumptions(
        production_time_hours_base=1.0,
        human_hourly_rate_usd=50.0,
        approval_probability_base=1.0
    )
    
    res = rank_campaign(camp, assumptions)
    assert res.priority_score > 80
    assert "High expected profit/hour" in res.reasons
    assert res.recommendation == Recommendation.PRODUCE

def test_ranking_campaign_expiring():
    exp_date = datetime.now(timezone.utc) + timedelta(days=3)
    camp = NormalizedCampaign(
        id="test_3",
        provider_id="test",
        provider_campaign_id="3",
        brand="BrandC",
        topic="t",
        title="Expiring",
        campaign_type=CampaignType.PER_POST,
        status=CampaignStatus.ACTIVE,
        budget_total=100.0,
        budget_remaining=100.0,
        payout_rate=50.0,
        expires_at_iso=exp_date.isoformat()
    )
    
    assumptions = EconomicAssumptions(
        approval_probability_base=0.9
    )
    
    res = rank_campaign(camp, assumptions)
    assert any("expires soon" in reason for reason in res.reasons)

def test_ranking_high_risk_and_low_approval():
    camp = NormalizedCampaign(
        id="test_4",
        provider_id="test",
        provider_campaign_id="4",
        brand="BrandD",
        topic="t",
        title="High Risk",
        campaign_type=CampaignType.CPM,
        status=CampaignStatus.ACTIVE,
        budget_total=1000.0,
        budget_remaining=1000.0,
        payout_rate=5.0
    )
    
    assumptions = EconomicAssumptions(
        approval_probability_base=0.4 # 40% chance of getting paid
    )
    
    res = rank_campaign(camp, assumptions)
    assert res.risk_level == RiskLevel.HIGH
    assert any("approval risk is high" in warning for warning in res.warnings)

def test_ranking_insufficient_budget():
    camp = NormalizedCampaign(
        id="test_5",
        provider_id="test",
        provider_campaign_id="5",
        brand="BrandE",
        topic="t",
        title="Low Budget",
        campaign_type=CampaignType.CPM,
        status=CampaignStatus.ACTIVE,
        budget_total=100.0,
        budget_remaining=5.0, # only $5 left
        payout_rate=5.0
    )
    
    assumptions = EconomicAssumptions(
        estimated_views_base=100000.0, # 100k views = $500 expected
        approval_probability_base=1.0
    )
    
    res = rank_campaign(camp, assumptions)
    assert any("budget is running low" in warning for warning in res.warnings)

def test_ranking_inactive_campaign():
    camp = NormalizedCampaign(
        id="test_6",
        provider_id="test",
        provider_campaign_id="6",
        brand="BrandF",
        topic="t",
        title="Inactive",
        campaign_type=CampaignType.CPM,
        status=CampaignStatus.PAUSED,
        budget_total=100.0,
        budget_remaining=100.0,
        payout_rate=5.0
    )
    
    res = rank_campaign(camp)
    assert res.recommendation == Recommendation.REJECT
    assert "Campaign is not ACTIVE" in res.warnings
