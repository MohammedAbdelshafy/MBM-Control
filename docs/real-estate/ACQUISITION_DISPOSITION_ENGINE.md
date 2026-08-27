# Acquisition-Disposition Engine — Architecture

**Date:** 2026-08-27
**Status:** P0 Implementation

---

## RELATIONSHIP GRAPH

```
PERSON (Lead/Buyer/Seller/Partner)
 ├── owns PROPERTY
 ├── submitted DEAL
 ├── has BUY BOX (if buyer)
 ├── generated LEAD
 ├── interacted with CONTENT
 ├── belongs to CAMPAIGN
 ├── has APPOINTMENTS
 ├── made OFFERS
 ├── participated in JV
 └── generated REVENUE
```

### Data Flow

```
CONTENT → INTERACTION → LEAD → PERSON → PROPERTY/DEAL → BUYER MATCH → OUTREACH → OFFER → TRANSACTION → REVENUE
```

---

## FOUR DISTINCT PIPELINES

### 1. SELLER PIPELINE
```
NEW → CONTACTED → QUALIFYING → MOTIVATED → UNDERWRITING → OFFER → NEGOTIATION → CONTRACT → CLOSED/LOST
```

### 2. BUYER PIPELINE
```
NEW → QUALIFYING → BUY_BOX_CAPTURED → VERIFIED → ACTIVE → MATCHED → ENGAGED → OFFER → CLOSED
```

### 3. DEAL-SOURCE PIPELINE
```
NEW → DEAL_SUBMITTED → UNDER_REVIEW → QUALIFIED → BUYER_MATCHED → DISPOSITION → JV/ASSIGNMENT → CLOSED
```

### 4. JV/PARTNER PIPELINE
```
NEW → VETTING → VERIFIED → ACTIVE → DEAL → JV → SETTLEMENT → CLOSED
```

---

## ENGINE ARCHITECTURE

### Layer 1: Data Collection (Intake)

```
┌─────────────────────────────────────────────────┐
│                  INTAKE LAYER                    │
├─────────────────────────────────────────────────┤
│ Social CTA Router → Lead Classification          │
│ Deal Submission Portal → Deal Intake             │
│ Buyer Registration → Buy Box Capture             │
│ Manual Entry → CRM Sync                          │
│ API Webhook → External Integration               │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│              CLASSIFICATION LAYER                │
├─────────────────────────────────────────────────┤
│ Intent: DEAL / BUY / SELL / JV / INVEST          │
│ Source: Instagram / Facebook / Manual / Referral  │
│ Priority: HOT / WARM / NORMAL / LOW              │
│ Pipeline: Seller / Buyer / DealSource / JV        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│             SCORING & QUALIFICATION              │
├─────────────────────────────────────────────────┤
│ Seller Motivation Scorer (0-100)                 │
│ Deal Scorer (MAO, margin, demand)                │
│ Buyer Verification (POF, activity, close history)│
│ Data Completeness Gate                           │
│ Next-Best-Action Recommendation                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│            MATCHING & DISPOSITION                │
├─────────────────────────────────────────────────┤
│ Buyer Demand Engine (what do buyers want?)       │
│ Buyer Match Engine (who wants this deal?)        │
│ Deal Distribution (3-tier: Hot/Engaged/Broad)    │
│ JV Agreement Generator                           │
│ Disposition Pipeline (Kanban)                    │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│            OUTREACH & CONVERSION                 │
├─────────────────────────────────────────────────┤
│ MBM Dialer Integration                           │
│ Phound SMS Campaigns                             │
│ Email Sequences                                  │
│ Follow-up Automation                             │
│ Appointment Booking                              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│           CLOSE & REVENUE ATTRIBUTION            │
├─────────────────────────────────────────────────┤
│ Transaction Recording                            │
│ Revenue Attribution (source → content → deal)    │
│ Feedback Loop (best sources, markets, content)   │
│ Learning (improve acquisition)                   │
└─────────────────────────────────────────────────┘
```

---

## SCORING WEIGHTS (Configurable)

