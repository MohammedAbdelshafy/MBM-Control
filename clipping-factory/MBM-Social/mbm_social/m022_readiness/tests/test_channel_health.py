"""Tests for M-022 channel health (read-only)."""
from ..channel_health import ChannelStatus, ChannelMatrixEntry, ChannelHealthChecker


def test_channel_status_values():
    assert ChannelStatus.VALID.value == "VALID"
    assert ChannelStatus.BLOCKED.value == "BLOCKED"
    assert ChannelStatus.MISSING_TOKEN.value == "MISSING_TOKEN"


def test_channel_matrix_default_publishing_blocked():
    from ..channel_health import ChannelMatrixEntry
    entry = ChannelMatrixEntry(
        channel_id="UCtest123",
        display_name="Test Channel",
        health="VALID",
    )
    assert entry.publishing_enabled is False  # BLOCKED by M-022 policy


def test_channel_health_checker_read_only():
    from ..channel_health import ChannelHealthChecker
    checker = ChannelHealthChecker()
    entries = checker.get_channel_entries(max_channels=5)
    # Should return exactly 5 entries (or fewer if registry has less, but filled to max)
    assert len(entries) <= 5
    assert len(entries) > 0  # At minimum empty entries exist
    for entry in entries:
        assert entry.publishing_enabled is False
