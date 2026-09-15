# MBM Demand-to-Revenue Factory

The DemandFactory is the orchestration layer for autonomous product monetization.

It does **not** assume the product is an ebook or that the distributor is a creator. It starts from evidence of demand and selects the lowest-cost path to a measurable transaction.

## Core loop

```text
Observe → Normalize → Cluster → Validate → Score → Offer → Build → QA → Convince → Distribute → Sell → Attribute → Learn → Next Best Action
```

## Consumer Conviction Engine

A product is not launch-ready merely because it is attractive or commercially plausible. Before launch, the factory evaluates:

- relevance to the buyer's real problem
- outcome clarity
- substantiated proof
- risk reduction and transparent limitations
- purchase friction
- creative readiness
- personalization
- trust
- usage readiness
- claim integrity

The goal is to remove legitimate reasons to hesitate through relevance, evidence, clarity, product quality, and a low-friction experience. The factory never uses fake scarcity, fabricated testimonials, deceptive claims, or coercive UX.

## Decision contract

Every opportunity must explain:

- why demand exists
- why this buyer matters
- why a distributor/channel can reach them
- why this offer fits the problem
- why this product is the right validation artifact
- why this channel is appropriate
- why the price is defensible
- expected value and confidence
- validation plan
- kill conditions
- next action

## Evidence hierarchy

`hypothesis < single_signal < repeated_signal < explicit_request < observed_purchase < repeat_purchase`

Observed transactions outrank AI assumptions.

## Product quality contract

Launchable products need an outcome statement, proof inventory, buyer preview, usage path, objection map, transparent limitations, QA checks, and a sufficient evidence level for the claims being made.

## Product graduation

A validated opportunity may graduate through:

`free artifact → low-ticket product → toolkit/system → managed service → recurring product/SaaS → white-label`

The factory prefers the cheapest artifact capable of validating the demand hypothesis.

## Distribution graph

Distribution is broader than creator outreach:

`creator | affiliate | community | newsletter | consultant/agency | reseller | marketplace | SEO/content | direct sales`

## Integration contracts

**Knowledge Graph:** connects demand, buyer, pain, offer, proof, objections, creative, channel, and outcomes.

**HubSpot:** supplies commercial-memory and attribution payloads for contacts, companies, deals, campaigns, and lifecycle outcomes. The adapter is proposal-only until explicit CRM write authorization is available.

**Higgsfield:** receives structured creative briefs mapped to product claims and buyer objections. The factory asks for hero visuals, demos, objection visuals, proof cards, and creator-native variants rather than generic decoration.

## Safety / quality gates

- no fabricated demand evidence
- no fabricated contacts, testimonials, customer data, or performance claims
- no product build without a recorded demand hypothesis
- no launch while a critical conviction gate is below threshold
- no live outreach without explicit live/armed mode
- no automatic destructive CRM mutation
- every action returns a structured result and next action

## CLI

```bash
python -m MBM.DemandFactory --file MBM/DemandFactory/sample_opportunity.json
npm run factory:evaluate -- --file MBM/DemandFactory/sample_opportunity.json
```

## MBM integration

The factory sits above existing MBM capabilities including LeadEngine, pain-point discovery, sales pipeline, revenue engines, Whop tooling, Instagram/network intelligence, and artifact/knowledge stores. It is an orchestration layer, not a replacement for those systems.
