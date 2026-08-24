# AGENTS.md — Base44 Control Plane

## Project Context

Monorepo with four subsystems:
- **Frontend** (`src/`) — React 18 + Vite 6 + Tailwind dashboard with shadcn/ui (Radix primitives)
- **Clipping Factory** (`clipping-factory/`) — Python/FastAPI video pipeline + Celery + Docker
- **MBM Social** (`clipping-factory/MBM-Social/`) — Brand management & multi-channel YouTube publishing
- **MBM Ops** (`MBM/`) — Lead-gen, outreach, real estate scripts
- **Lead Engine** (`MBM/LeadEngine/`) — Property intelligence & lead gen platform (TypeScript/Fastify/BullMQ)

## Monetization: Neteller (canonical rail)

ALL checkout/payout surfaces route through the **Neteller** wallet
(`abdelshafyclapps@gmail.com`, Account ID `4599228811`). Stripe was removed.

Canonical link builders (one source of truth, all three read `NETELLER_*` env):
- Python: `MBM/Scripts/neteller_config.py` → `neteller_link(amount, item, currency="USD", **kw)`
- Node (ESM): `server/neteller.js` → `netellerLink(amount, item, opts)`
- Frontend: `src/lib/neteller.js` → `netellerLink(amount, item, opts)`

Link format: `https://member.neteller.com/pay?email=<enc>&account=<id>&amount=X.XX&currency=USD&item=SKU`.

Python scripts import via a sys.path bootstrap (`parents[2]` = repo root) then
`from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID`,
with a local `def neteller_link` fallback inside `try/except Exception`.

Exceptions (deliberate, user-approved): the **Whop storefront** (`MBM/Whop/whop_monetize.py`)
remains a separate hosted sales channel; marketplaces listings (`digital_product_store.py`
gumroad/whop/etsy metadata) are distribution channels, not checkout rails.

## Workflow Rules

| Phase | Mode | What You Do |
|---|---|---|
| **plan** | read-only | Inspect, diagnose, propose. NO file edits. |
| **build** | full | Implement approved changes. One scope at a time. |
| **verify** | read-only | Test, lint, review. NO additional edits. Report issues. |

Default: **plan**. Switch with `/opencode build` or `/opencode verify`.

## Real-Lead Pipeline (Track 1-4, profit sprint)

The old feeds (`propertyleads.com` personas, generated phones) were fabricated and produced 0 conversions. The honest path uses the **free US government CMS NPI registry** — every row is a real, licensed business with a real phone.

```bash
npm run leads:hygiene        # Gate: strip synthetic rows (phone+DNS+persona) -> Artifacts
npm run leads:callsheet       # Pull fresh REAL healthcare businesses from NPI registry
npm run leads:recover         # Report;  --apply purges fake rows from live queues (backup first)
npm run leads:dial            # Dry-run ranked dial list (rings your mobile via Twilio bridge)
npm run leads:dial:live       # Place real calls -> your phone, bridged to real clinic
npm run leads:sellers         # Dry-run hybrid seller skip-trace (DCAD->RapidAPI->GMaps->free). --apply writes (backup .bak)
npm run leads:gate:audit      # Audit every dialer queue against the verification gate
npm run leads:all             # hygiene + fresh callsheet in one shot
npm run leads:ingest          # P0 daily ingestion: verify -> dedupe -> classify -> script -> canonical write -> LIVE VERIFY (dry-run)
npm run leads:ingest:apply    # P0 daily ingestion COMMIT (--apply; fails unless canonical write + live dialer check pass)
npm run leads:pack            # Build monthly lead pack (dry-run; gate blocks unverified)
npm run leads:pack:apply      # Write lead pack CSV + brief + manifest + Whop spec
```

