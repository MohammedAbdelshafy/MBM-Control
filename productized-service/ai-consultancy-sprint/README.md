# AI Consultancy Sprint — Funnel Package

**Status:** SHIPPED · deployable · Whop checkout live
**Owner:** GLM_MONETIZATION_ENGINE + GLM_GTM_ENGINE
**Created:** 2026-08-21

## Funnel map (content → revenue)
```
CONTENT (MBM-Social clips / LinkedIn / cold call)
  → OFFER (AI Consultancy Sprint: Audit $297 / Build $1,497 / Managed $497/mo)
  → LANDING (landing.html — Whop purchase CTAs + free-plan capture form)
  → LEAD (mailto capture OR Whop checkout → kickoff email in 24h)
  → FOLLOW-UP (follow_up_sequence.md — 7-touch, stops on BUY/STOP)
  → CUSTOMER (Audit → Build → Managed recurring)
  → REVENUE (Whop → Contec AI Agentic Teamz / Product prod_qoPikOSNXZBcI)
```

## Files
- `landing.html` — deployable page, 3 paid tiers + free-plan capture. Self-contained.
- `outreach_script.md` — cold call / email / DM scripts + objection handling.
- `follow_up_sequence.md` — 7-touch cadence + booking/fulfillment paths.
- `whop_manifest.json` — canonical Whop checkout links (single source of truth).
- `neteller_manifest.json` — fallback direct checkout configuration.

## Provenance
- Offer spec: `MBM/Whop/ai-consultancy-agency/OFFER.md`
- Verified lead source: `MBM/Whop/ai-consultancy-agency/prospects_pool.csv` (GTM agent uses this for outreach lists)
- Checkout rail: Whop (Company: Contec AI Agentic Teamz, Business ID: `biz_2VDyenKpD0KOyo`, Product ID: `prod_qoPikOSNXZBcI`)
  - Audit ($297): `plan_e3ibiYXeeAaZV` → `https://whop.com/checkout/plan_e3ibiYXeeAaZV`
  - Build & Deploy ($1,497): `plan_j5bQuNA8nRbWo` → `https://whop.com/checkout/plan_j5bQuNA8nRbWo`
  - Managed AI Growth ($497/mo): `plan_GM82PrzSTSmmK` → `https://whop.com/checkout/plan_GM82PrzSTSmmK`
- Delivery stack: AI cold-calling assistant + verified lead engine + after-call analytics (production)
- No fabricated metrics. Buyer count claims are qualitative ("real, phone-verified businesses").

## Deploy
Static host on Vercel (`https://mbm-dialer-app.vercel.app/sprint`) or standalone static server.
