# MBM AI Network — Existing Capabilities Inventory

All functional components, APIs, and data stores currently within the MBM workspace.

## Subsystems

| # | Name | Type | File Path | Core Function |
|---|------|------|-----------|---------------|
| 1 | MBM Dialer | CLI | `MBM-Dialer/app` | Voice call platform; lead scoring; skip-trace; real-time analytics; canvas-based 2D UI |
| 2 | Lead Engine | Python | `MBM/LeadEngine/` | Lead collection, enrichment, NPI verification, skip-trace verification, score-based prioritization |
| 3 | MBM Social | Python | `MBM-Social/` | Multi-channel publishing (TikTok, Instagram Reels, YouTube, LinkedIn); video generation; async runtime |
| 4 | Jarvis Orchestrator | Python | `MBM/LeadEngine/jarvis_orchestrator.py` | Agent-based workflow engine; approval gating; cross-system task routing |
| 5 | Server (Express) | Node.js | `server/` | API endpoints; email queue daemon; lead pipeline; demo campaigns; Twilio integration |
| 6 | Phone Normalization | Python | `MBM/LeadEngine/cleanPhone()` | E.164 normalization; 555/000 rejection; phone deduplication |
| 7 | CRM Sync (Airtable) | Python | `MBM/LeadEngine/airtable_sync.py` | Real Airtable REST API sync; upsert; field mapping |
| 8 | CRM Sync (HubSpot) | Python | `MBM/LeadEngine/hubspot_sync.py` | HubSpot API integration; workflow + trigger mapping |
| 9 | AI ChatGPT Script Generator | Python | `MBM/LeadEngine/cgpt_script_generator.py` | Per-lead script generation via OpenAI chat completions; template fallback |
| 10 | AI Lead Export | Python | `MBM/LeadEngine/dialer_export.py` | Leads JSON → CSV; Airtable sync |
| 11 | AI Lead Enrichment | Python | `MBM/LeadEngine/contact_enrichment.py` | NPI lookups; CMS NPI registry; owner verification |
| 12 | AI Agent Pipeline | Python | `MBM/LeadEngine/agent_factory.py` | Agent creation; task routing; multi-agent orchestration |
| 13 | AI Research Agent | Python | `MBM/LeadEngine/ai_research.py` | Market research; competitor intelligence; trend detection |
| 14 | AI Field Service | Python | `MBM/LeadEngine/field_service.py` | Technician dispatch; work orders; field reports |
| 15 | AI Document Extraction | Python | `MBM/LeadEngine/doc_extraction.py` | PDF/email/table extraction; BOQ extraction; tender analysis |
| 16 | AI Lead Intelligence | Python | `MBM/LeadEngine/lead_intelligence.py` | Scoring; pipeline analytics; ROI assessment |
| 17 | AI Operations Agent | Python | `MBM/LeadEngine/ai_agent.py` | Routing; scheduling; exception handling; reporting |
| 18 | AI Customer Agent | Python | `MBM/LeadEngine/customer_agent.py` | Support qualification; escalation; next-best-action |
| 19 | AI Company Brain | Python | `MBM/LeadEngine/company_brain.py` | Internal knowledge; SOP retrieval; controlled actions |
| 20 | AI Research Agent | Python | `MBM/LeadEngine/ai_research.py` | Market + competitor + supplier + customer research |
| 21 | AI Finance Operations | Python | `MBM/LeadEngine/finance_ops.py` | Invoice matching; AP/AR; reporting; cash-flow alerts |
| 22 | AI Construction Intelligence | Python | `MBM/LeadEngine/construction_intel.py` | BOQ; tender; estimate; supplier; project workflow |
| 23 | AI Content Generation | Python | `MBM/LeadEngine/content_gen.py` | Content creation; SEO; repurposing; publishing |
| 24 | AI Executive Intelligence | Python | `MBM/LeadEngine/executive_intel.py` | Meeting summaries; email intelligence; dashboards |
| 25 | AI Automation Recipes | Python | `MBM/LeadEngine/ai_recipes.py` | Reusable automation templates; triggers; actions; approvals |

## Data Stores

| Store | Location | Schema | Notes |
|-------|----------|--------|-------|
| `leads_database.json` | `app/public/` | List of leads with fields: id, company, contact, phone, vertical, skip_trace_status, skip_trace_source, skip_trace_confidence, skip_trace_phone_alt, npi_number, details (Call_Script, Owner_Name, Owner_Title, verified_phone, city, state, address, taxonomy) | Full lead warehouse |
| `publish_queue/*.json` | `MBM-Social/publish_queue/` | Each file is a publish-ready draft: brand, title, description, video_path, is_short, metadata, tags, status, scheduled_for, metrics | Orchestrated by post_orchestrator |
| `MBM/LeadEngine/logs/` | `MBM/LeadEngine/logs/` | Dispositions (call_log), call_list (tonight), weekly stats, upwork jobs | Pipeline execution artifacts |
| `MBM/Artifacts/` | `MBM/Artifacts/` | CSV exports: Final_Qualified_Leads.csv, Verification_Report.csv, all_states_ictdialer_import.csv | Staging exports |

## Technical

| Capability | Implementation | Status |
|------------|---------------|--------|
| Python (3.10+) | `MBM/LeadEngine/` | Production |
| Node.js (Express) | `server/` | Production |
| React/Vite 6 | `MBM-Dialer/app/` | Production |
| Docker | `clipping-factory/` (full Docker Compose) | Production |
| PostgreSQL | `MBM/LeadEngine/` (Postgres via Prisma) | Production |
| Redis | BullMQ queues | Production |
| Supabase Edge Functions | `functions/` | Production |
| Airflow-style cron | `server/index.js` (node-cron) | Production |
| Twilio API | DIALER + LEAD ENGINE integration | Production |
| Airtable API | `airtable_sync.py` | Prototype (needs keys) |
| HubSpot API | `hubspot_sync.py` | Prototype |
| OpenAI/OpenRouter | `cgpt_script_generator.py` | Prototype |
| FFmpeg | `generate_all_shorts_mp4.py` | Production |
| Canva API | `MBM-Social/publish_package.py` | Production |
| GROQ/OpenAI model | `learning_engine.py` | Production |
| HTML2Canvas | `app/src/components/gallery/` | Development |
| AI Clipping | `CLIPPING.md` pipeline | Production |

## Exports

- `MBM/Artifacts/Final_Qualified_Leads.csv`
- `MBM/Artifacts/Verification_Report.csv`
- `MBM/Artifacts/all_states_ictdialer_import.csv`
- `MBM/Config/heartbeat.json`

## Notes

- All paths are Windows absolute paths (C:\Users\omare\OneDrive\Desktop\AI\…).
- .gitignore: excludes all; specific paths un-ignored.
- `.env.example` contains placeholders for all required credentials.
