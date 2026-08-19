# PRODUCT REGISTRY — AI Enhancement Company

**Rule:** every piece of work must answer *"Can this become something we can sell?"* → attach to product factory / extract component / keep internal / park.
**Statuses:** IDEA · PROTOTYPE · INTERNAL · MVP · CUSTOMER READY · LIVE · REVENUE · SCALE

---

## CUSTOMER READINESS GATE (applies to every product below)

A product is NOT customer ready unless ALL are true:
- [ ] Core workflow works
- [ ] Real input works
- [ ] Real output works
- [ ] Error handling works
- [ ] Authentication works
- [ ] Tenant isolation works
- [ ] Data persistence works
- [ ] Billing path exists
- [ ] Logs exist
- [ ] Tests pass
- [ ] Deployment works
- [ ] Demo works
- [ ] Landing page works
- [ ] Customer onboarding works
- [ ] Support path exists

---

## TIER A PRODUCTS

### P1 — AI Real Estate Wholesaler Lead Engine
| Field | Value |
|---|---|
| PRODUCT | AI Real Estate Wholesaler Lead Engine |
| CATEGORY | Real Estate / Sales |
| STATUS | MVP (API + pipelines exist; tenant scoping incomplete) |
| REPOSITORY | this repo — `MBM/LeadEngine/` + `MBM/LeadEngine/api/` |
| DEPLOYMENT | Fastify API (local, port 3002 via server); DB: Prisma/PostgreSQL |
| CORE COMPONENTS | `code_violation/`, `property_intel/`, `npi_verified_callsheet.py`, `lead_pack_builder.py`, `seller_skip_tracer.py`, `dcad_owner_lookup.py` |
| SHARED COMPONENTS | `lead_provenance.py`, `dialer_gateway.py`, `dialer_queue_engine.py`, auth (JWT), Client/credits |
| CUSTOMER | Wholesalers, RE investors, cold-call VA agencies |
| MVP STATUS | ✅ leads list/claim/export API; ❌ tenant-scoped list; ❌ customer onboarding; ❌ billing loop |
| TEST STATUS | 34 pytest + 29 TS test files in `MBM/LeadEngine/tests/` |
| MONETIZATION | Monthly credit packs by market/volume |
| PRICE | Starter $297/mo (100 verified leads) · Pro $597/mo (500) · Agency $1,197/mo (1,500 + white-label export) · DFY $1,997/mo (we dial for you) |
| NEXT ACTION | Enforce `clientId` scope on `GET /api/leads` + export; wire Neteller→credits; tenant onboarding page |
| OWNER | system/founder |
| BLOCKER | None technical — scope middleware + billing loop only |

### P2 — AI Cold Calling Assistant
| Field | Value |
|---|---|
| PRODUCT | AI Cold Calling Assistant |
| CATEGORY | Sales / Voice |
| STATUS | MVP (dialer + scripts live; caller workspace exists) |
| REPOSITORY | this repo — `mbm-dialer/app/` (primary) + `coldcall/dialer/` (sellable standalone) + `server/dialer/` |
| DEPLOYMENT | Vite dev :5173; coldcall cockpit :8878 (Python stdlib) |
| CORE COMPONENTS | `mbm-dialer/app/public/leads_database.json`, `server/dialer/{dialerDbGateway,freshnessOrder,phoundSmsProvider}.js`, `MBM/LeadEngine/dialer_script_engine.py`, `close_queue_dialer.py` |
| SHARED COMPONENTS | canonical DB + single-writer, queue engine, script engine, Phound/Twilio, `src/pages/MobileDialer.jsx` |
| CUSTOMER | SMB sales teams, RE agents, agencies |
| MVP STATUS | ✅ lead queue + freshness + scripts + tap-to-call + dispositions UI; ❌ tenant isolation; ❌ billing; ❌ analytics per tenant |
| TEST STATUS | `freshnessOrder.test.js`, `phoundSmsProvider.test.js`, `test_dialer_script_engine.py`, `test_dialer_freshness_ordering.py` |
| MONETIZATION | SaaS seat model + call minutes |
| PRICE | Starter $199/mo (1 seat) · Pro $499/mo (3 seats + CRM) · Agency $999/mo (10 seats + white-label) · DFY $1,499/mo (we run your campaigns) |
| NEXT ACTION | Tenant-scope the queue; script selection per segment already segment-aware (12 segments verified in `dialer_script_engine.py`); add call analytics |
| OWNER | system/founder |
| BLOCKER | None technical — multi-tenant queue + billing |

