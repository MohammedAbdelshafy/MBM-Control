import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

from .campaign import NormalizedCampaign, CampaignStatus

class ChangeType(Enum):
    BUDGET_INCREASE = "BUDGET_INCREASE"
    BUDGET_DECREASE = "BUDGET_DECREASE"
    CPM_CHANGE = "CPM_CHANGE"
    RULE_CHANGE = "RULE_CHANGE"
    STATUS_CHANGE = "STATUS_CHANGE"
    CAMPAIGN_CLOSURE = "CAMPAIGN_CLOSURE"
    CAMPAIGN_REOPENING = "CAMPAIGN_REOPENING"

@dataclass
class CampaignChange:
    change_type: ChangeType
    old_value: Any
    new_value: Any
    message: str

def compute_rules_hash(campaign: NormalizedCampaign) -> str:
    """
    Computes a deterministic hash for rules and requirements.
    """
    # Create a stable dictionary of rules
    rules_dict = {
        "min_duration_s": campaign.min_duration_s,
        "max_duration_s": campaign.max_duration_s,
        "required_hashtags": sorted(campaign.required_hashtags),
        "required_mentions": sorted(campaign.required_mentions),
    }
    
    # Serialize to stable JSON string
    rules_json = json.dumps(rules_dict, sort_keys=True)
    return hashlib.sha256(rules_json.encode("utf-8")).hexdigest()

@dataclass
class CampaignSnapshot:
    """
    An immutable historical snapshot of a campaign.
    """
    id: str
    campaign_id: str
    timestamp_iso: str
    
    status: CampaignStatus
    budget_total: float
    budget_remaining: float
    payout_rate: float
    
    rules_hash: str
    expires_at_iso: Optional[str]
    
    @classmethod
    def from_campaign(cls, campaign: NormalizedCampaign, snapshot_id: str) -> "CampaignSnapshot":
        return cls(
            id=snapshot_id,
            campaign_id=campaign.id,
            timestamp_iso=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            status=campaign.status,
            budget_total=campaign.budget_total,
            budget_remaining=campaign.budget_remaining,
            payout_rate=campaign.payout_rate,
            rules_hash=compute_rules_hash(campaign),
            expires_at_iso=campaign.expires_at_iso
        )

def detect_changes(old_snapshot: Optional[CampaignSnapshot], new_snapshot: CampaignSnapshot) -> List[CampaignChange]:
    """
    Compares two snapshots and returns a list of detected changes.
    """
    if not old_snapshot:
        return []
        
    changes = []
    
    if new_snapshot.budget_total > old_snapshot.budget_total:
        changes.append(CampaignChange(
            change_type=ChangeType.BUDGET_INCREASE,
            old_value=old_snapshot.budget_total,
            new_value=new_snapshot.budget_total,
            message=f"Total budget increased from {old_snapshot.budget_total} to {new_snapshot.budget_total}"
        ))
    elif new_snapshot.budget_total < old_snapshot.budget_total:
        changes.append(CampaignChange(
            change_type=ChangeType.BUDGET_DECREASE,
            old_value=old_snapshot.budget_total,
            new_value=new_snapshot.budget_total,
            message=f"Total budget decreased from {old_snapshot.budget_total} to {new_snapshot.budget_total}"
        ))
        
    if new_snapshot.payout_rate != old_snapshot.payout_rate:
        changes.append(CampaignChange(
            change_type=ChangeType.CPM_CHANGE,
            old_value=old_snapshot.payout_rate,
            new_value=new_snapshot.payout_rate,
            message=f"Payout rate changed from {old_snapshot.payout_rate} to {new_snapshot.payout_rate}"
        ))
        
    if new_snapshot.rules_hash != old_snapshot.rules_hash:
        changes.append(CampaignChange(
            change_type=ChangeType.RULE_CHANGE,
            old_value=old_snapshot.rules_hash,
            new_value=new_snapshot.rules_hash,
            message="Campaign rules or requirements have changed"
        ))
        
    if new_snapshot.status != old_snapshot.status:
        changes.append(CampaignChange(
            change_type=ChangeType.STATUS_CHANGE,
            old_value=old_snapshot.status.value,
            new_value=new_snapshot.status.value,
            message=f"Status changed from {old_snapshot.status.value} to {new_snapshot.status.value}"
        ))
        
        if old_snapshot.status == CampaignStatus.ACTIVE and new_snapshot.status == CampaignStatus.CLOSED:
            changes.append(CampaignChange(
                change_type=ChangeType.CAMPAIGN_CLOSURE,
                old_value=old_snapshot.status.value,
                new_value=new_snapshot.status.value,
                message="Campaign has been closed"
            ))
        elif old_snapshot.status == CampaignStatus.CLOSED and new_snapshot.status == CampaignStatus.ACTIVE:
            changes.append(CampaignChange(
                change_type=ChangeType.CAMPAIGN_REOPENING,
                old_value=old_snapshot.status.value,
                new_value=new_snapshot.status.value,
                message="Campaign has been reopened"
            ))
            
    return changes
