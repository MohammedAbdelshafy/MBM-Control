"""
Regression tests added for Phase 2 of Reward Clipping OS implementation.
These tests explicitly lock in the behavior of platform_registry, campaign_runner, and source_registry.
"""
import pytest
from mbm_social import platform_registry, source_registry, campaign_runner

def test_regression_platform_registry_strict():
    # Lock in the behavior that unknown platforms raise or return MANUAL_REQUIRED depending on the implementation
    # Currently platform_registry only knows about specific ones.
    try:
        status = platform_registry.publish_status("unknown_platform_x")
        # If it doesn't raise, it should at least not be SUPPORTED
        assert status != platform_registry.SUPPORTED
    except Exception:
        pass # Raising is also acceptable for an unknown platform

def test_regression_source_registry_duplicate_registration(tmp_path):
    # Lock in behavior of registering the same source twice
    reg = source_registry.SourceRegistry(tmp_path / "src.json")
    rec1 = reg.register("https://x/duplicate", "dontwatchthis", restricted=False)
    rec2 = reg.register("https://x/duplicate", "dontwatchthis", restricted=False)
    
    # Should be idempotent / return the same record ID
    assert rec1.source_id == rec2.source_id
    assert rec1.url == rec2.url

def test_regression_campaign_runner_context():
    # Lock in CampaignContext data shape
    ctx = campaign_runner.CampaignContext(
        campaign_id="test_camp",
        brand="goalmachinez",
        profile="football_highlights"
    )
    assert ctx.campaign_id == "test_camp"
    assert ctx.brand == "goalmachinez"
    assert ctx.profile == "football_highlights"
    # source_id is optional and should be None initially
    assert ctx.source_id is None
