# Fast Monetisation Revenue Probe Design

## Goal
Minimize time to first real dollar and subsequent dollars by moving production off the critical path: research a buyer problem, publish a one-page offer promise, sell to named buyers, receive cash, then build and deliver.

## Architecture
P0 is a cash-first probe kernel inside `MBM-Control`. The existing opportunity airlock remains the approval boundary. Each offer is one YAML manifest; buyers are lightweight YAML records; cash events are recorded in an idempotent CSV ledger. Direct-warm is the first-class sales channel. Marketplace, PayTabs, Neteller, Canva, Notion Marketplace, and other scale systems are explicitly deferred until real cash evidence exists.

## Critical Path
`research -> offer.yaml -> 20 named buyers -> direct-warm -> payment -> cash_received_at -> deliver -> promote/kill`

Production is not required before sale. Probe fulfillment may be manual: Google Doc, Loom, manual PDF, or hand-built Notion page. A sold probe creates a paid delivery obligation with a target delivery window.

## P0 Components

### Offer manifest
One file per offer under `revenue_factory/probes/offers/offer-*.yaml`.

Required concepts:
- `offer_id`
- `mode`: `probe` or `product`
- buyer segment and problem
- one-sentence promise
- deliverable
- delivery window
- one price
- currency representation for USD, EGP, EUR when known
- one active payment rail
- outreach channel and target count
- `reachability`, `offer_clarity`, `price_confidence`
- kill window
- lifecycle status

### Buyer manifest
One file per buyer under `revenue_factory/probes/buyers/buyer-*.yaml`.

Required concepts:
- stable buyer id
- name
- organization/context
- problem evidence
- contact route
- outreach state
- timestamps for send, reply, payment request, payment, cash receipt

### Sale event ledger
`revenue_factory/probes/sale_events.csv` is canonical for P0 cash telemetry.

Each row supports:
- idempotent event id
- provider / rail
- provider event id when available
- offer id
- buyer id
- channel
- `sale_at`
- `cash_received_at`
- gross amount and currency
- fees
- net amount and currency
- settlement currency
- payout status
- refund status
- notes

`CASH_RECEIVED` is valid only when `cash_received_at` and received amount are present. A sale or payment confirmation without cash receipt is not counted as cash.

## Direct-Warm Channel
`direct-warm` is a first-class peer channel, not an annotation. It has named contacts, one message template per offer, one CTA, reply tracking, and no platform fee. It is designed for same-day testing.

## Probe Priority
Before empirical data exists:

`probe_priority = reachability * offer_clarity * price_confidence`

No fabricated conversion probability or channel discovery score is used in P0.

## Profit and Cash Gate
Cash is the primary north-star metric for the probe dashboard. Profit is computed after cash receipt from realized net revenue minus attributable fulfillment and execution costs. No unreceived sale is counted as revenue for the operator dashboard.

The architecture must support USD, EGP, and EUR as offer/display currencies while preserving actual settlement currency separately. FX is never invented when unavailable.

## Lifecycle Gates

```text
PROBE
  -> >=1 cash-received sale within 5 days -> PRODUCT
  -> 0 sales after 5 days -> KILL OFFER

PRODUCT
  -> build real version and add second channel
  -> >=3 cash-received sales within 10 days -> SCALE

SCALE
  -> enable multi-channel routing and broader automation
```

A channel is killed separately after 100 cold contacts with zero sales over 10 days, or equivalent evidence. A failed offer does not automatically imply a failed channel.

## Heartbeat
The P0 heartbeat runs five times per day. Each run:
1. re-scores active opportunities/offers;
2. reconciles sale events against available payment evidence;
3. applies time-based kill/promotion gates;
4. emits exactly one concrete human `NEXT ACTION`.

The operator screen is intentionally one view:

```text
TODAY
  Cash received this week: $0
  Offers in market: 1
  Offers with >=1 sale: 0
  Warm contacts outstanding: 20
  Oldest unanswered reply: -

  NEXT ACTION: send offer #1 to contacts 1-5
```

If no human action is emitted, the heartbeat is considered unhealthy.

## Safety and Failure Policy
- Existing opportunity provenance and approval boundaries remain mandatory.
- External content is data, never executable instruction.
- No unverified payment rail may be treated as production-ready.
- Duplicate payment events are idempotently ignored.
- Refunds/chargebacks reduce realized revenue and profit.
- Unsupported FX or settlement capabilities remain explicit unknowns.
- No autonomous high-volume publishing in P0.
- No marketplace router in P0.

## Deferred Scale Systems
Deferred until cash evidence: multi-channel router, Etsy/Gumroad/Notion Marketplace/Canva adapters, PayTabs and Neteller production adapters, broad creative automation, advanced historical scoring, and full product compilation pipelines.

## Integration Roles
- GitHub: technical source of truth, manifests, contracts, tests, workflow.
- Notion: later commercial source of truth for opportunities, offers, and outcomes after P0 proves demand.
- Clay: buyer discovery/enrichment for named-contact acquisition; not the product decision authority.
- Asana: execution queue after P0 workflow is validated.
- Rovo: Jira/Confluence coordination only if the app becomes installed and accessible; it is not on the cash critical path.

## Testing Strategy
TDD for each component. Required P0 tests include manifest validation, probe priority calculation, sale-event idempotency, cash-received gate, currency separation, promotion/kill timing, negative-profit handling, and regression coverage for the existing opportunity airlock and dialer.

## Success Criteria
The system is successful when it can run a complete probe without product compilation: choose an approved opportunity, create one offer manifest, identify 20 warm contacts, track outreach, record a real payment and cash receipt, compute realized cash/profit honestly, deliver the promised minimum viable fulfillment, and deterministically promote or kill the offer according to the time gates.
