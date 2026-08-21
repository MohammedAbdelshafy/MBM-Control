# AI Consultancy Sprint — Funnel Package

**Status:** SHIPPED · deployable · Neteller checkout live
**Owner:** GLM_MONETIZATION_ENGINE + GLM_GTM_ENGINE
**Created:** 2026-08-21

## Funnel map (content → revenue)
```
CONTENT (MBM-Social clips / LinkedIn / cold call)
  → OFFER (AI Consultancy Sprint: Audit $297 / Build $1,497 / Managed $497/mo)
  → LANDING (landing.html — Neteller buy buttons + free-plan capture form)
  → LEAD (mailto capture OR Neteller payment → kickoff email in 24h)
  → FOLLOW-UP (follow_up_sequence.md — 7-touch, stops on BUY/STOP)
  → CUSTOMER (Audit → Build → Managed recurring)
  → REVENUE (Neteller → abdelshafyclapps@gmail.com / Account 4599228811)
```

## Files
- `landing.html` — deployable page, 3 paid tiers + free-plan capture. Self-contained.
- `outreach_script.md` — cold call / email / DM scripts + objection handling.
- `follow_up_sequence.md` — 7-touch cadence + booking/fulfillment paths.
- `neteller_manifest.json` — canonical checkout links (single source of truth).

## Provenance
- Offer spec: `MBM/Whop/ai-consultancy-agency/OFFER.md`
- Verified lead source: `MBM/Whop/ai-consultancy-agency/prospects_pool.csv` (GTM agent uses this for outreach lists)
- Checkout rail: Neteller (mirrors `src/lib/neteller.js`, `server/neteller.js`, `MBM/Scripts/neteller_config.py`)
- Delivery stack: AI cold-calling assistant + verified lead engine + after-call analytics (production)
- No fabricated metrics. Buyer count claims are qualitative ("real, phone-verified businesses").

## Deploy
Static host (GitHub Pages / Netlify / Whop Files). Form posts via mailto; paid path is direct Neteller.
