# P4 First-Customer Sales Playbook (DRAFT_ONLY assets)

Offer facts: $499 one-time · ≤10,000 records · 48-hour target turnaround ·
CSV/JSON in → cleaned.csv + summary.json + report.md out · Neteller checkout
(see `FIRST_CUSTOMER_OFFER.md`, `landing.html`). No guarantees, no ROI claims,
no fake urgency/scarcity. Every claim below must stay inside these bounds.

## 1. First-contact message (template; per-prospect drafts in p4_outreach_queue.json)
Subject: `Idea for {company}: {observed pain}`

> Hi {name},
>
> Noticed {company} may be dealing with {specific observation}.
> {One-sentence pain hypothesis, labeled as our read, not their fact.}
>
> Relevant proof: P4 demo -- an 11-row sample classified into
> CALLABLE / NOT CALLABLE / DUPLICATE / SUPPRESSED with per-row reason codes.
>
> Open to a 10-minute look next week?
>
> -- MBM

Rules: verified observation only; hypothesis labeled; proof = demo only;
CTA = 10-minute look (not a close).

## 2. Follow-up #1 (3-5 business days, only if no reply and no opt-out)
> Circling back once -- happy to run a free 25-row sample of your list so you
> can see the classification before any $499 commitment. Worth it?

Rules: free-sample offer max 25 rows (bounded, real capability); one follow-up only.

## 3. Follow-up #2 (final, 7+ days later; never after opt-out/refusal)
> Last note from me -- the sample offer stands if list hygiene becomes a
> priority later. Reply STOP any time to opt out.

Rules: explicit opt-out instruction; after this, NURTURE only with permission.

## 4. Reply handling (maps to classify_sales_reply states)
- READY_TO_BUY → open customer job immediately (Phase 10 gate).
- ASKS_FOR_SAMPLE → run ≤25-row free sample via clean_leads, deliver bundle, then paid pilot.
- ASKS_FOR_DEMO → send demo summary (11-row stats) + book 10-minute call.
- PRICE_OBJECTION → restate $499 scope; no discounts without owner approval.
- TIMING_OBJECTION → nurture with permission only; no scheduled sends.
- NEEDS_INFO → answer from FIRST_CUSTOMER_OFFER.md only; say "I don't know" otherwise.
- NOT_INTERESTED → suppress immediately, no further contact (opt-out respected same day).
- WRONG_PERSON → ask for one referral; suppress if refused or no reply.
- INTERESTED → discovery call: qualification questions below.

## 5. Sales qualification questions
1. How many records in the list, and what format?
2. Where did the records come from, and how old are they?
3. What phone column header do you use?
4. Do you hold an internal DNC/suppression list to apply?
5. Who approves a $499 one-time purchase, and what turnaround do you need?

## 6. Objection handling (evidence-only)
- "Does it verify numbers live?" → No. NANP/E.164 syntax + dedupe + suppression only (offer doc §4).
- "Will it find missing numbers?" → No. Missing phones classify NOT CALLABLE; no skip-tracing in this package.
- "Will it improve conversions?" → No guarantee is made or implied (offer doc §4).
- "Is my data kept private?" → Local processing; bundle delivered privately; rows never resold (operational fact of DFY flow).

## 7. Short proposal (per-customer, fill before approval)
Customer: ____ · Records: ____ (≤10,000) · Price: $499 one-time ·
Deliverables: cleaned.csv + summary.json + report.md · Turnaround: 48h target ·
Boundaries: offer doc §4 attached verbatim · Payment: Neteller link from landing.html.

## 8. Payment instructions (existing approved rail)
Pay the $499 setup fee at the Neteller checkout link published on the P4
landing page (`productized-service/p4-lead-cleaner/landing.html`), then email
the CSV/JSON per the landing instructions. Payment received → receipt recorded
→ fulfillment starts. No payment links are constructed ad hoc.

## 9. Customer intake checklist
- [ ] Dataset received (CSV/JSON, phone column present)
- [ ] Scope confirmed (≤10,000 rows; overage → second package, same price)
- [ ] DNC list received or explicitly waived by customer in writing
- [ ] $499 Neteller receipt recorded (transaction reference stored)
- [ ] Approval record created (ProductionGate.set_approval, human approver named)
- [ ] Fulfillment run → graduation test on the job → QA → manifest → ARMED release
- [ ] Bundle delivered privately; RevenueEvent recorded against the real receipt
