# WIRING.md — timesfm-forecast → founder products

## Primary lane: DataClean AI → the "Forecasts" capability

DataClean AI ($499) cleans a client's messy list in 48h. The natural
follow-on question every client asks: *"so what happens next?"*
TimesFM answers it for any numeric series inside that cleaned data:

- **Weekly signups / sales / traffic forecast** — from the client's own
  cleaned CSV, delivered as a one-page forecast sheet with quantile bands.
- **Pitch pattern:** the Bolt-Slides deck (`night-shift/bolt-slides`) gets a
  third live widget: paste 12+ weeks of numbers → see the next 12 weeks
  with uncertainty bands. "Your clean data, projected."
- **Offer framing (honest):** "baseline forecast from your numbers —
  no crystal ball; the model doesn't know your launches." The caveat is a
  trust feature, not a disclaimer to hide.

Cost per forecast: $0 (local CPU). Margin on the upsell is ~100%.

## Secondary: MBM-Control internal ops

- **Outreach pipeline:** forecast weekly reply/pilot volume from the
  campaign send logs → staffing/planning input for the founder's money
  check-ins (Wed + Sat mornings, per the $5k goal cadence).
- **Campaign economics:** pair with power #10 (voice calls) cost
  estimates — forecast call volume → projected spend before a Vapi
  campaign runs.

## Tertiary: Wholesaler Lead Engine

- Market-level series (median days-on-market, list-price trends per zip)
  → absorption forecasts feeding the buy-box pricing model. Needs a
  data source (separate job); the forecasting engine is ready.

## Activation checklist

1. `pip install timesfm torch` on the machine that will run forecasts
   (CPU fine; ~1 GB one-time).
2. First `forecast(...)` call downloads the checkpoint from HuggingFace
   once (~800MB), then runs offline.
3. No key, no account, no network needed afterward.
4. Skill: `~/workspace/skills/timesfm-forecast/SKILL.md`.