New scripts: `MBM/Scripts/lead_hygiene.py`, `MBM/Scripts/revenue_recovery.py`,
`MBM/LeadEngine/npi_verified_callsheet.py`, `MBM/LeadEngine/close_queue_dialer.py`,
`MBM/LeadEngine/seller_skip_tracer.py`, `MBM/LeadEngine/dialer_verification_gate.py`,
`MBM/LeadEngine/lead_pack_builder.py`.
`schedule.yml` runs `hourly-npi-callsheet` (once/day at UTC 00) to keep a fresh
verified call sheet. Twilio Lookup (number-level verify) returned 401 — account
needs the separate Lookup product enabled; NPI-registry phones are already real.

## Property Intelligence (Issue #23, data side)

Package: `MBM/LeadEngine/property_intel/` — fresh Auction pipeline,
authoritative county ownership verification, business-owner AI-services
prospecting, scoring/ranking with reason traces. See `property_intel/README.md`
and `property_intel/REPORT.md`. **Never fabricate** owners/phones/auction rows;
a blocked/missing source returns `blocked`/`NOT_FOUND`, never mock data.

```bash
npm run leads:prop            # Offline pipeline dry-run on sample fixture
npm run leads:prop:live       # Live DCAD ownership verify + artifacts (--verify-live --apply)
npm run leads:prop:test       # Hermetic test suite (83 tests, no network)
npm run leads:auction         # Auction.com freshness (file/dry-run)
npm run leads:auction:live    # Live scrape (currently BLOCKED by Incapsula)
npm run leads:biz             # Business prospector (needs RAPIDAPI_KEY; 429 observed)
npm run leads:biz:file        # Offline business scoring on sample rows
```

- Ownership verified live (2026-08-15) for **Dallas (DCAD)**: real owners + APN.
  Tarrant/Harris/Collin ArcGIS endpoints are reachable but slower; Harris address
  matches are ambiguous → CONFLICT until an APN is provided.
- Ambiguity rule: multiple distinct owners at one site address → **CONFLICT**,
  no owner asserted (see `ownership_verifier.py::_build`).
- Callability is hard-capped ≤39 without a real phone/verified owner, and for
  any recorded `BAD_NUMBER`/`WRONG_PERSON`/`NON_OWNER`/`DNC` — garbage is never
  recycled into the prime queue (`PRIME_QUEUE_CALLABILITY=50`).
- Auction.com live scrape is blocked by Imperva/Incapsula; RapidAPI Google Maps
  returned HTTP 429. Both are documented blockers, not papered over.
- Supabase property tables (properties/parcels/owners/auctions/evidence/
  lead_scores) do not exist yet — canonical record shapes are in `schema.py`.

## Phound SMS Blasting (canonical outbound rail)

Twilio is dead for this workflow. SMS outreach routes through **Phound**:

```bash
npm run leads:sms            # Dry-run Phound Wave campaign (default safe)
npm run leads:sms:list       # List eligible leads (VERIFIED, not opted-out)
npm run leads:sms:apply      # Write campaign bundle (CSV + JSON + history)
```

- Engine: `MBM/LeadEngine/phound_wave_campaign.py` — reads
  `mbm-dialer/app/public/leads_database.json`, filters VERIFIED rows for the
  vertical, builds personalized messages with `neteller_link()` checkout links,
  excludes opted-out/STOP numbers, writes to `logs/phound_wave/` (gitignored).
- Secure boundary: `server/dialer/phoundSmsProvider.js` (+ test) — native-app
  mode returns `https://web.phound.app/?phone=...` prefill links; API mode stays
  **disabled** until Phound provisions `PHOUND_SMS_ENDPOINT` + `PHOUND_API_TOKEN`.
- Blasters repointed to Phound: `extreme_sales_blaster.py`,
  `twilio_whatsapp_direct_blaster.py` (now "Phound Direct Blaster", Neteller-linked).
- **Never** hardcode Twilio SID/token — all `TWILIO_*` reads are env-only (no fallback).
- Phound Wave requires Pro/Business plan + TCR campaign registration for volume.

## Key Boundaries

