"""state_machine -- explicit transition law + audit trail (contract v2.0).

Canonical states (21): DISCOVERED, RESEARCHING, RESEARCHED, SCORED,
OFFER_READY, CONTACT_PENDING, PHONE_PENDING, EMAIL_PENDING, EMAIL_READY,
CALL_READY, CONTACTED, RESPONDED, DEMO_REQUESTED, DEMO_BOOKED, PILOT,
WON, LOST, NURTURE, SUPPRESSED, INVALID, BLOCKED.

Laws:
  - No transition without its gate; downstream states are never inferred.
  - SUPPRESSED / INVALID reachable from any non-terminal state.
  - BLOCKED is entered on failed gates (research/contact/email/phone);
    re-entry BLOCKED -> RESEARCHING is legal ONLY as NEW_EVIDENCE rework.
  - NURTURE is a holding loop: NURTURE -> CONTACTED on approved re-engagement.
  - Terminal states (WON, LOST, SUPPRESSED, INVALID) admit nothing.
  - Every applied transition appends an immutable TransitionRecord carrying
    from_state, to_state, actor, timestamp, reason, evidence/reference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pain_to_offer.schema import GateResult, PipelineState

_ALLOWED = {
    PipelineState.DISCOVERED: {PipelineState.RESEARCHING},
    PipelineState.RESEARCHING: {PipelineState.RESEARCHED},
    PipelineState.RESEARCHED: {PipelineState.SCORED, PipelineState.BLOCKED},
    PipelineState.SCORED: {PipelineState.OFFER_READY, PipelineState.BLOCKED},
    PipelineState.OFFER_READY: {PipelineState.CONTACT_PENDING, PipelineState.BLOCKED},
    PipelineState.CONTACT_PENDING: {PipelineState.EMAIL_PENDING, PipelineState.PHONE_PENDING, PipelineState.BLOCKED},
    PipelineState.EMAIL_PENDING: {PipelineState.EMAIL_READY, PipelineState.BLOCKED},
    PipelineState.PHONE_PENDING: {PipelineState.CALL_READY, PipelineState.EMAIL_PENDING, PipelineState.BLOCKED},
    PipelineState.EMAIL_READY: {PipelineState.CONTACTED},
    PipelineState.CALL_READY: {PipelineState.CONTACTED},
    PipelineState.CONTACTED: {PipelineState.RESPONDED, PipelineState.LOST},
    PipelineState.RESPONDED: {PipelineState.DEMO_REQUESTED, PipelineState.NURTURE, PipelineState.LOST},
    PipelineState.DEMO_REQUESTED: {PipelineState.DEMO_BOOKED, PipelineState.NURTURE, PipelineState.LOST},
    PipelineState.DEMO_BOOKED: {PipelineState.PILOT, PipelineState.LOST},
    PipelineState.PILOT: {PipelineState.WON, PipelineState.LOST},
    PipelineState.NURTURE: {PipelineState.CONTACTED},
    PipelineState.BLOCKED: {PipelineState.RESEARCHING},
    PipelineState.WON: set(),
    PipelineState.LOST: set(),
    PipelineState.SUPPRESSED: set(),
    PipelineState.INVALID: set(),
}

_TERMINAL = {
    PipelineState.WON,
    PipelineState.LOST,
    PipelineState.SUPPRESSED,
    PipelineState.INVALID,
}

_BLOCKABLE = {
    PipelineState.RESEARCHED,
    PipelineState.SCORED,
    PipelineState.OFFER_READY,
    PipelineState.CONTACT_PENDING,
    PipelineState.EMAIL_PENDING,
    PipelineState.PHONE_PENDING,
}

ALLOWED_TRANSITIONS = {s: set(t) for s, t in _ALLOWED.items()}
TERMINAL_STATES = frozenset(_TERMINAL)


def _targets_for(state: PipelineState) -> set[PipelineState]:
    targets = set(_ALLOWED.get(state, set()))
    if state not in _TERMINAL:
        targets |= {PipelineState.SUPPRESSED, PipelineState.INVALID}
        if state in _BLOCKABLE:
            targets |= {PipelineState.BLOCKED}
    return targets


ALLOWED_TRANSITIONS_EFFECTIVE = {s: _targets_for(s) for s in PipelineState}


def validate_transition(current: PipelineState, target: PipelineState) -> GateResult:
    reasons: list[str] = []
    if current in _TERMINAL:
        reasons.append(f"{current.value} is terminal; no transitions allowed")
    elif target not in ALLOWED_TRANSITIONS_EFFECTIVE[current]:
        reasons.append(
            f"illegal transition {current.value} -> {target.value}; "
            f"allowed: {sorted(t.value for t in ALLOWED_TRANSITIONS_EFFECTIVE[current])}"
        )
    return GateResult(gate="state_transition", passed=not reasons, reasons=reasons)


@dataclass(frozen=True)
class TransitionRecord:
    """Immutable audit entry for one applied transition."""

    from_state: PipelineState
    to_state: PipelineState
    actor: str
    timestamp: str
    reason: str
    evidence_ref: str

    def to_dict(self) -> dict:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "evidence_ref": self.evidence_ref,
        }


def _iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class DuplicateTransitionError(ValueError):
    pass


class MissingEvidenceError(ValueError):
    pass


@dataclass
class StateTransitionLog:
    """Append-only ledger of applied transitions for one entity."""

    entity_id: str = ""
    entries: list[TransitionRecord] = field(default_factory=list)

    def apply(
        self,
        current: PipelineState,
        target: PipelineState,
        actor: str,
        reason: str = "",
        evidence_ref: str = "",
    ) -> TransitionRecord:
        verdict = validate_transition(current, target)
        if not verdict.passed:
            raise ValueError("; ".join(verdict.reasons))
        if not evidence_ref:
            raise MissingEvidenceError(
                f"{current.value}->{target.value}: evidence/reference is mandatory"
            )
        key = (current, target, evidence_ref)
        for e in self.entries:
            if (e.from_state, e.to_state, e.evidence_ref) == key:
                raise DuplicateTransitionError(
                    f"duplicate transition {current.value}->{target.value} "
                    f"for evidence_ref={evidence_ref}"
                )
        rec = TransitionRecord(
            from_state=current,
            to_state=target,
            actor=actor,
            timestamp=_iso_now(),
            reason=reason,
            evidence_ref=evidence_ref,
        )
        self.entries.append(rec)
        return rec

    def current_state(self) -> PipelineState | None:
        return self.entries[-1].to_state if self.entries else None

    def to_dict(self) -> dict:
        return {"entity_id": self.entity_id, "transitions": [e.to_dict() for e in self.entries]}
