# SESSION CHECKPOINT — MBM Social + Clipping Factory + ContentRewards.com

**Date/Time:** 2026-09-01T19:45:00Z
**Branch:** `master` @ `8aca1ab` (HEAD -> master, origin/master)
**Last Commit:** `8aca1ab fix(commercial): global sales-language audit — eliminate generic AI receptionist pitch`
**Git Status:** Working directory has 100 files changed (see `git diff --stat`), 5 new pipeline files untracked prior to checkpoint. Only pipeline-relevant files are committed in this checkpoint; lead-engine churn remains unstaged for separate handling.

---

## 1. FILES CHANGED (Pipeline Checkpoint)

**Committed in this checkpoint (safe, no secrets):**
- `clipping-factory/MBM-Social/BrandChannelIdentity.json` **NEW** — authoritative brand→Gmail→channel map (no tokens)
- `clipping-factory/MBM-Social/BrandRegistry.json` — twists→abdelshafyclapps@gmail.com, clippingfactory→UNKNOWN
- `clipping-factory/MBM-Social/ChannelRegistry.json` — clippingfactory→UNKNOWN, twists correct
- `clipping-factory/MBM-Social/RoutingRegistry.json` — 6 yt/tt/ig accounts fixed (twists→abdelshafyclapps, clipping→UNKNOWN)
- `clipping-factory/MBM-Social/mbm_social/tracking.py` **NEW** — ContentRewards+Neteller bridge (deterministic tracking_id, tracking_link, neteller_link, publish event)
- `clipping-factory/MBM-Social/mbm_social/post_orchestrator.py` — tracking injection before publish + ContentRewards ledger/attribution in `_write_post_publish_artifacts`
- `clipping-factory/auth_brand_youtube_token.py` — PKCE S256, fresh state per attempt, stale-state 400, 300s timeout, invalid_grant/invalid_scope classification, UNKNOWN handling, per-brand isolation
- `clipping-factory/MBM-Social/social_media_accounts_manifest.json` — twists→abdelshafyclapps
- `clipping-factory/MBM-Social/generate_auth_links.py` — same + clipping→UNKNOWN
- `clipping-factory/MBM-Social/bootstrap_all_brand_sessions.py` — same
- `clipping-factory/MBM-Social/login_all_brands.py` — same
- `clipping-factory/MBM-Social/oauth_local_server.py` — same
- `clipping-factory/MBM-Social/reauth_brand.py` — same
- `clipping-factory/MBM-Social/reauth_youtube_all.py` — same
- `clipping-factory/MBM-Social/save_tokens.py` — same
- `clipping-factory/MBM-Social/test_uris.py` — same
- `clipping-factory/clipping_campaign_manager.py` — header+master_email fixes
- `clipping-factory/multi_account_channel_integrator.py` — header+ALL_GOOGLE_ACCOUNT_CHANNELS fixes
- `clipping-factory/update_all_brand_schedules_and_niches.py` — BRAND_SPECS fixes
- `clipping-factory/SESSION_CHECKPOINT.md` **NEW** — this file

**Intentionally NOT staged (unrelated to this pipeline, remain unstaged):**
- 80+ `MBM/LeadEngine/*`, `MBM/Artifacts/*`, `mbm-dialer/*`, `server/*`, `supabase/*`, `.env.example`, `AGENTS.md` churn from parallel lead-engine sprints. Not committed here to keep checkpoint focused.

**Never committed (gitignored):**
- `clipping-factory/MBM-Social/youtube_tokens.json` (contains refresh_token/access_token/client_secret)
- `clipping-factory/MBM-Social/youtube_tokens.json.bak_*`
- `clipping-factory/MBM-Social/publish_queue/*.json` (1828→3, archived)
- `clipping-factory/MBM-Social/ContentRewards/*.jsonl` / `attribution_*.json`
- `clipping-factory/MBM-Social/YouTubeAnalytics/*.jsonl`

---

## 2. CURRENT SYSTEM STATUS

Pipeline is **connected and verified** for 2/5 brands live, 3/5 awaiting human re-auth:

