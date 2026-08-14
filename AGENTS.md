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

## Mission Registry

| Mission | Status | Description |
|---|---|---|
| M-021 | COMPLETE | MBM Social Production Launch — multi-brand, autonomous runtime, learning engine, night ops |
| M-022 | PLANNED | Production Activation — first real campaigns, OAuth setup, multi-platform publishing |

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
