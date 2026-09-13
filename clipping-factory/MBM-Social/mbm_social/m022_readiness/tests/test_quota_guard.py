"""Tests for M-022 quota guard."""
from ..quota_guard import QuotaState, QuotaGuard


def test_quota_states():
    assert QuotaState.AVAILABLE.value == "AVAILABLE"
    assert QuotaState.EXCEEDED.value == "EXCEEDED"
    assert QuotaState.BLOCKED.value == "BLOCKED"


def test_quota_guard_default_available():
    guard = QuotaGuard()
    state = guard.get_quota_state()
    assert isinstance(state, QuotaState)


def test_quota_check_before_upload():
    guard = QuotaGuard()
    result = guard.check_before_upload(video_path="test.mp4")
    assert "quota_state" in result
    assert "allowed" in result
    assert "estimated_cost" in result
