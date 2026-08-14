# MoneyBeast Scoring

Evidence-backed weighted composite (jarvis-mbm#8 signal framework).

## Weights

| Component | Weight |
|---|---|
| Distress severity | 30% |
| Recency / urgency | 20% |
| Multi-signal overlap | 20% |
| Seller fatigue / friction | 15% |
| Property / liquidation practicality | 10% |
| Evidence confidence | 5% |

## Scoring rules

1. **Distress severity** = strongest present distress signal scaled to 0-100
   (auction ~96, foreclosure ~90, ...). Computed from `SIGNAL_EVIDENCE` in
   `moneybeast_engine.py`.
2. **Recency** = 90 (<7d), 70 (<30d), 45 (<90d), 20 (older), 30 (unknown date).
3. **Overlap** = 15 for a single signal; 30 per extra signal (cap 100).
4. **Fatigue** = stacked listing-cycle signals (relist 40, price-cut 25, DOM/
   concessions 20, failed listing 15), cap 100.
5. **Practicality** = 60 base; -35 if no property address/parcel, -15 if no
   phone; floor 5.
6. **Confidence** = 20 + evidence items x 12, cap 100.

## Hard caps

- No property key (address/parcel): composite capped at **39** — below the
  Growth200 floor (45). Market-only records never become property leads.
- Composite = weighted sum of the six components, rounded to int.
- Urgency overrides: auction >95, foreclosure/REO >85, probate+vacant >80,
  tax-delinquent+vacant/absentee >78, relist+price-cut >70.

## Placement

- **Hot100**: VERIFIED >= 65 or LIKELY >= 60.
- **Growth200**: VERIFIED >= 45 or LIKELY >= 40.
- Tie-break: composite desc, then `lead_id` asc (deterministic).
- Ranks are sequential within each pipeline.
