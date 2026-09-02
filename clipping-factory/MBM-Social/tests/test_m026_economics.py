import pytest
from mbm_social.models.campaign import NormalizedCampaign, CampaignType, CampaignStatus
from mbm_social.economics import (
    calculate_economics, 
    EconomicAssumptions, 
    Scenario
)

@pytest.fixture
def base_cpm_campaign():
    return NormalizedCampaign(
        id="test_1",
        provider_id="test",
        provider_campaign_id="1",
        brand="BrandA",
        topic="t",
        title="title",
        campaign_type=CampaignType.CPM,
        status=CampaignStatus.ACTIVE,
        budget_total=1000.0,
        budget_remaining=1000.0,
        payout_rate=5.0 # $5 CPM
    )

def test_economics_cpm_base(base_cpm_campaign):
    assumptions = EconomicAssumptions(
        estimated_views_base=10000.0, # 10k views
        production_time_hours_base=1.0, # 1 hr
        human_hourly_rate_usd=20.0,
        ai_generation_cost_usd=0.0,
        platform_fixed_cost_usd=0.0,
        approval_probability_base=1.0,
        provider_fee_rate=0.0
    )
    results = calculate_economics(base_cpm_campaign, assumptions)
    base_res = results[Scenario.BASE]
    
    # 10k views @ $5 CPM = $50 gross
    assert base_res.gross_expected_revenue == 50.0
    assert base_res.total_cost == 20.0
    assert base_res.expected_profit == 30.0
    assert base_res.profit_per_hour == 30.0

def test_economics_per_post():
    camp = NormalizedCampaign(
        id="test_2",
        provider_id="test",
        provider_campaign_id="2",
        brand="BrandB",
        topic="t",
        title="title",
        campaign_type=CampaignType.PER_POST,
        status=CampaignStatus.ACTIVE,
        budget_total=500.0,
        budget_remaining=500.0,
        payout_rate=150.0 # $150 per post
    )
    
    assumptions = EconomicAssumptions(
        production_time_hours_base=2.0,
        human_hourly_rate_usd=25.0,
        ai_generation_cost_usd=5.0,
        approval_probability_base=0.8,
        provider_fee_rate=0.10 # 10% fee
    )
    
    res = calculate_economics(camp, assumptions)[Scenario.BASE]
    
    assert res.gross_expected_revenue == 150.0
    assert res.provider_fees == 15.0
    assert res.net_revenue == 135.0
    assert res.total_cost == 55.0 # 2*25 + 5
    # Risk adjusted revenue: 135 * 0.8 = 108
    # Profit: 108 - 55 = 53
    assert res.expected_profit == 53.0
    assert res.profit_per_hour == 26.5 # 53 / 2

def test_economics_retainer():
    camp = NormalizedCampaign(
        id="test_3",
        provider_id="test",
        provider_campaign_id="3",
        brand="BrandC",
        topic="t",
        title="title",
        campaign_type=CampaignType.RETAINER,
        status=CampaignStatus.ACTIVE,
        budget_total=2000.0,
        budget_remaining=2000.0,
        payout_rate=2000.0
    )
    
    assumptions = EconomicAssumptions(
        production_time_hours_base=10.0,
        human_hourly_rate_usd=30.0,
        approval_probability_base=1.0
    )
    
    res = calculate_economics(camp, assumptions)[Scenario.BASE]
    assert res.gross_expected_revenue == 2000.0
    assert res.expected_profit == 1699.5 # 2000 - 300.5

def test_economics_budget_cap(base_cpm_campaign):
    # Campaign only has $10 remaining, but views would yield $50
    base_cpm_campaign.budget_remaining = 10.0
    assumptions = EconomicAssumptions(
        estimated_views_base=10000.0, 
        approval_probability_base=1.0
    )
    res = calculate_economics(base_cpm_campaign, assumptions)[Scenario.BASE]
    
    # Revenue is capped at the remaining budget
    assert res.gross_expected_revenue == 10.0

def test_economics_zero_views(base_cpm_campaign):
    assumptions = EconomicAssumptions(
        estimated_views_pessimistic=0.0
    )
    res = calculate_economics(base_cpm_campaign, assumptions)[Scenario.PESSIMISTIC]
    assert res.gross_expected_revenue == 0.0

def test_economics_invalid_negative_rates(base_cpm_campaign):
    base_cpm_campaign.payout_rate = -5.0
    with pytest.raises(ValueError, match="cannot be less than 0.0"):
        calculate_economics(base_cpm_campaign)
        
def test_economics_invalid_negative_budget(base_cpm_campaign):
    base_cpm_campaign.budget_remaining = -5.0
    with pytest.raises(ValueError, match="cannot be less than 0.0"):
        calculate_economics(base_cpm_campaign)
