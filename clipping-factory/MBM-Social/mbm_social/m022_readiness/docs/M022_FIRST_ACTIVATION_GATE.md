# M-022 FIRST ACTIVATION GATE

This gate controls when M-022 can move from BLOCKED → READY_FOR_CONTROLLED_ACTIVATION.

Requirements (ALL must pass):

[ ] OAuth validated (`youtube_oauth_readiness.check_oauth_state()` == AUTHENTICATED)
[ ] Scope validated (`youtube_oauth_readiness.get_scope_status()` == PRESENT)
[ ] Token file exists and readable (`youtube_tokens.json`)
[ ] Channel registry has 5 entries (`ChannelRegistry.json`)
[ ] Read-only channel health PASS (`channel_health.get_channel_entries()` all VALID)
[ ] Quota guard AVAILABLE (`quota_guard.get_quota_state()` == AVAILABLE)
[ ] Idempotency engine functional (`upload_policy.idempotency.generate_key()` works)
[ ] Upload policy BLOCKED (`UploadPolicy.gate_state` == BLOCKED by default)
[ ] Security config passes (`security_config.check_env_secrets()` reports no secrets in source)
[ ] All M-022 tests pass (`pytest clipping-factory/MBM-Social/mbm_social/m022_readiness/tests/ -q`)
[ ] Existing MBM-Social regressions pass (`pytest clipping-factory/MBM-Social/`)
[ ] No live uploads attempted
[ ] No public publishes attempted
[ ] No external spend enabled

Only after ALL conditions confirmed and a separate explicit authorization action taken:
- Set `UploadPolicy.gate_state = READY_FOR_CONTROLLED_ACTIVATION`
- Even then: first real campaign must use `TEST` or `PRIVATE` (not `public`)
- Even then: `youtube_api_publisher.py` `publish_via_api()` requires `allow_public=True` explicitly for public; by default public remains BLOCKED

This document does NOT represent automatic activation. It is a checklist.
