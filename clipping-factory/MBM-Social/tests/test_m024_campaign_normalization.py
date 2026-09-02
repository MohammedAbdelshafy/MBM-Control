import pytest
from mbm_social.models.campaign import (
    normalize_provider_campaign,
    CampaignType,
    CampaignStatus,
    NormalizedCampaign
)

def test_normalization_cpm_campaign():
    raw_data = {
        "brand": "Nike",
        "topic": "shoes",
        "title": "Air Max Promo",
        "type": "cpm",
        "status": "active",
        "budget_total": 5000.0,
        "budget_remaining": 4000.0,
        "payout_rate": 2.50, # $2.50 CPM
        "min_duration_s": 20,
        "max_duration_s": 60,
        "provider_specific_field": "some_value"
    }
    
    camp = normalize_provider_campaign("whop", "camp_123", raw_data)
    assert camp.id == "whop_camp_123"
    assert camp.campaign_type == CampaignType.CPM
    assert camp.status == CampaignStatus.ACTIVE
    assert camp.budget_total == 5000.0
    assert camp.budget_remaining == 4000.0
    assert camp.payout_rate == 2.50
    assert camp.brand == "Nike"
    assert camp.raw_provider_data["provider_specific_field"] == "some_value"
    assert camp.min_duration_s == 20
    assert camp.max_duration_s == 60

def test_normalization_per_post_campaign():
    raw_data = {
        "brand_id": "Adidas",
        "type": "PER_POST",
        "payout_rate": 50.0, # $50 per post
    }
    
    camp = normalize_provider_campaign("whop", "camp_456", raw_data)
    assert camp.campaign_type == CampaignType.PER_POST
    assert camp.brand == "Adidas"
    assert camp.payout_rate == 50.0

def test_normalization_retainer_campaign():
    raw_data = {
        "brand": "Puma",
        "type": "RETAINER",
        "payout_rate": 1000.0, # $1000 flat
    }
    
    camp = normalize_provider_campaign("agency", "camp_789", raw_data)
    assert camp.campaign_type == CampaignType.RETAINER
    assert camp.payout_rate == 1000.0

def test_normalization_missing_optional_fields():
    raw_data = {
        "brand": "Reebok"
        # No type, budget, etc.
    }
    camp = normalize_provider_campaign("whop", "camp_000", raw_data)
    assert camp.campaign_type == CampaignType.CPM # Default
    assert camp.budget_total == 0.0
    assert camp.min_duration_s == 15 # Default
    assert camp.max_duration_s == 90 # Default

def test_normalization_malformed_data_missing_brand():
    raw_data = {
        "type": "CPM"
    }
    with pytest.raises(ValueError, match="Campaign must have a brand"):
        normalize_provider_campaign("whop", "camp_111", raw_data)

def test_normalization_malformed_negative_budget():
    raw_data = {
        "brand": "Test",
        "budget_total": -100
    }
    with pytest.raises(ValueError, match="Budget total cannot be negative"):
        normalize_provider_campaign("whop", "camp_222", raw_data)

def test_normalization_malformed_duration():
    raw_data = {
        "brand": "Test",
        "min_duration_s": 90,
        "max_duration_s": 15
    }
    with pytest.raises(ValueError, match="min_duration_s cannot be greater than max_duration_s"):
        normalize_provider_campaign("whop", "camp_333", raw_data)

def test_normalization_invalid_type():
    raw_data = {
        "brand": "Test",
        "type": "UNKNOWN_TYPE"
    }
    with pytest.raises(ValueError, match="Invalid campaign type: UNKNOWN_TYPE"):
        normalize_provider_campaign("whop", "camp_444", raw_data)