- **Base44**: See `base44/` config. Use `base44 dev` for local backend.
- **Clipping Factory**: See `clipping-factory/CLIPPING.md` for pipeline, agents, Docker stack.
- **MBM Social**: See `clipping-factory/MBM-Social/SOCIAL.md` for brand config, publishing, analytics.
- **MBM Ops**: See `MBM/MBM.md` for lead-gen, scripts, outreach, real estate.
- **Lead Engine**: See `MBM/LeadEngine/` — TypeScript/Fastify, Prisma/PostgreSQL, BullMQ/Redis.

## Quick Reference

```bash
npm run dev              # Frontend dev server (port 5173, proxies /api to :3002)
npm run lint && npm run typecheck && npm run build   # Pre-commit gate
npm run clip:build       # Build one clip (uses .venv\Scripts\python.exe — Windows)
npm run clip:server      # docker compose up (Full stack: api/workers/beat/redis/postgres/minio)
npm run clip:seed        # Seed demo campaigns
npm run hunt:send        # Send outreach emails (clientHunter.js)
npm run send-emails      # Drain email queue (emailSender.js)
npm run demo:campaign    # Generate demo campaign data
```

## CLI Quirks

- **`clip:*` scripts** hardcode `.venv\Scripts\python.exe` (Windows). They also force `DATABASE_URL` to localhost in `build_one_clip.py` — overriding Neon/Supabase.
- **`npm run server`** starts the Express server (index.js) — also starts email/lead pipeline daemons.
- **`npm run start`** runs `start.cjs` (separate entry from `server`).
- **jsconfig.json** typechecks only `src/components/**/*.js`, `src/pages/**/*.jsx`, `src/Layout.jsx` — high `maxNodeModuleJsDepth: 0` means no auto-typing.
- **vite.config.js** proxies `/api/*` → `http://localhost:3002`. The Express server must be running for API calls.
- **`.gitignore`** is structured as `/*` (ignore all) then `!/path/` (un-ignore selectively). New root-level directories must be explicitly added to `.gitignore`.

## CI Pipeline

`.github/workflows/`:
- `check.yml` — lint → typecheck → build (concurrent lint/typecheck, serial build). Auto-fix on master.
- `schedule.yml` — Hourly: email queue (with dry-run support) + lead pipeline + clipping.com scan
- `health-report.yml` — Nightly (06:00 UTC): workflow file check, env.example coverage, README freshness
- `mbm-social.yml` — Brand validation + dir verification + pipeline import test on MBM-Social changes

## Subsystem Docs

Each subsystem has a dedicated `.md` at its root:
- `clipping-factory/CLIPPING.md` — 12-container Docker stack, 15 agents, beat schedule, API routes
- `clipping-factory/MBM-Social/SOCIAL.md` — 5 brands, 10 campaign profiles, autonomous runtime, learning engine, night operations
- `MBM/MBM.md` — 20+ directory structure, 50+ scripts, lead pipeline flow

## MBM-Social Modules

`clipping-factory/MBM-Social/mbm_social/` contains:
| Module | Purpose |
|---|---|
| `brand_config.py` | Registry + brand YAML loader |
| `brand_router.py` | Brand-fit scoring and channel selection |
| `model_registry.py` | Local LLM routing (Ollama) |
| `pipeline.py` | End-to-end publish flow (manual trigger) |
| `autonomous_runtime.py` | Full 14-stage autonomous campaign lifecycle |
| `learning_engine.py` | Self-improving analytics memory + auto weight adjustment |
| `night_operations.py` | 10 automated overnight maintenance missions |
| `publish_package.py` | Build brand-aware title/desc/hashtags/thumb text |
| `publisher.py` | Playwright YouTube Studio publisher |
| `youtube_api_publisher.py` | YouTube Data API v3 publisher |
| `candidate_pool.py` | Phase 1: large candidate pool (10/25/50/100/250) + 8-axis scoring + selection |
| `video_editing.py` | Phase 2: ffmpeg reframe (9:16/16:9/1:1) + caption burn-in command builder |
| `content_intelligence.py` | Phase 3: hook/title/desc/caption/hashtags/CTA via Model Registry |
| `distribution_optimizer.py` | Phase 5: volume controls + performance auto-scaling + caps |
| `routing_decision.py` | Phase 4: WHERE/WHEN/SHOULD/variant decision (reuses routing + platform_registry) |
| `publishing.py` | Phase 6: resilient publish (retry/backoff/idempotency/DLQ) wrapper |
| `revenue_attribution.py` | Phase 7: configurable RPM, ESTIMATED vs ACTUAL, ROI |
| `observability.py` | Phase 11: metrics aggregator |
| `learning_feedback.py` | Phase 8: Enterprise Memory learning loop wrapper |
| `crayo_engine.py` | Canonical Crayo-class loop orchestrator (wires Phases 1–11) |