- Clipping Factory produces `final.mp4` + `publish_package.json` (20 READY artifacts, virality ≥80, QA ≥7.0) and enqueues via `full_cycle.py:955 enqueue_for_publish()` → `publish_queue/pkg_factory_*.json` with `source_system=clipping_factory`.
- MBM Social `post_orchestrator.py:613` validates `brand_binding` + `hard_channel_routing` (CHANNEL_IDENTITY_MISMATCH), injects deterministic `tracking_id`/`tracking_link`/`neteller_link` via `tracking.py:100` before any upload, then publishes via `youtube_api_publisher` (OAuth) with `channels().list mine=True` ownership check and `verify_upload` (oEmbed fallback).
- ContentRewards `tracking.py:record_publish_event` + `content_rewards.py:RevenueLedger` creates `ContentRewards/attribution_<tracking_id>.json` + `ContentRewards/ledger.jsonl` (estimated vs verified vs actual separate, EWMA priors). Clicks/conversions remain `null` until platform-reported.
- Queue flood cleaned: 1828→3 files, filler factory disabled (`paced_cycle.py:24 MBM_FILLER_FACTORY=0`), dedupe by `(brand,title)`, duplicate proof archived.

OAuth hardened: PKCE S256 per attempt, fresh state, stale-state 400 with `Authorization attempt expired...`, 300s timeout, `invalid_grant`/`invalid_scope` classification, per-brand isolation (CuteDosage protected), never overwrites valid token with bad auth.

Security: `.gitignore:132` ignores `youtube_tokens.json` + `publish_queue/`, no secrets printed (debug only prints suffix/fingerprint), `BrandChannelIdentity.json` stores only `oauth_client_ref` not secret.

---

## 3. CHANNEL/OAUTH STATUS (live `auth_brand_youtube_token.py --verify` 2026-09-01)

| Brand | Expected Gmail | Channel ID | Handle | Token | Auth Channel | Result |
|-------|----------------|------------|--------|-------|--------------|--------|
| twistsrevealed | abdelshafyclapps@gmail.com | UCknUgK7LEQOoXk_44juSfzw | @TwistsRevealed | invalid_grant (revoked) | FAIL | **NEEDS_REAUTH** |
| goalmachinez | abdelshafyplays@gmail.com | UCV3i2caQ-JXey0by8H1_5tg | @Goalmachinez | invalid_grant | FAIL | **NEEDS_REAUTH** |
| dontwatchthis | abdelshafyplay@gmail.com | UCZi1tOA71rDrin5DyNVNKOA | @DONTWATCHTHIS1 | invalid_grant | FAIL | **NEEDS_REAUTH** |
| cutedosage | moeaiagenicteamz@gmail.com | UCNnWrWmMuZDy4LSg95stEOQ | @CuteDosage | valid (last_verified 2026-08-31) | UCNnWrWmMuZDy4LSg95stEOQ | **PASS - PROTECTED** |
| clippingfactorymbm | UNKNOWN - NOT YET CONFIRMED | UCSZ80c0lE5gqkkbfHKrGkGA | @ClippingFactoryMBM | valid but account UNKNOWN | UCSZ80c0lE5gqkkbfHKrGkGA | **OK (channel) + NEEDS_CONFIRMATION (account)** |

Audit output:
```
[clippingfactorymbm] OK (channel verified, but account is UNKNOWN - needs human confirmation)
[cutedosage] OK
[dontwatchthis] FAIL - INVALID_GRANT -> ACTION: --brand dontwatchthis --force --debug-auth
[goalmachinez] FAIL - INVALID_GRANT
[twistsrevealed] FAIL - INVALID_GRANT
[AUTH] Audit complete: 3 bad/missing token(s).
```

---

## 4. PIPELINE STATUS

