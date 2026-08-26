"""Dialer + CRM state machines for CONTEC_REAL_ESTATE_AI_MEDIA.

Dialer:  READY -> DIALED -> CONNECTED | NO_ANSWER | CALLBACK -> INTERESTED ->
         SAMPLE_REQUESTED -> SAMPLE_SENT -> QUOTED -> NEGOTIATING -> WON |
         LOST; DO_NOT_CONTACT terminal from ANY state (opt-out law).
CRM:     New Lead .. Lost / Do Not Contact (15 stages, timestamped).

Rules:
- Every transition is validated against an explicit table; illegal moves raise.
- Opt-out (DO_NOT_CONTACT) is legal from EVERY state and is TERMINAL.
- Retry limits + cooldowns enforced per (lead, state) history.
- Transitions are pure: callers persist timestamps.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DIALER_STATES = [
    "READY", "DIALED", "CONNECTED", "NO_ANSWER", "CALLBACK", "INTERESTED",
    "SAMPLE_REQUESTED", "SAMPLE_SENT", "QUOTED", "NEGOTIATING", "WON",
    "LOST", "DO_NOT_CONTACT",
]

CRM_STAGES = [
    "New Lead", "Qualified", "Sample Candidate", "Sample Generated",
    "Contacted", "Connected", "Sample Sent", "Interested", "Quote Sent",
    "Negotiating", "Won", "Fulfillment", "Repeat Customer", "Lost",
    "Do Not Contact",
]

# dialer transition table
_DIALER_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "READY": ("DIALED",),
    "DIALED": ("CONNECTED", "NO_ANSWER", "CALLBACK"),
    "NO_ANSWER": ("READY",),            # retry after cooldown
    "CALLBACK": ("DIALED",),            # scheduled re-dial
    "CONNECTED": ("INTERESTED", "LOST", "DO_NOT_CONTACT"),
    "INTERESTED": ("SAMPLE_REQUESTED", "QUOTED", "LOST", "DO_NOT_CONTACT"),
    "SAMPLE_REQUESTED": ("SAMPLE_SENT",),
    "SAMPLE_SENT": ("QUOTED", "LOST", "DO_NOT_CONTACT"),
    "QUOTED": ("NEGOTIATING", "WON", "LOST", "DO_NOT_CONTACT"),
    "NEGOTIATING": ("WON", "LOST", "DO_NOT_CONTACT"),
    "WON": (),
    "LOST": (),
    "DO_NOT_CONTACT": (),
}

# dialer -> CRM mirror
_CRM_MIRROR: Dict[str, str] = {
    "READY": "New Lead",
    "DIALED": "Contacted",
    "CONNECTED": "Connected",
    "NO_ANSWER": "Contacted",
    "CALLBACK": "Contacted",
    "INTERESTED": "Interested",
    "SAMPLE_REQUESTED": "Sample Sent",
    "SAMPLE_SENT": "Sample Sent",
    "QUOTED": "Quote Sent",
    "NEGOTIATING": "Negotiating",
    "WON": "Won",
    "LOST": "Lost",
    "DO_NOT_CONTACT": "Do Not Contact",
}

# default retry/cooldown policy (override via RE Media Settings)
DEFAULT_POLICY = {
    "max_no_answer_retries": 3,
    "no_answer_cooldown_hours": 48,
    "callback_min_gap_hours": 24,
}


class IllegalTransition(Exception):
    pass


class OptedOut(Exception):
    """Any attempted contact on a DO_NOT_CONTACT lead."""


def can_transition(current: str, target: str) -> bool:
    if current == "DO_NOT_CONTACT":
        return False
    if target == "DO_NOT_CONTACT":
        return True  # opt-out from anywhere
    return target in _DIALER_TRANSITIONS.get(current, ())


def transition(current: str, target: str) -> Dict[str, Any]:
    """Validate and describe a transition. Pure - no IO."""
    if current not in _DIALER_TRANSITIONS:
        raise IllegalTransition(f"unknown state {current!r}")
    if not can_transition(current, target):
        raise IllegalTransition(f"{current} -> {target} not allowed")
    crm = "Fulfillment" if (current == "NEGOTIATING" and target == "WON") else _CRM_MIRROR[target]
    return {"from": current, "to": target, "crm_stage": crm,
            "terminal": target in ("WON", "LOST", "DO_NOT_CONTACT")}


def guard_contact(state: str) -> None:
    if state == "DO_NOT_CONTACT":
        raise OptedOut("lead is DO_NOT_CONTACT")


def retry_allowed(history: List[Dict[str, Any]], policy: Optional[Dict[str, Any]] = None,
                  now=None) -> Tuple[bool, str]:
    """history: [{state:'NO_ANSWER'|'DIALED', at: datetime}, ...] ascending."""
    from datetime import timedelta
    pol = dict(DEFAULT_POLICY)
    pol.update(policy or {})
    no_answers = [h for h in history if h.get("state") == "NO_ANSWER"]
    if len(no_answers) >= int(pol["max_no_answer_retries"]):
        return False, "retry_limit_reached"
    if no_answers:
        last = no_answers[-1]["at"]
        if now is not None and now < last + timedelta(hours=int(pol["no_answer_cooldown_hours"])):
            return False, "cooldown_active"
    callbacks = [h for h in history if h.get("state") == "CALLBACK"]
    if callbacks:
        last = max(c["at"] for c in callbacks)
        earliest_dial = last + timedelta(hours=int(pol["callback_min_gap_hours"]))
        pending = [h for h in history if h.get("state") == "DIALED" and h["at"] > last]
        if not pending and now is not None and now < earliest_dial:
            return False, "callback_gap"
    return True, ""
