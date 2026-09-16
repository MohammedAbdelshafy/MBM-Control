# P4 PILOT PROPOSAL (template — proposal-only, no customer, no send)

Status: RELEASE-CANDIDATE pending genuine human approval.
Source facts only: `productized-service/p4-lead-cleaner/FIRST_CUSTOMER_OFFER.md`,
`clean_leads.py --demo` (11 rows → 3 CALLABLE, deterministic),
`MBM/Offers/tests/test_offer_graduation.py` (all gates pass, publish denied
without approval). No customer evidence exists; no revenue has occurred.

## Pilot scope
- One customer-provided CSV/JSON lead list, ≤10,000 records, with a phone column.
- Price: $499.00 one-time (repo offer metadata). Checkout rail: Neteller.
- Turnaround target: 48 hours from dataset receipt.
- Fulfillment: `clean_leads.run_cleaner` (canonical gate) + founder QC review.

## Deliverables (exact bundle)
- `cleaned.csv` (every input row preserved + 8 diagnostic columns)
- `summary.json` (counts, dialable %, reason breakdown)
- `report.md` (before/after + calling sequence)

## Acceptance criteria (machine-checkable)
- `total_records` in == rows out (zero shrinkage).
- `validate_offer` returns [] and `run_qa` passes on the job's evidence_ids.
- `validate_release_manifest` returns [].
- Graduation test for the job passes (`test_offer_graduation` pattern).

## Truthful boundaries (from the offer doc)
- NANP/E.164 syntax + deterministic dedupe + suppression match only.
- NO live carrier pinging, NO skip-tracing, NO conversion guarantees.
- Customer owns TCPA/TSR/FTC-DNC/consent compliance.

## Approval record format (existing architecture)
`ProductionGate.set_approval(entity_id="pilot:<job>", status=APPROVED,
approved_by="<human>", notes="<scope + price + customer>")`
persisted to `MBM/Artifacts/gtm_action_approvals.json`. No approval exists yet.

## Post-approval release procedure (existing architecture)
1. Re-run `validate_offer_end_to_end` + graduation test on the customer job.
2. `lifecycle.can_publish(qa, manifest, mode="ARMED", approval=<record>)` must
   return allowed (reasons == []).
3. Walk `GtmStateMachine` QUALIFIED → CONTACTING → ENGAGED on first delivery.
4. Record `RevenueEvent` only against a real Neteller transaction reference.
5. Feed outcome into `revenue_bridge.attribution_key` + learning ledger.

Any step failing stops the release (fail-closed). No step sends outreach,
charges, or publishes without its own gate.
