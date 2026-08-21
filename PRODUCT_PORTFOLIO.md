# AI Enhancement Company — Customer Product Portfolio

**Owner:** Founder / Strategic Brain (this document is updated whenever new work lands)
**Last updated:** 2026-08-19
**Rule:** every project, repo, agent, workflow, script, and experiment is evaluated on landing against this portfolio and classified as:
> CUSTOMER PRODUCT · REUSABLE COMPONENT · INTERNAL TOOL · DEAD-END EXPERIMENT

---

## 1. MASTER COMPANY ARCHITECTURE

```
AI ENHANCEMENT COMPANY
│
├── AI SALES            → Lead Engine, Qualification, Dialer, Outreach, Voice Agents
├── AI MARKETING        → Content Factory, Video Clipping, Social Automation, Content Intelligence
├── AI CONSTRUCTION     → BOQ Reader, Estimator, Supplier Intelligence, Procurement, Arabic UI
├── AI OPERATIONS       → Agents, Workflows, CRM, Reporting, Document Processing
├── AI INDUSTRIAL       → Waste Matching, Supplier Matching, Marketplace
└── AI AGENT PLATFORM   → Agent Registry, Worker System, Mission System, Orchestration, Billing
```

**Platform rule:** ONE core AI platform + reusable agents + reusable automations + reusable data pipelines + vertical customer apps. Never build a fully separate system when a shared component exists.

---

## 2. TOP 20 CUSTOMER APPLICATIONS (scored 0–100)

Scoring weights: Speed to MVP 15 · Speed to revenue 20 · Willingness to pay 20 · Reusability of MBM tech 15 · Low infra cost 10 · Competitive advantage 10 · Scalability 10

| # | Product | Score | Tier | Category | Who pays |
|---|---|---|---|---|---|
| 1 | AI Real Estate Wholesaler Lead Engine | 92 | A | Real Estate | Wholesalers/investors |
| 2 | AI Cold Calling Assistant (sales dialer + scripts) | 90 | A | Sales | SMB sales teams |
| 3 | Construction BOQ AI Estimator (Arabic UI) | 88 | A | Construction | Contractors, GCs, consultants |
| 4 | AI Lead Qualification Agent | 86 | A | Sales | Sales teams, agencies |
| 5 | Podcast-to-Shorts Content Factory | 84 | A | Social | Creators, agencies, coaches |
| 6 | AI Appointment Setter / AI Receptionist | 83 | A | Ops | Local businesses, clinics |
| 7 | Industrial Waste Matching Marketplace | 82 | A | Recycling | Factories, waste buyers |
| 8 | AI WhatsApp Business Assistant | 80 | A | Ops | Local businesses, e-commerce |
| 9 | AI Proposal/Quotation Generator | 78 | B | Document | B2B services, contractors |
| 10 | Supplier Price Intelligence (construction) | 77 | B | Construction | Contractors, procurement |
| 11 | White-label Outbound Sales Platform | 76 | B | Sales | Agencies, B2B SaaS |
| 12 | AI Social Media Manager (multi-brand autopilot) | 75 | B | Marketing | SMBs, agencies |
| 13 | AI Employee/Copilot System (per-role agents) | 74 | B | Operations | SMBs, agencies |
| 14 | AI Customer Support Agent | 72 | B | Ops | E-commerce, SaaS |
| 15 | AI Document-to-Database System | 71 | B | Document | Real estate, legal, logistics |
| 16 | AI CRM Assistant (pipeline automation) | 70 | B | Sales | SMBs, real estate |
| 17 | AI Reporting Agent (money & progress briefs) | 68 | B | Operations | Founders, ops teams |
| 18 | Vertical Agent Builder (no-code agent factory) | 66 | C | Platform | Agencies, SMBs |
| 19 | AI Operations Dashboard (multi-agent cockpit) | 62 | C | Platform | Ops teams |
| 20 | Multilingual Content Engine (subtitles/l10n) | 60 | C | Marketing | Global creators |

**TIER A** (build & sell immediately): #1–#8.
**TIER B** (build after first revenue): #9–#17.
**TIER C** (long-term platform): #18–#20.

