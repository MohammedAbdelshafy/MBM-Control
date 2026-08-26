# Airtable ↔ MBM Dialer Integration Contract

## Purpose

Airtable is an operational intelligence/CRM mirror. The canonical Dialer database remains the source of truth for dialing eligibility and lead ordering.

## Ownership

- **Canonical Dialer truth:** `mbm-dialer/app/public/leads_database.json` and the approved single-writer gateways.
- **Airtable:** enrichment, AI opportunity, next-best-action, scripts/offer context, CRM-style operational fields.
- **Production telephony:** Phound only.
- **Deployment source:** GitHub `master` → existing Vercel production.

## Safety rules

1. Airtable NEVER makes a lead callable by itself.
2. `Verified Phone`, `Phone`, verification timestamps, DNC, suppression, and owner/contact evidence originate from the canonical verification pipeline.
3. Airtable writes must be idempotent and keyed by a stable lead identity. Phone-only matching is insufficient for seller leads.
4. Never overwrite stronger canonical evidence with weaker Airtable data.
5. Missing evidence stays missing. No inferred classification, phone, owner, or offer is fabricated.
6. A lead remains `CALL_READY` only when the canonical gate passes.
7. Sync failures must fail soft and never block the Dialer.

## Initial direction

Phase 1 is **read/mirror only** from canonical Dialer → Airtable using the existing `MBM/LeadEngine/airtable_sync.py` integration.

Phase 2 can add controlled Airtable → Dialer updates only for explicitly allowlisted operational fields, with validation and audit.

## Allowed Airtable enrichment fields

- AI Opportunity
- AI Fit Score
- Next Best Action
- AI Service Script
- Lead Stage
- Sales notes / CRM notes

## Protected canonical fields

These must never be mutated from Airtable without an explicit governed write path:

- verified phone
- phone verification status
- owner/contact identity verification
- DNC / suppression
- canonical lead ID
- segment
- script assignment
- source/provenance
- queue position
- callable / CALL_READY

## Acceptance criteria

- Existing Dialer tests remain green.
- Airtable sync is additive/idempotent.
- No duplicate Airtable lead records after repeated syncs.
- No Airtable field can promote an unsafe lead to callable.
- Production telephony remains Phound.
- No secrets committed to Git.
