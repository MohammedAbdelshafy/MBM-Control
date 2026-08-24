# WHOP_MAX_VALUE_MATRIX.md — Maximum Customer Value by Segment

```yaml
timestamp: 2026-08-24T12:15:00+00:00
owner: ox-alpha
evidence_basis: live Whop API (biz_UxlhGUdO9TpGb0, 5 products/6 plans), whop_product_intel.py,
                whop_revenue_qa.py 100/100, GTM_TOP25_EXECUTION_QUEUE.json (CMS NPI)
revenue_status: NO_REVENUE_EVIDENCE — every $ figure below is PRICE, not earnings.
```

## Ladder Validation (Phase 7)

**Ladder: ENTRY → CORE → SPECIALIZED → FLAGSHIP (structurally supported, commercially unproven)**

```
$149 Revenue Audit Engine          ENTRY  (one-time, low-friction trust builder)
   ├→ $297/mo AI Voice Agent Factory      CORE recurring (fixes what audit exposes)
   │     └→ $1,997/mo DFY AI Employee Suite  FLAGSHIP managed service
   └→ $97/mo Property Intelligence API    SPECIALIZED data recurring
$497/$997/mo AI Video Clipping     SPECIALIZED standalone (creator segment)
```

Verdict: the hypothesis `$149 Audit → $297/mo Voice → $1,997/mo DFY` is **SUPPORTED
by structure** (cross-sell matrix passes QA check 15; upsell fields wired in product
intel) but **UNPROVEN commercially** — 0 members, 0 conversions ever. Confidence:
structural HIGH, commercial UNVERIFIED.

## Segment × Offer Matrix (Phase 8)

| Segment | Entry | Core | Upsell | Recurring | Premium | Evidence |
|---|---|---|---|---|---|---|
| **Medical/therapy clinic owners** (NPI Top-25: real phones, decision makers named) | $149 Audit (72h leakage verdict on their lead spend) | $297/mo Voice Agent Factory (front-desk overflow, recall calls) | DFY Suite $1,997/mo | Voice + Suite retainers | Multi-location rollout (UNPRICED) | GTM_TOP25 rows 1–25; pain fields populated from hiring/timing signals |
| **RE investors / wholesalers** | $97/mo Property Intelligence API | API + weekly packs | $297/mo Voice (dial the feed) → $1,997 DFY | API renewal native | County-expansion tiers (UNPRICED) | property_intel pipeline LIVE; DCAD verified; hourly NPI cron |
| **Creators / media brands** | $497/mo Clipping Engine | $997/mo tier | DFY Suite | Clipping renewal ×2 | Agency white-label (UNBUILT) | clipping-factory stack operational |
| **Agencies (resellers)** | UNDEFINED — no reseller SKU exists | — | — | — | White-label of API/Voice | OPPORTUNITY, no evidence of demand yet |

## Per-Product Value Ceiling (prices REAL from live plans API)

| Product | Price | Billing | Retention story | Delivery cost | Margin | Capacity |
|---|---|---|---|---|---|---|
| Revenue Audit Engine | $149 | one-time | Weekly re-audit retainer possible (UNPRICED) | UNKNOWN | UNKNOWN | HIGH (software-run) |
| Property Intelligence API | $97/mo | renewal | Fresh verified data daily | UNKNOWN (quota costs scale) | UNKNOWN | MEDIUM (source rate limits) |
| AI Voice Agent Factory | $297/mo | renewal | Agent keeps calling 24/7 | UNKNOWN (Retell/min) | UNKNOWN | MEDIUM |
| AI Video Clipping Engine | $497–$997/mo | renewal ×2 | Continuous content output | UNKNOWN (GPU/API) | UNKNOWN | MEDIUM-HIGH |
| DFY AI Employee Suite | $1,997/mo | renewal | Done-for-you ops dependency | UNKNOWN (labor!) | UNKNOWN | LOW-MEDIUM (human time) |

**Honest ceiling statement:** with current evidence, the portfolio can support a
plausible path to ~$3–8k MRR-equivalent per 10 mixed customers WITHOUT new
engineering. Anything beyond that requires delivery-capacity proof that does not
exist today. No revenue projections are claimed beyond this.

## Biggest leaks & opportunities

- BIGGEST LEAK: zero tracked traffic (2 landing events ever) + webhook unregistered
  (purchases would be invisible to our funnel measurement).
- CHEAPEST REVENUE: $149 Audit sold via 1-click WhatsApp/Gmail to NPI Top-25 (zero media spend).
- HIGHEST MARGIN: unknown until first delivery is time-tracked (do not guess).
- HIGHEST LTV: DFY Suite ($1,997/mo) behind Voice retainer.
- BEST B2B: multi-location clinics (suite replicated across sites).
