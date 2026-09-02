from typing import Protocol, List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class CapabilityStatus(Enum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_WITH_LIMITATIONS = "SUPPORTED_WITH_LIMITATIONS"
    MANUAL_ONLY = "MANUAL_ONLY"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"

@dataclass
class ProviderCapabilities:
    discover_campaigns: CapabilityStatus
    fetch_campaign: CapabilityStatus
    fetch_rules: CapabilityStatus
    fetch_budget: CapabilityStatus
    fetch_submission_requirements: CapabilityStatus
    submit_content: CapabilityStatus
    check_submission: CapabilityStatus
    fetch_metrics: CapabilityStatus
    fetch_payout_status: CapabilityStatus
    health_check: CapabilityStatus

class RewardProvider(Protocol):
    """
    Abstract interface for reward/campaign marketplaces.
    """
    
    @property
    def provider_id(self) -> str:
        """Unique identifier for the provider (e.g., 'whop', 'vyro')."""
        ...
        
    def get_capabilities(self) -> ProviderCapabilities:
        """Returns the officially supported capabilities of this provider adapter."""
        ...
        
    def discover_campaigns(self) -> List[Dict[str, Any]]:
        """Fetch list of available campaigns."""
        ...
        
    def fetch_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Fetch details for a specific campaign."""
        ...
        
    def fetch_rules(self, campaign_id: str) -> Dict[str, Any]:
        """Fetch the content, eligibility, and platform rules for a campaign."""
        ...
        
    def fetch_budget(self, campaign_id: str) -> Dict[str, Any]:
        """Fetch current budget status (total, remaining, velocity)."""
        ...
        
    def fetch_submission_requirements(self, campaign_id: str) -> Dict[str, Any]:
        """Fetch submission metadata requirements (e.g., hashtags, links)."""
        ...
        
    def submit_content(self, campaign_id: str, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a produced clip to the campaign."""
        ...
        
    def check_submission(self, submission_id: str) -> Dict[str, Any]:
        """Check the review/approval status of a submission."""
        ...
        
    def fetch_metrics(self, submission_id: str) -> Dict[str, Any]:
        """Fetch verified view metrics and performance."""
        ...
        
    def fetch_payout_status(self, submission_id: str) -> Dict[str, Any]:
        """Fetch financial status (validated, pending, paid)."""
        ...
        
    def health_check(self) -> bool:
        """Verify the provider API is reachable and authorized."""
        ...
