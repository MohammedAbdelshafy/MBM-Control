# P4 First-Customer Runbook (human operator)

Companion artifacts: `p4_first_25_prospects.csv` (25 QUALIFIED, 0 rejected),
`p4_outreach_queue.json` (25 DRAFT_ONLY, 0 sends), `p4_sales_playbook.md`,
`p4_sales_metrics.json` (all counters zero except found/qualified/drafted).

## Gate 0 — Human review (required before any contact)
- [ ] Open each of the 25 drafts; edit or drop any that overstates evidence.
- [ ] Confirm sender identity + reply-to mailbox you control.
- [ ] Confirm Neteller checkout link resolves (landing.html link).
- [ ] Record review decision per draft (approve/edit/drop) — no bulk approve.

## Gate 1 — First contact (approved drafts only)
- [ ] Send ONLY human-approved drafts, from your own mailbox, ≤10/day.
- [ ] Set queue record send_status CONTACTED with timestamp (manual edit).
- [ ] metrics: contacted += n.

## Gate 2 — Reply classification (same day)
- [ ] Run every reply through `classify_sales_reply` (or by hand against the
  playbook §4 table); apply required_action (suppressions same day).
- [ ] READY_TO_BUY → open customer job per Phase 10 (identity, dataset, scope,
  price, approval record — all real before any run).

## Gate 3 — Fulfillment (per customer job)
- [ ] Intake checklist (playbook §9) complete, $499 receipt recorded.
- [ ] `run_cleaner` → graduation test → QA → manifest → `can_publish` ARMED.
- [ ] Deliver bundle privately; record RevenueEvent against the real receipt;
  attribution + learning entries.

## Gate 4 — Measure (weekly)
- [ ] Update `p4_sales_metrics.json` from records only (never forecasts).
- [ ] Review: qualification rate, reply rate, time-to-close, fulfillment time.
- [ ] Feed gaps back (Muse loop): scoring, evidence, research, ICP.

## Hard stops (any violation ends the run)
- Any fabricated email/phone/company/claim discovered in the queue.
- Any send without a recorded human approval.
- Any opt-out not suppressed same day.
- Any revenue recorded without a real transaction reference.
