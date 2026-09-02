import pytest
from mbm_social.providers.base import CapabilityStatus
from mbm_social.providers.whop_adapter import WhopProvider

def test_provider_contract_unsupported_capability():
    provider = WhopProvider()
    assert provider.provider_id == "whop"
    
    caps = provider.get_capabilities()
    assert caps.discover_campaigns == CapabilityStatus.UNSUPPORTED
    assert caps.submit_content == CapabilityStatus.MANUAL_ONLY
    assert caps.health_check == CapabilityStatus.SUPPORTED

def test_provider_contract_raises_on_unsupported():
    provider = WhopProvider()
    with pytest.raises(NotImplementedError, match="Whop does not support automated campaign discovery"):
        provider.discover_campaigns()

def test_provider_contract_health_check():
    provider = WhopProvider()
    assert provider.health_check() is True

def test_provider_contract_error_handling():
    # If a provider encounters an API error, it should raise appropriately.
    # For now, Whop just raises NotImplementedError for all fetch actions.
    provider = WhopProvider()
    with pytest.raises(NotImplementedError):
        provider.fetch_budget("camp_123")
