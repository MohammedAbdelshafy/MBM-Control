# M-022 Deferred Blockers — GitHub Issues (Phase 19)

These are genuine blockers that require external credentials or new publisher
implementations. They are intentionally NOT faked. File as GitHub issues when a
maintainer has the credentials/access.

Each issue body below can be pasted directly into `gh issue create --title ... --body ...`.

---

## Issue 1 — LinkedIn publisher implementation
**Title:** Add LinkedIn publisher adapter (BLOCKED platform)
**Labels:** enhancement, publishing, blocker
**Body:**
LinkedIn is currently BLOCKED in `mbm_social/platform_registry.py` because no publisher
exists. Any package targeting LinkedIn is preserved in `publish_queue/dead_letter/` and a
GitHub issue is opened.
- Implement `publisher.py` LinkedIn adapter (OAuth2, Organization/Person share).
- Provision a LinkedIn Developer API app with `w_member_social` scope.
- Register the app in `github_app.py` / env so `assert_publishable("linkedin")` returns SUPPORTED.
Do NOT mark any LinkedIn post Published without a real share URN.

## Issue 2 — X/Twitter publisher implementation
**Title:** Add X/Twitter publisher adapter (BLOCKED platform)
**Labels:** enhancement, publishing, blocker
**Body:**
X/Twitter is BLOCKED; no adapter. Packages targeting X are dead-lettered.
- Implement `publisher.py` X adapter (API v2 tweet with media).
- Provision X API v2 write access (paid tier).
Same honesty contract: real tweet id required to mark Published.

## Issue 3 — Instagram Graph API app + token
**Title:** Provision Instagram Graph API for automated Reels publishing
**Labels:** credentials, publishing
**Body:**
Instagram is MANUAL_REQUIRED (Playwright-only, no auto-verify). To automate:
- Register an Instagram Graph API app (Business/Creator account).
- Set `INSTAGRAM_GRAPH_TOKEN`; add a real `verify_publish` path.
Until then MANUAL mode is acceptable (packages produced, human publishes).

## Issue 4 — TikTok Content Posting API app
**Title:** Provision TikTok Content Posting API for automated publishing
**Labels:** credentials, publishing
**Body:**
TikTok is MANUAL_REQUIRED. To automate: apply for/audited TikTok Content Posting API,
set `TIKTOK_API_KEY`, implement real `verify_publish`. MANUAL mode acceptable meanwhile.

## Issue 5 — Restore YouTube Analytics API scopes
**Title:** Re-enable YouTube Analytics API for verify_analytics
**Labels:** credentials, analytics
**Body:**
`youtube_analytics.py` is currently provider-less because OAuth scopes were revoked
during the secret scrub. Restore `ytanalytics.readonly` scope and re-run the token
exchange so `verify_analytics` returns real watch-time/retention instead of fabricating
or returning NOT_FOUND.

## Issue 6 — Purge fabricated legacy metrics
**Title:** Remove fabricated rows written by quarantined root runtime
**Labels:** data-hygiene, blocker
**Body:**
The quarantined `mbm_social_autonomous_runtime.py.QUARANTINED` previously wrote
fabricated analytics into `ChannelMetrics.json` and similar. Backup those files, then
purge rows lacking a real source/proof id. Do not let fabricated rows feed the learning
engine.

## Issue 7 — LLM routing tuning
**Title:** Tune brand_router LLM routing after model_registry fix
**Labels:** tuning, routing
**Body:**
`brand_router.py` had an `MBM_LLM_ROUTING=1` path that depended on the now-fixed
`model_registry.generate()`. Re-validate routing with Ollama running; confirm
`_past_performance()` reads `LearningMemory.json` correctly.
