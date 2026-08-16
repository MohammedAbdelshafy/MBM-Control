"""
GTM ATTRIBUTION & REVENUE EVENT LAYER
=============================================================================
Multi-touch attribution tracker linking initial signals to Neteller revenue.

Revenue Lifecycle Stages:
  lead_discovered -> lead_qualified -> contact_attempted -> contact_connected ->
  identity_confirmed -> meeting_booked -> meeting_completed -> proposal_sent ->
  deal_won -> deal_lost -> revenue_received

Rules:
  - Proposal is NOT revenue.
  - Pipeline is NOT realized revenue.
  - Only 'revenue_received' with verified transaction id counts as realized revenue.
=============================================================================
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid


class RevenueStage(str, Enum):
    LEAD_DISCOVERED = "lead_discovered"
    LEAD_QUALIFIED = "lead_qualified"
    CONTACT_ATTEMPTED = "contact_attempted"
    CONTACT_CONNECTED = "contact_connected"
    IDENTITY_CONFIRMED = "identity_confirmed"
    MEETING_BOOKED = "meeting_booked"
    MEETING_COMPLETED = "meeting_completed"
    PROPOSAL_SENT = "proposal_sent"
    DEAL_WON = "deal_won"
    DEAL_LOST = "deal_lost"
    REVENUE_RECEIVED = "revenue_received"


class Touchpoint:
    """Represents an atomic interaction point in the buyer journey."""

    def __init__(
        self,
        entity_id: str,
        stage: RevenueStage,
        channel: str,
        agent: str,
        source: str,
        signal_id: Optional[str] = None,
        notes: str = "",
        monetary_value: float = 0.0,
        transaction_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        touch_id: Optional[str] = None,
    ):
        self.touch_id = touch_id or f"tch_{uuid.uuid4().hex[:10]}"
        self.entity_id = entity_id
        self.stage = stage
        self.channel = channel
        self.agent = agent
        self.source = source
        self.signal_id = signal_id or ""
        self.notes = notes
        self.monetary_value = float(monetary_value)
        self.transaction_id = transaction_id
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "touch_id": self.touch_id,
            "entity_id": self.entity_id,
            "stage": self.stage.value,
            "channel": self.channel,
            "agent": self.agent,
            "source": self.source,
            "signal_id": self.signal_id,
            "notes": self.notes,
            "monetary_value": self.monetary_value,
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp,
        }


class AttributionTracker:
    """Tracks multi-touch progression and computes realized vs pipeline revenue."""

    def __init__(self):
        self._touches: Dict[str, List[Touchpoint]] = {}

    def record_touchpoint(self, touch: Touchpoint) -> None:
        """Record a touchpoint in an entity's journey."""
        if touch.entity_id not in self._touches:
            self._touches[touch.entity_id] = []
        self._touches[touch.entity_id].append(touch)

    def get_journey(self, entity_id: str) -> List[Touchpoint]:
        """Retrieve full chronological touchpoint history for an entity."""
        return self._touches.get(entity_id, [])

    def calculate_attribution(self, entity_id: str) -> Dict[str, Any]:
        """
        Compute multi-touch attribution breakdown for an entity.
        Calculates first-touch, last-touch, pipeline value, and realized revenue.
        """
        journey = self.get_journey(entity_id)
        if not journey:
            return {
                "entity_id": entity_id,
                "first_touch": None,
                "last_touch": None,
                "total_touches": 0,
                "pipeline_value_usd": 0.0,
                "realized_revenue_usd": 0.0,
                "is_closed_won": False,
            }

        first_touch = journey[0]
        last_touch = journey[-1]

        pipeline_val = 0.0
        realized_rev = 0.0
        is_won = False

        for t in journey:
            if t.stage in {RevenueStage.PROPOSAL_SENT, RevenueStage.DEAL_WON}:
                pipeline_val = max(pipeline_val, t.monetary_value)
            if t.stage == RevenueStage.DEAL_WON:
                is_won = True
            if t.stage == RevenueStage.REVENUE_RECEIVED:
                realized_rev += t.monetary_value

        return {
            "entity_id": entity_id,
            "first_touch_source": first_touch.source,
            "first_touch_agent": first_touch.agent,
            "last_touch_agent": last_touch.agent,
            "last_stage": last_touch.stage.value,
            "total_touches": len(journey),
            "pipeline_value_usd": pipeline_val,
            "realized_revenue_usd": realized_rev,
            "is_closed_won": is_won,
        }

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {k: [t.to_dict() for t in v] for k, v in self._touches.items()}
