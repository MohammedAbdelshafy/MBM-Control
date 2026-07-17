# MBM.md — MBM Ops (Lead Gen, Outreach, Real Estate)

## Purpose & Subsystems

MBM Ops is the operational arm of the Contech AI monorepo. It automates three revenue-generating workflows:

- **Lead Generation** — Discover, score, and qualify distressed sellers, wholesalers, and real estate buyers from public records and third-party APIs.
- **Outreach** — Email-based agency outreach with templated campaigns, bounce handling, follow-up scheduling, and deal pipeline tracking.
- **Real Estate Scripts** — Auction scraping, skip tracing, multi-market deployment, pain-point discovery, and transaction matching.

## Directory Structure

| Directory | Purpose |
|---|---|
| `Artifacts/` | Output files: lead CSVs, mission reports, QA reports, scored/qualified lists |
| `Clients/` | Per-client workspaces (BAGA, Internal) |
| `Config/` | Runtime configuration files |
| `Constitution/` | Operating principles (ChatGPT -> Jarvis -> Antigravity pipeline) |
| `Contacts/` | Contact records and lookups |
| `Knowledge/` | Reference knowledge base (Markdown) |
| `LeadPacks/` | Date-stamped lead pack output directories |
| `LeadPoster/` | Lead posting automation |
| `LessonsLearned/` | Post-mortem and retrospective docs |
| `Logs/` | Pipeline run logs, decision log, KPI tracker |
| `Memory/` | Agent memory: architecture, campaigns, competitors, customers, experiments, hooks, KPIs, lessons, models, prompts, revenue |
| `Missions/` | Mission briefs (BAGA sprints, simulated dry runs), inbox/in-progress/review folders |
| `MultiMarket/` | Multi-market deployment configs |
| `Outreach/` | Outreach logs (CSV with send/bounce/followup history) |
| `PainPoints/` | Discovered pain-point data for solution pitching |
| `ParkingLot/` | Backlog and parked ideas |
| `Pipeline/` | Deal pipeline CSV (company, email, phone, deal value, stage, followup dates) |
| `Reports/` | Hunt reports and periodic summaries |
| `Scripts/` | All automation scripts (Python + PowerShell) |
| `Skills/` | Reusable skill definitions |
| `SOPs/` | Standard operating procedures |
| `Targets/` | JSON files with new target discoveries |
| `Templates/` | Outreach and campaign templates |
| `Wholesale/` | Wholesaler-specific pipeline and data |

## Scripts Overview

Scripts live in `MBM/Scripts/` and are organized by function:

**Lead Discovery & Collection**
- `collect_all_leads.py`, `daily_lead_pack.py` — Daily lead gathering from free/public sources
- `free_lead_engine.py` — Free-tier lead engine
- `new_target_discovery.py` — Discover new targets from public records
- `skip_trace_leads.py` — Enrich leads with contact data via skip-tracing API
- `multi_city_violations.py` — Code-violation scraping across multiple cities
- `auction_scraper.py` — Scrape foreclosure auction data

**Lead Scoring & Qualification**
- `lead_scorer.py` — Weight-based scoring (vacant, boarding, code concern, rental, etc.)
- `lead_qualification.py` — Qualification filtering
- `matching_engine.py` — Match leads to buyer preferences (cash buyer, wholesaler, investor)

**Pain Points & Sales**
- `pain_point_discovery.py` — Scans reviews, job postings, social media for business pain points
- `pain_point_sales_pipeline.py` — AI solution pitching based on pain points
- `sales_catalog.py`, `sales_pipeline.py` — Product catalog and sales pipeline automation

**Outreach & Email**
- `outreach_pipeline.py` — SMTP-based email outreach with attachments and logging
- `outreach_templates.py` — Agency cold-email and DM template library
- `email_sender.py` — Generic email send utility
- `demo_outreach.py` — Demo campaign outreach

**QA & Verification**
- `qa_001.py`, `qa_002_verification.py` — Quality assurance checks on lead data
- `evidence_collector.py` — Collects evidence for qualification decisions
- `revenue_review.py` — Revenue-focused review gate

**Pipeline Orchestration**
- `pipeline_runner.ps1` — Sequential step runner with logging and Telegram notifications
- `lead_engine_forever.ps1` — Scheduler-triggered cycle (retry logic, heartbeat, Telegram)
- `simulated_pipeline.py` — Dry-run / test pipeline

**Monitoring & Notifications**
- `telegram_listener.py`, `telegram_notify.py` — Telegram bot integration for alerts and summaries
- `watchdog.ps1` — Liveness monitor for the lead engine

**Utilities**
- `reusable_parsers.py` — Shared parsing helpers
- `roi_calculator.py` — ROI projection for deals
- `memory_manager.py` — Agent memory read/write
- `setup_daily_schedule.ps1`, `install_scheduler.ps1`, `install_scheduler.bat` — Task scheduler setup

**Sub-packages** (each with their own scripts):
- `keelead/`, `leadhunter/`, `leadhunter-pro/` — Specialized hunter agent scripts
- `lead-pipeline/` — Lead pipeline sub-modules
- `wholesaile/` — Wholesaler workflow scripts

**Text templates:**
- `email_diamond_acquisitions.txt`, `email_piphouse.txt`, `email_swift_home.txt` — Pre-written email bodies for specific agency targets

## Lead Pipeline Flow

1. **Discover** — `new_target_discovery.py` / `multi_city_violations.py` / `auction_scraper.py` pull raw leads from public records and code-violation databases.
2. **Collect** — `daily_lead_pack.py` / `collect_all_leads.py` aggregate raw leads into date-stamped packs in `LeadPacks/`.
3. **Skip Trace** — `skip_trace_leads.py` enriches leads with phone/email via skip-tracing API.
4. **Score** — `lead_scorer.py` assigns weighted scores based on distress signals (vacancy, code concerns, equity, rental status).
5. **Match** — `matching_engine.py` pairs scored leads with buyer preferences (cash buyers, wholesalers, investors).
6. **Verify** — `lead_qualification.py` + `qa_001.py` / `qa_002_verification.py` filter duds and cross-reference data.
7. **Package** — Qualified leads are written to `Artifacts/` as CSVs and staged for outreach.
8. **Outreach** — `outreach_pipeline.py` sends templated emails, logs bounces, and updates `Pipeline/pipeline.csv`.
9. **Follow-up** — Pipeline CSV tracks deal stage (outreach_sent, bounced, meeting_scheduled, closed) and next followup dates.

## Key Commands

```bash
npm run hunt           # Run client hunter (lead discovery + scoring + matching)
npm run hunt:send      # Run hunter and send outreach emails
npm run hunt:report    # Generate hunt report
```

Pipeline automation (PowerShell):
```powershell
# Full lead engine cycle (scheduler-triggered)
.\Scripts\lead_engine_forever.ps1

# Sequential pipeline runner
.\Scripts\pipeline_runner.ps1
```

## Environment Variables

Copy `.env.example` to `.env` and set:

| Variable | Required | Purpose |
|---|---|---|
| `PROPSTREAM_API_KEY` | Yes | PropStream API for signal stacking (Absentee + 7yrs + Equity + Distress) |
| `SKIP_TRACING_API_KEY` | Yes | Skip-tracing API (Twilio / BatchLeads) for contact verification |
| `OPENAI_API_KEY` | No | LLM fallback when local Ollama is insufficient for QA reasoning |
| `ANTHROPIC_API_KEY` | No | LLM fallback for complex reasoning tasks |
