import pytest
from mbm_social.models.campaign import normalize_provider_campaign
from mbm_social.models.snapshot import CampaignSnapshot, detect_changes, ChangeType

@pytest.fixture
def base_campaign():
    raw = {
        "brand": "Nike",
        "type": "CPM",
        "status": "ACTIVE",
        "budget_total": 5000.0,
        "payout_rate": 2.50,
        "min_duration_s": 20,
        "max_duration_s": 60,
        "required_hashtags": ["#nike", "#justdoit"]
    }
    return normalize_provider_campaign("whop", "123", raw)

def test_snapshot_unchanged(base_campaign):
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    assert len(changes) == 0

def test_snapshot_budget_increase(base_campaign):
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.budget_total = 6000.0
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.BUDGET_INCREASE

def test_snapshot_budget_decrease(base_campaign):
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.budget_total = 4000.0
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.BUDGET_DECREASE

def test_snapshot_cpm_change(base_campaign):
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.payout_rate = 3.00
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.CPM_CHANGE

def test_snapshot_rule_change(base_campaign):
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.required_hashtags.append("#new")
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.RULE_CHANGE

def test_snapshot_status_change_to_closed(base_campaign):
    from mbm_social.models.campaign import CampaignStatus
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.status = CampaignStatus.CLOSED
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    # It should emit STATUS_CHANGE and CAMPAIGN_CLOSURE
    change_types = [c.change_type for c in changes]
    assert ChangeType.STATUS_CHANGE in change_types
    assert ChangeType.CAMPAIGN_CLOSURE in change_types

def test_snapshot_status_change_reopen(base_campaign):
    from mbm_social.models.campaign import CampaignStatus
    base_campaign.status = CampaignStatus.CLOSED
    snap1 = CampaignSnapshot.from_campaign(base_campaign, "snap_1")
    
    base_campaign.status = CampaignStatus.ACTIVE
    snap2 = CampaignSnapshot.from_campaign(base_campaign, "snap_2")
    
    changes = detect_changes(snap1, snap2)
    # It should emit STATUS_CHANGE and CAMPAIGN_REOPENING
    change_types = [c.change_type for c in changes]
    assert ChangeType.STATUS_CHANGE in change_types
    assert ChangeType.CAMPAIGN_REOPENING in change_types