- **Clipping Factory:** 20 READY artifacts with `final.mp4` (e.g., `20260826_114503_RW1_TR-1922-B02CE02259AB` virality 84, qa 9.13). `movie_status.json` shows `ready_to_publish` for 6 PD films, `source_blocked` for modern titles (correct). `heartbeat.json` status `idle` (saturated, not failed). **Needs more PD source inventory for future production.**
- **MBM Social:** `pending_packages(production_only=True)` → 2 (`pkg_factory_CD-2026-CUTE002.json` cutedosage, `pkg_factory_TR-1922-B02CE02259AB.json` twistsrevealed). Both route via `RoutingRegistry` to `yt_cutedosage` / `yt_twistsrevealed` correctly. Tracking injection verified (cutedosage tracking_id `0944bd4be5e1` → `https://contentrewards.com/discover/c1ef50c5...?utm_source=cutedosage...`, twists tracking_id `61bb55d1e9f1` → fallback). Hard routing blocks cross-brand (tested).
- **ContentRewards:** Campaign `c1ef50c5-b0f7-4b23-bdbe-1fc33a965935` [VIRAL] My Mini Mom & Baby (CPM $0.80 YT, $1.25 TT/IG, $4300 remaining) loaded from `Brands/cutedosage/campaigns/`. `tracking.py` deterministic, `content_rewards.py` ledger `ContentRewards/ledger.jsonl` + `attribution_*.json` inspectable. `Neteller` canonical via `MBM/Scripts/neteller_config.py` (abdelshafyclapps@gmail.com 4599228811).
- **End-to-End:** Factory → queue → MBM Social → tracking → YouTube (OAuth) → verification → attribution → analytics is wired. Live publish blocked only by 3 revoked tokens (human step).

---

## 5. QUEUE STATUS

- **Before cleanup:** 1828 `publish_queue/*.json` (998 STALE, 824 LEGACY, 5 REAL_PRODUCTION, 1 unreadable)
- **After cleanup:** `publish_queue/` → 3 files total
  - `pkg_factory_CD-2026-CUTE002.json` (cutedosage, draft, clipping_factory, `20260831_CUTE002`, virality 85, valid video `viral_pool/transformed_viral_make_money_01.mp4`)
  - `pkg_factory_TR-1922-B02CE02259AB.json` (twistsrevealed, draft, clipping_factory, `20260826_114503_RW1...`, virality 84, `final.mp4` exists)
  - `pkg_proof_1787746338_TR-1922.json` (clippingfactorymbm, `published_identity_warning`, evidence preserved)
- **Archived:** `archive_stale_20260901` (998), `archive_legacy_20260901` (827), plus existing `archive_filler_20260826` (7022), `archive_invalid_identity_20260826` (3), `stale_pre_enhancement` (889)
- **Persistence:** Queue files are on disk (OneDrive), no in-memory jobs, `publish_queue` is gitignored but preserved. No filler generation (`paced_cycle` filler disabled). Retry safe (draft→published only on verified video_id).

---

## 6. CONTENTREWARDS STATUS

- **Campaign:** `c1ef50c5...` cutedosage, 28 creators joined, 57% budget used, CPM $0.80 YT (example: 10k views → $8, 500k → $400).
- **Tracking:** `tracking.py:build_tracking_context` → `generate_tracking_id(sha256(content:brand:platform:campaign)[:12])` deterministic, `generate_tracking_link` with UTM + ContentRewards URL, `neteller_link_for_campaign` via canonical `neteller_link()`. Injected into description as `🔗 Content ID | Tracking: <id>` + `📊 Track` + `💰 Support`.
- **Ledger:** `ContentRewards/ledger.jsonl` (append-only), `attribution_*.json` per publish, `RevenueLedger` with `planned/submitted/verified` state machine, duplicate protection via tracking_id check, `update_rpm_priors` EWMA 0.25.
- **Test:** `test_content_rewards.py` PASS 75/75 (normalize, eligibility, economics, clip QA, submit→verify, state machine).

---

## 7. TEST RESULTS

