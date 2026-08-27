"""
MBM LeadEngine — Buyer Buy Box Engine
======================================
Structured buyer profiles with deterministic matching.
Extends existing CanonicalBuyer with full buy box criteria.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]


class PropertyType(str, Enum):
    SFR = "SFR"
    DUPLEX = "DUPLEX"
    TRIPLEX = "TRIPLEX"
    QUAD = "QUAD"
    MULTI_FAMILY = "MULTI_FAMILY"
    TOWNHOUSE = "TOWNHOUSE"
    CONDO = "CONDO"
    LAND = "LAND"
    COMMERCIAL = "COMMERCIAL"
    MIXED_USE = "MIXED_USE"


class InvestmentStrategy(str, Enum):
    FIX_AND_FLIP = "FIX_AND_FLIP"
    BRRRR = "BRRRR"
    BUY_AND_HOLD = "BUY_AND_HOLD"
    WHOLESALING = "WHOLESALING"
    WHOLETAIL = "WHOLETAIL"
    SUBJECT_TO = "SUBJECT_TO"
    SELLER_FINANCE = "SELLER_FINANCE"
    LAND_FLIP = "LAND_FLIP"


class FundingType(str, Enum):
    CASH = "CASH"
    HARD_MONEY = "HARD_MONEY"
    CONVENTIONAL = "CONVENTIONAL"
    DSCR = "DSCR"
    SELLER_FINANCE = "SELLER_FINANCE"
    PRIVATE_MONEY = "PRIVATE_MONEY"


class RepairTolerance(str, Enum):
    TURNKEY = "TURNKEY"
    LIGHT = "LIGHT"
    MEDIUM = "MEDIUM"
    HEAVY = "HEAVY"
    ANY = "ANY"


class CloseSpeed(str, Enum):
    SEVEN_DAYS = "7_DAYS"
    FOURTEEN_DAYS = "14_DAYS"
    THIRTY_DAYS = "30_DAYS"
    FLEXIBLE = "FLEXIBLE"


class DemandSignal(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    NORMAL = "NORMAL"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


@dataclass
class BuyerBuyBox:
    """Structured buyer buy box criteria."""
    buyer_id: str
    buyer_name: str
    company: str = ""

    # Location
    markets: List[str] = field(default_factory=list)
    zip_codes: List[str] = field(default_factory=list)
    radius_miles: float = 25.0

    # Property Requirements
    property_types: List[str] = field(default_factory=lambda: ["SFR"])
    min_beds: int = 0
    max_beds: int = 0
    min_baths: float = 0.0
    min_sqft: int = 0
    max_sqft: int = 0
    min_lot_acres: float = 0.0
    max_lot_acres: float = 0.0

    # Financial Parameters
    price_min: float = 0.0
    price_max: float = 0.0
    arv_min: float = 0.0
    arv_max: float = 0.0
    rehab_min: float = 0.0
    rehab_max: float = 0.0
    min_spread: float = 0.0
    min_cash_on_cash: float = 0.0
    min_yield: float = 0.0

    # Strategy
    strategy: List[str] = field(default_factory=lambda: ["FIX_AND_FLIP"])
    cash_or_finance: List[str] = field(default_factory=lambda: ["CASH"])
    closing_speed_days: int = 14
    occupancy_preference: str = "ANY"  # ANY | VACANT | OWNER_OCCUPIED

    # Deal Types
    preferred_deal_types: List[str] = field(default_factory=lambda: ["WHOLESALE"])
    avoid_list: List[str] = field(default_factory=list)

    # Activity & Reliability
    last_verified: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "manual"
    reliability_score: float = 50.0  # 0-100
    activity_score: float = 50.0    # 0-100
    verification_status: str = "UNVERIFIED"  # VERIFIED | PROBABLE | UNVERIFIED
    total_closes: int = 0
    avg_days_to_close: float = 0.0
    last_offer_date: Optional[str] = None
    last_close_date: Optional[str] = None

    # Contact
    phone: str = ""
    email: str = ""
    whatsapp: str = ""
    instagram: str = ""
    facebook: str = ""

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_active(self) -> bool:
        """Check if buyer is considered active (verified or recent activity)."""
        if self.verification_status == "VERIFIED":
            return True
        if self.activity_score >= 50:
            return True
        return False

    def completeness_score(self) -> float:
        """Calculate how complete the buy box is (0-100)."""
        fields = [
            bool(self.markets), bool(self.property_types),
            self.price_min > 0, self.price_max > 0,
            self.arv_min > 0, self.arv_max > 0,
            bool(self.strategy), bool(self.cash_or_finance),
            self.closing_speed_days > 0,
        ]
        return (sum(fields) / len(fields)) * 100


@dataclass
class MatchResult:
    """Result of matching a deal/property to a buyer."""
    buyer_id: str
    property_id: str
    match_score: int = 0        # 0-100
    confidence: float = 0.0     # 0-1
    positive_matches: List[str] = field(default_factory=list)
    negative_matches: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    recommended_action: str = ""
    recommended_buyers: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DemandSegment:
    """Aggregated demand signal for a market segment."""
    market: str
    property_type: str
    price_band: str
    signal: str = "UNKNOWN"
    active_buyers: int = 0
    verified_buyers: int = 0
    recent_offers: int = 0
    recent_closes: int = 0
    avg_days_to_close: float = 0.0
    avg_spread: float = 0.0
    top_buyers: List[Dict[str, Any]] = field(default_factory=list)
    trend: str = "STABLE"  # IMPROVING | STABLE | DECLINING

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BuyerBuyBoxEngine:
    """Engine for managing buyer buy boxes and matching."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (ROOT_DIR / "MBM" / "LeadEngine" / "buyer_buy_boxes.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.buyers: Dict[str, BuyerBuyBox] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for item in data:
                    buyer = BuyerBuyBox(**item)
                    self.buyers[buyer.buyer_id] = buyer
            except Exception as e:
                print(f"[WARN] Error loading buyer buy boxes: {e}")

    def save(self) -> None:
        data = [b.to_dict() for b in self.buyers.values()]
        self.storage_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def register_buyer(self, buyer: BuyerBuyBox) -> BuyerBuyBox:
        """Register or update a buyer buy box."""
        buyer.updated_at = datetime.now(timezone.utc).isoformat()
        self.buyers[buyer.buyer_id] = buyer
        self.save()
        return buyer

    def get_buyer(self, buyer_id: str) -> Optional[BuyerBuyBox]:
        return self.buyers.get(buyer_id)

    def get_active_buyers(self) -> List[BuyerBuyBox]:
        """Return all active buyers sorted by activity score."""
        active = [b for b in self.buyers.values() if b.is_active()]
        return sorted(active, key=lambda x: -x.activity_score)

    def get_buyers_for_segment(self, market: str, property_type: str, price_min: float, price_max: float) -> List[BuyerBuyBox]:
        """Find buyers whose buy box matches a segment."""
        matches = []
        for buyer in self.buyers.values():
            if not buyer.is_active():
                continue
            # Market match
            if buyer.markets and market.lower() not in [m.lower() for m in buyer.markets]:
                continue
            # Property type match
            if buyer.property_types and property_type.upper() not in buyer.property_types:
                continue
            # Price range overlap
            if buyer.price_max > 0 and price_min > buyer.price_max:
                continue
            if buyer.price_min > 0 and price_max < buyer.price_min:
                continue
            matches.append(buyer)
        return sorted(matches, key=lambda x: -x.activity_score)

    def match_deal_to_buyers(self, deal: Dict[str, Any], top_n: int = 10) -> List[MatchResult]:
        """Match a deal against all active buyers. Returns top N matches."""
        results = []
        for buyer in self.buyers.values():
            if not buyer.is_active():
                continue
            result = self._score_deal_against_buyer(deal, buyer)
            if result.match_score >= 30:  # Minimum threshold
                results.append(result)
        results.sort(key=lambda x: -x.match_score)
        return results[:top_n]

    def _score_deal_against_buyer(self, deal: Dict[str, Any], buyer: BuyerBuyBox) -> MatchResult:
        """Score a deal against a single buyer's buy box (100pt scale)."""
        score = 0
        positive = []
        negative = []
        missing = []

        # MARKET MATCH (20pt)
        deal_market = deal.get("city", "").lower()
        if buyer.markets:
            if deal_market in [m.lower() for m in buyer.markets]:
                score += 20
                positive.append("market_match")
            elif deal.get("zip_code", "").lower() in [z.lower() for z in buyer.zip_codes]:
                score += 15
                positive.append("zip_match")
            else:
                negative.append("no_market_match")
        else:
            score += 10  # Open market, partial credit
            positive.append("market_open")

        # PROPERTY TYPE (10pt)
        deal_type = deal.get("property_type", "SFR").upper()
        if buyer.property_types:
            if deal_type in buyer.property_types:
                score += 10
                positive.append("property_type_match")
            else:
                negative.append("property_type_mismatch")
        else:
            score += 5
            positive.append("property_type_open")

        # PRICE RANGE (15pt)
        asking_price = deal.get("asking_price", 0) or 0
        if asking_price > 0:
            if buyer.price_min <= asking_price <= buyer.price_max:
                score += 15
                positive.append("price_in_range")
            elif asking_price < buyer.price_min:
                score += 8
                positive.append("price_below_budget")
            else:
                negative.append("price_above_budget")
        else:
            missing.append("asking_price")

        # ARV RANGE (10pt)
        arv = deal.get("arv", 0) or 0
        if arv > 0:
            if buyer.arv_min <= arv <= buyer.arv_max:
                score += 10
                positive.append("arv_in_range")
            elif buyer.arv_min == 0 and buyer.arv_max == 0:
                score += 5
                positive.append("arv_open")
            else:
                negative.append("arv_out_of_range")
        else:
            missing.append("arv")

        # REPAIR TOLERANCE (10pt)
        repairs = deal.get("estimated_repairs", 0) or 0
        if repairs > 0:
            if buyer.rehab_max > 0 and repairs <= buyer.rehab_max:
                score += 10
                positive.append("repairs_within_tolerance")
            elif buyer.rehab_max == 0:
                score += 5
                positive.append("rehab_open")
            else:
                negative.append("repairs_exceed_tolerance")
        else:
            missing.append("estimated_repairs")

        # STRATEGY FIT (5pt)
        deal_type_str = deal.get("deal_type", "").upper()
        if buyer.strategy and deal_type_str:
            if deal_type_str in [s.upper() for s in buyer.strategy]:
                score += 5
                positive.append("strategy_fit")
            else:
                negative.append("strategy_mismatch")
        else:
            score += 2
            positive.append("strategy_open")

        # CLOSE SPEED (5pt)
        closing_date = deal.get("closing_date")
        if closing_date:
            try:
                from datetime import date as date_type
                if isinstance(closing_date, str):
                    close_dt = date_type.fromisoformat(closing_date)
                else:
                    close_dt = closing_date
                days_to_close = (close_dt - date_type.today()).days
                if days_to_close <= buyer.closing_speed_days:
                    score += 5
                    positive.append("closing_speed_match")
                else:
                    negative.append("closing_speed_slow")
            except (ValueError, TypeError):
                missing.append("closing_date")

        # SPREAD/YIELD (5pt)
        if arv > 0 and asking_price > 0:
            spread = arv - asking_price
            if buyer.min_spread > 0 and spread >= buyer.min_spread:
                score += 5
                positive.append("spread_meets_target")
            elif buyer.min_spread == 0:
                score += 2
                positive.append("spread_open")

        # RECENCY/ACTIVITY (5pt)
        if buyer.activity_score >= 70:
            score += 5
            positive.append("active_buyer")
        elif buyer.activity_score >= 40:
            score += 3
            positive.append("moderately_active")

        # Calculate confidence
        if len(missing) > 3:
            confidence = 0.3
        elif len(negative) > len(positive):
            confidence = 0.5
        else:
            confidence = min(0.95, 0.5 + (len(positive) * 0.05))

        # Determine recommended action
        if score >= 70 and confidence >= 0.7:
            action = "SEND_DEAL_NOW"
        elif score >= 50 and confidence >= 0.5:
            action = "SEND_DEAL_REQUEST_MORE"
        elif score >= 30:
            action = "QUALIFY_BUYER_FIRST"
        else:
            action = "NO_MATCH"

        property_id = deal.get("id", deal.get("address", "unknown"))

        return MatchResult(
            buyer_id=buyer.buyer_id,
            property_id=property_id,
            match_score=min(100, score),
            confidence=confidence,
            positive_matches=positive,
            negative_matches=negative,
            missing_information=missing,
            recommended_action=action,
        )

    def calculate_demand(self, market: str, property_type: str, price_min: float, price_max: float) -> DemandSegment:
        """Calculate demand signal for a market segment."""
        buyers = self.get_buyers_for_segment(market, property_type, price_min, price_max)
        active_count = len([b for b in buyers if b.activity_score >= 50])
        verified_count = len([b for b in buyers if b.verification_status == "VERIFIED"])

        # Determine signal
        if active_count >= 5:
            signal = "HOT"
        elif active_count >= 3:
            signal = "WARM"
        elif active_count >= 1:
            signal = "NORMAL"
        elif verified_count >= 1:
            signal = "WEAK"
        else:
            signal = "UNKNOWN"

        # Price band label
        price_band = f"${price_min/1000:.0f}K-${price_max/1000:.0f}K" if price_min and price_max else "Any"

        # Top buyers
        top_buyers = [
            {"buyer_id": b.buyer_id, "name": b.buyer_name, "activity_score": b.activity_score}
            for b in buyers[:5]
        ]

        return DemandSegment(
            market=market,
            property_type=property_type,
            price_band=price_band,
            signal=signal,
            active_buyers=active_count,
            verified_buyers=verified_count,
            top_buyers=top_buyers,
        )
