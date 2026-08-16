"""
GTM STATE MACHINE
=============================================================================
Defines the 14-state Opportunity Lifecycle with strict transition validation.

States:
  DISCOVERED -> QUALIFYING -> QUALIFIED -> CONTACTING -> ENGAGED ->
  MEETING_PENDING -> MEETING_BOOKED -> DISCOVERY_COMPLETE -> PROPOSAL ->
  NEGOTIATION -> WON / LOST / NURTURE / SUPPRESSED
=============================================================================
"""

from enum import Enum
from typing import Dict, Set, List, Optional, Any
from datetime import datetime, timezone


class GtmState(str, Enum):
    DISCOVERED = "DISCOVERED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    CONTACTING = "CONTACTING"
    ENGAGED = "ENGAGED"
    MEETING_PENDING = "MEETING_PENDING"
    MEETING_BOOKED = "MEETING_BOOKED"
    DISCOVERY_COMPLETE = "DISCOVERY_COMPLETE"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"
    NURTURE = "NURTURE"
    SUPPRESSED = "SUPPRESSED"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal transition is attempted on a GTM opportunity."""
    pass


class GtmStateMachine:
    """Deterministic, validated state machine for GTM opportunity lifecycles."""

    # Valid transitions from each state
    ALLOWED_TRANSITIONS: Dict[GtmState, Set[GtmState]] = {
        GtmState.DISCOVERED: {
            GtmState.QUALIFYING,
            GtmState.QUALIFIED,
            GtmState.SUPPRESSED,
            GtmState.NURTURE,
        },
        GtmState.QUALIFYING: {
            GtmState.QUALIFIED,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.QUALIFIED: {
            GtmState.CONTACTING,
            GtmState.NURTURE,
            GtmState.SUPPRESSED,
            GtmState.LOST,
        },
        GtmState.CONTACTING: {
            GtmState.ENGAGED,
            GtmState.MEETING_PENDING,
            GtmState.MEETING_BOOKED,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.ENGAGED: {
            GtmState.MEETING_PENDING,
            GtmState.MEETING_BOOKED,
            GtmState.DISCOVERY_COMPLETE,
            GtmState.PROPOSAL,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.MEETING_PENDING: {
            GtmState.MEETING_BOOKED,
            GtmState.CONTACTING,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.MEETING_BOOKED: {
            GtmState.DISCOVERY_COMPLETE,
            GtmState.PROPOSAL,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.DISCOVERY_COMPLETE: {
            GtmState.PROPOSAL,
            GtmState.NEGOTIATION,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.PROPOSAL: {
            GtmState.NEGOTIATION,
            GtmState.WON,
            GtmState.NURTURE,
            GtmState.LOST,
            GtmState.SUPPRESSED,
        },
        GtmState.NEGOTIATION: {
            GtmState.WON,
            GtmState.LOST,
            GtmState.NURTURE,
            GtmState.SUPPRESSED,
        },
        GtmState.WON: set(),  # Terminal state
        GtmState.LOST: {
            GtmState.NURTURE,
            GtmState.QUALIFYING,  # Re-evaluation on fresh trigger
            GtmState.SUPPRESSED,
        },
        GtmState.NURTURE: {
            GtmState.QUALIFYING,
            GtmState.QUALIFIED,
            GtmState.CONTACTING,
            GtmState.SUPPRESSED,
        },
        GtmState.SUPPRESSED: set(),  # Terminal isolation unless explicit audit override
    }

    def __init__(self, current_state: GtmState = GtmState.DISCOVERED, entity_id: Optional[str] = None):
        self.entity_id = entity_id or "ANON_OPP"
        self._current_state = current_state
        self.history: List[Dict[str, Any]] = [
            {
                "from_state": None,
                "to_state": current_state.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "INITIALIZATION",
                "actor": "system",
            }
        ]

    @property
    def current_state(self) -> GtmState:
        return self._current_state

    def can_transition_to(self, target_state: GtmState) -> bool:
        """Check if transition from current state to target state is legally allowed."""
        if target_state == self._current_state:
            return True
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition(self, target_state: GtmState, reason: str = "", actor: str = "system", force: bool = False) -> GtmState:
        """
        Transition opportunity to target state with validation.
        Raises InvalidStateTransitionError if illegal and force is False.
        """
        if target_state == self._current_state:
            return self._current_state

        if not force and not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                f"Illegal GTM state transition for '{self.entity_id}': "
                f"Cannot move from '{self._current_state.value}' to '{target_state.value}'. "
                f"Allowed destinations: {[s.value for s in self.ALLOWED_TRANSITIONS.get(self._current_state, set())]}"
            )

        prev_state = self._current_state
        self._current_state = target_state
        self.history.append({
            "from_state": prev_state.value,
            "to_state": target_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason or f"State changed from {prev_state.value} to {target_state.value}",
            "actor": actor,
            "forced": force,
        })
        return self._current_state

    def is_terminal(self) -> bool:
        """Check if current state is terminal (WON or SUPPRESSED)."""
        return self._current_state in {GtmState.WON, GtmState.SUPPRESSED}

    def is_callable(self) -> bool:
        """Check if current state is in active outreach zone."""
        return self._current_state in {
            GtmState.QUALIFIED,
            GtmState.CONTACTING,
            GtmState.ENGAGED,
            GtmState.MEETING_PENDING,
            GtmState.PROPOSAL,
            GtmState.NEGOTIATION,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "current_state": self._current_state.value,
            "is_terminal": self.is_terminal(),
            "is_callable": self.is_callable(),
            "history_count": len(self.history),
            "history": self.history,
        }
