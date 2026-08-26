# Connector Batch 2: Max-Power Revenue + Execution Adapters

## Purpose

Turn the connected-app ecosystem into a reusable operating layer for MBM Dialer, MBM Social, AI Consultancy, ConTec, and future verticals without creating competing sources of truth or allowing connector failures to corrupt canonical state.

## Canonical authority model

- **GitHub:** source/release truth for production code, schemas, adapters, tests and governance.
- **Dialer LeadEngine / canonical lead store:** authoritative for lead identity state, phone verification, DNC, suppression, queue eligibility and CALL_READY.
- **Supabase:** structured event/state ledger where appropriate; must not silently replace the protected Dialer canonical store.
- **Airtable:** operator-facing operational CRM/intelligence mirror, playbooks, offer catalog, integration registry and revenue-event mirror. It is never authoritative for CALL_READY, DNC, suppression or canonical phone verification.
- **HubSpot:** downstream commercial CRM and activity/opportunity mirror when write permissions are authorized.
- **Phound:** production telephony execution. Manual handoff is valid when API access is unavailable. `DIAL` means opening/launching Phound, never `CONNECTED`.
- **Clay / AI Vibe Prospecting:** prospect discovery and enrichment evidence only.
- **LinkedIn:** professional identity/company/role evidence where supported.
- **Ace Knowledge Graph:** relationship/context layer for companies, people, evidence, signals, campaigns and workflows; not transactional truth.
- **Business Helper:** source-backed decision support; recommendations remain distinct from facts.
- **Figma:** UX/design contract only; GitHub remains production implementation authority.
- **Notion:** SOPs, playbooks, scripts and reusable operating knowledge.
- **Granola:** conversation/meeting context and customer feedback evidence.
- **Asana:** human execution and follow-up task layer.
- **Slack:** operational notification and exception layer.

## Production telephony rule

Twilio is retired and must not be reintroduced.

Phound is the production calling path. Because the current operating model may require a manual handoff, the Dialer must support:

`verified phone -> DIAL -> open/launch Phound -> human call -> return -> disposition`

No external connector may fabricate `CONNECTED`, `INTERESTED`, `MEETING_BOOKED`, `PROPOSAL_SENT`, `PAYMENT`, or `REVENUE`.

## Connector lifecycle

Every connector follows:

**DISCOVER → AUTHENTICATE → CONFIGURE → USE → TEST → AUDIT → DEPLOY → LIVE VERIFY**

If credentials or permissions are unavailable, the adapter may be implemented and contract-tested, but the connector remains explicitly `BLOCKED` or `UNKNOWN` until real usage is proven.

## Provider-neutral adapter contract

Every integration should expose a minimal provider-neutral interface so business logic never depends directly on one vendor's field names.

Recommended capability families:

- `LeadDiscoveryProvider`
- `EnrichmentProvider`
- `IdentityEvidenceProvider`
- `CRMProvider`
- `EventStoreProvider`
- `ConversationProvider`
- `TaskProvider`
- `NotificationProvider`
- `KnowledgeProvider`
- `DecisionSupportProvider`

Normalized objects should include where available:

- stable internal ID
- provider name
- provider external ID
- source/reference URL
- retrieved timestamp
- evidence type
- confidence
- provenance
- sync status
- error status

## Lead intelligence pipeline

Target flow:

**DISCOVERY → ENRICHMENT → IDENTITY EVIDENCE → PHONE EVIDENCE → QUALIFICATION → CALL_READY → DIALER**

Primary sources:

- Vibe Prospecting: discovery
- Clay: enrichment, intent, company/contact signals
- LinkedIn: person/company/role evidence
- Knowledge Graph: relationship and context
- LeadEngine: deterministic qualification and safety gating

### Contact-quality law

A lead must not become CALL_READY merely because several providers agree.

The deterministic gate must consider:

- company ↔ phone match
- person ↔ company match
- role relevance
- phone source quality
- freshness
- provider agreement
- identity evidence
- DNC/suppression state
- campaign eligibility

Recommended states:

`VERIFIED / SUPPORTED / UNKNOWN / CONFLICT / REJECTED`

Only policy-approved verified records may enter CALL_READY.

Expose the verification evidence to the operator before Dial.

## Dialer operator flow

The production cockpit should present:

1. **SUMMARY**
2. **EVIDENCE**
3. **VERIFIED CONTACT**
4. **SCRIPT**
5. **OFFER**
6. **DIAL / OPEN PHOUND**
7. **AFTER CALL**
8. **FOLLOW-UP**
9. **NEXT ACTION**

The bottom of the workflow must contain the after-call and follow-up actions so the rep can first understand the lead, evidence, script and offer.

### Dial semantics

`DIAL` = an attempted/manual handoff event.

`CALL_OPENED` or equivalent = Phound launch/open event.

`CONNECTED` = only a real telephony/provider event, or an operator disposition explicitly recording that the call connected.

Never infer a conversation from a button click.

## Specialty-aware AI sales engine

The Dialer must not default to a generic AI receptionist pitch.

Build reusable Clinic AI Core capabilities from the existing Dental AI implementation and specialize them by vertical.

Core capability families include:

- treatment/service follow-up
- recall/reactivation
- lead conversion/opportunity detection
- document/insurance workflow where applicable
- referral/intake workflow
- no-show recovery
- patient communication automation
- operational analytics
- revenue-opportunity detection

Initial specialty playbooks:

- dental
- dermatology
- orthopedics
- ophthalmology
- physiotherapy
- cardiology
- pediatrics
- ENT
- medical aesthetics
- veterinary

For each qualified clinic/account generate:

- primary AI opportunity
- secondary opportunity
- evidence
- confidence
- recommended module
- discovery questions
- script angle
- offer angle
- next best action

