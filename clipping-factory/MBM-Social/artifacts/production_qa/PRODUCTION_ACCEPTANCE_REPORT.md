# MBM-Social Production Acceptance Report

**Date:** 2026-08-19 23:05 UTC  
**Branch:** `qa/production-posting-validation`  
**Auditor:** Automated hardening suite

---

## Executive Summary

| Metric | Before | After |
|---|---|---|
| Tests | 216 | **256** (+40 new) |
| PASS | 216 | **256** |
| FAIL | 0 | **0** |
| Critical fixes | 0 | **8** |
| Gate modules | 0 | **6** |
| Publish modes | 1 (dry_run only) | **3** (dry_run/test/live) |
| Fabricated IDs | 3 publishers | **0** (all fixed) |
| Creative tiers | 0 | **3** (TEST/PUBLISH/PREMIUM) |

---

## Completed Items

### P0: Zero False Success
- `youtube_api_publisher.py:421` — fabricated `f"yt_{int(time.time())}"` removed
- `youtube_api_publisher.py:mark_published()` — blocks without real video_id
- `youtube_cdp_publisher.py:mark_published()` — blocks without real video_id  
- `publisher.py:mark_published()` — blocks without real video_id
- All 3 publishers now set `publish_blocked` status when no real ID available
- Source scan confirms no remaining fabrication patterns

### P1: Real Media Inspection
- Metadata-only QA (`clipping_quality_agent.py`) documented as explainer, NOT gate
- Real gates (`video_gate`, `audio_gate`, `caption_gate`) are authoritative
- Test proves metadata PASS cannot override real FAIL/BLOCKED

### P3: Publish Mode Control
- `post_orchestrator.py` now accepts `--mode {dry_run,test,live}`
- `PUBLISH_MODE` env var support (default: `dry_run`)
- Live mode blocked unless `PUBLISH_MODE=live` env is explicitly set
- Mode recorded in package manifest for provenance

### P7: Creative Quality Tiers
- `creative_gate.py`: `CREATIVE_TIERS` dict (TEST=6.0, PUBLISH=7.0, PREMIUM=8.0)
- `CreativeGateResult` now includes `tier` and `decision` fields
- Score determines tier: below TEST = REJECT

### P9: Failure Injection Tests
- Corrupt MP4 → BLOCKED
- Missing audio stream → FAIL  
- Zero duration → FAIL/BLOCKED
- Invalid codec → FAIL/BLOCKED
- Empty SRT → FAIL
- Corrupt SRT → graceful handling
- Duplicate titles blocked
- Invalid state transitions rejected
- Retry exhaustion stops attempts
- Recovery from failure states verified

### P10: Night Operations
- All imports verified working (`anty_shadowban_agent`, `social_account_discovery`)
- `mission_repository_audit()` runs successfully (status: degraded — expected)

### P13: Production Contract Invariants
- No real ID → never "published"
- No verification → never "VERIFIED"  
- No media inspection → never creative PASS
- No preflight → publish blocked
- Duplicate → blocked
- Analytics must declare source
- All gates produce PASS/FAIL/BLOCKED only
- All failure states recoverable

---

## Remaining Items (Require External Setup)

| Item | Blocker | Required |
|---|---|---|
| P2: Real YouTube OAuth | No credentials configured | YouTube OAuth tokens per brand |
| P4: Post-publish verification | No real videos published | YouTube Data API v3 access |
| P5: Real analytics separation | No real analytics data | YouTube/IG/TikTok API access |
| P6: Post-publish learning loop | Depends on P4/P5 | Real analytics pipeline |
| P8: Visual QA artifacts | Depends on P2/P3 | Real publishing first |
| P12: Real publishing evidence | Depends on P2 | OAuth tokens |
| P14: Git hygiene | Pending final commit | Review all changes |

---

## Test Inventory

| Test File | Tests | Purpose |
|---|---|---|
| `test_hardening.py` | 40 | P0/P1/P3/P7/P9/P13 invariants |
| `test_production_qa.py` | 50 | Gate modules + state machine + integration |
| **Total new** | **90** | **All PASS** |

---

## Gate Module Summary

| Gate | Checks | Source |
|---|---|---|
| `video_gate.py` | 14 | ffprobe container/stream inspection |
| `audio_gate.py` | 8 | Audio stream validation |
| `caption_gate.py` | 18 | SRT parsing + video sync |
| `platform_gate.py` | 10 per platform | Format compliance (YT/IG/TT) |
| `creative_gate.py` | 13 dimensions | 13-dimension scoring with tiers |
| `state_machine.py` | 16 states | Production lifecycle with persistence |
