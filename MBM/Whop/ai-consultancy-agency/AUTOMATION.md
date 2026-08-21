# AUTOMATION — AI Consultancy Sprint

Reuse MBM infrastructure. Automate ONLY what directly increases sales. Do NOT automate
low-volume manual work for the first 10 customers.

## REUSE (not rebuild)
- Prospect source: `mbm-dialer/app/public/leads_database.json` (single-writer locked).
- Verified lead engine: `MBM/LeadEngine/npi_verified_callsheet.py`, `lead_pack_builder.py`.
- Call scripts: `MBM/LeadEngine/dialer_script_engine.py`, `lead_scripts.py`.
- After-call automation: OmniRoute (MBM/GLM + OmniRoute config).
- Analytics: `MBM/LeadEngine/revenue_tracker.py`, Whop `whop_monetize.py report`.
- Outbound: Phound SMS (`phound_wave_campaign.py`) — already Neteller/checkout-aware.
- Whop fulfillment hub: Files + Chat (existing `whop_monetize.py`).

## AUTOMATE
1. LEAD CAPTURE: prospects_pool.csv already extracted. Refresh weekly from dialer leads
   (verified + callable) via a 1-line PS/py filter — no new CRM.
2. QUALIFICATION: priority_score already computed in dialer. Sort, take top N. Manual yes/no.
3. FOLLOW-UP: Phound SMS wave for Audit offer to pool; template from SALES_ASSETS.md.
   Use existing `phound_wave_campaign.py` (do not hardcode Twilio).
4. DELIVERY: for first 10 — manual. Deliverables (plan PDF, script pack) dropped into
   Whop Files app. Template the Audit so it's 2h of work each.
5. CUSTOMER TRACKING: Whop memberships ledger (`whop_monetize.py monitor`) + revenue
   tracker. No separate CRM.
6. RENEWALS: Whop handles $497/mo recurring billing natively. `monitor` flags at-risk.
7. ANALYTICS: `whop_monetize.py report` → whop_revenue.json; Telegram digest.

## DO NOT AUTOMATE (yet)
- Audit production for first 10 (manual = higher quality + testimonial fuel).
- Kickoff calls (personal).
- Upsell conversations (manual until pattern is proven).

## INTEGRATION POINT
Add this product to `whop_monetize.py` PRODUCTS list (with a real Whop product id after
creating the hub manually) so `publish`/`checkout`/`report`/`monitor` cover it. See
`whop_product_spec.json`.