---

## 3. TOP 5 FASTEST-TO-REVENUE

| Product | Why fast | Time to sellable | Stack |
|---|---|---|---|
| 1. AI Cold Calling Assistant | Dialer + script engine already live (mbm-dialer, 1,091 records) | ≤1 week | Existing dialer + Twilio/Phound |
| 2. AI Real Estate Wholesaler Lead Engine | Code-violation + NPI pipelines already run daily | 1–2 weeks | Existing LeadEngine |
| 3. AI Lead Qualification Agent | Verification gate + NPI registry already built | 1 week | Existing gate + API |
| 4. Construction BOQ AI Estimator | Estimator engine exists (concept stage) | 2–4 weeks | Python + local LLM |
| 5. AI Appointment Setter | Voice/agent infrastructure exists | 2–3 weeks | Twilio/Retell/Phound + CRM |

**Sell-first ladder (per product):** AI service → productized service → managed AI solution → SaaS → white-label platform. Sell before full SaaS.

---

## 4. TOP 5 HIGHEST-MRR PRODUCTS

| Product | Price range/mo | MRR potential @ 20 clients |
|---|---|---|
| Construction BOQ AI Estimator (Arabic) | $500–$2,000 | $10k–$40k |
| White-label Outbound Sales Platform | $499–$1,499 | $10k–$30k |
| AI Real Estate Wholesaler Lead Engine | $297–$997 | $6k–$20k |
| AI Social Media Manager (multi-brand) | $250–$1,000 | $5k–$20k |
| AI Cold Calling Assistant | $199–$799 | $4k–$16k |

---

## 5. TOP 5 EASIEST MVPs

| MVP | Scope | Reusable parts |
|---|---|---|
| AI Lead Qualification Agent | API + CSV in/out + verification gate | `dialer_verification_gate.py`, NPI callsheet |
| AI Cold Calling Assistant | Web dashboard + phone bridge + script gen | `mbm-dialer`, `close_queue_dialer.py`, Phound/Twilio bridge |
| AI Proposal/Quotation Generator | PDF in → itemized quote out | BOQ engine, Neteller rails |
| AI Appointment Setter | Form/WhatsApp → calendar + confirm | VoiceAgencyStudio, voice-agent-saas backend |
| AI Reporting Agent | Scheduled money & progress digest | `delivery_report.py`, GTM bus, Telegram adapter |

---

## 6. SHARED TECHNOLOGY COMPONENTS (build once, reuse everywhere)

| Module | Purpose | Current home |
|---|---|---|
| Auth + billing | Sessions, subscriptions, Neteller checkout | Neteller rails, Whop |
| CRM + leads | Canonical lead DB, dedupe, suppression, single-writer | `leads_database.json`, `dialerDbGateway.js`, `single_writer_lock.py` |
| Contacts/companies | Company + owner resolution, verification | `lead_provenance.py`, NPI/DCAD adapters |
| Documents | PDF/BOQ ingestion, extraction, itemization | `construction_estimator_engine.py` |
| AI agents | Registry, workers, missions, routing | `MBM/GLM/*` |
| Workflows | Daily refresh, hourly cron, artifact pipeline | `schedule.yml`, `daily_refresh.py` |
| Notifications | Email (Gmail SMTP), Telegram, WhatsApp, SMS (Phound) | `server/emailSender.js`, GTM bus |
| Voice | Call bridge, native-app prefill links, API provider | `server/dialer/phoundSmsProvider.js`, Twilio bridge |
| Dashboards | Sales cockpit, approval UI, terminal monitor | `src/`, Vite dashboard |
| Reporting | Money & progress, delivery reports, health reports | `delivery_report.py`, `.github/workflows/health-report.yml` |
| Knowledge base | Memory, lessons, SOPs, pain points | `MBM/Knowledge/`, `MBM/Memory/` |
| File ingestion + search | Content corpus, repo inventory | `content-engine/`, repomix |
| Analytics | KPIs, cost/usage, mission ledgers | `mission_ledger.py`, lead analytics |

