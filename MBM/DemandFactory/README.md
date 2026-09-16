# MBM Demand-to-Revenue Factory

The DemandFactory is the orchestration layer for autonomous digital-product monetization.

It does not assume the product is an ebook or that the distributor is a creator. It starts from evidence of demand and selects the lowest-cost path to a measurable transaction.

## Core loop

```text
Observe → Normalize → Cluster → Validate → Score → Offer → Build → QA → Convince → Package → Distribute → Sell → Attribute → Learn → Next Best Action
```

## Consumer conviction gate

A product is not launch-ready merely because it exists or looks polished. The factory evaluates:

- relevance
- outcome clarity
- proof
- risk reduction
- purchase friction
- creative readiness
- personalization
- trust
- usage readiness

The quality gate also requires verified claims, proof provenance, a real checkout rail, and actual delivery assets.

The system does not use coercion, fake scarcity, fabricated testimonials, or unsupported claims. Its job is to make a legitimate offer easier to understand, evaluate, trust, buy, and use.

## Monetization graduation

```text
signal
  ↓
low-cost validation
  ↓
paid pilot / pre-sale
  ↓
one-time product or DFY service
  ↓
managed service
  ↓
recurring product / SaaS
  ↓
affiliate / reseller / white-label expansion
```

The factory should use the cheapest step that can produce real commercial evidence, then graduate only when actual buyer outcomes justify the next layer.

## Existing money rails

The repository already contains monetization paths for digital products, Whop checkout/plans/affiliates/revenue reporting, Shopify, high-ticket sales, affiliate revenue, lead products, and social distribution. DemandFactory orchestrates those rails instead of creating duplicate storefronts.

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

Every commercial action should also be attributable to an opportunity, offer, product, distributor, channel, campaign, and transaction where those identifiers exist.

## Safety

- no fabricated demand evidence
- no fabricated contacts or customer data
- no unsupported claims
- no product build without a recorded demand hypothesis
- no live outreach without an explicit live/armed mode
- no automatic destructive CRM mutation
- live CRM writes require provider authorization and confirmation
- every action returns structured output and a next action

## Operational invariants (verified foundation)

- **Creator Acquisition Gate (#65):** `creator_gate.py` enforces >=20,000
  evidenced audience with platform, profile, audience_type, audience_count,
  evidence_url, evidence_source, timestamp. Rejects missing/malformed/future/
  stale (>90 days) with deterministic reason codes. Audience size is never
  interpreted as intent/conversion/revenue/PMF (`assert_audience_isolation`).
  Integration: `creator_loop.qualify_creator_with_evidence_gate`.
- **Lifecycle controller (#33):** `lifecycle.py` owns DISCOVERED→…→RELEASED
  transitions (fail-closed), QA aggregation (`run_qa`), release-manifest
  validation (`validate_release_manifest`), retry/quarantine
  (`RetryTracker`, max 3), guarded activation (`activation_mode`: OFF/DRY_RUN/
  ARMED requires human flag + `FACTORY_ARMED=1`), and `can_publish` (failed
  gates cannot publish). Scheduled runs allowed only OFF/DRY_RUN proposal-only.
- **Activation prerequisites:** ARMED requires human approval record +
  `FACTORY_ARMED=1` + all gates passed. Half-armed stays DRY_RUN.
- **No-publish invariant:** `can_publish` is False without QA passed +
  manifest valid + ARMED + approval. Adapters remain proposal-only.
- **MCP routing:** capabilities registered in
  `jarvis_control_plane/capability_registry.py`, routed via
  `jarvis_control_plane/factory_routing.py` through policy/approval to
  Factory stages. Unknown capability/provider/tool = DENY.
- **Known blockers:** legacy `MBM/Offers/*.md` contain unsupported
  market/ROI claims and FAIL `offer_schema` validation; factory branch
  `check.yml` factory-test job is not present on local `master` check workflow
  (verified via local pytest instead).
