# M-022 READINESS — YouTube OAuth → Read-Only Validation → Controlled Activation

Status: READINESS GATE IMPLEMENTED. Live uploads BLOCKED.
Module: `clipping-factory/MBM-Social/mbm_social/m022_readiness/`

## Current State

- `youtube_oauth_readiness.py`: OAuth state machine (UNCONFIGURED → AUTH_REQUIRED → AUTHENTICATED → CHANNEL_VALID → READY_FOR_CONTROLLED_ACTIVATION). Scope validation against `https://www.googleapis.com/auth/youtube.upload`. Redirect URI HTTPS check.
- `channel_health.py`: Read-only health check using existing `youtube_api_publisher.py` infrastructure (token file, registry). No mutation.
- `quota_guard.py`: Quota-aware guard (AVAILABLE / LOW / EXCEEDED / BLOCKED). Tracks uploads and quota units.
- `dry_run_campaign.py`: Complete dry-run representation (title, desc, tags, privacy status, idempotency key, quota cost). `public` uploads blocked by default.
- `upload_policy.py`: BLOCKED gates for uploads, publishes, deletes, updates. Idempotency engine prevents duplicates.
- `security_config.py`: No secrets in source verification. Environment-based secrets only.

Tests: All M-022 tests pass (5 files).

Safety:
- uploads: BLOCKED (default)
- publishes: BLOCKED (default)
- deletes: BLOCKED
- updates: BLOCKED
- external_spend: BLOCKED
- no live writes performed by any M-022 component

## Readiness Gate (Not Yet Activated)

Before M-022 can move to READY_FOR_CONTROLLED_ACTIVATION, the following must be confirmed (separate from this module):

1. YouTube OAuth flow completed per brand/channel
2. `youtube_tokens.json` contains valid refresh_token + access_token
3. `youtube.upload` scope granted
4. `ChannelRegistry.json` has 5 channel entries with correct `youtube_channel_id`
5. Read-only health check (`ChannelHealthChecker`) returns `VALID` for all 5
6. Quota guard confirms `AVAILABLE` (not `EXCEEDED`)
7. Dry-run campaign creates a valid representation without mutation
8. Idempotency engine prevents duplicate uploads
9. All 5 tests pass (OAuth, channel health, quota, dry-run, security)
10. No secrets committed in `.env` or source files

Only after these conditions are met may a separate explicit authorization step set:
`UploadPolicy.gate_state = READY_FOR_CONTROLLED_ACTIVATION`
Even then, the first real campaign should start with `TEST` / `PRIVATE` (not `public`) and use `publish_via_api` with `allow_public=False` per existing `youtube_api_publisher.py` mode safety.

## Integration with Existing Infrastructure

Reuses (not replaces):
- `youtube_api_publisher.py` (token resolution, OAuth, scope checking, privacy status enforcement)
- `youtube_tokens.json`
- `ChannelRegistry.json`
- `post_orchestrator.py` (queue concepts)
- `autonomous_runtime.py` (14-stage lifecycle — M-022 is a readiness gate before stage 12 activation)

Does NOT modify:
- `autonomous_runtime.py`
- `post_orchestrator.py`
- `publish_package.py`
- `brand_router.py`
- `pipeline.py`
- `clipping-factory/backend/app/agents/`
- `tiktok_shop/` module
- `TikTokPublishingProviderImpl` (remains `TEST_ONLY`)

## Next Step (Blocked)

After readiness gate conditions verified:
- Set `UploadPolicy.gate_state = READY_FOR_CONTROLLED_ACTIVATION` via explicit authorization (not automatic)
- Run first dry-run campaign with `TEST` / `PRIVATE` privacy status
- Verify `youtube_api_publisher.py` `publish_via_api()` behavior with `allow_public=False`
- Only after dry-run verification: proceed to controlled activation (still not public by default)

No further M-022 implementation required until authorization confirmed.
