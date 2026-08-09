# BASE44 — GitHub Repos & Workflows Enhancement Plan (Revenue-First)

> **Goal: a lot of money.** Every change below exists to close the loop between
> **outreach → reply → phone call → deal → cash**, and to make failures/leaks
> loud instead of silent. Implemented: ✅ (Aug 2026). Backlog: 🔜.

---

## 1. Money-Leak Audit (what was wrong)

| # | Leak | Evidence | Impact |
|---|------|----------|--------|
| 1 | **Email throttled to 21–50/hr** | `schedule.yml` ran `--batchSize=21`, `overnight.yml` `--batchSize=50`. Script default is **5000**. | Outreach volume was ~45/day. Volume → replies → deals. Capped at ~1% of capacity. |
| 2 | **NPI real-lead pull was offline** | `hourly-npi-callsheet` ran `npi_verified_callsheet.py --cap 15 --no-net`. Offline mode breaks after one page per vertical. | The free CMS NPI registry (real businesses, real phones) was never actually pulled fresh. |
| 3 | **Master revenue orchestrator wired to nothing** | `master_online_revenue_workflow.py` (Upwork bids + high-ticket matcher + B2B audits + Shopify + Whop + revenue gate) has **no workflow** invoking it. | 6 revenue engines never ran in CI. |
| 4 | **Revenue gate verdict stayed silent** | `revenue_hourly_*.json` shows `answer: NO`, hours-without-revenue climbing — no alert fired. | Revenue stall is invisible until the human opens the Actions tab. |
| 5 | **No failure alerts** | No workflow alerted on failure. `telegram_notify.py` only read a local `telegram_chat_id.txt`, so it failed in CI (no `TELEGRAM_CHAT_ID` env support). | Broken jobs ran silently for days. |
| 6 | **No secret scanning** | Public repo, 474 MB, with `openclaw-secrets-plan.json` + LLM config + OAuth token files in the working tree. | One bad commit = credentials leaked publicly. |
| 7 | **Repo bloat / PII churn** | Logs, lead CSVs, browser profiles, publish-queue state tracked. | 474 MB repo = slow checkouts; PII/state churn in every PR. |

---

## 2. Implemented ✅ (this change-set)

### 2.1 Money movers
- **Email throttle lifted** — `schedule.yml` now drains **400/hr** (dry-run stays 21), `overnight.yml` drains **1000**. SMTP is the only remaining constraint.
- **Live NPI pull, 2×/day** — `hourly-npi-callsheet` now runs `--cap 50` **live** (hits `npiregistry.cms.hhs.gov`, free) at UTC 00 and 12, with offline fallback only if the live call fails. Volume went from ~cached scraps to hundreds of real US healthcare businesses/day.
- **Master revenue workflow wired** — `overnight.yml` new `master-revenue-workflow` phase runs `master_online_revenue_workflow.py` (all 6 money engines) nightly, uploads its summary, and alerts on failure.
- **Revenue STOP alert** — `schedule.yml` revenue gate now fires a Telegram alert when the verdict is `NO` and hours-without-revenue ≥ 12 (or score < 40), including the signal breakdown.
- **Speed-to-lead reply alert** — as soon as `reply_detector` finds new replies, a Telegram alert goes out telling you to **call them now**.

### 2.2 Reliability & visibility
- **Reusable Telegram action** — `.github/actions/telegram-notify/action.yml` (safe no-op when secrets unset). Used for failure alerts in **8 workflows**.
- **`telegram_notify.py` fixed for CI** — now reads `TELEGRAM_CHAT_ID` env first (CI) and adds a `send` command.
- **`check.yml` hardened** — added `actionlint` (validates all workflows), `gitleaks` (secret scan), `npm-audit` (production dependency vulnerabilities).
- **`security.yml` (new)** — gitleaks full-history scan on push/PR + weekly cron; Telegram alert on any leak.

### 2.3 Notification persistence (every alert leaves a record)
- **`notify_lib.py` (new)** — single implementation for send + persist: fires the Telegram message **and** inserts into the Supabase `notifications` table (service-role REST). Used by the composite action, `telegram_notify.py`, and every inline alert step.
- **Migration `00010_notifications.sql`** — `public.notifications` table (event, channel, message, status, repo, workflow, run_id, created_at). Survives fresh CI checkouts; queryable for audits.
- **Events persisted:** `ci:hourly-failure`, `ci:overnight`, `ci:agent-factory`, `ci:daily`, `ci:crawler`, `ci:lead-pack`, `ci:health`, `revenue:stall`, `revenue:daily`, `revenue:dashboard-file`, `reply:new`, `telegram_notify` (local runs), security leaks.
- **Query it:** `SELECT event, message, status, created_at FROM notifications ORDER BY created_at DESC LIMIT 50;` (Supabase SQL editor).

### 2.3 Money visibility
- **`revenue_dashboard_html.py` (new)** — stdlib-only generator producing a self-contained dark-mode dashboard: verdict, score, hours-without-revenue, last-YES, replies/deals/orders, stream targets, last-24 verdicts table.
- **`revenue-dashboard.yml` (new)** — daily 07:00 UTC build → artifact + **Telegram message + HTML file** delivery.

### 2.4 Repo hygiene
- **`.gitignore` expanded** — Ops secrets (`openclaw-secrets-plan.json`, `master_ai_models_config.json`, OmniRoute-Deploy), PII/lead CSVs, log dirs, browser profiles, channel manifests, publish-queue media, generated ads/blueprints/lead packs.

