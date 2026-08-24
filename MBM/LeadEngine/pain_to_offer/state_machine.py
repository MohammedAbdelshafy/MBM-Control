"""state_machine -- explicit transition law for PipelineState.

Terminal states: WON, LOST, SUPPRESSED, INVALID.
SUPPRESSED and INVALID are reachable from any non-terminal state.
"""
from __future__ import annotations

from pain_to_offer.schema import GateResult, PipelineState

_ALLOWED = {
    PipelineState.DISCOVERED: {PipelineState.RESEARCHING},
    PipelineState.RESEARCHING: {PipelineState.RESEARCHED},
    PipelineState.RESEARCHED: {PipelineState.SCORED},
    PipelineState.SCORED: {PipelineState.OFFER_READY},
    PipelineState.OFFER_READY: {PipelineState.EMAIL_READY, PipelineState.PHONE_PENDING},
    PipelineState.PHONE_PENDING: {PipelineState.CALL_READY, PipelineState.EMAIL_READY},
    PipelineState.EMAIL_READY: {PipelineState.CONTACTED},
    PipelineState.CALL_READY: {PipelineState.CONTACTED},
    PipelineState.CONTACTED: {PipelineState.RESPONDED, PipelineState.LOST},
    PipelineState.RESPONDED: {PipelineState.MEETING_BOOKED, PipelineState.LOST},
    PipelineState.MEETING_BOOKED: {PipelineState.PILOT, PipelineState.LOST},
    PipelineState.PILOT: {PipelineState.WON, PipelineState.LOST},
    PipelineState.WON: set(),
    PipelineState.LOST: set(),
    PipelineState.SUPPRESSED: set(),
    PipelineState.INVALID: set(),
}

_TERMINAL = {PipelineState.WON, PipelineState.LOST, PipelineState.SUPPRESSED,
             PipelineState.INVALID}


def _targets_for(state: PipelineState) -> set[PipelineState]:
    targets = set(_ALLOWED.get(state, set()))
    if state not in _TERMINAL:
        targets |= {PipelineState.SUPPRESSED, PipelineState.INVALID}
    return targets


ALLOWED_TRANSITIONS = {s: _targets_for(s) for s in PipelineState}


def validate_transition(current: PipelineState, target: PipelineState) -> GateResult:
    reasons: list[str] = []
    if current in _TERMINAL:
        reasons.append(f"{current.value} is terminal; no transitions allowed")
    elif target not in ALLOWED_TRANSITIONS[current]:
        reasons.append(
            f"illegal transition {current.value} -> {target.value}; "
            f"allowed: {sorted(t.value for t in ALLOWED_TRANSITIONS[current])}"
        )
    return GateResult(gate="state_transition", passed=not reasons, reasons=reasons)
