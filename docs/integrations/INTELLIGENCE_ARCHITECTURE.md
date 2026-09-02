# Intelligence → Content → Monetization — Architecture Report

## 0) Operating Principle

`agent -> typed tool interface -> normalized internal contract -> existing system` over browser automation. Official MCP/API/SDK only (§0).

## 1) Audit Findings (READ-ONLY phase)

### Repo shape
- Root: `base44-ai-app` (Vite 6 + React 18 + Tailwind + Radix + Express `server/index.js` on :3002, Supabase, canvas-confetti, recharts)
- LeadEngine: `MBM/LeadEngine/` (~360 Python modules) — P0 `daily_lead_ingest.py` is the canonical orchestrator (stages: source_fetch -> raw_ingest -> phone_identity -> provenance -> synthetic -> dedupe -> suppression/DNC -> classification -> script -> canonical_write -> revision_audit -> queue_prioritization -> live_verification). Current live DB: `mbm-dialer/app/public/leads_database.json` = **4,953 records, revision 91** (author `REAL_PHONE_RECOVERY_ENGINE`). Writer: `MBM/GLM/single_writer_lock.py:66 DialerSingleWriter` (thread lock + file lock + 30s stale break + monotonic revision + checksum + validate-before-replace + atomic `os.replace` + fsync + backup + audit sidecar).
- AD Engine: `MBM/LeadEngine/ad_orchestrator.py` + `ad_repository.py` (Supabase with JSON fallback, env-gated PRODUCTION/STAGING/LOCAL/TEST) + `ad_service.py`. Buy boxes, deals, social routing, demand signals, revenue events.
- Clipping Factory: `clipping-factory/backend` (FastAPI + Celery) + `clipping-factory/MBM-Social/mbm_social/` (brand_router, pipeline, autonomous_runtime, learning_engine, night_operations, crayo_engine wiring candidate_pool -> routing_decision -> content_intelligence -> video_editing -> publishing (retry/idempotency/DLQ + circuit_breaker) -> revenue_attribution -> learning_feedback -> observability).
- MBM Dialer: TanStack Start SSR app, bare JSON list at `/leads_database.json`, TanStack query, exposed at `mbm-dialer/app/public/`.
- Supabase migrations `00001..00019` (users, buildings, email_queue, pg_cron, lead_pipeline_logs, voice_agents, etc.). No property tables yet — shapes in `MBM/LeadEngine/property_intel/schema.py`.
- CI: `check.yml` (lint -> typecheck -> build), `schedule.yml` hourly email + lead pipeline, `health-report.yml` nightly.
- .gitignore is `/*` allowlist; `!/MBM/**` so new `MBM/LeadEngine/intelligence/` is tracked. Secrets gitignored.

### Existing integration abstractions
- `server/dialer/telephonyProvider.js` (provider abstraction), `server/neteller.js` (canonical monetization rail), `MBM/LeadEngine/ad_repository.py` (Supabase/JSON abstraction), `MBM/LeadEngine/property_intel/free_first_gateway.py` (multi-source), `clipping-factory/MBM-Social/mbm_social/circuit_breaker.py` + `publishing.py` (retry/idempotency/DLQ), `MBM/GLM/single_writer_lock.py` (sole writer).
- Retry is ad-hoc per module; no global resilience bus. No central idempotency store for generations — now added as `intelligence/jobs.py`.

### Safe insertion points
- Intelligence layer is **additive files** only; no existing file modified except `.env.example` (docs). New tables would be additive (`intelligence_events`, `content_opportunities`, etc.) inspected and found non-duplicative.
- Entry points for future dialer injection: `daily_lead_ingest.py:_build_row` + `DialerSingleWriter.commit_update` (use only via that path, §14).

## 2) Provider Verification Matrix (stub — live verification required before removing pending flags)

