# Platform Capability Matrix (M-022, Phase 8/18)

Honest capability classification for the MBM-Social publishing surface. Anything not
marked SUPPORTED is surfaced to a human (MANUAL_REQUIRED) or blocked from silent
success (BLOCKED). No platform is ever marked "published" without a real success id.

| Platform | Level | Mechanism | Auto-verify | Public | Required to enable |
|---|---|---|---|---|---|
| YouTube | SUPPORTED | YouTube Data API v3 (OAuth) → CDP → Playwright | Yes (post_orchestrator + verify_analytics) | Yes (`PUBLISH_MODE=live`) | Per-brand OAuth refresh token |
| Instagram Reels | MANUAL_REQUIRED | Playwright (YouTube Studio / IG web) | No (CDP not available) | Browser-only | Instagram Graph API app + token (or keep MANUAL) |
| TikTok | MANUAL_REQUIRED | Playwright | No | Browser-only | Audited TikTok Content Posting API app |
| LinkedIn | BLOCKED | — | — | — | API app + `publisher.py` LinkedIn adapter |
| X / Twitter | BLOCKED | — | — | — | API v2 write access + `publisher.py` X adapter |

## Behaviour contract
- `PlatformRegistry.all_capabilities()` returns the full matrix with `display_name`.
- `PlatformRegistry.assert_publishable(platform)` raises `KeyError` for BLOCKED; returns
  `MANUAL_REQUIRED` for platforms that need a human. `campaign_runner` converts a MANUAL
  result into a preserved dead-letter entry (`reason="manual_required"`) and opens a
  GitHub issue (via `github_app`) when a repo is configured.
- A package targeting an unknown or BLOCKED platform is **never** marked Published; it is
  preserved in `publish_queue/dead_letter/` so a human can resolve it.

## Quality-gate platform_fit axis
`quality_gate_policy.evaluate` includes a `platform_fit` gate that checks each target
platform is SUPPORTED or MANUAL_REQUIRED (never BLOCKED). BLOCKED targets → `QUALITY_FAILED`
with `reason="blocked_platform"`.

## Credentials map
| Need | Env / file |
|---|---|
| YouTube tokens | `backend/youtube_tokens.json` or `YOUTUBE_SESSION_STATE` / per-brand `youtube_profile/` |
| Instagram | `INSTAGRAM_GRAPH_TOKEN` (optional; absence ⇒ MANUAL) |
| TikTok | `TIKTOK_API_KEY` (optional; absence ⇒ MANUAL) |
| LinkedIn | none provisioned ⇒ BLOCKED |
| X | none provisioned ⇒ BLOCKED |
| GitHub App (issue reporting) | `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` + `GITHUB_WEBHOOK_SECRET` |

## Coverage summary
- Supported (fully automated): 1 / 5 (YouTube)
- Manual-required (package produced, human publishes): 2 / 5 (Instagram, TikTok)
- Blocked (no implementation): 2 / 5 (LinkedIn, X)
- Overall publish automation: ~40% of target platforms; ~75% for YouTube-only campaigns.
