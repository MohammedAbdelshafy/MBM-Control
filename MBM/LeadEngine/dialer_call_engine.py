"""
Dialer Call Engine — Call Lifecycle State Machine
=================================================
Enforces deterministic call progression and terminal DNC/opt-out states.
Per AGENTS.md: Once a number is marked DO_NOT_CALL, WRONG_NUMBER, or BAD_NUMBER,
it can NEVER transition back to QUEUED or be recycled into the prime queue.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class CallState(str, Enum):
    QUEUED = "QUEUED"
    DIALING = "DIALING"
    RINGING = "RINGING"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    DO_NOT_CALL = "DO_NOT_CALL"
    WRONG_NUMBER = "WRONG_NUMBER"
    BAD_NUMBER = "BAD_NUMBER"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal transition is attempted in the call state machine."""
    pass


TERMINAL_STATES = {
    CallState.DO_NOT_CALL,
    CallState.WRONG_NUMBER,
    CallState.BAD_NUMBER,
    CallState.COMPLETED,
}


ALLOWED_TRANSITIONS: Dict[CallState, set[CallState]] = {
    CallState.QUEUED: {
        CallState.DIALING,
        CallState.DO_NOT_CALL,
        CallState.BAD_NUMBER,
        CallState.FAILED,
    },
    CallState.DIALING: {
        CallState.RINGING,
        CallState.CONNECTED,
        CallState.BUSY,
        CallState.NO_ANSWER,
        CallState.FAILED,
        CallState.DO_NOT_CALL,
        CallState.WRONG_NUMBER,
        CallState.BAD_NUMBER,
    },
    CallState.RINGING: {
        CallState.CONNECTED,
        CallState.BUSY,
        CallState.NO_ANSWER,
        CallState.FAILED,
        CallState.DO_NOT_CALL,
    },
    CallState.CONNECTED: {
        CallState.COMPLETED,
        CallState.DO_NOT_CALL,
        CallState.WRONG_NUMBER,
        CallState.FAILED,
    },
    CallState.BUSY: {
        CallState.QUEUED,
        CallState.DO_NOT_CALL,
        CallState.FAILED,
    },
    CallState.NO_ANSWER: {
        CallState.QUEUED,
        CallState.DO_NOT_CALL,
        CallState.FAILED,
    },
    CallState.FAILED: {
        CallState.QUEUED,
        CallState.DO_NOT_CALL,
        CallState.BAD_NUMBER,
    },
    CallState.COMPLETED: set(),
    CallState.DO_NOT_CALL: set(),
    CallState.WRONG_NUMBER: set(),
    CallState.BAD_NUMBER: set(),
}


class CallStateMachine:
    """Deterministic, validated state machine for individual call lifecycles."""

    def __init__(self, initial_state: CallState = CallState.QUEUED):
        self.state = initial_state
        self.history: List[Dict[str, Any]] = [
            {
                "from_state": None,
                "to_state": initial_state.value,
                "reason": "initial",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

    def transition_to(self, new_state: CallState, reason: str = "") -> CallState:
        if isinstance(new_state, str):
            new_state = CallState(new_state)

        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal call transition: {self.state.value} -> {new_state.value}. "
                f"Reason: {reason or 'none'}. Terminal states cannot be recycled."
            )

        old_state = self.state
        self.state = new_state
        self.history.append({
            "from_state": old_state.value,
            "to_state": new_state.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return self.state
