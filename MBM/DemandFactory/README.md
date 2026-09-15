# MBM Demand-to-Revenue Factory

The DemandFactory is the orchestration layer for autonomous digital-product monetization.

It does **not** assume the product is an ebook or that the distributor is a creator. It starts from evidence of demand and selects the lowest-cost path to a measurable transaction.

## Core loop

```text
Observe → Normalize → Cluster → Validate → Score → Offer → Build → QA → Distribute → Sell → Attribute → Learn → Next Best Action
```

## Decision contract

Every opportunity must explain:

- `why_demand`
- `why_buyer`
- `why_distributor`
- `why_offer`
- `why_product`
- `why_channel`
- `why_price`
- `expected_value`
- `confidence`
- `validation_plan`
- `kill_conditions`
- `next_action`

## Evidence hierarchy

`hypothesis < single_signal < repeated_signal < explicit_request < observed_purchase < repeat_purchase`

Observed transactions outrank AI assumptions.

## Product graduation

A validated opportunity may graduate through:

`free artifact → low-ticket product → toolkit/system → managed service → recurring product/SaaS → white-label`

The factory should prefer the cheapest artifact capable of validating the demand hypothesis.

## Distribution types

- creator partnership
- affiliate
- community owner
- newsletter
- consultant/agency
- reseller
- marketplace
- SEO/content
- direct sales

## Safety / quality gates

- no fabricated demand evidence
- no fabricated contacts or customer data
- no product build without a recorded demand hypothesis
- no live outreach without an explicit live/armed mode
- no automatic destructive CRM mutation
- every action returns a structured result and next action

## MBM integration

The factory sits above existing MBM capabilities including LeadEngine, pain-point discovery, sales pipeline, revenue engines, Whop tooling, Instagram/network intelligence, and existing artifact/knowledge stores.
