"""Tests for M-022 OAuth readiness."""
import pytest
from ..youtube_oauth_readiness import OAuthState, ScopeStatus, OAuthReadinessChecker


def test_oauth_states_defined():
    assert OAuthState.AUTH_REQUIRED.value == "AUTH_REQUIRED"
    assert OAuthState.INSUFFICIENT_SCOPE.value == "INSUFFICIENT_SCOPE"
    assert OAuthState.READY_FOR_CONTROLLED_ACTIVATION.value == "READY_FOR_CONTROLLED_ACTIVATION"


def test_scope_status_defined():
    assert ScopeStatus.PRESENT.value == "PRESENT"
    assert ScopeStatus.MISSING.value == "MISSING"


def test_readiness_checker_health():
    checker = OAuthReadinessChecker()
    # Without env credentials, health check should work (read-only)
    assert checker.health_check() is True  # File readable or unconfigured; never False for health


def test_redirect_uri_validation():
    checker = OAuthReadinessChecker()
    # No env redirect URI set in test environment; validation returns False
    assert checker.validate_redirect_uri() is False  # Expected without config