### P3 — Construction BOQ AI Estimator
| Field | Value |
|---|---|
| PRODUCT | Construction BOQ AI Estimator |
| CATEGORY | Construction / Document AI |
| STATUS | PROTOTYPE (engine computes; no PDF ingest, no Arabic-first UI, no supplier history) |
| REPOSITORY | this repo — `Construction/construction_estimator_engine.py` |
| DEPLOYMENT | none yet (CLI script) |
| CORE COMPONENTS | `Construction/construction_estimator_engine.py` (margin/tax/itemized math, EGP) |
| SHARED COMPONENTS | shared document ingest (MISSING), Neteller billing |
| CUSTOMER | Contractors, GCs, quantity surveyors, procurement (Arabic-speaking) |
| MVP STATUS | ✅ itemized cost math + margins + tax + report JSON; ❌ PDF/drawing extraction; ❌ supplier price DB; ❌ historical prices; ❌ Arabic UI; ❌ flag-for-review |
| TEST STATUS | none |
| MONETIZATION | Per-quote fee + monthly tier; setup fee |
| PRICE | Starter $99/mo (10 quotes) · Pro $299/mo (50) · Business $799/mo (unlimited + supplier DB) · DFY $999 setup + $499/mo (we estimate your BOQs) |
| NEXT ACTION | Build PDF/BOQ extractor (shared), supplier price store, Arabic UI (RTL), FLAG_FOR_REVIEW for missing prices |
| OWNER | system/founder |
| BLOCKER | PDF extraction + supplier DB + Arabic UI all unbuilt |

### P4 — AI Lead Qualification Agent
| Field | Value |
|---|---|
| PRODUCT | AI Lead Qualification Agent |
| CATEGORY | Sales / Data |
| STATUS | MVP→CUSTOMER READY (DFY runner + demo + landing + checkout live; API works) |
| REPOSITORY | this repo — `MBM/LeadEngine/{dialer_verification_gate.py,qualification_runner.py}`, `lead_provenance.py`, `quarantine_synthetic_production.py`, `productized-service/p4-lead-cleaner/` |
| DEPLOYMENT | CLI (`npm run leads:qualify`) + authenticated Fastify `POST /api/qualify` + DFY service `productized-service/p4-lead-cleaner/clean_leads.py` |
| CORE COMPONENTS | `dialer_verification_gate.py` (phone/name/placeholder/verified checks, NPI proof), `qualification_runner.py` (read-only CSV/JSON reports), `lead_provenance.py` (synthetic fingerprints), `clean_leads.py` (DFY: statuses VERIFIED/CALLABLE/NOT CALLABLE/DUPLICATE/SUPPRESSED/NEEDS REVIEW + reason codes + suppression index + dedupe) |
| SHARED COMPONENTS | phone normalization, provenance, suppression — canonical for EVERY product |
| CUSTOMER | Agencies, B2B teams, real estate investors who buy lead lists |
| MVP STATUS | ✅ CSV/JSON qualification + reason codes; ✅ authenticated API; ✅ non-mutating structured reports; ✅ DFY runner + demo (before/after, synthetic-labeled sample); ✅ landing page (`landing.html`); ✅ Neteller checkout (`P4_LEAD_CLEAN_DFY_10K` $499, `P4_LEAD_CLEAN_MONTHLY_1K` $49/mo, `P4_FREE_SAMPLE_1K` free); ✅ campaign tracker + 9 real prospects; ✅ revenue dashboard; ❌ credit-based billing loop behind the API |
| TEST STATUS | `test_qualification_runner.py`, `test_lead_provenance.py`, `test_phone_recovery_and_bad_number_purge.py` |
| MONETIZATION | Per-1,000-lead fee + monthly API |
| PRICE | Starter $49/mo (1k leads) · Pro $149/mo (10k) · Agency $499/mo (100k + API) · DFY $499/setup (we clean your lists, ≤10k, 48h) |
| NEXT ACTION | FIRST PAYING CUSTOMER: send free 1,000-lead sample offers to the 9-prospect batch (`campaign_tracker.md`), close one $499 DFY, then add credit-based billing to the API |
| OWNER | system/founder |
| BLOCKER | None — execution only (send outreach to batch 1) |

