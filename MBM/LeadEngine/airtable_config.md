# Airtable Warehouse Mapping

Base: `MBM Lead Warehouse`

## Leads table

Recommended additions:

- `Lead ID` — stable canonical identity; create as single-line text if absent.
- Existing intelligence fields remain operational mirrors.

Mapped from Dialer:

- Business Name
- Owner Name
- Phone
- Email
- Industry
- Lead Score
- Status
- Source
- Notes
- AI Opportunity
- Next Best Action
- AI Service Script
- Lead Stage
- AI Fit Score
- Verified Phone
- Phone Status
- Phone Source
- Verification Date
- Contact Verified
- DNC
- Suppressed
- Segment
- Script ID
- Sales Strategy

## Authority

The Dialer remains authoritative for eligibility and canonical lead identity. Airtable is an operational mirror and intelligence workspace.

Airtable `AI Opportunity`, `Next Best Action`, `AI Service Script`, `Lead Stage`, and `AI Fit Score` can support operators and future governed write-back. They cannot directly change `CALL_READY`, DNC, suppression, phone verification, owner/contact verification, canonical source, queue ordering, or script assignment.

## Next phase

After Phase 1 mirror validation, add explicit field-level write-back only for allowlisted CRM fields with audit events and server-side validation.