Verified fact, supported inference and unknown must remain distinguishable.

## Event model

Use real, event-derived telemetry only.

Recommended events:

- `PROSPECT_DISCOVERED`
- `PROSPECT_ENRICHED`
- `IDENTITY_VERIFIED`
- `PHONE_VERIFIED`
- `CALL_READY`
- `CALL_OPENED`
- `DISPOSITION_RECORDED`
- `FOLLOWUP_CREATED`
- `OFFER_PRESENTED`
- `CHECKOUT_STARTED`
- `PAYMENT_CONFIRMED`

Every event should support:

- event ID
- stable lead ID
- source event ID
- provider
- occurred-at timestamp
- evidence/reference
- idempotency key
- processing state

## Airtable strategy

Use the existing **MBM Lead Warehouse** base.

Known operational tables:

- `Leads`
- `AI Automation Services`
- `AI Niche Playbook`
- `Revenue Events`
- `Integration Registry`

Airtable is a human-friendly mirror, not a safety authority.

Lead synchronization should map, where available:

- stable Lead ID
- company/person identity
- evidence status
- phone status/source
- contact identity verification
- AI opportunity
- script ID
- sales strategy
- offer recommendation
- next best action
- lead stage/status
- sync status
- last enrichment timestamp

Prefer stable Lead ID upserts. Never deduplicate on phone alone.

## CRM synchronization

### HubSpot

Use for commercial lifecycle, contact/company records, activities and opportunity/customer state after write authorization is available.

### Supabase

Use for high-volume structured events/state where appropriate, with RLS and auditability.

### Circular sync prevention

All outward synchronization must be idempotent and source-aware.

Recommended metadata:

`origin_source`
`origin_event_id`
`provider`
`external_id`
`processed_at`
`attempt_count`
`sync_version`

Prevent:

`Supabase → HubSpot → Supabase → HubSpot`

and equivalent loops.

## Business Helper + Knowledge Graph

Business Helper consumes verified evidence and returns structured recommendations:

- account summary
- likely pain points
- rationale
- confidence
- recommended angle
- next action

Knowledge Graph models:

`company ↔ person ↔ evidence ↔ signal ↔ campaign ↔ interaction ↔ offer`

Generated recommendations must remain explicitly separate from verified facts.

## Notion / Granola / Asana / Slack

### Notion

SOPs, sales playbooks, scripts, connector documentation and reusable operating knowledge.

### Granola

Meeting/conversation context and customer feedback. Do not silently overwrite canonical outcomes.

### Asana

Human follow-up tasks driven by actual business state. Use deterministic task IDs to prevent duplicate work.

### Slack

Operational alerts for:

- verification conflicts
- hot leads
- provider failures
- stuck syncs
- deployment failures
- appointments
- payments

## Figma

Use Figma to define the operator cockpit and interaction hierarchy, especially:

`Summary → Evidence → Contact → Script → Offer → Dial → After Call → Follow-up`

Do not create a second production source of truth outside GitHub.

## Observability

Track at minimum:

- discovered
- enriched
- verified
- rejected
- callable
- wrong-number rate
- wrong-party rate
- calls opened
- real dispositions
- conversations
- follow-ups
- offers
- appointments
- checkouts
- payments
- revenue

Zero means no verified event occurred. Never substitute simulations or fixture values.

## Failure and recovery model

Every adapter should support:

- timeout handling
- retry with bounded backoff
- idempotency
- partial batch failure
- dead-letter state
- replay
- structured errors
- health status
- last successful operation

Connector failure must not block unrelated systems or mutate canonical lead eligibility.

## Security

- Secrets remain environment/secret-manager only.
- Never commit tokens.
- Never expose secrets client-side.
- Never log credentials.
- Use least-privilege credentials.
- Treat imported external data as untrusted input.

## Testing requirements

At minimum test:

- duplicate records
- conflicting provider evidence
- stale enrichment
- wrong phone
- wrong party
- DNC
- suppression
- unverified contact
- valid verified contact
- Phound launch event
- manual disposition
- duplicate disposition
- follow-up creation
- duplicate CRM sync
- timeout/retry
- dead-letter
- restart/recovery
- circular sync protection
- canonical no-shrink
- script/segment consistency
- provenance retention
- specialty offer selection

Do not weaken tests to make CI pass.

## Deployment rules

Before merge:

- inspect complete diff
- scan for secrets
- run tests
- run lint
- run typecheck
- run build
- validate migrations
- validate dependency changes
- verify no unrelated behavior changed

Deploy only the known production application.
Do not create duplicate Vercel projects.

Production proof must include:

- deployed commit SHA
- HTTP status
- live lead count
- callable count
- newest lead
- script/segment coverage
- phone-safety checks
- Dial → Phound behavior
- After Call placement
- Follow-up placement

## Reusable skill extraction

Every successful integration should leave behind reusable artifacts where appropriate:

- adapter interface
- provider configuration contract
- normalized schema
- tests
- runbook
- failure modes
- example event payloads
- capability/permission matrix

These patterns should be reusable across MBM Social, AI Consultancy, ConTec and future projects.

## Definition of done

A connector is not complete because code exists.

It is complete only when the available capability is:

**DISCOVERED → AUTHENTICATED → CONFIGURED → USED → TESTED → AUDITED → DEPLOYED → LIVE VERIFIED**

and the end-to-end commercial path is traceable:

**DISCOVERY → ENRICHMENT → IDENTITY → PHONE VERIFICATION → QUALIFICATION → SCRIPT → OFFER → DIAL/PHOUND → REAL DISPOSITION → FOLLOW-UP → CRM → REVENUE**

Any unavailable credential, permission or provider capability must be reported as a specific blocker rather than disguised as successful integration.