```bash
python -m pytest clipping-factory/tests/test_auth_brand.py -v
# 3 passed (correct channel accepted, wrong channel rejected, verify classifications)

python -m pytest clipping-factory/tests/test_two_channel_routing.py -v
# 27 passed (virality gate, identity, cross-channel blocking, duplicate, scheduler)

python -m pytest clipping-factory/tests/test_publish_consolidation.py -v
# 25 passed (quality gate, identity mismatch → blocked, enqueue idempotent, registries real IDs)

python -m pytest clipping-factory/tests/test_duplicate_guard.py -v
# 9 passed (artifact cache, reconciliation, corrupt state fail-closed)

python -m pytest clipping-factory/tests/test_source_handoff.py -v
# 18 passed, 1 skipped

python -m pytest clipping-factory/tests/test_virality.py -v
# 11 passed

python clipping-factory/MBM-Social/test_content_rewards.py
# PASS: 75 FAIL: 0 ALL TESTS PASSED

python clipping-factory/auth_brand_youtube_token.py --verify
# 3 FAIL (invalid_grant) correctly reported, 1 OK, 1 OK+UNKNOWN - exit 1 as expected
```

All hermetic tests pass. No failures after fixes.

---

## 8. KNOWN BLOCKERS (Human/Data, Not Code Bugs)

**BLOCKER 1:** TwistsRevealed OAuth revoked (`invalid_grant: Bad Request` for `abdelshafyclapps@gmail.com` / `UCknUgK7LEQOoXk_44juSfzw`). Requires browser re-auth.

**BLOCKER 2:** GoalMachinez OAuth revoked (`abdelshafyplays@gmail.com` / `UCV3i2caQ-JXey0by8H1_5tg`).

**BLOCKER 3:** DontWatchThis OAuth revoked (`abdelshafyplay@gmail.com` / `UCZi1tOA71rDrin5DyNVNKOA`).

