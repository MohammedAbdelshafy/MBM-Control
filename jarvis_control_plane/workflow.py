"""JARVIS control-plane workflow engine (P0.3).

Makes the existing 7-phase execution model explicit and inspectable:

    UNDERSTAND -> DISCOVER -> RANK -> COMPOSE -> REJECT -> EXECUTE -> VALIDATE

LLMs perform reasoning where reasoning adds value. Phase *gates* are
deterministic code in this module: only legal transitions are representable,
every transition is timestamped and auditable, and a run can be serialized,
resumed, and replayed without re-invoking any model.

This module owns NO business logic. It wraps orchestration state only.
JARVIS (MBM/GLM/orchestrator.py) remains the top-level decider.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkflowPhase(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    DISCOVER = "DISCOVER"
    RANK = "RANK"
    COMPOSE = "COMPOSE"
    REJECT = "REJECT"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"


# Deterministic gate: the only legal edges. Linear forward flow plus two
# explicit, auditable re-plan edges (REJECT->RANK when the plan is rejected,
# EXECUTE->COMPOSE when execution evidence forces a re-plan).
ALLOWED_TRANSITIONS: Dict[WorkflowPhase, List[WorkflowPhase]] = {
    WorkflowPhase.UNDERSTAND: [WorkflowPhase.DISCOVER],
    WorkflowPhase.DISCOVER: [WorkflowPhase.RANK],
    WorkflowPhase.RANK: [WorkflowPhase.COMPOSE],
    WorkflowPhase.COMPOSE: [WorkflowPhase.REJECT],
    WorkflowPhase.REJECT: [WorkflowPhase.EXECUTE, WorkflowPhase.RANK],
    WorkflowPhase.EXECUTE: [WorkflowPhase.VALIDATE, WorkflowPhase.COMPOSE],
    WorkflowPhase.VALIDATE: [],  # terminal
}


class InvalidWorkflowTransitionError(ValueError):
    """Raised when a workflow attempts an illegal phase transition."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseRecord:
    phase: str
    entered_at: str
    note: str = ""
    actor: str = "system"  # system | human | agent:<id>


@dataclass
class WorkflowRun:
    """Inspectable, resumable, auditable workflow state."""

    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    parent_run_id: Optional[str] = None
    objective: str = ""
    phase: WorkflowPhase = WorkflowPhase.UNDERSTAND
    history: List[PhaseRecord] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    done: bool = False

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(
                PhaseRecord(
                    phase=self.phase.value,
                    entered_at=utcnow(),
                    note="run created",
                )
            )

    # -- deterministic gates -------------------------------------------------
    def allowed_next(self) -> List[WorkflowPhase]:
        return list(ALLOWED_TRANSITIONS[self.phase])

    def advance(self, note: str = "", actor: str = "system") -> WorkflowPhase:
        """Take the single default forward edge (REJECT->EXECUTE, EXECUTE->VALIDATE)."""
        candidates = self.allowed_next()
        if not candidates:
            raise InvalidWorkflowTransitionError(
                f"run {self.run_id} is terminal at {self.phase.value}; no advance possible"
            )
        return self.transition_to(candidates[0], note=note, actor=actor)

    def transition_to(
        self, target: WorkflowPhase, note: str = "", actor: str = "system"
    ) -> WorkflowPhase:
        if isinstance(target, str):
            target = WorkflowPhase(target)
        if target not in ALLOWED_TRANSITIONS[self.phase]:
            raise InvalidWorkflowTransitionError(
                f"illegal transition {self.phase.value} -> {target.value} "
                f"(allowed: {[p.value for p in ALLOWED_TRANSITIONS[self.phase]] or ['<terminal>']})"
            )
        self.phase = target
        if target is WorkflowPhase.VALIDATE and note.startswith("terminal:"):
            pass
        self.history.append(PhaseRecord(phase=target.value, entered_at=utcnow(), note=note, actor=actor))
        return self.phase

    def record_decision(self, decision: Dict[str, Any]) -> None:
        """Attach an LLM/person routing decision to the audit trail (advisory, not a gate)."""
        entry = dict(decision)
        entry.setdefault("at", utcnow())
        entry.setdefault("phase", self.phase.value)
        self.decisions.append(entry)

    def mark_complete(self, note: str = "validated") -> None:
        if self.phase is not WorkflowPhase.VALIDATE:
            raise InvalidWorkflowTransitionError(
                f"run {self.run_id} cannot complete from {self.phase.value}; "
                "must reach VALIDATE first"
            )
        self.done = True
        self.history.append(
            PhaseRecord(phase="DONE", entered_at=utcnow(), note=note, actor="system")
        )

    # -- persistence ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["phase"] = self.phase.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowRun":
        data = dict(data)
        data["phase"] = WorkflowPhase(data["phase"])
        data["history"] = [PhaseRecord(**h) for h in data.get("history", [])]
        return cls(**data)


def start_run(objective: str, parent_run_id: Optional[str] = None) -> WorkflowRun:
    return WorkflowRun(objective=objective, parent_run_id=parent_run_id)