---

## 7. EXISTING REPOSITORIES / COMPONENTS REUSABLE PER PRODUCT

| Product | Reuses |
|---|---|
| AI Wholesaler Lead Engine | `MBM/LeadEngine/code_violation/*`, `property_intel/*`, `npi_verified_callsheet.py`, `lead_pack_builder.py`, `seller_skip_tracer.py` |
| AI Cold Calling Assistant | `mbm-dialer/*`, `server/dialer/*`, `freshnessOrder.js`, `close_queue_dialer.py`, `phound_wave_campaign.py` |
| Construction BOQ Estimator | `Construction/construction_estimator_engine.py`, `contech-*` skills, Arabic UI needs build |
| Lead Qualification Agent | `dialer_verification_gate.py`, `lead_provenance.py`, `quarantine_synthetic_production.py` |
| Podcast-to-Shorts | `clipping-factory/*` (backend, workers, agents), `content-engine/` |
| Social Media Manager | `clipping-factory/MBM-Social/mbm_social/*` (autonomous_runtime, learning_engine, night_operations) |
| Industrial Waste Marketplace | match-scoring logic pattern (mirror lead scoring + 40/20/20/10/10) |
| AI Reporting Agent | `delivery_report.py`, GTM adapters, Telegram bus, `health-report.yml` |
| AI Appointment Setter | `voice-agent-saas/backend`, `MBM/VoiceAgencyStudio`, Twilio/Retell adapters |
| AI WhatsApp Assistant | Phound SMS rail, WhatsApp direct blaster pattern, Neteller links |
| White-label Sales Platform | `src/` dashboard, `server/index.js`, dialer API, agent registry |

---

## 8. RECOMMENDED ARCHITECTURE (product factory)

```
┌─ Client App (web / WhatsApp / phone / dashboard) ──────────────┐
├─ API Gateway (Fastify/Express per vertical, shared auth+billing)│
├─ Agent Layer (registry → worker → mission → orchestrator)       │
├─ Automation Layer (cron + queue + workflows)                    │
├─ Data Layer (Supabase + canonical JSON DBs + artifact store)    │
└─ Integration Layer (Neteller, Phound, Twilio, Gmail, Telegram,
   Google/YouTube API, DCAD/ArcGIS/NPI adapters, Supabase)
```

- Every vertical app = config (niches, sources, scripts, prompts) on top of shared platform. Never fork.
- Product config lives as YAML/JSON (mirror `brand_config.py` + `source_registry.json` pattern).
- One `leads_database`-style canonical store per tenant, namespaced, single-writer enforced.

---

## 9. FREE / LOW-COST MODEL + STACK

**Models:** local Ollama (deep-reasoning GLM tier), Qwen, DeepSeek, Gemini free tier, Groq fast inference; OpenAI only when a paid feature justifies it.
**Stack:** GitHub + GitHub Actions · Supabase (DB/auth/edge) · Vercel/Cloudflare (web) · n8n or GitHub Actions (workflows) · Tailscale (private infra) · Twilio/Phound (voice) · Gmail SMTP (email) · Telegram (notifications) · Neteller/Whop (billing).
**Rule:** never lock a customer product into an expensive dependency. Default to the cheapest rail that works; bill the client for paid API usage as pass-through where unavoidable.

---

## 10. PRICING STRATEGY

- **Entry hook:** AI service / productized service ($500–$2,500 setup + monthly retainer).
- **Managed solution:** setup fee $1k–$5k + $500–$2k/mo managed.
- **SaaS:** $99–$1,499/mo by vertical tier.
- **White-label:** license fee + % of platform revenue.
- **Upsells:** additional niches, more seats/agents, priority support, extra pipeline volume, training.
- **Never free forever:** always a paid tier; free = limited trial to prove value.

---

## 11. CUSTOMER ACQUISITION STRATEGY

