# P0 Connector Execution Runbook

## Objective

Convert the connector architecture from documentation into measured production capability without destabilizing the MBM Dialer.

## Non-negotiable authority model

- GitHub: code and release truth.
- LeadEngine + Dialer canonical store: lead identity, phone verification, DNC, suppression, queue order, and CALL_READY authority.
- Airtable: operational CRM/intelligence mirror.
- Clay + AI Vibe Prospecting + LinkedIn: discovery/enrichment evidence only.
- Phound: production telephony execution and provider-derived events. Twilio is retired and must not be restored as a fallback.
- Supabase: structured event/state layer only where adopted.
- HubSpot: downstream CRM/activity mirror when permissions allow.
- Vercel/Netlify/AppDeploy: deployment/preview surfaces only.
- Figma: Dialer UX contract.
- Dropbox: evidence/assets/archive.
- AI/media/build connectors: accelerators, never canonical truth.

## Execution order

### P0-A: Production integrity

1. Confirm master and production deployment status.
2. Preserve single-writer and no-shrink invariants.
3. Confirm no simulated telephony or index-based conversion paths.
4. Confirm unverified, DNC, suppressed, synthetic, wrong-party, and malformed leads cannot become CALL_READY.

### P0-B: Contact quality

1. Enrich through Clay/Vibe/LinkedIn where available.
2. Persist provider, source timestamp, evidence reference, and confidence.
3. Re-run LeadEngine verification before queue admission.
4. Never use phone as the sole identity key.
5. Quarantine bad/wrong-party numbers and trigger re-verification.

### P0-C: Telephony

1. Use Phound only.
2. Validate provider configuration without exposing secrets.
3. Perform an authorized smoke test.
4. Verify real provider call ID/status/webhook events.
5. A UI click is not a connection and an initiated call is not a conversation.
6. Unknown provider outcome remains UNKNOWN until evidence arrives.

### P0-D: Rep workflow

Order the Dialer screen as:

Summary → Evidence → Verified Contact → Script → Offer → Dial → After-call → Follow-up → Next Action.

Hide Dial when the contact fails the verified-call gate.

### P0-E: CRM/event layer

Use idempotent, auditable events:

lead_verified
call_requested
call_created
call_ringing
call_connected
call_ended
disposition_recorded
followup_created
offer_presented
checkout_clicked
payment_received

Do not count commercial outcomes unless an event with evidence exists.

### P0-F: Revenue loop

Verified prospect → real contact → real conversation → offer → checkout → payment.

The primary optimization metric is verified commercial progress, not code volume.

## Connector promotion contract

For each connector:

DISCOVERED → AUTHENTICATED → CONFIGURED → USED → TESTED → AUDITED → DEPLOYED → LIVE VERIFIED

If a capability is unavailable because of permissions or missing credentials, mark it BLOCKED with an exact prerequisite. Do not weaken the rest of the system.

## Reusable artifacts

Every promoted connector leaves:

- adapter/interface
- config schema
- smoke test
- failure-mode tests
- security notes
- rollback plan
- example workflow
- measurable success criteria

## Next connector gate

Do not add another major connector batch until:

- Phound can produce one real end-to-end call event;
- ten current CALL_READY leads pass contact-quality inspection;
- Dialer UI ordering is verified in production;
- Airtable/CRM event mirroring is idempotent;
- no fabricated outcomes remain;
- production deployment is traceable to GitHub.

Only then promote the next batch.
