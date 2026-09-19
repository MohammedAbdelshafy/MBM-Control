"""Tests for M-022 dry-run and upload policy (updated for state-machine contract)."""
from ..dry_run_campaign import DryRunCampaign
from ..upload_policy import UploadPolicy, UploadGate, IdempotencyEngine, IdempotencyState


def test_dry_run_public_blocked():
    campaign = DryRunCampaign()
    result = campaign.build(
        campaign_id="test_001",
        video_path="video.mp4",
        title="Test",
        description="Desc",
        tags=["test"],
        privacy_status="public",
        channel_id="UCtest",
    )
    assert result.privacy_status == "public"
    assert result.would_upload is False
    assert result.upload_blocked_reason is not None
    assert result.publish_enabled is False


def test_dry_run_private_allowed():
    campaign = DryRunCampaign()
    result = campaign.build(
        campaign_id="test_002",
        video_path="video.mp4",
        title="Test",
        description="Desc",
        tags=["test"],
        privacy_status="private",
    )
    assert result.privacy_status == "private"
    assert result.idempotency_key.startswith("test_002")
    assert result.expected_quota_cost > 0


def test_upload_policy_gate_blocked():
    policy = UploadPolicy(gate_state=UploadGate.BLOCKED)
    result = policy.check_upload_allowed(
        campaign_id="test_003", video_path="video.mp4", title="T", privacy_status="public"
    )
    assert result["allowed"] is False
    assert "BLOCKED" in result["reason"]


def test_idempotency_contract():
    import tempfile, os, pathlib
    # Never delete or mutate the production idempotency store.
    # Use isolated temporary storage for this test only.
    persistent = pathlib.Path("metrics/idempotency_store.json")
    # Verify persistent file untouched (if exists, must not be deleted)
    persistent_exists_before = persistent.exists()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = f.name
    try:
        from ..upload_policy import IdempotencyEngine, IdempotencyState
        eng = IdempotencyEngine(storage_path=temp_path)
        key = eng.generate_key(campaign_id="contract", title="t", privacy_status="private")
        # First call: RESERVED
        assert eng.register(key) is True
        assert eng.get_state(key) == IdempotencyState.RESERVED.value
        # Second call on RESERVED: retry allowed (updates to IN_PROGRESS)
        assert eng.register(key) is True
        assert eng.get_state(key) == IdempotencyState.IN_PROGRESS.value
        # After SUCCEEDED: duplicate prevented
        eng.set_state(key, IdempotencyState.SUCCEEDED)
        assert eng.register(key) is False
        assert eng.is_duplicate(key) is True
        # After FAILED_RETRYABLE: retry allowed
        eng.set_state(key, IdempotencyState.FAILED_RETRYABLE)
        assert eng.register(key) is True
        assert eng.get_state(key) == IdempotencyState.IN_PROGRESS.value
        # After FAILED_TERMINAL: duplicate prevented
        eng.set_state(key, IdempotencyState.FAILED_TERMINAL)
        assert eng.register(key) is False
        assert eng.is_duplicate(key) is True
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    # Verify production store untouched
    persistent = pathlib.Path("metrics/idempotency_store.json")
    if persistent_exists_before:
        assert persistent.exists(), "Production idempotency store must not be deleted by tests"
    # If no persistent file existed before, it still must not exist (no corruption)
    # The key point: we never deleted it.


def test_persistent_store_untouched_by_tests():
    import pathlib
    # The persistent production store must not be deleted or corrupted by tests.
    persistent = pathlib.Path("metrics/idempotency_store.json")
    # If it exists, verify it is intact (valid JSON) and not deleted
    if persistent.exists():
        import json
        try:
            data = json.loads(persistent.read_text(encoding="utf-8"))
            assert "keys" in data
        except Exception as exc:
            raise AssertionError(f"Production idempotency store corrupted: {exc}")
