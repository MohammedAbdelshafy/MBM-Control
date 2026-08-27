"""
MBM LeadEngine — Deal Scoring Engine
=====================================
Consolidated deal scoring with MAO (70% Rule), margin analysis, and demand signals.
Replaces fragmented scoring across 5 separate engines with one deterministic scorer.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class DealQuality(str, Enum):
    A_PLUS = "A+"     # Excellent deal, high margin, strong demand
    A = "A"           # Good deal, solid margin, decent demand
    B_PLUS = "B+"     # Decent deal, acceptable margin
    B = "B"           # Marginal deal, needs negotiation
    C = "C"           # Weak deal, low margin or high risk
    D = "D"           # Poor deal, likely not viable
    INCOMPLETE = "INCOMPLETE"  # Missing critical data


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class DealScore:
    """Transparent deal scoring result."""
    deal_id: str
    overall_score: int = 0           # 0-100
    quality_grade: str = "INCOMPLETE"
    confidence: float = 0.0          # 0-1

    # Component scores (each 0-100)
    margin_score: int = 0
    arv_confidence: int = 0
    repair_confidence: int = 0
    market_liquidity: int = 0
    buyer_demand: int = 0
    price_competitiveness: int = 0
    closing_timeline: int = 0
    data_completeness: int = 0

    # Economics
    asking_price: Optional[float] = None
    arv: Optional[float] = None
    estimated_repairs: Optional[float] = None
    mao: Optional[float] = None      # Max Allowable Offer = (ARV * 0.70) - Repairs
    margin: Optional[float] = None   # ARV - Asking - Repairs
    margin_pct: Optional[float] = None
    spread: Optional[float] = None   # ARV - Asking

    # Analysis
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    recommended_action: str = ""
    demand_signal: str = "UNKNOWN"

    # Scoring weights (configurable)
    weights: Dict[str, int] = field(default_factory=lambda: {
        "margin": 20,
        "arv_confidence": 15,
        "repair_confidence": 10,
        "market_liquidity": 15,
        "buyer_demand": 15,
        "price_competitiveness": 10,
        "closing_timeline": 5,
        "data_completeness": 10,
    })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DealScoringEngine:
    """Deterministic deal scoring engine using MAO (70% Rule) and configurable weights."""

    def __init__(self, weights: Optional[Dict[str, int]] = None):
        self.weights = weights or {
            "margin": 20,
            "arv_confidence": 15,
            "repair_confidence": 10,
            "market_liquidity": 15,
            "buyer_demand": 15,
            "price_competitiveness": 10,
            "closing_timeline": 5,
            "data_completeness": 10,
        }

    def score_deal(self, deal: Dict[str, Any], demand_signal: str = "UNKNOWN", active_buyers: int = 0) -> DealScore:
        """
        Score a deal using deterministic MAO calculation and configurable weights.

        Args:
            deal: Dictionary with deal data (address, asking_price, arv, estimated_repairs, etc.)
            demand_signal: HOT/WARM/NORMAL/WEAK/UNKNOWN from buyer demand engine
            active_buyers: Number of active buyers in this segment

        Returns:
            DealScore with full breakdown
        """
        deal_id = deal.get("id", deal.get("address", "unknown"))
        asking_price = deal.get("asking_price") or deal.get("contract_price") or 0
        arv = deal.get("arv") or 0
        estimated_repairs = deal.get("estimated_repairs") or 0

        result = DealScore(
            deal_id=deal_id,
            asking_price=asking_price,
            arv=arv,
            estimated_repairs=estimated_repairs,
            demand_signal=demand_signal,
        )

        # Calculate MAO: (ARV * 0.70) - Estimated Repairs
        if arv > 0:
            result.mao = (arv * 0.70) - estimated_repairs

        # Calculate margin: ARV - Asking - Repairs
        if arv > 0 and asking_price > 0:
            result.margin = arv - asking_price - estimated_repairs
            result.spread = arv - asking_price
            if arv > 0:
                result.margin_pct = (result.margin / arv) * 100

        # 1. MARGIN SCORE (0-100)
        result.margin_score = self._score_margin(asking_price, arv, estimated_repairs, result.mao, result.margin)

        # 2. ARV CONFIDENCE (0-100)
        result.arv_confidence = self._score_arv_confidence(deal)

        # 3. REPAIR CONFIDENCE (0-100)
        result.repair_confidence = self._score_repair_confidence(deal)

        # 4. MARKET LIQUIDITY (0-100)
        result.market_liquidity = self._score_market_liquidity(deal, active_buyers)

        # 5. BUYER DEMAND (0-100)
        result.buyer_demand = self._score_buyer_demand(demand_signal, active_buyers)

        # 6. PRICE COMPETITIVENESS (0-100)
        result.price_competitiveness = self._score_price_competitiveness(asking_price, arv)

        # 7. CLOSING TIMELINE (0-100)
        result.closing_timeline = self._score_closing_timeline(deal)

        # 8. DATA COMPLETENESS (0-100)
        result.data_completeness = self._score_data_completeness(deal, result)

        # Calculate weighted overall score
        total_weight = sum(self.weights.values())
        weighted_sum = (
            result.margin_score * self.weights["margin"]
            + result.arv_confidence * self.weights["arv_confidence"]
            + result.repair_confidence * self.weights["repair_confidence"]
            + result.market_liquidity * self.weights["market_liquidity"]
            + result.buyer_demand * self.weights["buyer_demand"]
            + result.price_competitiveness * self.weights["price_competitiveness"]
            + result.closing_timeline * self.weights["closing_timeline"]
            + result.data_completeness * self.weights["data_completeness"]
        )
        result.overall_score = round(weighted_sum / total_weight)

        # Assign quality grade
        result.quality_grade = self._assign_grade(result.overall_score, result.data_completeness)

        # Calculate confidence
        result.confidence = self._calculate_confidence(result)

        # Generate reasons and risks
        result.reasons = self._generate_reasons(result)
        result.risks = self._generate_risks(result)
        result.missing_data = self._identify_missing_data(deal, result)

        # Recommend action
        result.recommended_action = self._recommend_action(result)

        return result

    def _score_margin(self, asking_price: float, arv: float, repairs: float, mao: float, margin: Optional[float]) -> int:
        """Score based on margin over MAO."""
        if not asking_price or not arv:
            return 0
        if margin is None:
            return 0

        # Margin as percentage of ARV
        margin_pct = (margin / arv) * 100 if arv > 0 else 0

        if margin_pct >= 30:
            return 100  # Excellent margin
        elif margin_pct >= 25:
            return 90
        elif margin_pct >= 20:
            return 80
        elif margin_pct >= 15:
            return 70
        elif margin_pct >= 10:
            return 50
        elif margin_pct >= 5:
            return 30
        elif margin > 0:
            return 15
        else:
            return 0  # No margin or negative

    def _score_arv_confidence(self, deal: Dict[str, Any]) -> int:
        """Score confidence in ARV estimate."""
        arv_source = deal.get("arv_source", "")
        arv = deal.get("arv") or 0

        if not arv:
            return 0

        # Higher confidence for better sources
        source_scores = {
            "COMPS_VERIFIED": 95,
            "COMPS_ESTIMATED": 80,
            "ZILLOW_ZESTIMATE": 60,
            "USER_PROVIDED": 50,
            "AUTOMATED_AVM": 55,
            "ML_ESTIMATE": 45,
            "UNKNOWN": 30,
        }
        return source_scores.get(arv_source.upper().replace(" ", "_"), 30)

    def _score_repair_confidence(self, deal: Dict[str, Any]) -> int:
        """Score confidence in repair estimate."""
        repair_source = deal.get("repair_source", "")
        repairs = deal.get("estimated_repairs") or 0

        if not repairs:
            return 20  # No estimate is low confidence

        source_scores = {
            "INSPECTION": 95,
            "CONTRACTOR_BID": 90,
            "EXPERIENCED_ESTIMATE": 75,
            "USER_PROVIDED": 50,
            "AUTOMATED_ESTIMATE": 40,
            "UNKNOWN": 25,
        }
        return source_scores.get(repair_source.upper().replace(" ", "_"), 35)

    def _score_market_liquidity(self, deal: Dict[str, Any], active_buyers: int) -> int:
        """Score based on how many active buyers exist in this segment."""
        if active_buyers >= 10:
            return 100
        elif active_buyers >= 7:
            return 85
        elif active_buyers >= 5:
            return 70
        elif active_buyers >= 3:
            return 50
        elif active_buyers >= 1:
            return 30
        else:
            return 10

    def _score_buyer_demand(self, demand_signal: str, active_buyers: int) -> int:
        """Score based on demand signal."""
        signal_scores = {
            "HOT": 100,
            "WARM": 70,
            "NORMAL": 45,
            "WEAK": 20,
            "UNKNOWN": 15,
        }
        return signal_scores.get(demand_signal, 15)

    def _score_price_competitiveness(self, asking_price: float, arv: float) -> int:
        """Score how competitive the asking price is vs ARV."""
        if not asking_price or not arv:
            return 0

        price_to_arv = asking_price / arv

        if price_to_arv <= 0.50:
            return 100  # Below 50% of ARV
        elif price_to_arv <= 0.55:
            return 90
        elif price_to_arv <= 0.60:
            return 80
        elif price_to_arv <= 0.65:
            return 70
        elif price_to_arv <= 0.70:
            return 60
        elif price_to_arv <= 0.75:
            return 40
        elif price_to_arv <= 0.80:
            return 20
        else:
            return 5

    def _score_closing_timeline(self, deal: Dict[str, Any]) -> int:
        """Score based on closing timeline."""
        closing_date = deal.get("closing_date")
        if not closing_date:
            return 50  # Unknown, neutral score

        try:
            from datetime import date as date_type
            if isinstance(closing_date, str):
                close_dt = date_type.fromisoformat(closing_date)
            else:
                close_dt = closing_date
            days = (close_dt - date_type.today()).days

            if days <= 7:
                return 100
            elif days <= 14:
                return 85
            elif days <= 21:
                return 70
            elif days <= 30:
                return 55
            elif days <= 45:
                return 40
            else:
                return 20
        except (ValueError, TypeError):
            return 30

    def _score_data_completeness(self, deal: Dict[str, Any], result: DealScore) -> int:
        """Score how complete the deal data is."""
        required_fields = ["asking_price", "arv", "estimated_repairs", "property_type", "address"]
        optional_fields = ["closing_date", "occupancy", "photos", "listing_url", "contract_status"]

        required_present = sum(1 for f in required_fields if deal.get(f))
        optional_present = sum(1 for f in optional_fields if deal.get(f))

        required_score = (required_present / len(required_fields)) * 70
        optional_score = (optional_present / len(optional_fields)) * 30

        return round(required_score + optional_score)

    def _assign_grade(self, score: int, completeness: int) -> str:
        """Assign quality grade based on overall score and data completeness."""
        if completeness < 40:
            return "INCOMPLETE"
        elif score >= 85:
            return "A+"
        elif score >= 75:
            return "A"
        elif score >= 65:
            return "B+"
        elif score >= 55:
            return "B"
        elif score >= 40:
            return "C"
        else:
            return "D"

    def _calculate_confidence(self, result: DealScore) -> float:
        """Calculate overall confidence in the score."""
        if result.data_completeness < 30:
            return 0.2
        elif result.data_completeness < 50:
            return 0.4
        elif result.arv_confidence < 50 or result.repair_confidence < 40:
            return 0.5
        elif result.data_completeness >= 80:
            return 0.85
        else:
            return 0.65

    def _generate_reasons(self, result: DealScore) -> List[str]:
        """Generate positive reasons for the score."""
        reasons = []
        if result.margin_score >= 70:
            reasons.append(f"Strong margin: ${result.margin:,.0f} ({result.margin_pct:.1f}% of ARV)" if result.margin else "Strong margin potential")
        if result.buyer_demand >= 70:
            reasons.append(f"High buyer demand: {result.demand_signal}")
        if result.price_competitiveness >= 70:
            reasons.append("Competitive asking price")
        if result.arv_confidence >= 70:
            reasons.append("Reliable ARV estimate")
        if result.data_completeness >= 80:
            reasons.append("Complete deal data")
        return reasons

    def _generate_risks(self, result: DealScore) -> List[str]:
        """Generate risk factors."""
        risks = []
        if result.margin and result.margin < 0:
            risks.append("Negative margin — deal may not be viable")
        if result.arv_confidence < 50:
            risks.append("Low ARV confidence — estimate may be unreliable")
        if result.repair_confidence < 40:
            risks.append("Low repair confidence — costs may be underestimated")
        if result.data_completeness < 50:
            risks.append("Incomplete data — additional information needed")
        if result.demand_signal in ("WEAK", "UNKNOWN"):
            risks.append("Weak buyer demand — may be difficult to dispose")
        return risks

    def _identify_missing_data(self, deal: Dict[str, Any], result: DealScore) -> List[str]:
        """Identify missing fields needed for accurate scoring."""
        missing = []
        critical_fields = {
            "asking_price": "Asking/contract price",
            "arv": "After Repair Value (ARV)",
            "estimated_repairs": "Repair estimate",
            "property_type": "Property type",
            "address": "Property address",
            "city": "City",
            "state": "State",
            "zip_code": "Zip code",
        }
        for field_key, label in critical_fields.items():
            if not deal.get(field_key):
                missing.append(label)
        return missing

    def _recommend_action(self, result: DealScore) -> str:
        """Recommend next action based on score."""
        if result.quality_grade == "INCOMPLETE":
            return "COLLECT_MISSING_DATA"
        elif result.quality_grade in ("A+", "A"):
            return "MATCH_TO_BUYERS_NOW"
        elif result.quality_grade in ("B+", "B"):
            return "MATCH_TO_BUYERS_REQUEST更多信息"
        elif result.quality_grade == "C":
            return "NEGOTIATE_PRICE_OR_WALK"
        else:
            return "PASS_ON_DEAL"