| Tool | Claim | Repo | License | API Surface | Auth | Confidence | Implementation Value | Status |
|---|---|---|---|---|---|---|---|---|
| World Monitor | MCP/REST/SDK/CLI, open-source, AGPL-3.0 | `koala73/worldmonitor` (per prompt, re-verify) | AGPL-3.0 | MCP `tools/list`, REST `/api/events` etc. (docs) | Bearer | High (design avoids AGPL vendoring) | Very high | allow |
| Topview | AI video agent + API repo | vendor GH (unverified URL) | Proprietary | `api.topview.ai` (pending verify) | Bearer | Medium | Very high | allow_pending_verification |
| SkySnail | AI thumbnail, transcript, avatars, 4K | unverified | Proprietary | `api.skysnail.ai` (pending) | Bearer | Medium | High | allow_pending_verification |
| Anderro | Affiliate marketplace, rates vary (30% observed) | `anderro.com` | Proprietary | `/api/offers` etc. (pending) | Bearer if exists | Medium | High | allow_pending_verification |
| VoxCPM | Zero-shot voice clone, misuse warning | canonical OSS (find org) | OSS TBD | self-host | n/a | Low (needs repo ID) | Gated | gated |
| voxcpm.net | Similar name | unverified | unknown | unknown | — | Do not trust | — | blocked |
| McStumble | Browser utility hub | — | — | n/a | — | Medium | — | (not wired) |
| Famelack | Live-TV aggregator, copyright disclaimer | — | — | n/a | — | Research only | — | research_only |
| AnkerGames | Pre-installed commercial games | — | — | — | — | Flagged by scanners | — | blocked |
| Vidbox.dev | Streaming clone, newly registered | — | — | — | — | High risk | — | blocked |

Never trust viral post as source of truth; similarly named domains not authoritative (§3).

## 3) Data Flow (Implemented)

```
World Monitor (MCP/REST) --WorldMonitorAdapter--> IntelligenceEngine --IntelligenceStore--> OpportunityEngine --ContentOrchestrator--+--> TopviewAdapter (GenerationJob)
                                                                                              |                                  +--> SkySnailAdapter (CreativeVariant)
                                                                                              |                                          |
                                                                                              +-----> QA Gate -> Human Approval -> existing publishing (clipping-factory/MBM-Social)
```

- Every external call is a `GenerationJob` (QUEUED/RUNNING/SUCCEEDED/FAILED/BLOCKED/RETRYING/CANCELLED) with bounded retries (§16).
- Provenance (`provider/tool/retrievedAt/sourceUrl/transform`) survives every transformation (§5).
- Affiliate rates are live `AffiliateOffer` with `confidence` + `status` (VERIFIED/NOT_VERIFIED/BLOCKED); never fabricated (`anderro_adapter.py:_normalize_offers`).

## 4) Database Design

Additive, not destructive (§15). Inspected `supabase/migrations` and `property_intel/schema.py` — no collision. For now JSON under `MBM/Artifacts/intelligence/` (gitignored-friendly; mirrors AD fallback pattern). Supabase migration (future) would be additive:

```sql
create table if not exists intelligence_events (id text primary key, source text, category text, title text, summary text, entities text[], locations text[], topics text[], confidence float, freshness_seconds int, raw_reference text, provenance jsonb, retrieved_at timestamptz);
create table if not exists content_opportunities (id text primary key, intelligence_event_id text references intelligence_events, niche text, hook text, angle text, opportunity_score float, monetization_offer_id text, provenance jsonb);
create table if not exists affiliate_offers (...);
create table if not exists generation_jobs (id text primary key, provider text, provider_job_id text, input_hash text unique, status text, attempts int, ...);
```

Stable IDs + idempotency keys (`input_hash`, `idempotencyKey`) enforced.

## 5) Security

Env-only secrets, redaction, timeout, bounded retry, rate-limit, schema validation, SSRF allowlist, content-type/payload-size, idempotency, audit log, health checks (§12). See `docs/integrations/INTELLIGENCE_RUNBOOK.md` §6.

## 6) Git Safety

Branch `master` ahead of `origin/master` by 3, dirty working tree noted before any edit. No force-push, no history rewrite, small additive commits. Checkpoint is the current revision sidecar (rev 91).

## 7) Test Plan

See §18: 25 hermetic tests for adapters/engines/policy; plus `test_dialer_integrity_gate.py` proves lead pipeline untouched. Remaining: live contract tests (require real creds) + chaos tests (rate limit / malformed).

## 8) License Risks

AGPL avoidance by API/MCP consumption (World Monitor). Pending verification per `license-review.md`. Topview/SkySnail/Anderro proprietary ToS pending. VoxCPM gated.

## 9) Rollback

Feature-flag instant OFF; code revert is `git revert` + delete `MBM/Artifacts/intelligence/` (additive, no migration).
