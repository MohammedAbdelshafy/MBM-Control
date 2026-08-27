# Buyer Matching — Design Spec

**Date:** 2026-08-27

---

## BUYER BUY BOX FIELDS

```python
@dataclass
class BuyerBuyBox:
    # Location
    markets: List[str]           # ["Houston", "Dallas"]
    zip_codes: List[str]         # ["77001", "77002"]
    radius_miles: float          # 25.0

    # Property
    property_types: List[str]    # ["SFR", "DUPLEX", "TRIPLEX"]
    min_beds: int                # 2
    max_beds: int                # 5
    min_baths: float             # 1.0
    min_sqft: int                # 800
    max_sqft: int                # 3000
    min_lot_acres: float         # 0.1
    max_lot_acres: float         # 1.0

    # Financial
    price_min: float             # 50000
    price_max: float             # 300000
    arv_min: float               # 100000
    arv_max: float               # 500000
    rehab_min: float             # 0
    rehab_max: float             # 50000
    min_spread: float            # 15000
    min_cash_on_cash: float      # 0.15
    min_yield: float             # 0.08

    # Strategy
    strategy: List[str]          # ["FLIP", "BRRRR", "BUY_AND_HOLD"]
    cash_or_finance: List[str]   # ["CASH", "HARD_MONEY"]
    closing_speed_days: int      # 14
    occupancy_preference: str    # "ANY" | "VACANT" | "OCCUPIED"

    # Deal Types
    preferred_deal_types: List[str]  # ["WHOLESALE", "SUBJECT_TO", "SELLER_FINANCE"]
    avoid_list: List[str]        # ["FLOOD_ZONE", "HOA"]

    # Meta
    last_verified: datetime
    source: str                  # "manual" | "csv" | "api"
    reliability_score: float     # 0-100
    activity_score: float        # 0-100
```

---

## MATCHING ALGORITHM

### Deterministic Scoring (100pt)

```python
def calculate_match_score(property: Property, deal: Deal, buyer: BuyerBuyBox) -> MatchResult:
    score = 0
    positive = []
    negative = []
    missing = []

    # MARKET MATCH (20pt)
    if property.city in buyer.markets:
        score += 20
        positive.append("market_match")
    elif property.zip in buyer.zip_codes:
        score += 15
        positive.append("zip_match")
    else:
        negative.append("no_market_match")

    # PROPERTY TYPE (10pt)
    if property.type in buyer.property_types:
        score += 10
        positive.append("property_type_match")
    else:
        negative.append("property_type_mismatch")

    # PRICE RANGE (15pt)
    if deal.asking_price:
        if buyer.price_min <= deal.asking_price <= buyer.price_max:
            score += 15
            positive.append("price_in_range")
        elif deal.asking_price < buyer.price_min:
            score += 8  # Below budget is usually OK
            positive.append("price_below_budget")
        else:
            negative.append("price_above_budget")
    else:
        missing.append("asking_price")

    # ARV RANGE (10pt)
    if deal.arv:
        if buyer.arv_min <= deal.arv <= buyer.arv_max:
            score += 10
            positive.append("arv_in_range")
        else:
            negative.append("arv_out_of_range")
    else:
        missing.append("arv")

    # REPAIR TOLERANCE (10pt)
    if deal.estimated_repairs:
        if deal.estimated_repairs <= buyer.rehab_max:
            score += 10
            positive.append("repairs_within_tolerance")
        else:
            negative.append("repairs_exceed_tolerance")
    else:
        missing.append("estimated_repairs")

    # STRATEGY FIT (5pt)
    if deal.deal_type and deal.deal_type in buyer.strategy:
        score += 5
        positive.append("strategy_fit")

    # CLOSE SPEED (5pt)
    if deal.closing_date:
        days_to_close = (deal.closing_date - date.today()).days
        if days_to_close <= buyer.closing_speed_days:
            score += 5
            positive.append("closing_speed_match")

    # YIELD/SPREAD (5pt)
    if deal.arv and deal.asking_price:
        spread = deal.arv - deal.asking_price
        if spread >= buyer.min_spread:
            score += 5
            positive.append("spread_meets_target")

    # RECENCY/ACTIVITY (5pt)
    if buyer.activity_score >= 70:
        score += 5
        positive.append("active_buyer")
    elif buyer.activity_score >= 40:
        score += 3

    return MatchResult(
        match_score=score,
        confidence=calculate_confidence(positive, negative, missing),
        positive_matches=positive,
        negative_matches=negative,
        missing_information=missing,
        recommended_action=get_recommended_action(score, positive, negative, missing)
    )
```

### Output
```python
@dataclass
class MatchResult:
    match_score: int           # 0-100
    confidence: float          # 0-1
    positive_matches: List[str]
    negative_matches: List[str]
    missing_information: List[str]
    recommended_action: str    # "SEND_DEAL" | "REQUEST更多信息" | "QUALIFY_BUYER" | "NO_MATCH"
    recommended_buyers: List[BuyerMatch]
```

### Confidence Calculation
```python
def calculate_confidence(positive, negative, missing):
    total_possible = 100
    if len(missing) > 3:
        return 0.3  # Too much missing data
    if len(negative) > len(positive):
        return 0.5
    return min(0.95, 0.5 + (len(positive) * 0.05))
```

---

## MATCHING MODES

### 1. Deal → Buyers (Find buyers for a deal)
- Input: Deal + Property
- Output: Top 10 buyers ranked by match_score
- Use: When new deal comes in, find who wants it

### 2. Buyer → Deals (Find deals for a buyer)
- Input: BuyerBuyBox
- Output: Matching deals ranked by match_score
- Use: When buyer is active, show them what's available

### 3. Demand Lookup (What does market X want?)
- Input: Market + PropertyType + PriceRange
- Output: Number of active buyers, demand signal
- Use: Guide acquisition targeting

---

## DEMAND SIGNALS

### Aggregation
```python
def get_demand_signal(market, property_type, price_min, price_max):
    buyers = get_active_buyers(market, property_type, price_min, price_max)
    recent_offers = get_recent_offers(market, property_type, price_min, price_max)
    recent_closes = get_recent_closes(market, property_type, price_min, price_max)

    if len(buyers) >= 5 and len(recent_offers) >= 2:
        return "HOT"
    elif len(buyers) >= 3 and len(recent_offers) >= 1:
        return "WARM"
    elif len(buyers) >= 1:
        return "NORMAL"
    elif len(buyers) > 0:
        return "WEAK"
    else:
        return "UNKNOWN"
```

### Output
```python
@dataclass
class DemandSignal:
    market: str
    property_type: str
    price_band: str
    signal: str           # HOT/WARM/NORMAL/WEAK/UNKNOWN
    active_buyers: int
    verified_buyers: int
    recent_offers: int
    recent_closes: int
    avg_days_to_close: float
    top_buyers: List[BuyerMatch]
```