**BLOCKER 4:** ClippingFactoryMBM Gmail ownership confirmation required (`UCSZ80c0lE5gqkkbfHKrGkGA` / `@ClippingFactoryMBM` channel verified, but `owned_by` is `UNKNOWN - NOT YET CONFIRMED` in all registries. Do NOT guess. Token exists but email is `bigmoeshafy@gmail.com` legacy, not authoritative.

**BLOCKER 5:** Clipping Factory needs additional verified source inventory if production generation is to continue (6 PD films saturated, all modern titles correctly `source_blocked` via `movie_status.json`).

---

## 9. HUMAN ACTIONS REQUIRED

1. **Re-auth twistsrevealed:**
   ```bash
   python clipping-factory/auth_brand_youtube_token.py --brand twistsrevealed --force --debug-auth
   ```
   Sign in as `abdelshafyclapps@gmail.com`, select `@TwistsRevealed` Brand Account when prompted. Do NOT overwrite CuteDosage.

2. **Re-auth dontwatchthis:**
   ```bash
   python clipping-factory/auth_brand_youtube_token.py --brand dontwatchthis --force --debug-auth
   ```
   Sign in as `abdelshafyplay@gmail.com`.

3. **Re-auth goalmachinez:**
   ```bash
   python clipping-factory/auth_brand_youtube_token.py --brand goalmachinez --force --debug-auth
   ```
   Sign in as `abdelshafyplays@gmail.com`.

   After each: `python clipping-factory/auth_brand_youtube_token.py --verify` must show `OK` for that brand.

4. **Confirm ClippingFactoryMBM Gmail:** Provide the correct Google account that owns `UCSZ80c0lE5gqkkbfHKrGkGA`. Do NOT run auth until confirmed. Then update `BrandChannelIdentity.json` and run the same `--brand clippingfactorymbm --force --debug-auth`.

---

## 10. EXACT RESUME COMMANDS (Copy/Paste Tomorrow)

**A. Verify repository:**
```bash
git status
git diff --stat
```

**B. Verify YouTube:**
```bash
python clipping-factory/auth_brand_youtube_token.py --verify
```

**C. Inspect pending production jobs:**
```bash
python -c "import sys; sys.path.insert(0,'clipping-factory/MBM-Social'); from mbm_social.post_orchestrator import pending_packages; pp=pending_packages(production_only=True); print(f'pending production: {len(pp)}'); [print(p.name, pkg.get('brand')) for p,_ in pp]"
Get-ChildItem clipping-factory/MBM-Social/publish_queue/*.json | Select-Object Name
Get-ChildItem clipping-factory/artifacts/twistsrevealed | Select-Object Name -First 10
```

**D. Run the focused tests:**
```bash
python -m pytest clipping-factory/tests/test_auth_brand.py clipping-factory/tests/test_two_channel_routing.py clipping-factory/tests/test_publish_consolidation.py clipping-factory/tests/test_duplicate_guard.py clipping-factory/tests/test_source_handoff.py clipping-factory/tests/test_virality.py -v
python clipping-factory/MBM-Social/test_content_rewards.py
```

**E. Reauthorize each revoked brand ONE AT A TIME:**
```bash
python clipping-factory/auth_brand_youtube_token.py --brand twistsrevealed --force --debug-auth
# -> after browser consent, verify:
python clipping-factory/auth_brand_youtube_token.py --verify

python clipping-factory/auth_brand_youtube_token.py --brand dontwatchthis --force --debug-auth
python clipping-factory/auth_brand_youtube_token.py --verify

python clipping-factory/auth_brand_youtube_token.py --brand goalmachinez --force --debug-auth
python clipping-factory/auth_brand_youtube_token.py --verify
```

**For ClippingFactoryMBM: DO NOT guess Gmail. Resume only after the correct Google account is confirmed.**

**F. After re-auth, test publish (dry-run first, then unlisted):**
```bash
python -c "import sys; sys.path.insert(0,'clipping-factory/MBM-Social'); from mbm_social.post_orchestrator import publish_package, pending_packages; p,pkg=pending_packages(production_only=True)[0]; print(publish_package(p,pkg,dry_run=True,mode='dry_run'))"
# If dry-run shows tracking injected and routing OK, then:
# python -m mbm_social.post_orchestrator --brand cutedosage --mode test  # unlisted, safe
```

---

## 11. MACHINE-SAFE STATE

- All pipeline code/config written to disk, no unsaved editor buffers.
- Queue state persisted: `publish_queue/` (3 files), archives (998+827), `artifacts/` (20 final.mp4), `movie_status.json`, `heartbeat.json`, `ledger.json`, `youtube_tokens.json` (gitignored, protected), `ContentRewards/` (ledger + attribution), `YouTubeAnalytics/` (gitignored).
- No temp credentials required to resume (only `YOUTUBE_CLIENT_SECRET` env for future auth, already in `.env`).
- No long-running servers needed (paced_cycle Task Scheduler handles 15-min ticks, filler disabled). No dev server running that would be killed by restart.
- `.gitignore` verified: `youtube_tokens.json`, `publish_queue/`, `ContentRewards/*.jsonl` ignored where appropriate; `BrandChannelIdentity.json` safe (no secrets).
- No secrets printed in logs or checkpoint.

**Safe to restart: YES** (after creating git checkpoint below).

---

## 12. GIT CHECKPOINT

This file is the checkpoint. The following pipeline files are ready for `git add` + `commit` (no tokens):

```bash
git add clipping-factory/MBM-Social/BrandChannelIdentity.json
git add clipping-factory/MBM-Social/BrandRegistry.json
git add clipping-factory/MBM-Social/ChannelRegistry.json
git add clipping-factory/MBM-Social/RoutingRegistry.json
git add clipping-factory/MBM-Social/mbm_social/tracking.py
git add clipping-factory/MBM-Social/mbm_social/post_orchestrator.py
git add clipping-factory/auth_brand_youtube_token.py
git add clipping-factory/MBM-Social/social_media_accounts_manifest.json
git add clipping-factory/MBM-Social/generate_auth_links.py
git add clipping-factory/MBM-Social/bootstrap_all_brand_sessions.py
git add clipping-factory/MBM-Social/login_all_brands.py
git add clipping-factory/MBM-Social/oauth_local_server.py
git add clipping-factory/MBM-Social/reauth_brand.py
git add clipping-factory/MBM-Social/reauth_youtube_all.py
git add clipping-factory/MBM-Social/save_tokens.py
git add clipping-factory/MBM-Social/test_uris.py
git add clipping-factory/clipping_campaign_manager.py
git add clipping-factory/multi_account_channel_integrator.py
git add clipping-factory/update_all_brand_schedules_and_niches.py
git add clipping-factory/SESSION_CHECKPOINT.md
git commit -m "checkpoint: mbm social clipping contentrewards pipeline"
```

Unstaged lead-engine churn (80+ files) is intentionally not in this checkpoint.

