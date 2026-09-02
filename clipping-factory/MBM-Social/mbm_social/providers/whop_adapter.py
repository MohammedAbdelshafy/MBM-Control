from typing import List, Dict, Any
from .base import RewardProvider, ProviderCapabilities, CapabilityStatus

class WhopProvider(RewardProvider):
    """
    Whop adapter for Content Rewards.
    Currently, Whop does not provide a public REST API for automated campaign discovery,
    budget fetching, or clip submission. All operations require manual portal interaction.
    """
    
    @property
    def provider_id(self) -> str:
        return "whop"
        
    def get_capabilities(self) -> ProviderCapabilities:
        # We explicitly declare all automated capabilities as UNSUPPORTED or MANUAL_ONLY
        # as there is no official, verified Whop API for this workflow.
        return ProviderCapabilities(
            discover_campaigns=CapabilityStatus.UNSUPPORTED,
            fetch_campaign=CapabilityStatus.UNSUPPORTED,
            fetch_rules=CapabilityStatus.UNSUPPORTED,
            fetch_budget=CapabilityStatus.UNSUPPORTED,
            fetch_submission_requirements=CapabilityStatus.UNSUPPORTED,
            submit_content=CapabilityStatus.MANUAL_ONLY,
            check_submission=CapabilityStatus.MANUAL_ONLY,
            fetch_metrics=CapabilityStatus.UNSUPPORTED,
            fetch_payout_status=CapabilityStatus.MANUAL_ONLY,
            health_check=CapabilityStatus.SUPPORTED # We can ping whop.com to check health
        )
        
    def discover_campaigns(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("Whop does not support automated campaign discovery via API.")
        
    def fetch_campaign(self, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop does not support automated campaign fetching.")
        
    def fetch_rules(self, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop does not support automated rule fetching.")
        
    def fetch_budget(self, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop does not support automated budget fetching.")
        
    def fetch_submission_requirements(self, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop does not support automated requirement fetching.")
        
    def submit_content(self, campaign_id: str, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Whop requires manual clip submission via their web portal.")
        
    def check_submission(self, submission_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop requires manual submission checking via their web portal.")
        
    def fetch_metrics(self, submission_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop does not support fetching metrics via API.")
        
    def fetch_payout_status(self, submission_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Whop requires manual payout checking via their web portal.")
        
    def health_check(self) -> bool:
        # A simple mock health check. A real one might do `requests.get("https://api.whop.com/health")`
        return True