### P5 — AI Appointment Setter
| Field | Value |
|---|---|
| PRODUCT | AI Appointment Setter |
| CATEGORY | Operations / Voice |
| STATUS | PROTOTYPE (Vapi backend + booking service exists; no frontend tenant flow) |
| REPOSITORY | this repo — `voice-agent-saas/backend/` |
| DEPLOYMENT | FastAPI backend (local) |
| CORE COMPONENTS | `voice-agent-saas/backend/app/services/{vapi_service,calendar_service}.py`, `app/routers/voice_webhook.py`, `system_prompt.txt` (receptionist persona) |
| SHARED COMPONENTS | Vapi/Twilio/Phound adapters, calendar service, notifications |
| CUSTOMER | Plumbers, clinics, law firms, salons, any appointment-driven local business |
| MVP STATUS | ✅ inbound call → answer → book via `book_appointment` tool; ✅ webhook router; ❌ website/WhatsApp/form entry; ❌ qualification/intent logic; ❌ follow-up/reschedule/cancel flows; ❌ tenant + billing |
| TEST STATUS | none |
| MONETIZATION | Per-location monthly + per-minute |
| PRICE | Starter $149/mo (1 location, 500 min) · Pro $349/mo (3 locations, 2k min) · Business $749/mo (unlimited) · DFY $1,299 setup + $649/mo (we handle calls) |
| NEXT ACTION | Add web/WhatsApp/form entry channels, qualification + escalation, reschedule/cancel/follow-up, tenant config per business, billing |
| OWNER | system/founder |
| BLOCKER | Multi-channel intake + lifecycle flows + tenant/billing |

---

## OTHER CUSTOMER-READY ADJACENT ASSETS
| Asset | Classification | Notes |
|---|---|---|
| Cold Call Cockpit (`coldcall/dialer/`) | CUSTOMER PRODUCT (standalone) | Python+SQLite+Twilio, documented as sellable in `mbm-dialer/DIALER_ARCHITECTURE.md` |
| Digital Product Store (`digital-product-store/`) | CUSTOMER PRODUCT (storefront) | Next.js, deployable on Vercel, marketplace listings |
| Voice Agency Studio (`MBM/LeadEngine/voice_agency_studio.py`) | REUSABLE COMPONENT | Platform revenue adapters (ElevenLabs/Retell/Vapi/Synthflow) |
| Clipping Factory / MBM-Social | CUSTOMER PRODUCT (Content Factory tier) | Separate portfolio line — see `PRODUCT_PORTFOLIO.md` |
| Lead Pack Builder + Whop specs | CUSTOMER PRODUCT (lead packs) | Sells as monthly pack |

---

## INTERNAL TOOLS (keep internal, reuse components)
- GTM commander/execution queue/notification bus → internal ops + reporting component
- Jarvis autonomous commander / GLM swarm → internal orchestration
- Revenue/monetization/audit scripts → internal money tracking
- Email/WhatsApp/SMS blasters → internal outreach (reuse Phound rail)
- Reply detector, hunter, email sender → internal comms

## DEAD-END / PARK (lessons only, do not build on)
- `shortfall_lead_harvester.py` — fabricates leads (violates provenance gate); quarantine already applied to its 122 injected rows; file must be deprecated.
- Stale `test_*.py` probes (test_fastpeoplesearch, test_scrapeninja, test_usphonebook, test_rapidapi_skiptrace, test_reverse_phone, test_web_call) — one-off connectivity probes.
- Parked: `upwork_auto_bidding_daemon.py`, `us_50_phone_extractor.py` (no strategic value as products).

---

## PLATFORM MAP (summary)
See `PRODUCT_FACTORY_PLATFORM_MAP.md` for the full canonical-component map. Canonical anchors: single-writer lead DB → `leads_database.json`; queue → `dialer_queue_engine.py` + `freshnessOrder.js`; scripts → `dialer_script_engine.py`; auth → `api/auth.ts`; billing → Neteller rails; voice → Phound/Twilio + `voice-agent-saas`.

## BUILD ORDER (revenue-first)
1. **P4 API** (1–2 days) — fastest: gate already works, wrap it, sell list-cleaning immediately.
2. **P1 tenant scoping + billing** (2–3 days) — list/export scoped by clientId, Neteller→credits.
3. **P2 multi-tenant queue + analytics** (3–4 days) — tenant-scope `leads_database` view; add call analytics.
4. **P5 multi-channel intake + lifecycle** (1–2 weeks) — web/WhatsApp/form, reschedule/cancel/follow-up, tenant config.
5. **P3 PDF extractor + supplier DB + Arabic UI** (2–3 weeks) — highest price point, slowest build.

## MONETIZATION SUMMARY
Every product: STARTER / PRO / AGENCY-BUSINESS tiers + DONE-FOR-YOU. Path: SERVICE → MANAGED SERVICE → PRODUCT → SAAS → WHITE LABEL. No free-forever tiers; free = limited trial only.

## NEXT PORTFOLIO UPDATE
Whenever new work lands: classify (customer product / reusable component / internal tool / dead-end), update registry status, re-run readiness gate. Do not let work disappear inside MBM, Social, Construction, Voice, or individual experiments.
