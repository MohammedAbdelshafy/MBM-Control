# Buyer Demand Engine — Design Spec

**Date:** 2026-08-27

---

## PURPOSE

Answer the question: **"What are our buyers hungry for right now?"**

Feed demand signals back into acquisition targeting so we source deals that buyers actually want.

---

## DEMAND DIMENSIONS

| Dimension | Example Values |
|---|---|
| Market | Houston, Dallas, San Antonio |
| Zip Code | 77001, 75201 |
| Property Type | SFR, DUPLEX, TRIPLEX, MULTI_FAMILY |
| Price Band | $100K-$150K, $150K-$200K, $200K-$300K |
| ARV Band | $150K-$200K, $200K-$300K |
| Strategy | FLIP, BRRRR, BUY_AND_HOLD, WHOLESALE |
| Repair Tolerance | LIGHT ($0-$15K), MEDIUM ($15K-$40K), HEAVY ($40K+) |
| Close Speed | 7 DAYS, 14 DAYS, 30 DAYS |
| Yield Target | 10%, 15%, 20%+ |

---

## DEMAND SIGNAL CALCULATION

### Inputs
1. **Active buyers** in segment (verified, last 90 days)
2. **Recent offers** in segment (last 30 days)
3. **Recent closes** in segment (last 90 days)
4. **Response times** to deal alerts
5. **Buyer activity scores**

### Signal Rules

```python
def calculate_demand(market, property_type, price_min, price_max):
    buyers = get_verified_buyers(market, property_type, price_min, price_max)
    offers_30d = get_offers_last_n_days(market, property_type, price_min, price_max, 30)
    closes_90d = get_closes_last_n_days(market, property_type, price_min, price_max, 90)

    active_count = len([b for b in buyers if b.activity_score >= 50])
    verified_count = len([b for b in buyers if b.verification_status == "VERIFIED"])

    if active_count >= 5 and len(offers_30d) >= 3 and len(closes_90d) >= 1:
        return "HOT"
    elif active_count >= 3 and len(offers_30d) >= 1:
        return "WARM"
    elif active_count >= 1:
        return "NORMAL"
    elif verified_count >= 1:
        return "WEAK"
    else:
        return "UNKNOWN"
```

---

## DEMAND DASHBOARD OUTPUT

### Per-Segment View
```
MARKET: Houston
PROPERTY_TYPE: SFR
PRICE_BAND: $150K-$250K
STRATEGY: FLIP

DEMAND SIGNAL: HOT
─────────────────────────
Active Buyers:        37
Verified Buyers:      21
Offers (30d):         14
Closes (90d):          8
Avg Days to Close:    23
Avg Spread:          $42K

TOP BUYERS:
1. John Smith — Score 92 — Last active 2 days ago
2. ABC Capital — Score 87 — Last active 5 days ago
3. Jane Doe — Score 84 — Last active 7 days ago
```

### Market Overview View
```
MARKET OVERVIEW: Houston
═══════════════════════════════════════
SFR $100-150K    FLIP    HOT     (12 buyers, 8 offers)
SFR $150-200K    FLIP    WARM    (7 buyers, 3 offers)
SFR $200-300K    FLIP    NORMAL  (4 buyers, 1 offer)
SFR $150-250K    BRRRR   HOT     (15 buyers, 6 offers)
DUPLEX $200-350K HOLD    WARM    (5 buyers, 2 offers)
MULTI $400-800K  HOLD    UNKNOWN (0 buyers)
```

---

## ACQUISITION FEEDBACK

### Signal → Action
```
HOT signal → Source more deals in this segment
WARM signal → Maintain pipeline, test new sources
NORMAL signal → Monitor, don't over-invest
WEAK signal → Re-engage buyers, check if still active
UNKNOWN signal → Build buyer list first
```

### Daily Demand Report
```python
def generate_demand_report():
    segments = get_all_active_segments()
    report = []
    for segment in segments:
        signal = calculate_demand(**segment)
        report.append({
            "segment": segment,
            "signal": signal,
            "trend": calculate_trend(segment),  # improving/stable/declining
            "action": get_recommended_action(signal)
        })
    return sorted(report, key=lambda x: SIGNAL_PRIORITY[x["signal"]])
```

---

## DATA SOURCES

| Source | Data | Freshness |
|---|---|---|
| BuyerProfile (Prisma) | Buy box criteria | Real-time |
| BuyerMatch (Prisma) | Match history | Real-time |
| Deal (Prisma) | Close history | Real-time |
| Call (Prisma) | Engagement signals | Real-time |
| leads_database.json | Dialer activity | Real-time |
| External: PropStream | Buyer deed records | Daily |
| External: BatchLeads | Buyer contact data | Weekly |

---

## INTEGRATION POINTS

1. **Deal Scoring** → Look up demand for deal's segment → boost score if HOT
2. **Buyer Match** → Weight active buyers in HOT segments higher
3. **Acquisition** → Target sellers in HOT demand segments
4. **Disposition** → Prioritize outreach to HOT buyers first
5. **Content** → Create content targeting HOT demand segments
6. **Next-Best-Action** → "Source more Houston SFR $150-250K deals"
