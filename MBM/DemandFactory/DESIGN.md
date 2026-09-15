# Autonomous Demand-to-Revenue Factory

## Mission

Convert verified market demand into measurable revenue experiments with the smallest reasonable build cost, while producing products that are highly relevant, credible, easy to evaluate, easy to use, and easy to buy.

## State machine

```text
DISCOVERED
  ↓
VALIDATING
  ├── rejected
  └── commercial_fit
          ↓
     OFFER / PRODUCT
          ↓
      QUALITY GATES
          ├── failed → REPAIR
          └── passed
                ↓
       CONSUMER CONVICTION
          ├── failed → PROOF / CREATIVE / OFFER REPAIR
          └── passed
                ↓
        READY_TO_LAUNCH
                ↓
             LAUNCHED
                ↓
        MEASURE / ATTRIBUTE
          ├── kill
          ├── iterate
          └── scale
                ↺
```

## Decision priorities

1. Evidence before invention.
2. Validation before expensive production.
3. Transactions and retention before vanity metrics.
4. Distribution is a capability, not a single creator channel.
5. Every important product claim needs evidence or a clearly stated limitation.
6. Conviction comes from relevance, proof, clarity, risk reduction, experience, and trust, not coercion.
7. Every action produces structured output and a next action.
8. Live side effects require an explicit armed mode and provider-specific permission.

## Consumer Conviction dimensions

The factory evaluates:

- relevance
- outcome clarity
- proof
- risk reduction
- purchase friction
- creative readiness
- personalization
- trust
- usage readiness
- claim integrity

A product is not launch-ready merely because it scores highly on commercial potential. Critical failures produce a repair action instead of a launch action.

## Distribution graph

The factory can route an offer through creators, affiliates, community owners, newsletters, consultants/agencies, resellers, marketplaces, search/content, or direct sales.

## Product ladder

The factory may graduate a successful offer from free artifact to low-ticket product, toolkit/system, managed service, recurring product/SaaS, and eventually white-label deployment.

## Creative system

Higgsfield is treated as the production layer for product-specific visual proof: hero visuals, demos, objection visuals, proof cards, and creator-native variants. Creative work must map to a product claim or buyer objection; generic decorative generation is not a launch gate.

## Knowledge graph

The graph links demand → buyer → pain → offer → proof → objection → creative → channel → transaction → outcome. It is used to explain why a product exists and why an action is being selected.

## Commercial memory

HubSpot is the preferred CRM surface for relationship/deal state when permissions allow. Revenue events remain attributable to opportunity, offer, product, distributor, channel, campaign, and transaction. The current adapter is proposal-only and does not mutate HubSpot.

## Existing MBM reuse

Do not duplicate existing pain-point discovery, sales pipeline, revenue engines, Whop lifecycle/affiliate flows, Instagram/network intelligence, LeadEngine, or artifact/knowledge stores. DemandFactory orchestrates these systems through adapters.

## Safety / trust boundary

The factory must not create fabricated demand evidence, testimonials, contacts, customer data, performance claims, fake scarcity, or deceptive guarantees. The system's objective is to make legitimate value obvious and reduce legitimate uncertainty.
