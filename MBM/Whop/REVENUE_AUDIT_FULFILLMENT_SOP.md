# REVENUE_AUDIT_FULFILLMENT_SOP.md
# Revenue Audit Engine — $149 one-time — prod_L2MmMKYlE9LAv

```yaml
version: 1.0
timestamp: 2026-08-24
owner_of_sop: operator (human) + ox-alpha (system stages)
promise_on_checkout: 72-hour revenue leakage audit with ranked fix list
hard_rule: NO stage may be marked done without its verification artifact.
           No delivery claims without the customer-confirmed receipt evidence.
execution_log: MBM/Whop/logs/fulfillments.jsonl   (append-only; created on first real order)
unit_economics: MBM/Whop/revenue_unit_economics.py record <event_id> ...
```

## Stage Chain

### 1. PURCHASE
- **Owner:** Whop (platform)
- **Input:** customer clicks `https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ`
- **Output:** completed Whop checkout
- **Verification:** `payment.succeeded` exists for the plan (dashboard or webhook)
- **Failure condition:** checkout abandoned → nothing to fulfill; no action

### 2. PAYMENT VERIFICATION
- **Owner:** system (`webhook_log.json` + `revenue_events.jsonl`)
- **Input:** signed Whop webhook at `POST /api/webhook/whop`
- **Output:** persisted event with `metadata.product_id=prod_L2MmMKYlE9LAv`, non-smoke `event_id`
- **Verification:** row visible in `python MBM/Whop/whop.py daily` under PURCHASES (classification REAL)
- **Failure condition:** payment seen in dashboard but no webhook row after 24h → integration incident;
  verify manually from Whop dashboard, never fabricate the event

### 3. CUSTOMER RECORD
- **Owner:** system (`whop_revenue_os.build_customer_360`)
- **Input:** webhook membership/user payload (email required for delivery)
- **Output:** customer_360 entry linked to the purchase event_id
- **Verification:** `python MBM/Whop/whop.py customers` shows the buyer
- **Failure condition:** no email captured → BLOCKED; contact via Whop DM before any audit work

### 4. INPUT COLLECTION
- **Owner:** operator (human)
- **Input:** customer email access
- **Output:** customer's pipeline export (leads/calls/replies/deals CSV or read-only access),
  plus 5-question intake (monthly lead spend, channels used, close rate, avg deal value, biggest bottleneck)
- **Verification:** inputs received & openable; reply stored in `logs/fulfillments.jsonl`
- **Failure condition:** no response within 48h → send ONE reminder (governor-capped);
  no response by hour 60 → offer reschedule or refund; the 72h clock starts ONLY when inputs land

### 5. AUDIT EXECUTION
- **Owner:** operator + system tooling (lead_quality_scorer / revenue-review skill where applicable)
- **Input:** customer pipeline data + intake answers
- **Output:** working analysis: lead→reply→close conversion by stage, leakage points ranked by $ impact,
  time-to-first-contact measurement if data allows
- **Verification:** every finding cites a number from THEIR data (no generic advice); findings list ≥ 3 leaks or explicit "no significant leak found"
- **Failure condition:** data too sparse/incomplete → request one supplement within 12h;
  if still insufficient → partial audit + pro-rated refund option, stated honestly

### 6. QA
- **Owner:** operator (second pass, ideally next morning — fresh eyes rule)
- **Input:** draft findings
- **Output:** QA checklist passed: numbers reproducible, no fabricated claims,
  recommendations ranked by expected $ recovery, no unverifiable promises
- **Verification:** QA checklist recorded in fulfillments.jsonl
- **Failure condition:** any fabricated/unverifiable claim → remove it before delivery. Non-negotiable.

### 7. REPORT
- **Owner:** operator
- **Input:** QA-passed findings
- **Output:** PDF/markdown report ≤ 6 pages:
  verdict → top 3 leaks ($ impact × confidence) → ranked fix list → what we'd automate next
- **Verification:** file opens, renders, matches findings; stored alongside fulfillment record
- **Failure condition:** report exceeds scope promise (it is an audit, not an implementation)

### 8. DELIVERY
- **Owner:** operator
- **Input:** final report
- **Output:** report sent to customer email + Whop DM, WITHIN the 72h window from input receipt
- **Verification:** send receipt timestamp logged; customer acknowledgment requested (not required to be valid delivery, but tracked)
- **Failure condition:** cannot deliver by hour 72 → proactive message BEFORE deadline with new ETA + goodwill credit; silence = broken promise

### 9. FEEDBACK
- **Owner:** operator
- **Input:** delivered report
- **Output:** one feedback question set (clarity 1–5, usefulness 1–5, "what would you implement first?")
- **Verification:** responses (or explicit non-response after 2 capped attempts) logged
- **Failure condition:** refund requested → process immediately via Whop; log reason in unit economics (refund field)

### 10. UPSELL QUALIFICATION
- **Owner:** system recommendation + HUMAN decision (governor L3 for any outbound)
- **Input:** audit findings + feedback
- **Output:** at most ONE tailored recommendation, only if the audit exposed the matching gap:
  - calling/recall gap → AI Voice Agent Factory ($297/mo)
  - data-quality/freshness gap → Property Intelligence API ($97/mo)
  - ops-capacity gap across roles → DFY AI Employee Suite ($1,997/mo)
- **Verification:** recommendation references THE CUSTOMER'S OWN audit numbers; respects cooldowns
  (whop_governor + OUTREACH_COOLDOWN_DAYS); max 2 total touches ever
- **Failure condition:** no legitimate gap matching an existing product → NO upsell. Never invent need.

## Timing Summary

| Clock | Starts | Deadline |
|---|---|---|
| Delivery promise | INPUT COLLECTION verified | +72h |
| Payment→first contact | webhook received | +24h |
| Reminder cap | first reminder | 1 reminder, then refund/reschedule offer at h60 |

## Cost Capture (feeds revenue_unit_economics.py)

At delivery, record actuals once:
```
python MBM/Whop/revenue_unit_economics.py record <purchase_event_id> \
  --labor-minutes <actual> --ai-cost <actual-or-0> --api-cost <actual-or-0> \
  --refund 0
```
Until that record exists, every economic field reports UNKNOWN. That is correct behavior.