1. **Founder-led service sales** to warm verticals (real estate, construction) — this company already does agency outreach (clientHunter, pain-point pipeline).
2. **Vertical landing pages** per product with a live demo (not marketing fluff) — reuse `digital-product-store`/`voice-agency-site` Next.js patterns.
3. **Marketplace/distribution channels:** Whop storefront + Gumroad listing for productized offers (already operational).
4. **Content-led inbound:** MBM-Social already publishes; use it to demo Content Factory.
5. **Partner/reseller:** real estate agents, construction consultants, WhatsApp agencies as channel partners.
6. **Proof-first:** deliver one free mini-diagnostic (e.g., 15-min BOQ sample, lead quality audit) → convert to paid.

---

## 12. MVP BUILD ORDER

1. **Week 1–2:** Productize existing dialer + lead engine as services (AI Cold Calling + Wholesaler Lead Engine). Reuse 100% existing code. Sell as service.
2. **Week 2–3:** Lead Qualification Agent as API + CSV service. Wrap verification gate.
3. **Week 3–6:** Construction BOQ Estimator MVP (Arabic UI) — highest price point.
4. **Week 4–6:** AI Appointment Setter using existing voice stack.
5. **Ongoing:** turn each delivered service into a managed offer, then a thin SaaS shell (shared platform).

---

## 13. 30-DAY EXECUTION ROADMAP

| Day | Action |
|---|---|
| 1–2 | Freeze this portfolio; assign owners; create product folders |
| 3–5 | Wrap dialer + lead engine into two productized service offers with pricing + landing pages |
| 6–10 | Pitch Wholesaler Lead Engine + Cold Calling to warm real estate/agency contacts (existing outreach rails) |
| 6–10 | Ship Lead Qualification API + sample report as the free diagnostic hook |
| 11–14 | First paid client(s); run service with existing pipelines (no new code) |
| 15–21 | Build Construction BOQ Estimator MVP (Arabic) using existing engine; 2 pilot contractors |
| 22–26 | Build AI Appointment Setter MVP on existing voice stack |
| 27–30 | Collect revenue + feedback; re-score portfolio; promote wins to TIER A managed/SaaS offers; update this doc |

---

## 14. CATALOG (categories)

**REAL ESTATE:** Wholesaler Lead Engine · Investor Dialer · Cash Offer App · Skip Trace API · Auction Intelligence
**CONSTRUCTION:** BOQ Estimator (AR) · Supplier Price Intel · Procurement Agent · Tender Assistant
**SALES:** Cold Calling Assistant · Lead Qualification · Proposal Generator · Sales Dialer
**MARKETING:** Content Factory · Repurposing SaaS · Social Manager · Content Intelligence
**SOCIAL MEDIA:** Podcast-to-Shorts · Multilingual Engine · Creator Pipeline
**RECRUITMENT:** Candidate Sourcing Agent · Screening Agent
**CUSTOMER SUPPORT:** Support Agent · Receptionist · FAQ Knowledge Agent
**OPERATIONS:** Appointment Setter · CRM Assistant · Reporting Agent · Ops Dashboard
**MANUFACTURING:** Document-to-DB · QC/Process Agents
**RECYCLING:** Waste Marketplace · Waste Match Agent · Supplier Match
**PROFESSIONAL SERVICES:** Quote Generator · Document Processor · Internal Knowledge Assistant
**LOCAL BUSINESSES:** WhatsApp Assistant · AI Receptionist · Review/Pain-Point Agent
**E-COMMERCE:** Product Content Cards · Chatbot · Order Agents
**DOCUMENT AUTOMATION:** PDF/BOQ extraction · Proposal/Quote · Document-to-Database
**AI AGENTS:** Vertical Agent Builder · Agent Factory · Multi-Agent Automation

---

## 15. EVALUATION CHECKLIST (every new piece of work)

On every new project/repo/agent/script/experiment, answer:
- Can it become a CUSTOMER PRODUCT? → which catalog category?
- Can it become a REUSABLE COMPONENT? → which platform module?
- Is it an INTERNAL TOOL? → which team workflow?
- Or is it a DEAD-END EXPERIMENT? → document the lesson in `MBM/LessonsLearned/` and park it.

Then update this portfolio if it lands in any of the top 20, changes scores, or adds a reusable module.