### Deal Score (100pt)
| Factor | Weight | Source |
|---|---|---|
| Margin (MAO vs asking) | 20 | ARV, repairs, asking price |
| ARV Confidence | 15 | Data source quality |
| Repair Confidence | 10 | Estimate quality |
| Market Liquidity | 15 | Active buyers in segment |
| Buyer Demand | 15 | Demand engine signal |
| Price Competitiveness | 10 | vs market comps |
| Closing Timeline | 5 | Days to close |
| Data Completeness | 10 | Required fields present |

### Buyer Match Score (100pt)
| Factor | Weight |
|---|---|
| Market Match | 20 |
| Zip Match | 15 |
| Property Type | 10 |
| Price Range | 15 |
| ARV Range | 10 |
| Repair Tolerance | 10 |
| Strategy Fit | 5 |
| Close Speed | 5 |
| Yield/Spread | 5 |
| Recency/Activity | 5 |

### Seller Motivation (100pt)
| Factor | Weight |
|---|---|
| Distress Signals | 25 |
| Equity Position | 20 |
| Absentee Owner | 15 |
| Vacancy | 15 |
| Code Violations | 10 |
| Tax Delinquency | 10 |
| Timeline Urgency | 5 |

---

## BUYER DEMAND ENGINE

### Aggregation Dimensions
- Market (city/county)
- Zip code
- Property type
- Price band ($50K increments)
- ARV band
- Strategy (flip/BRRRR/hold/wholesale)
- Repair tolerance
- Close speed

### Demand Signals
- **HOT** — 5+ active buyers, 2+ recent offers, closing history
- **WARM** — 3-4 active buyers, 1+ recent offer
- **NORMAL** — 1-2 active buyers, interest shown
- **WEAK** — Buyer interest but no action
- **UNKNOWN** — No data

### Feedback Loop
```
DEAL CLOSES → Record: source, content, buyer, market, price, type, time_to_close
→ Update demand signals → Feed back to acquisition targeting
```

---

## SOCIAL → CRM ROUTING

### Platform Abstraction
```python
SOCIAL_PLATFORMS = [
    "instagram", "facebook", "tiktok", "youtube",
    "whatsapp", "website", "phone", "email",
    "community", "manual", "referral"
]
```

### CTA Keywords → Pipeline Routing
```python
CTA_ROUTING = {
    "DEAL": "deal_source",
    "SELL": "seller",
    "BUY": "buyer",
    "JV": "partner",
    "INVEST": "investor",
}
```

---

## CONTENT ATTRIBUTION

### Funnel
```
content → impression → interaction → CTA → conversation → lead → qualified → appointment → deal → revenue
```

### Metrics
- qualified_leads per content piece
- appointments per content piece
- revenue per content piece
- revenue per campaign
- cost per qualified lead by channel

---

## NEXT-BEST-ACTION RULES

| Condition | Action | Priority |
|---|---|---|
| New HOT seller | CALL NOW | 1 |
| New deal source with deal | UNDERWRITE NOW | 2 |
| New HOT buyer | SEND MATCHED DEAL | 3 |
| Buyer with incomplete buy box | QUALIFY | 4 |
| Stale lead (7+ days) | REACTIVATION | 5 |
| No response (3+ touches) | FOLLOW-UP | 6 |
| High-value JV partner | CALL | 7 |
| Deal with no buyer matches | EXPAND SEARCH | 8 |

---

## MBM DIALER INTEGRATION

### Pass to Dialer
```json
{
  "lead_type": "seller|buyer|deal_source|partner",
  "score": 85,
  "source": "instagram",
  "content_origin": "post_abc123",
  "property_context": {...},
  "deal_context": {...},
  "buy_box": {...},
  "recommended_script": "DISTRESSED_SELLER",
  "objection_context": ["timeline", "price"],
  "next_best_action": "CALL_NOW"
}
```

### Preserve
- Normalized phone number
- Scripts and dispositions
- Notes and follow-up
- Call history

---

## FAILURE CONDITIONS

Stop and report if:
- Existing data model is unclear
- Production behavior could be broken
- Credentials required
- External API unavailable
- Legal assumption unverifiable
- Migration could destroy data
- Another agent editing same area
- Existing workflow conflicts

Never hide blockers behind fake completion.
