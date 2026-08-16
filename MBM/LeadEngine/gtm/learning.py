"""
GTM LEARNING INTERFACE
=============================================================================
Consumes real-world sales outcomes to compute feedback weights for scoring.

Outcomes:
  WIN, LOSS, NO_RESPONSE, WRONG_PERSON, WRONG_NUMBER, OWNER_CONFIRMED,
  MEETING_BOOKED, MEETING_HELD, OBJECTION, OFFER_ACCEPTED
=================================================================================================================
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class OutcomeType(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    NO_RESPONSE = "NO_RESPONSE"
    WRONG_PERSON = "WRONG_PERSON"
    WRONG_NUMBER = "WRONG_NUMBER"
    OWNER_CONFIRMED = "OWNER_CONFIRMED"
    MEETING_BOOKED = "MEETING_BOOKED"
    MEETING_HELD = "MEETING_HELD"
    OBJECTION = "OBJECTION"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"


class GtmLearningEngine:
    """Consolidates feedback across campaigns to refine vertical and hook weights."""

    def __init__(self):
        self._outcomes: List[Dict[str, Any]] = []

    def record_outcome(
        self,
        entity_id: str,
        vertical: str,
        pain_point: str,
        assistant_sku: str,
        outcome: OutcomeType,
        channel: str = "PHONE",
        notes: str = "",
        revenue: float = 0.0,
    ) -> None:
        """Record a discrete sales or conversion outcome."""
        self._outcomes.append({
            "entity_id": entity_id,
            "vertical": vertical,
            "pain_point": pain_point,
            "assistant_sku": assistant_sku,
            "outcome": outcome.value,
            "channel": channel,
            "notes": notes,
            "revenue": float(revenue),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def feedback_for_scoring(self) -> Dict[str, Any]:
        """
        Compute feedback multipliers for the Buyer Hunter scoring engine.
        Does NOT alter active Buyer Hunter code; exposes clean calibration weights.
        """
        vertical_counts: Dict[str, Dict[str, int]] = {}
        sku_conversions: Dict[str, int] = {}
        total_won = 0
        total_wrong_person = 0

        for rec in self._outcomes:
            v = rec.get("vertical", "General")
            out = rec.get("outcome")
            sku = rec.get("assistant_sku", "GENERIC")

            if v not in vertical_counts:
                vertical_counts[v] = {"wins": 0, "meetings": 0, "failures": 0, "total": 0}
            vertical_counts[v]["total"] += 1

            if out in {OutcomeType.WIN.value, OutcomeType.OFFER_ACCEPTED.value}:
                vertical_counts[v]["wins"] += 1
                sku_conversions[sku] = sku_conversions.get(sku, 0) + 1
                total_won += 1
            elif out == OutcomeType.MEETING_BOOKED.value:
                vertical_counts[v]["meetings"] += 1
            elif out in {OutcomeType.WRONG_PERSON.value, OutcomeType.WRONG_NUMBER.value, OutcomeType.LOSS.value}:
                vertical_counts[v]["failures"] += 1
                if out == OutcomeType.WRONG_PERSON.value:
                    total_wrong_person += 1

        # Compute vertical multipliers
        vertical_multipliers = {}
        for vert, stats in vertical_counts.items():
            tot = stats["total"]
            if tot > 0:
                win_rate = (stats["wins"] + (0.5 * stats["meetings"])) / tot
                # Scale between 0.8 and 1.5
                vertical_multipliers[vert] = round(0.8 + (win_rate * 0.7), 2)
            else:
                vertical_multipliers[vert] = 1.0

        return {
            "total_outcomes_recorded": len(self._outcomes),
            "total_won": total_won,
            "total_wrong_person_flags": total_wrong_person,
            "top_converting_skus": sorted(sku_conversions.items(), key=lambda x: x[1], reverse=True),
            "vertical_multipliers": vertical_multipliers,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_outcomes(self) -> List[Dict[str, Any]]:
        return self._outcomes