## Mission Registry

| Mission | Status | Description |
|---|---|---|
| M-021 | COMPLETE | MBM Social Production Launch — multi-brand, autonomous runtime, learning engine, night ops |
| M-022 | COMPLETE | Production Revision — audit, P0 fixes, resilient runtime (event bus/checkpoint/circuit breaker/DLQ), honest platform matrix (YT supported; IG/TikTok manual; LI/X blocked), quality gates, client mode, websites, GitHub App, 21 hermetic tests. Blockers tracked as GitHub issues #10–#16 |
| M-023 | COMPLETE | Crayo-Class Engine — candidate pool (10/25/50/100/250) + 8-axis scoring, auto-edit (ffmpeg reframe/captions), content intelligence, routing decision, distribution optimizer, resilient publishing (retry/idempotency/DLQ), revenue attribution (estimated vs actual), learning loop, observability, crayo_engine orchestrator. Reuses viral_intelligence/content_rewards/routing/learning_engine. 24 hermetic tests. Tracking #17, brief link #22, deferred #18–#22 |

## Server Scripts (Node.js)

`server/` contains Express-based micro-services:
| Script | Function |
|---|---|
| `index.js` | Express server + email queue daemon |
| `emailSender.js` | Drains `email_queue` (qued→sent) via SMTP |
| `leadPipeline.js` | Lead pipeline processor |
| `clientHunter.js` | Client outreach + email campaign |
| `demoCampaign.js` | Demo data generator (--generate, --campaign, --once, --daemon) |
| `demoBuilder.js` | Demo clip builder |

## Supabase

`supabase/` contains Edge Functions and migrations:
- `functions/run-lead-pipeline/` — Triggered lead pipeline
- `functions/scan-clipping-campaigns/` — Campaign scan Edge Function
- `functions/send-email-queue/` — Email queue sender
- `functions/add-to-email-queue/` — Queue email endpoint
- `migrations/0000*` — DB schema: email_queue, client_orders, employees, lead_pipeline_logs, pg_cron schedules

## GLM Swarm Architecture (`MBM/GLM/`)

Central deep-reasoning engineering intelligence layer across all MBM repositories:
- **`orchestrator.py`**: Coordinates swarm audits, ranks missions, and manages regression gates.
- **`agent_registry.py`**: 16 specialized engineering roles across 3 model tiers (`LIGHT`, `MEDIUM`, `DEEP_GLM`).
- **`mission_router.py`**: Priority formula: $\text{Priority} = \text{Business} \times \text{Revenue} \times \text{Prob} \times \text{Urgency}$.
- **`single_writer_lock.py`**: SOLE authorized gateway for mutating `leads_database.json` (Zero dataset shrinkage invariant).
- **`mission_ledger.py`**: Persistent execution records and active file mutex locks.
- **`delivery_report.py`**: Generates `DAILY_GLM_ENGINEERING_REPORT.md` (Money & Progress first).

### Single-Writer Production Rule
All background processes, daemons, and scripts updating `mbm-dialer/app/public/leads_database.json` MUST use `MBM.GLM.single_writer_lock.DialerSingleWriter`. Direct file overwrites or dataset shrinkage (< initial count) are strictly blocked.

## Output Contract

Every workflow emits:
```
status: success | failure | skipped
inputs: { ... }
outputs: { ... }
errors: [ ... ]
next_action: string
owner: "system" | "human"
timestamp: ISO8601
```

