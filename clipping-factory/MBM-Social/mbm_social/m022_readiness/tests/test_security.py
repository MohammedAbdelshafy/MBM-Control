"""Tests for M-022 security (no secrets in source)."""
from ..security_config import SecurityConfig


def test_security_config_check_env():
    config = SecurityConfig()
    result = config.check_env_secrets()
    # In test environment, most env keys are missing; result should report that clearly
    assert "missing_env_keys" in result or "present_env_keys" in result
    assert isinstance(result["all_configured"], bool)


def test_token_storage_location_checked():
    config = SecurityConfig()
    info = config.verify_token_storage_location()
    assert "exists" in info
    assert info["exists"] is True or info["exists"] is False  # Either is valid; we check structure
    assert "production_recommendation" in info


def test_security_config_no_panics():
    # Ensure security_config module loads without errors and doesn't crash
    config = SecurityConfig()
    assert config is not None
