"""
MBM LeadEngine — Next-Best-Action Engine
==========================================
Every active lead gets exactly one recommended next action.
Priority-based, deadline-aware, revenue-optimized.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionType(str, Enum):
    CALL_NOW = "CALL_NOW"
    SEND_DEAL = "SEND_DEAL"
    QUALIFY = "QUALIFY"
    CAPTURE_BUY_BOX = "CAPTURE_BUY_BOX"
    REQUEST_PROPERTY_DETAILS = "REQUEST_PROPERTY_DETAILS"
    UNDERWRITE_NOW = "UNDERWRITE_NOW"
    MATCH_TO_BUYERS = "MATCH_TO_BUYERS"
    SEND_MATCHED_DEAL = "SEND_MATCHED_DEAL"
    FOLLOW_UP = "FOLLOW_UP"
    REACTIVATION = "REACTIVATION"
    SCHEDULE_CALL = "SCHEDULE_CALL"
    SEND_JV_INFO = "SEND_JV_INFO"
    NEGOTIATE = "NEGOTIATE"
    CLOSE = "CLOSE"
    PASS = "PASS"
    EXPAND_SEARCH = "EXPAND_SEARCH"


class ActionPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    DEFERRED = 5


@dataclass
class NextAction:
    """A recommended next action for a lead/deal."""
    entity_id: str
    entity_type: str           # seller, buyer, deal_source, deal, partner
    action: str
    priority: int              # 1-5 (1=CRITICAL)
    reason: str = ""
    deadline: str = ""         # ISO datetime
    owner: str = "system"
    scheduled_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NextBestActionEngine:
    """Deterministic next-best-action engine for all pipeline entities."""

    def __init__(self):
        self.actions: Dict[str, NextAction] = {}

    def compute_seller_action(self, seller: Dict[str, Any]) -> NextAction:
        """Compute next action for a seller lead."""
        entity_id = seller.get("id", seller.get("lead_id", ""))
        status = seller.get("status", "NEW")
        score = seller.get("motivation_score", seller.get("score", 0))
        last_contact = seller.get("last_contact_at")
        has_phone = bool(seller.get("phone"))
        has_offer = seller.get("has_offer", False)
        days_since_contact = self._days_since(last_contact)

        # Priority logic
        if status == "NEW" and score >= 70 and has_phone:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.CALL_NOW, priority=ActionPriority.CRITICAL,
                reason=f"High motivation score ({score}) with verified phone — call immediately",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            )

        if status == "NEW" and has_phone:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.CALL_NOW, priority=ActionPriority.HIGH,
                reason="New seller lead with phone — initiate contact",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            )

        if status == "CONTACTED" and days_since_contact and days_since_contact > 3:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.FOLLOW_UP, priority=ActionPriority.HIGH,
                reason=f"No response for {days_since_contact} days — follow up",
                deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            )

        if status == "QUALIFIED" and not has_offer:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.UNDERWRITE_NOW, priority=ActionPriority.HIGH,
                reason="Qualified seller but no offer made — underwrite and present offer",
                deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            )

        if status == "QUALIFIED" and has_offer:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.NEGOTIATE, priority=ActionPriority.MEDIUM,
                reason="Offer made — negotiate to contract",
                deadline=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            )

        if days_since_contact and days_since_contact > 14:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.REACTIVATION, priority=ActionPriority.MEDIUM,
                reason=f"Stale lead ({days_since_contact} days) — reactivation sequence",
                deadline=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            )

        if not has_phone:
            return NextAction(
                entity_id=entity_id, entity_type="seller",
                action=ActionType.QUALIFY, priority=ActionPriority.MEDIUM,
                reason="Missing phone — need skip trace or alternative contact",
            )

        return NextAction(
            entity_id=entity_id, entity_type="seller",
            action=ActionType.FOLLOW_UP, priority=ActionPriority.LOW,
            reason="Standard follow-up cadence",
            deadline=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        )

    def compute_buyer_action(self, buyer: Dict[str, Any]) -> NextAction:
        """Compute next action for a buyer."""
        entity_id = buyer.get("id", buyer.get("buyer_id", ""))
        has_buy_box = buyer.get("has_buy_box", False)
        completeness = buyer.get("buy_box_completeness", 0)
        activity = buyer.get("activity_score", 0)
        verified = buyer.get("verification_status") == "VERIFIED"
        last_active = buyer.get("last_active_at")
        matched_deals = buyer.get("matched_deals_count", 0)
        days_since_active = self._days_since(last_active)

        if not has_buy_box or completeness < 50:
            return NextAction(
                entity_id=entity_id, entity_type="buyer",
                action=ActionType.CAPTURE_BUY_BOX, priority=ActionPriority.HIGH,
                reason=f"Buy box incomplete ({completeness:.0f}%) — capture full criteria",
            )

        if not verified:
            return NextAction(
                entity_id=entity_id, entity_type="buyer",
                action=ActionType.QUALIFY, priority=ActionPriority.HIGH,
                reason="Buyer not verified — confirm identity and funding",
            )

        if matched_deals > 0:
            return NextAction(
                entity_id=entity_id, entity_type="buyer",
                action=ActionType.SEND_MATCHED_DEAL, priority=ActionPriority.HIGH,
                reason=f"{matched_deals} deals match buyer criteria — send now",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            )

        if days_since_active and days_since_active > 30:
            return NextAction(
                entity_id=entity_id, entity_type="buyer",
                action=ActionType.REACTIVATION, priority=ActionPriority.MEDIUM,
                reason=f"Inactive for {days_since_active} days — re-engagement",
            )

        return NextAction(
            entity_id=entity_id, entity_type="buyer",
            action=ActionType.SEND_MATCHED_DEAL, priority=ActionPriority.LOW,
            reason="Check for new matching deals",
        )

    def compute_deal_source_action(self, source: Dict[str, Any]) -> NextAction:
        """Compute next action for a deal source / wholesaler."""
        entity_id = source.get("id", source.get("source_id", ""))
        has_deal = source.get("has_submitted_deal", False)
        deal_status = source.get("deal_status", "")
        last_contact = source.get("last_contact_at")
        days_since = self._days_since(last_contact)

        if has_deal and deal_status in ("INTAKE", "VALIDATING", "UNDERWRITING"):
            return NextAction(
                entity_id=entity_id, entity_type="deal_source",
                action=ActionType.UNDERWRITE_NOW, priority=ActionPriority.HIGH,
                reason="Deal submitted — underwrite and score immediately",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            )

        if has_deal and deal_status == "SCORED":
            return NextAction(
                entity_id=entity_id, entity_type="deal_source",
                action=ActionType.MATCH_TO_BUYERS, priority=ActionPriority.HIGH,
                reason="Deal scored — find buyer matches now",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            )

        if not has_deal:
            return NextAction(
                entity_id=entity_id, entity_type="deal_source",
                action=ActionType.REQUEST_PROPERTY_DETAILS, priority=ActionPriority.MEDIUM,
                reason="Deal source engaged but no deal submitted — request property info",
            )

        if days_since and days_since > 7:
            return NextAction(
                entity_id=entity_id, entity_type="deal_source",
                action=ActionType.REACTIVATION, priority=ActionPriority.MEDIUM,
                reason=f"No activity for {days_since} days — follow up for new deals",
            )

        return NextAction(
            entity_id=entity_id, entity_type="deal_source",
            action=ActionType.FOLLOW_UP, priority=ActionPriority.LOW,
            reason="Maintain relationship for future deals",
        )

    def compute_deal_action(self, deal: Dict[str, Any]) -> NextAction:
        """Compute next action for a deal in the disposition pipeline."""
        entity_id = deal.get("id", "")
        status = deal.get("status", "INTAKE")
        deal_score = deal.get("deal_score", 0)
        buyer_matches = deal.get("buyer_matches_count", 0)
        outreach_sent = deal.get("outreach_sent_count", 0)
        responses = deal.get("response_count", 0)
        days_active = deal.get("days_active", 0)

        if status == "INTAKE":
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.UNDERWRITE_NOW, priority=ActionPriority.HIGH,
                reason="New deal intake — validate and score",
            )

        if status == "SCORED" and buyer_matches == 0:
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.EXPAND_SEARCH, priority=ActionPriority.HIGH,
                reason="Deal scored but no buyer matches — expand search criteria",
            )

        if status == "SCORED" and buyer_matches > 0:
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.SEND_DEAL, priority=ActionPriority.HIGH,
                reason=f"{buyer_matches} buyer matches found — send deal sheet now",
                deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            )

        if status == "BUYER_FOUND" and outreach_sent > 0 and responses == 0 and days_active > 3:
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.FOLLOW_UP, priority=ActionPriority.HIGH,
                reason=f"No responses after {outreach_sent} outreach — follow up",
            )

        if status == "OUTREACH_SENT" and responses > 0:
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.NEGOTIATE, priority=ActionPriority.HIGH,
                reason="Buyer responded — negotiate terms",
            )

        if days_active > 7 and status not in ("CLOSED", "LOST"):
            return NextAction(
                entity_id=entity_id, entity_type="deal",
                action=ActionType.EXPAND_SEARCH, priority=ActionPriority.MEDIUM,
                reason=f"Deal active for {days_active} days — expand buyer search or adjust price",
            )

        return NextAction(
            entity_id=entity_id, entity_type="deal",
            action=ActionType.FOLLOW_UP, priority=ActionPriority.LOW,
            reason="Standard deal pipeline cadence",
        )

    def compute_action(self, entity_type: str, entity: Dict[str, Any]) -> NextAction:
        """Universal action computation based on entity type."""
        if entity_type == "seller":
            return self.compute_seller_action(entity)
        elif entity_type == "buyer":
            return self.compute_buyer_action(entity)
        elif entity_type == "deal_source":
            return self.compute_deal_source_action(entity)
        elif entity_type == "deal":
            return self.compute_deal_action(entity)
        else:
            return NextAction(
                entity_id=entity.get("id", ""),
                entity_type=entity_type,
                action=ActionType.FOLLOW_UP,
                priority=ActionPriority.LOW,
                reason="Unknown entity type — standard follow-up",
            )

    def get_all_actions(self, entities: List[Dict[str, Any]], entity_type: str) -> List[NextAction]:
        """Compute actions for multiple entities, sorted by priority."""
        actions = []
        for entity in entities:
            action = self.compute_action(entity_type, entity)
            actions.append(action)
            self.actions[action.entity_id] = action
        return sorted(actions, key=lambda x: x.priority)

    def _days_since(self, date_str: Optional[str]) -> Optional[int]:
        """Calculate days since a date string."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - dt
            return delta.days
        except (ValueError, TypeError):
            return None
