import os
import pytest
from MBM.LeadEngine.intelligence.provider_policy import assert_allowed, ProviderBlocked, ProviderGated, ProviderResearchOnly

def test_worldmonitor_allowed():
    assert_allowed("worldmonitor")

def test_blocked_providers_always_block():
    for p in ("vidbox_dev", "ankergames", "voxcpm_net", "vidbox.dev", "voxcpm.net"):
        with pytest.raises(ProviderBlocked):
            assert_allowed(p)

def test_unknown_defaults_to_blocked():
    with pytest.raises(ProviderBlocked):
        assert_allowed("totally_unknown_provider_xyz")

def test_research_only_blocks_production():
    with pytest.raises(ProviderResearchOnly):
        assert_allowed("famelack", purpose="production")
    # non-production purpose is allowed to read
    assert_allowed("famelack", purpose="research")

def test_voxcpm_gated_by_default():
    os.environ.pop("VOXCPM_ENABLED", None)
    with pytest.raises(ProviderGated):
        assert_allowed("voxcpm_official")
    os.environ["VOXCPM_ENABLED"] = "true"
    try:
        assert_allowed("voxcpm_official")
    finally:
        os.environ.pop("VOXCPM_ENABLED", None)

def test_allow_pending_verification_passes_gate():
    # these are allowed_pending_verification -> gate passes
    for p in ("anderro", "topview", "skysnail"):
        assert_allowed(p)