---

## 3. Activation Checklist (do these once)

1. **Secrets in repo settings → Actions:**
   - `TELEGRAM_BOT_TOKEN` (required) and `TELEGRAM_CHAT_ID` (required) — powers every alert.
   - Verify existing: `VITE_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SMTP_*`, `WHOP_API_KEY`, `WHOP_ACCOUNT_ID`, `RAPIDAPI_KEY`, `RETELL_API_KEY`, `CLIPPING_*`, `GEMINI_API_KEY`.
   - Optional: `GITLEAKS_LICENSE` (skip if the free `gitleaks-action` path works — it does without a license for public repos).
2. **Push the notifications migration:** `supabase db push` (or apply `supabase/migrations/00010_notifications.sql` in the SQL editor). Without it, alerts still fire but `notifications` rows won't persist.
3. **First dispatch:** run `Revenue Dashboard` and `Security` via Actions → `workflow_dispatch` to confirm secrets + Telegram wiring.
4. **Confirm email throughput:** watch the `Email Queue` step summary — should report 400/hr instead of 21. Adjust `BATCH_SIZE` in `schedule.yml` if your SMTP host rate-limits.
5. **Watch NPI volume:** after UTC 00/12 runs, check the `npi-verified-callsheet` artifact row count. Scale `--cap` up (50 → 100) once dialing capacity exists.

---

## 4. Backlog 🔜 (highest-RoI next)

| Item | Why | Where |
|------|-----|-------|
| **Dial the sheet** | Real leads only pay when dialed. Wire `close_queue_dialer.py --live` behind a human trigger + push the day's `npi_verified_callsheet.csv` to Telegram every morning. | new `call-sheet.yml` |
| **Whop lifecycle on revenue** | `whop_monetize.py` tracks REAL sales; feed `logs/whop_revenue.json` into the revenue gate so `paid_orders` isn't always 0. | `schedule.yml` revenue gate |
| **Stripe/Shopify order sync** | Real order webhooks → revenue gate `paid_orders`. `server/shopifyWebhookServer.js` exists but isn't in CI. | new `orders-sync.yml` |
| **Auto-rotate outreach** | When replies ≤ 0 for 7 days, rotate markets + reset email copy automatically (the tracker already emits `pending_adjustments`). | revenue gate |
| **Cross-repo rollout** | Reuse this action + workflow set in `jarvis-mbm`, `MBM-Social`, `start-of-play`. | see §6 |

---

## 5. Workflow Inventory (base44-app)

| Workflow | Cadence | Purpose | Alerts |
|----------|---------|---------|--------|
| `check.yml` | push/PR | lint + typecheck + build + actionlint + gitleaks + npm audit | — |
| `security.yml` | push/PR/weekly | full-history secret scan | 🔴 leak |
| `schedule.yml` | hourly | email drain, hunter, lead pipeline, clipping scan, NPI callsheet (2×/day), Whop, video posting, revenue gate | 🔴 failure, 🔴 revenue stall, 📥 replies |
| `overnight.yml` | 18/00/06 UTC | agents, enrich, deploy, email (1000), revenue gate, **master revenue workflow** | 🔴 failure + 🌙 digest |
| `revenue-dashboard.yml` | 07 UTC | build + deliver dashboard | 🔴 failure |
| `agent-factory.yml` | 15 min | voice agents | 🔴 failure |
| `daily-run.yml` | 05 UTC | lead pipeline | 🔴 failure |
| `crawler-ci.yml` | hourly | clipping.com scan | 🔴 failure |
| `lead-pack.yml` | monthly | client lead pack | 🔴 failure |
| `mbm-social.yml` | MBM-Social changes | brand validation | — |
| `health-report.yml` | 06 UTC | repo health score | 🔴 <75 |

---

## 6. Cross-Repo Rollout Plan

Repos: `base44-app` (MBM HQ · this), `jarvis-mbm` (private), `MBM-Social` (private), `start-of-play` (private).

1. **Copy the reusable asset:** `.github/actions/telegram-notify/` → each repo.
2. **Drop the same 4 secrets** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, plus repo-specific ones) into each repo's Actions settings.
3. **Reuse** `security.yml`, `check.yml` hardening, and the `notify-failure` pattern.
4. **`start-of-play`** is the agentic command center repo — it should get the **revenue-dashboard** + **revenue-stop alert** pattern first (it owns deal orchestration).
5. **`MBM-Social`** should get failure alerts on its publish jobs (silent publish failure = missed content revenue).

---

## 7. Recommended Repo/Org Settings

- **Branch protection on `master`:** require `check.yml` (lint/typecheck/build/actionlint) to pass before merge.
- **Secret scanning + push protection** (GitHub Advanced Security, free on public; enable on private repos too).
- **`gh-pages`** is used for the public frontend — keep revenue dashboards **private** (artifacts + Telegram), never publish them to a public page.
- **Trim the repo size:** run `git rm --cached` for the now-gitignored state/log files and `git filter-repo` on the 474 MB of videos if checkout speed matters.

---

## 8. Definition of "Working"

The system is making money when the **revenue gate flips to `YES`** and the
**dashboard** shows: deals > 0, orders > 0, and hours-without-revenue reset.
Until then, every alert you get is a reason to **pick up the phone** — the
pipeline is the volume, the phone is the close.
