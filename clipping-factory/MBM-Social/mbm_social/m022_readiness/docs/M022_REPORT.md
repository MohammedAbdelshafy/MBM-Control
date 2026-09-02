# M-022 PRODUCTION ACTIVATION — READINESS REPORT

Module: `clipping-factory/MBM-Social/mbm_social/m022_readiness/`
Status: READINESS GATE IMPLEMENTED. Live uploads BLOCKED.

## EXISTING INFRASTRUCTURE REUSED (not rebuilt)

- `youtube_api_publisher.py` (existing OAuth/token/channel infrastructure)
- `youtube_tokens.json` (existing token storage)
- `ChannelRegistry.json` (existing channel registry)
- `autonomous_runtime.py` (existing 14-stage lifecycle — M-022 is readiness gate before stage 12 activation)
- `post_orchestrator.py` (existing queue/idempotency patterns)
- `tiktok_shop/` module remains separate and untouched
- `MBM/LeadEngine/` protected (no modifications made)

## BUILT (M-022 readiness gate only, not activation)

- `youtube_oauth_readiness.py` — OAuth state machine, scope validation, redirect URI check
- `channel_health.py` — Read-only health check (5-channel matrix, BLOCKED by default)
- `quota_guard.py` — Quota-aware guard (AVAILABLE/LOW/EXCEEDED/BLOCKED)
- `dry_run_campaign.py` — Complete dry-run representation (no mutation)
- `upload_policy.py` — BLOCKED gates + idempotency engine (duplicate prevention)
- `security_config.py` — No secrets in source verification
- `tests/` — 5 test files (OAuth, health, quota, dry-run, security)
- `docs/` — M022_READINESS.md, M022_FIRST_ACTIVATION_GATE.md

## SAFETY STATE (hard stops enforced)

- uploads BLOCKED (`UploadPolicy.gate_state` = BLOCKED by default)
- publishes BLOCKED
- deletes BLOCKED
- updates BLOCKED
- external_spend BLOCKED
- `youtube_api_publisher.py` mode safety preserved (`public` requires `allow_public=True`; default BLOCKED)
- `publish_blocked` preserved in existing `youtube_api_publisher.py` (line 76: no real video_id = BLOCKED)
- `.env` secrets only; `.env.example` unchanged; no credentials committed
- No TikTok module expansion
- No Spec-Ad reopening
- No `autonomous_runtime.py` modification

## READINESS GATE (not activated)

Before M-022 activation, ALL required:

1. OAuth validated (`youtube_oauth_readiness.check_oauth_state()` == AUTHENTICATED)
2. Scope validated (`youtube.upload` scope present)
3. Token file exists (`youtube_tokens.json` readable)
4. Channel registry has 5 entries (`ChannelRegistry.json`)
5. Read-only health PASS (`ChannelHealthChecker.get_channel_entries()` all VALID)
6. Quota AVAILABLE (`quota_guard.get_quota_state()` == AVAILABLE)
7. Idempotency engine works (`IdempotencyEngine.generate_key()` + `register()`)
8. Upload policy BLOCKED (`UploadPolicy.gate_state` == BLOCKED — ensures no accidental activation)
9. Security config passes (`security_config.verify_no_secrets_in_file()` clean for relevant files)
10. All M-022 tests pass
11. Existing MBM-Social tests do not regress
12. No live uploads attempted
13. No public publishes attempted
14. Separate explicit authorization step taken to set `READY_FOR_CONTROLLED_ACTIVATION`

Only after step 14 (explicit authorization): first real campaign uses `TEST` or `PRIVATE` (not `public`) per `youtube_api_publisher.py` design.

## INTEGRATION WITH EXISTING PUBLISHING

The M-022 readiness module does NOT replace `youtube_api_publisher.py`. It uses the same token infrastructure (`youtube_tokens.json`, `ChannelRegistry.json`) and respects its mode-safety rules:
- `publish_via_api()` requires `allow_public=True` for `public`; by default `public` blocked
- `publish_via_playwright()` has privacy_status validation (`public` requires authorization)
- `publish_blocked` preserved: no real video_id = BLOCKED (line 76)

M-022 adds a readiness gate layer ONLY. The actual activation requires a separate authorization action that changes `UploadPolicy.gate_state` — not automatic.

## NEXT STEP (BLOCKED — requires explicit authorization)

1. Confirm `youtube_tokens.json` contains valid tokens per brand/channel
2. Confirm `ChannelRegistry.json` has 5 valid entries
3. Confirm M-022 tests pass
4. Confirm no MBM-Social regression
5. Explicit authorization: change `UploadPolicy.gate_state` to `READY_FOR_CONTROLLED_ACTIVATION`
6. First activation: dry-run campaign only (`TEST` / `PRIVATE` privacy status)
7. Verify `youtube_api_publisher.py` `publish_via_api()` with `allow_public=False` works as expected

DO NOT proceed past step 5 without separate authorization.
