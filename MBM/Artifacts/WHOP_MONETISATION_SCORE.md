# WHOP_MONETISATION_SCORE.md

```yaml
timestamp: 2026-08-24T12:20:00+00:00
owner: ox-alpha
method: weighted 12-dimension model; scores grounded in repo evidence + live API only.
rule: UNKNOWN inputs score low and are listed as gaps, never estimated optimistically.
```

## Dimension Scores — CURRENT vs MAXIMUM SUPPORTED

| Dimension | Weight | Current | Max Supported* | Basis (evidence) |
|---|---|---|---|---|
| ACQUISITION | .12 | 5 | 60 | 2 real landing events ever; campaign engine now exists but 0 touches |
| CONVERSION | .12 | 5 | 60 | checkout links verified live; 0 checkout_started ever recorded |
| AOV | .08 | 40 | 60 | ladder spans $149–$1,997 structurally; no basket data |
| RECURRING | .12 | 10 | 55 | 4 renewal plans LIVE; 0 subscribers |
| UPSELL | .10 | 55 | 70 | cross-sell engine QA-passed; unexercised in reality |
| CROSS-SELL | .08 | 55 | 70 | matrix validated by tests |
| RETENTION | .08 | 25 | 50 | lifecycle module built; zero cohorts to retain |
| REFERRAL | .06 | 30 | 55 | affiliate CLI exists; never enabled on account |
| B2B | .08 | 35 | 55 | DFY suite + NPI B2B data; no B2B sale process run |
| MARGIN | .10 | 20 | 45 | ALL fulfillment costs UNKNOWN — cannot score higher honestly |
| CAPACITY | .05 | 70 | 75 | software-run products; DFY labor-bound |
| AUTOMATION | .05 | 65 | 75 | governor/experiments/lifecycle/campaign tooling built |

**CURRENT PORTFOLIO SCORE: 31/100**
**MAXIMUM SUPPORTED SCORE: ~62/100** *(with acquisition running, webhook registered,
first 10 customers delivered & measured — no new subsystems required)*

*Max Supported = ceiling achievable with current product infrastructure + evidence;
NOT a fantasy projection.

## Per-Product Scores (0–100)

| Product | Score | Strongest dims | Weakest dims | One-line gap |
|---|---|---|---|---|
| Revenue Audit Engine ($149) | **42** | conversion-readiness, capacity, automation | acquisition 0, margin unknown | nobody has been offered it yet |
| Property Intelligence API ($97/mo) | **38** | recurring-native, automation, data moat | acquisition 0, quota costs unknown | needs first subscriber to prove delivery cost |
| AI Voice Agent Factory ($297/mo) | **35** | upsell target from audit, retention story | acquisition 0, per-minute cost unknown | demo asset for prospects does not exist |
| AI Video Clipping Engine ($497/$997) | **30** | standalone stack works | different audience (creators) with ZERO current distribution there | wrong funnel traffic for this SKU |
| DFY AI Employee Suite ($1,997/mo) | **28** | highest price/LTV | capacity labor-bound, margin unknown, no case study | unsellable credibly until one Voice retainer is delivered |

## TOP 10 GAPS (ranked by lost expected value)

1. WEBHOOK UNREGISTERED → purchases invisible to measurement (integration gap)
2. ZERO TOUCHES → the entire funnel has never had input (distribution gap)
3. NO FIRST CUSTOMER → no proof, no testimonial, no margin data (proof gap)
4. WHOP_WEBHOOK_SECRET absent from env (config gap)
5. Fulfillment SOP for the $149 audit UNWRITTEN (ops gap: what exactly gets delivered?)
6. Margin instrumentation absent (no time/cost tracking on delivery)
7. Clipping Engine has no acquisition channel at all
8. Affiliate program not enabled (free referral lever idle)
9. Retainer pricing for weekly re-audits undefined (natural recurring add-on)
10. Agency/reseller SKU undefined

## TOP 10 ACTIONS

See `WHOP_NEXT_10_ACTIONS.md` — ranked by IMPACT × CONFIDENCE / EFFORT.
