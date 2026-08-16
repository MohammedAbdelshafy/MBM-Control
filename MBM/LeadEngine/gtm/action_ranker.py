"""
GTM ACTION RANKER & CHANNEL ROUTER
=================================================================================================================
Deterministic Next-Best-Action ranking engine for GTM opportunities.

Formula:
  rank_score = expected_revenue * probability_of_progress * urgency * confidence
  - penalties for staleness, suppression, duplicate touches, missing evidence,
    recent failed contact, and unresolved identity.
=================================================================================================================
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
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ChannelType(str, Enum):
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    SMS = "SMS"
    LINKEDIN = "LINKEDIN"
    MEETING = "MEETING"
    FOLLOW_UP = "FOLLOW_UP"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    NURTURE = "NURTURE"
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
        why_now: str = "",
        evidence: Any = None,
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
        self.why_now = why_now or reason
        self.evidence = evidence
        self.metadata = metadata or {}

    def _evidence_summary(self) -> str:
        """Render evidence into a single human-readable line; never invents facts."""
        if isinstance(self.evidence, dict):
            claim = self.evidence.get("claim") or self.evidence.get("why_this_company") or ""
            source = self.evidence.get("source") or "UNKNOWN"
            ref = self.evidence.get("source_reference") or self.evidence.get("source_url") or "UNKNOWN"
            if claim:
                return f"{claim} [source: {source} | reference: {ref}]"
            return f"UNKNOWN [source: {source} | reference: {ref}]"
        if isinstance(self.evidence, str) and self.evidence.strip():
            return self.evidence.strip()
        return "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "company": self.company,
            "buyer": self.buyer,
            "reason": self.reason,
            "why_now": self.why_now,
            "pain": self.pain,
            "ai_fit": self.ai_fit,
            "priority": self.priority,
            "recommended_channel": self.recommended_channel.value,
            "action_type": self.action_type.value,
            "confidence": self.confidence,
            "expected_revenue": self.expected_revenue,
            "evidence": self._evidence_summary(),
            "metadata": self.metadata,
        }

    def format_dry_run(self, index: int = 1) -> str:
        """Format action in the strict human-readable dry-run output format."""
        return (
            f"{index}.\n"
            f"Company: {self.company}\n"
            f"Buyer: {self.buyer}\n"
            f"Action: {self.action_type.value}\n"
            f"Why now: {self.why_now}\n"
            f"Pain: {self.pain}\n"
            f"AI fit: {self.ai_fit}\n"
            f"Priority: {self.priority}\n"
            f"Confidence: {self.confidence}\n"
            f"Evidence: {self._evidence_summary()}\n"
        )


class ChannelRouter:
    """Decision layer that picks the smallest useful next action per opportunity.

    Rule: never multi-channel every prospect automatically. One primary channel
    at a time, chosen from the narrowest step that advances the deal state.
    """

    SUPPRESSIVE_IDENTITY = {
        "WRONG_PERSON",
        "WRONG_NUMBER",
        "TENANT",
        "DO_NOT_CALL",
        "QUARANTINED",
    }

    @classmethod
    def route(cls, opportunity: Dict[str, Any]) -> Any:
        """Return a (ChannelType, ActionType) tuple for the opportunity."""
        state = str(opportunity.get("state", "DISCOVERED"))
        identity_state = str(opportunity.get("identity_state", "")).upper()

        # Terminal / suppressed states never receive outreach.
        if opportunity.get("is_suppressed") or state == "SUPPRESSED":
            return ChannelType.NONE, ActionType.SUPPRESS_LEAD
        if state in {"WON", "LOST"}:
            return ChannelType.NONE, ActionType.NURTURE
        if identity_state in cls.SUPPRESSIVE_IDENTITY:
            return ChannelType.HUMAN_REVIEW, ActionType.SUPPRESS_LEAD

        # Identity-unconfirmed high-intent deals still move to qualification review.
        if state in {"DISCOVERED", "QUALIFYING"}:
            return ChannelType.HUMAN_REVIEW, ActionType.HUMAN_REVIEW
        if state == "QUALIFIED":
            if opportunity.get("phone"):
                return ChannelType.PHONE, ActionType.CALL_DISCOVERY
            if opportunity.get("email"):
                return ChannelType.EMAIL, ActionType.SEND_COLD_EMAIL
            return ChannelType.LINKEDIN, ActionType.SEND_LINKEDIN_DM
        if state in {"CONTACTING", "ENGAGED", "MEETING_PENDING"}:
            if opportunity.get("email"):
                return ChannelType.MEETING, ActionType.BOOK_MEETING
            return ChannelType.PHONE, ActionType.BOOK_MEETING
        if state in {"MEETING_BOOKED", "DISCOVERY_COMPLETE", "PROPOSAL", "NEGOTIATION"}:
            return ChannelType.EMAIL, ActionType.SEND_PROPOSAL
        if state == "NURTURE":
            return ChannelType.NURTURE, ActionType.NURTURE

        # Default: smallest useful follow-up action.
        if opportunity.get("phone"):
            return ChannelType.FOLLOW_UP, ActionType.CALL_DISCOVERY
        if opportunity.get("email"):
            return ChannelType.EMAIL, ActionType.SEND_COLD_EMAIL
        return ChannelType.HUMAN_REVIEW, ActionType.HUMAN_REVIEW


class ActionRanker:
    """Deterministic ranking engine applying mathematical scoring and penalty gates."""

    @staticmethod
    def calculate_priority_score(opportunity: Dict[str, Any]) -> float:
        """
        Calculate rank_score = (expected_revenue / 1000) * prob_progress * urgency * confidence
        minus penalties, with identity confirmation as a multiplier.
        """
        # If suppressed, priority is hard zero
        if opportunity.get("is_suppressed") or opportunity.get("state") == "SUPPRESSED":
            return 0.0

        # Suppressive identity states are hard zero (garbage is never recycled).
        identity_state = str(opportunity.get("identity_state", "")).upper()
        if identity_state in ChannelRouter.SUPPRESSIVE_IDENTITY:
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

        # Identity confirmation multiplier: live owner/ADM confirmation boosts priority.
        identity_multiplier = 1.0
        if identity_state in {"OWNER_CONFIRMED", "AUTHORIZED_DECISION_MAKER"}:
            identity_multiplier = 1.25
        elif identity_state == "OWNER_LIKELY":
            identity_multiplier = 1.10
        elif identity_state in {"IDENTITY_UNCONFIRMED", "DATABASE_OWNER_VERIFIED"}:
            identity_multiplier = 0.85
        base_score *= identity_multiplier

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

        # Duplicate action penalty (same action repeatedly queued)
        dup_touches = int(opportunity.get("duplicate_touch_count", 0))
        if dup_touches >= 3:
            penalties += base_score * 0.25
        elif dup_touches >= 1:
            penalties += base_score * 0.10

        # Missing direct phone penalty
        if not opportunity.get("phone"):
            penalties += base_score * 0.35

        # Missing evidence penalty (zero-fabrication gate)
        evidence = opportunity.get("evidence")
        if not evidence:
            penalties += base_score * 0.10

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
            why_now = opp.get("why_now") or ""
            evidence = opp.get("evidence")
            confidence = float(opp.get("confidence", 0.85))
            expected_rev = float(opp.get("expected_revenue", 2000.0))

            # Channel determination via the Channel Router decision layer
            rec_channel, act_type = ChannelRouter.route(opp)

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
                why_now=why_now,
                evidence=evidence,
                metadata=opp,
            )
            ranked_actions.append(action)

        # Sort descending by priority
        ranked_actions.sort(key=lambda x: x.priority, reverse=True)
        return ranked_actions[:limit]