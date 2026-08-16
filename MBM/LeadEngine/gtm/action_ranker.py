"""
GTM ACTION RANKER
=============================================================================
Deterministic Next-Best-Action ranking engine for GTM opportunities.

Formula:
  rank_score = expected_revenue * probability_of_progress * urgency * confidence
  - penalties for staleness, suppression, duplicate touches, missing evidence.
=============================================================================
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class ActionType(str, Enum):
    CALL_DISCOVERY = "CALL_DISCOVERY"
    SEND_COLD_EMAIL = "SEND_COLD_EMAIL"
    SEND_SMS = "SEND_SMS"
    SEND_LINKEDIN_DM = "SEND_LINKEDIN_DM"
    SEND_PROPOSAL = "SEND_PROPOSAL"
    BOOK_MEETING = "BOOK_MEETING"
    EXECUTE_TAKE_OFF_AUDIT = "EXECUTE_TAKE_OFF_AUDIT"
    SUPPRESS_LEAD = "SUPPRESS_LEAD"
    NURTURE = "NURTURE"


class ChannelType(str, Enum):
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    SMS = "SMS"
    LINKEDIN = "LINKEDIN"
    DIRECT_CHECKOUT = "DIRECT_CHECKOUT"
    NONE = "NONE"


class NextBestAction:
    """Represents a deterministic recommended next action for a GTM opportunity."""

    def __init__(
        self,
        entity_id: str,
        company: str,
        buyer: str,
        reason: str,
        pain: str,
        ai_fit: str,
        priority: float,
        recommended_channel: ChannelType,
        action_type: ActionType,
        confidence: float,
        expected_revenue: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.entity_id = entity_id
        self.company = company
        self.buyer = buyer
        self.reason = reason
        self.pain = pain
        self.ai_fit = ai_fit
        self.priority = round(float(priority), 2)
        self.recommended_channel = recommended_channel
        self.action_type = action_type
        self.confidence = round(float(confidence), 2)
        self.expected_revenue = float(expected_revenue)
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "company": self.company,
            "buyer": self.buyer,
            "reason": self.reason,
            "pain": self.pain,
            "ai_fit": self.ai_fit,
            "priority": self.priority,
            "recommended_channel": self.recommended_channel.value,
            "action_type": self.action_type.value,
            "confidence": self.confidence,
            "expected_revenue": self.expected_revenue,
            "metadata": self.metadata,
        }

    def format_dry_run(self, index: int = 1) -> str:
        """Format action in strict human-readable dry-run output format."""
        return (
            f"{index}.\n"
            f"company: {self.company}\n"
            f"buyer: {self.buyer}\n"
            f"reason: {self.reason}\n"
            f"pain: {self.pain}\n"
            f"AI fit: {self.ai_fit}\n"
            f"priority: {self.priority}\n"
            f"recommended channel: {self.recommended_channel.value}\n"
            f"confidence: {self.confidence}\n"
        )


class ActionRanker:
    """Deterministic ranking engine applying mathematical scoring and penalty gates."""

    @staticmethod
    def calculate_priority_score(opportunity: Dict[str, Any]) -> float:
        """
        Calculate rank_score = (expected_revenue / 1000) * prob_progress * urgency * confidence
        minus penalties.
        """
        # If suppressed, priority is hard zero
        if opportunity.get("is_suppressed") or opportunity.get("state") == "SUPPRESSED":
            return 0.0

        # Base components
        expected_revenue = float(opportunity.get("expected_revenue", 2000.0))
        rev_factor = max(1.0, min(10.0, expected_revenue / 1000.0))  # Scale $1k-$10k to 1.0-10.0

        intent_score = float(opportunity.get("intent_score", 50.0)) / 100.0  # 0.0 - 1.0
        prob_progress = float(opportunity.get("probability_of_progress", intent_score or 0.6))
        urgency = float(opportunity.get("urgency", 0.8))
        confidence = float(opportunity.get("confidence", 0.85))

        # Base score (0 to 100 scale)
        base_score = rev_factor * prob_progress * urgency * confidence * 15.0

        # Penalties
        penalties = 0.0

        # Staleness penalty (>14 days old = 20% penalty, >30 days = 50% penalty)
        age_days = float(opportunity.get("signal_age_days", 2.0))
        if age_days > 30:
            penalties += base_score * 0.50
        elif age_days > 14:
            penalties += base_score * 0.20

        # Low confidence penalty (<0.70 confidence = 30% penalty)
        if confidence < 0.70:
            penalties += base_score * 0.30

        # Recent unsuccessful contact penalty
        attempts = int(opportunity.get("recent_attempts", 0))
        if attempts >= 3:
            penalties += base_score * 0.40
        elif attempts >= 1:
            penalties += base_score * 0.15

        # Missing direct phone penalty
        if not opportunity.get("phone"):
            penalties += base_score * 0.35

        final_score = max(0.0, base_score - penalties)
        return round(final_score, 2)

    def rank_opportunities(self, opportunities: List[Dict[str, Any]], limit: int = 10) -> List[NextBestAction]:
        """Rank a batch of opportunities and produce NextBestAction objects."""
        ranked_actions = []

        for opp in opportunities:
            priority = self.calculate_priority_score(opp)
            if priority <= 0.0 and opp.get("is_suppressed"):
                continue

            entity_id = opp.get("id") or opp.get("entity_id") or opp.get("company", "UNKNOWN")
            company = opp.get("company", "Target Enterprise")
            buyer = opp.get("decision_maker") or opp.get("role") or "Authorized Executive"
            pain = opp.get("pain_point") or opp.get("pain_description") or "Manual operations bottleneck"
            ai_fit = opp.get("recommended_assistant_sku") or opp.get("recommended_ai_assistant") or "AI Automation Retainer"
            reason = opp.get("why_this_company") or opp.get("reason") or f"High pain and verified executive authority at {company}."
            confidence = float(opp.get("confidence", 0.85))
            expected_rev = float(opp.get("expected_revenue", 2000.0))

            # Channel determination
            if opp.get("phone"):
                rec_channel = ChannelType.PHONE
                act_type = ActionType.CALL_DISCOVERY
            elif opp.get("email"):
                rec_channel = ChannelType.EMAIL
                act_type = ActionType.SEND_COLD_EMAIL
            else:
                rec_channel = ChannelType.LINKEDIN
                act_type = ActionType.SEND_LINKEDIN_DM

            action = NextBestAction(
                entity_id=entity_id,
                company=company,
                buyer=buyer,
                reason=reason,
                pain=pain,
                ai_fit=ai_fit,
                priority=priority,
                recommended_channel=rec_channel,
                action_type=act_type,
                confidence=confidence,
                expected_revenue=expected_rev,
                metadata=opp,
            )
            ranked_actions.append(action)

        # Sort descending by priority
        ranked_actions.sort(key=lambda x: x.priority, reverse=True)
        return ranked_actions[:limit]
