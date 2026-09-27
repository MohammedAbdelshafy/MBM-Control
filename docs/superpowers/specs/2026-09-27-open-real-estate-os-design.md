# Open Real-Estate Operating System Design

## Goal
Replace the dependency on an all-in-one XLeads-style platform with an open, self-hostable real-estate wholesaling operating layer built on the existing MBM-Control/LeadEngine system, while preserving the canonical lead database, single-writer invariant, provenance, DNC/suppression gates, and human approval for consequential seller actions.

## Current system constraints

- Canonical lead store remains `mbm-dialer/app/public/leads_database.json`.
- All mutations to the canonical lead store go through `MBM.GLM.single_writer_lock.DialerSingleWriter`.
- Scheduled ingestion already follows source -> raw ingest -> phone/identity validation -> provenance -> synthetic check -> dedupe -> suppression/DNC -> classification -> script assignment -> canonical write -> audit -> queue prioritization -> live verification.
- Property intelligence already provides county-source routing, APN/address ownership verification, conflict handling, provenance, opportunity scoring, and callability scoring.
- Opportunity Queue remains an airlock. Intelligence may propose candidates but must not bypass human approval or write directly into the dialer.
- Historical records must never be deleted merely to rotate the active queue. No-shrinkage remains mandatory.
- Offers, contracts, outbound campaigns, and other consequential seller actions remain human-approved.

## Desired XLeads-equivalent capabilities

The open stack should reproduce the useful functional categories rather than clone proprietary implementation details:

1. List/source ingestion
2. Property/APN/owner intelligence
3. Lead normalization and global dedupe
4. Motivation/distress signals
5. Seller qualification and MCTP discovery
6. Lead scoring and prioritized call queue
7. CRM lifecycle and activity timeline
8. Calling/SMS adapter layer
9. Conversation notes, disposition, and next-action automation
10. ARV/repair/MAO/LAO underwriting worksheet
11. Offer preparation with human approval gate
12. Contract/title milestone tracking
13. Cash-buyer database and buyer matching
14. Disposition pipeline
15. Reporting, audit, provenance, and source freshness
16. Lead-pack export and productized lead delivery

## Architecture

```text
SCHEDULED SOURCES
  -> SOURCE ADAPTERS
  -> NORMALIZE + ENTITY RESOLUTION
  -> PROPERTY INTELLIGENCE
  -> OWNER / APN / PHONE VERIFICATION
  -> GLOBAL DEDUPE + DNC / SUPPRESSION
  -> OPPORTUNITY SCORING
  -> OPPORTUNITY QUEUE (AIRLOCK)
  -> HUMAN APPROVAL
  -> CANONICAL DIALER WRITER
  -> CALL / SMS / MANUAL OUTREACH ADAPTERS
  -> DISPOSITION + CONVERSATION MEMORY
  -> MCTP QUALIFICATION
  -> UNDERWRITING (ARV / REPAIRS / MAO / LAO)
  -> HUMAN OFFER APPROVAL
  -> CONTRACT / TITLE
  -> BUYER MATCHING
  -> DISPOSITION
  -> CLOSED / WON-LOST ANALYTICS
```

### Data authority

- County assessor/official property sources are authoritative for APN and ownership where available.
- Verified contact sources provide phone/contact evidence but never overwrite authoritative property ownership.
- Enrichment sources are additive and provenance-tagged.
- The canonical lead DB is operational memory, not the source of truth for property ownership.
- Analytics and dashboards are read models and must not become competing writers.

### Lead lifecycle

`DISCOVERED -> VERIFIED -> PRIORITIZED -> CONTACTED -> QUALIFYING -> QUALIFIED -> OFFER_PENDING -> OFFERED -> FOLLOW_UP -> CONTRACT -> TITLE -> DISPOSITION -> CLOSED`.

Every state transition records actor, timestamp, evidence, prior state, and next action. The system must preserve negative outcomes, opt-outs, wrong-person results, and suppression state.

## Open-source adoption candidates

Adopt components by capability, not by replacing the existing LeadEngine wholesale:

