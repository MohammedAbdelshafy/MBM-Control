"""
Human Approval Boundary — explicit, auditable, never implicit (§17).

Transitions:
  DRAFT/REVIEW_REQUIRED -> APPROVED requires actor + timestamp + reason + correlation_id.
No implicit approval from score/confidence/job success.
"""
from __future__ import annotations

from typing import Optional

from .opportunity_queue import transition_opportunity, get_opportunity
from .types import OpportunityStatus

def approve_opportunity(opportunity_id: str, *, actor: str, reason: str = "", correlation_id: str = "") -> dict:
    if not actor or not actor.strip():
        raise ValueError("actor is required for approval (audit boundary)")
    if not reason or len(reason.strip()) < 5:
        raise ValueError("reason is required for approval (min 5 chars)")
    rec = get_opportunity(opportunity_id)
    if not rec:
        raise KeyError(f"Opportunity not found: {opportunity_id}")
    # Must be in REVIEW_REQUIRED to approve (fail-closed)
    if rec.get("status") != OpportunityStatus.REVIEW_REQUIRED.value:
        raise ValueError(f"Can only APPROVE from REVIEW_REQUIRED, current={rec.get('status')}")
    return transition_opportunity(opportunity_id, OpportunityStatus.APPROVED, actor=actor, reason=reason, correlation_id=correlation_id)

def reject_opportunity(opportunity_id: str, *, actor: str, reason: str = "", correlation_id: str = "") -> dict:
    if not actor or not actor.strip():
        raise ValueError("actor is required")
    return transition_opportunity(opportunity_id, OpportunityStatus.REJECTED, actor=actor, reason=reason, correlation_id=correlation_id)

def consume_opportunity(opportunity_id: str, *, actor: str, reason: str = "", correlation_id: str = "") -> dict:
    """Mark APPROVED -> CONSUMED after downstream action (e.g., after human creates draft lead)."""
    if not actor or not actor.strip():
        raise ValueError("actor is required")
    rec = get_opportunity(opportunity_id)
    if not rec or rec.get("status") != OpportunityStatus.APPROVED.value:
        raise ValueError(f"Can only CONSUME from APPROVED, current={rec.get('status') if rec else 'not found'}")
    return transition_opportunity(opportunity_id, OpportunityStatus.CONSUMED, actor=actor, reason=reason, correlation_id=correlation_id)
