# Autonomous Demand-to-Revenue Factory

## Mission

Convert verified market demand into measurable revenue experiments with the smallest reasonable build cost, while retaining an auditable decision trail.

## State machine

```text
DISCOVERED
  ↓
VALIDATING
  ├── rejected
  └── ready_to_build
          ↓
       BUILDING
          ↓
          QA
          ├── failed → BUILDING
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
```

## Decision priorities

1. Evidence before invention.
2. Validation before expensive production.
3. Transactions before vanity metrics.
4. Distribution is a capability, not a single creator channel.
5. Every action produces structured output and a next action.
6. Live side effects require an explicit armed mode and provider-specific permission.

## Distribution graph

The factory can route an offer through creators, affiliates, community owners, newsletters, consultants/agencies, resellers, marketplaces, search/content, or direct sales.

## Product ladder

The factory may graduate a successful offer from free artifact to low-ticket product, toolkit/system, managed service, recurring product/SaaS, and eventually white-label deployment.

## Commercial memory

HubSpot is the preferred CRM surface for relationship/deal state when permissions allow. Revenue events should remain attributable to opportunity, offer, product, distributor, channel, campaign and transaction.

## Existing MBM reuse

Do not duplicate the existing pain-point discovery, sales pipeline, revenue engines, Whop lifecycle/affiliate flows, Instagram/network intelligence, LeadEngine, or artifact/knowledge stores. DemandFactory should orchestrate these systems through adapters over time.

## First implementation slice

The first slice is intentionally proposal-only and deterministic:

- typed demand signals
- evidence weighting
- opportunity commercial scoring
- explicit build/test/launch decisions
- validation and kill conditions
- safe CLI
- hermetic unit tests

The next slices should add adapters for existing demand sources, product builders, HubSpot deal creation/update, commerce attribution, and scheduled autonomous execution.