- `InsulaCRM/InsulaCRM`: wholesaling-oriented CRM concepts, assignment/disposition pipeline, ARV/MAO worksheet, distress markers, repair costs. MIT license according to the repository README.
- `6t9xstar/Open-Cold-Dialer`: browser SIP dialer, lead management, campaigns, scripts, call history, REST API, Docker deployment. MIT license according to the repository README.
- `astradial/astradial`: self-hosted Asterisk-based telephony, CRM pipeline, call queues, AI voice bots, workflow automation, API/webhooks. AGPL-3.0. Treat as an optional isolated telephony reference/provider layer, not as a drop-in dependency without license review.
- Existing `MBM-Control/MBM/LeadEngine/property_intel`: authoritative property intelligence and provenance layer; keep as the canonical property-data implementation.
- Existing `MBM-Control/MBM/LeadEngine/daily_lead_ingest.py`: keep as canonical scheduled ingestion orchestrator.
- Existing `MBM-Control/MBM/GLM/single_writer_lock.py`: keep as the sole canonical lead DB writer.
- Existing `MBM-Control/MBM/LeadEngine/lead_pack_builder.py`: reuse for lead-pack production.
- Existing dialer/Phound integration: retain adapter boundary and fail-closed behavior; provider-specific credentials remain outside source control.

The implementation should extract patterns and isolated modules where useful. It must not blindly fork or merge an entire third-party CRM into MBM-Control.

## Core modules to add or extend

- `MBM/LeadEngine/open_re_os/`: orchestration package and interfaces.
- `source_registry.py`: source adapters, freshness, provenance contracts.
- `entity_resolution.py`: property/person/entity identity and global dedupe rules.
- `motivation_engine.py`: distress/property signal normalization and reason traces.
- `seller_qualification.py`: MCTP conversation state and qualification fields.
- `underwriting.py`: ARV/repairs/MAO/LAO calculations as advisory outputs only.
- `next_action_engine.py`: deterministic next-action generation from disposition/state.
- `buyer_matching.py`: buyer criteria normalization and property-to-buyer matching.
- `deal_lifecycle.py`: contract/title/disposition milestones and audit events.
- `read_model.py`: dashboard/reporting projections with no canonical writes.
- `adapters/`: dialer, SMS, CRM/export, and source integrations behind explicit interfaces.

## Scoring model

Maintain two separate scores:

- Opportunity score: motivation/distress, equity, vacancy, ownership confidence, market/buy-box fit, recency, contact confidence, liquidity.
- Contactability score: verified phone/contact source, owner match, recency, prior success, suppression/negative history.

No score can override hard gates. Missing property evidence, ambiguous ownership, DNC, wrong-person, synthetic/malformed phones, or unresolved conflicts remain blocked regardless of score.

## First-revenue operating slice

Phase 1 should focus on Dallas/Texas property-backed sellers already represented in the system and on converting existing scheduled-run inventory into a clean daily seller queue. The first useful surface is not a giant CRM. It is:

`Top seller queue -> property/evidence card -> MCTP questions -> call -> disposition -> next action -> underwriting worksheet -> human-approved offer`.

The seller queue must remain property-first. Existing audit data showed that 135 seller records had verified phones but only a subset had property-backed evidence, and the strict gate correctly kept unverified sellers out of `CALL_READY`. This behavior must remain intact.

## Success criteria

- One canonical lead store, zero competing writers.
- Zero dataset shrinkage during merges or queue rotation.
- Every active seller has traceable property, identity, contact, and provenance evidence.
- DNC/opt-out and negative dispositions cannot be bypassed by ranking.
- Scheduled-run leads are globally deduped rather than appended blindly.
- Every qualified seller has an explicit next action.
- Underwriting outputs are reproducible and auditable.
- Offer generation requires human approval.
- Buyer matching and disposition use the same canonical property/deal identity.
- The system can export lead packs without changing canonical state.
- Third-party open-source code is isolated behind interfaces and license-reviewed before commercial redistribution.
- The system remains useful if any one enrichment provider or telephony provider fails.

## Non-goals

- Do not create a second canonical lead database.
- Do not scrape private personal contact lists or infer ownership without authoritative evidence.
- Do not fabricate distress, equity, property, buyer, phone, or seller information.
- Do not auto-send offers or sign contracts.
- Do not make XLeads the runtime dependency.
- Do not replace the existing property-intelligence and single-writer safety architecture merely to adopt a third-party UI.
