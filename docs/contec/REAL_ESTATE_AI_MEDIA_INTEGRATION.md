# REAL ESTATE AI MEDIA — Integration Architecture & Delivery Report

Status: IMPLEMENTED (hermetic core + schemas; live-site install pending M1/S01) · D-021
Date: 2026-08-26 · Directive: "CONTEC AI CONSULTANCY — Real Estate AI Media + Lead Acquisition System"

## 1. Architecture mapping (per directive §15, done BEFORE code)

| Existing system | Location | Reused for |
|---|---|---|
| ERPNext v16.32.3 stack (9 containers, Up) | Docker project `contec` (compose: `repos/base44-app/deployment/compose/docker-compose.yml`) | persistence, auth, REST, background queues (queue-short/long), scheduler |
| `contec` custom app slot | repo subdir `apps/contec/` (04 §2/§3); NOT yet bench-installed | ALL vertical code lives here (D-004/D-019) |
| frappe_docker @ v3.2.2 | `deployment/contec/frappe_docker` | deployment tooling only |
| MBM telephony bridge (Twilio operator bridge) | `MBM/LeadEngine/close_queue_dialer.py` + `.env` creds | outbound calls for campaign rows — no second telephony stack built |
| Higgsfield CLI (host-installed) | external binary | preferred video provider via adapter |
| Governance rails | DECISION_LOG D-001..D-021, OX Alpha trust rules | AI-suggestions-only, provenance, no fabrication |

Integration points chosen:
- **CRM/pipeline**: dedicated DocTypes (Real Estate Agent / Property Sample /
  Fulfillment Job / RE Media Settings single) — Configure→Extend→Build ladder.
- **Lead engine**: pure-python dedup/scoring modules (`real_estate_media/`),
  hermetically testable without a Frappe runtime.
- **Automation layer**: restartable WorkQueue with retry/dead lanes;
  Frappe wiring via `frappe.enqueue` in `api.py`.
- **Dialer**: state machine owns the 13 mandated states in Contec and exports
  dialer-ready rows to the MBM bridge under campaign
  `CONTEC_REAL_ESTATE_AI_MEDIA`. Opt-out is terminal from every state.
- **Analytics**: `analytics.dashboard_counts()` — event-derived only,
  zero-event = zero. Dashboard UI deferred until site install.

## 2. Files added

```
apps/contec/
  pyproject.toml                       app packaging
  contec/__init__.py  hooks.py  api.py app entry, doc_events, whitelisted API
  contec/real_estate_media/
    lead_dedup.py        normalized email/phone primary + identity/domain secondary keys
    scoring.py           REAL_ESTATE_MEDIA_SCORE (8 weighted signals, evidence-traceable)
    listing_selection.py (covered by asset_pipeline sequencing + sample_store selection guards)
    asset_pipeline.py    LISTING_DISCOVERED→…→DELIVERY_READY; validation/dedup/QA; facts-only prompt
    state_machine.py     dialer states + CRM mirror + opt-out law + retry/cooldown policy
    script_engine.py     dynamic templates, 10 objection branches, NEEDS_REVIEW markers (no fabrication)
    offer_engine.py      config-driven catalog (NO hard-coded prices), recommendation rules, override
    sample_store.py      GENERATE_PROPERTY_SAMPLE record, duplicate prevention, generation limits
    fulfillment.py       won→fulfillment job, batch support, behavior-triggered upsells
    analytics.py         acquisition/sales/production/customer counters (event-derived)
    automation.py        qualify_and_route + observable/restartable WorkQueue
    providers/base.py    VideoProvider ABC + registry; NullProvider = honest unavailability
    providers/higgsfield_provider.py   preferred engine adapter (graceful when CLI absent)
  contec/doctype/{real_estate_agent,property_sample,re_media_settings,fulfillment_job}/  Frappe schemas
docs/contec/DECISION_LOG.md            D-021 entry (added BEFORE code per D-019)
.gitignore                             !/apps/ un-ignore
```

## 3. Schema changes (when bench-installed)

4 new DocTypes (see JSONs). No vendor-core changes (D-004). No financial
DocTypes touched — revenue figures remain event-derived records, never posted
by AI paths (D-019 rail).

## 4. Environment variables

| Var | Purpose | Absent behaviour |
|---|---|---|
| none required for core logic | tests run with zero env | — |
| higgsfield CLI on PATH (+ its auth) | video render provider | provider reports unavailable → samples SKIPPED_UNAVAILABLE, never simulated |

## 5. Tests executed

`pytest apps/contec/tests/ -q` → **59 passed** (dedup 6, scoring 3,
state machine 10 incl. opt-out/retry/cooldown, pipeline 7 incl. invalid assets,
providers/samples 6 incl. failure+QA gates, script/offer 11 incl. no-fabrication,
guards/fulfillment/upsell/automation 15, E2E full loop + zeros 2).
Full monorepo suite still green: LeadEngine pytest 489 passed.

## 6. Remaining blockers (honest)

1. **Live-site install not yet possible** — the running `contec.local` stack is
   preserved crash-evidence; the S01 plan builds a separate `contecm1` project.
   E2E ON A LIVE SITE stays open until then. Hermetic E2E passes today.
2. **Pricing values** intentionally empty — owner countersign required before
   production quoting (D-014 class).
3. **Listing asset ingestion** (scrape/import of public listing media) is a
   separate legal/technical work item; current pipeline consumes supplied
   assets and BLOCKS honestly when none are valid.
4. HRMS delivery path decision (pre-existing M1 gap #1) unrelated but blocks
   the same S01 build window.

## 7. Exact commands (local dev)

```bash
# run the vertical's test suite (no Frappe needed):
.venv\Scripts\python.exe -m pytest apps/contec/tests/ -q

# after S01 creates the contecm1 bench project:
bench --site <site> install-app contec
bench --site <site> migrate
bench --site <site> clear-cache
# set RE Media Settings → package catalog (JSON) + video_provider=higgsfield
```

## 8. Deployment steps

1. Complete PLATFORM_BAKEOFF S01 build (`contecm1`, port 8081) per M1 charter.
2. Add this repo as a Frappe app source (`bench get-app $REPO_URL apps/contec`).
3. `install-app` + `migrate` (commands above); verify doctypes exist.
4. Owner countersign pricing catalog → enable QUOTED stage usage.
5. Wire campaign exporter endpoint to MBM bridge queue; keep DO_NOT_CONTACT sync one-way authoritative FROM Contec.
6. Release gate (Terminal 3 QA) → GO/NO-GO per trust rules.
