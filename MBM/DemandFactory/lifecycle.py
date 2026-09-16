"""Digital Product Factory lifecycle controller (#33).

Deterministic controller/lifecycle behavior on top of the existing
DemandFactory engine. This module OWNS:

- policy (allowed transitions)
- state transitions
- scoring thresholds (reuses engine constants)
- validation / evidence requirements
- capability checks (activation + approval)
- release gates
- auditability (structured results with reasons)

Boundaries preserved:
- Guarded activation: default OFF/DRY_RUN. ARMED requires explicit
  activation prerequisites (human approval + FACTORY_ARMED=1 env).
- No autonomous external publishing: `can_publish()` is False unless
  every gate passes AND activation is ARMED AND approval is present.
- Unknown stage/event/dependency/reference/evidence/unsafe = FAIL CLOSED.
- Scheduled execution must run DRY_RUN (proposal-only) unless ARMED.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ActivationMode = Literal["OFF", "DRY_RUN", "ARMED"]

LifecycleStage = Literal[
    "DISCOVERED",
    "RESEARCHED",
    "SCORED",
    "STRATEGY_READY",
    "BUILD_READY",
    "BUILDING",
    "QA_PASSED",
    "QA_FAILED",
    "PACKAGE_READY",
    "RELEASE_CANDIDATE",
    "RELEASED",
    "QUARANTINED",
    "KILLED",
]

LifecycleEvent = Literal[
    "research_complete",
    "score_complete",
    "strategy_complete",
    "build_approved",
    "build_complete",
    "qa_pass",
    "qa_fail",
    "package_complete",
    "release_approved",
    "release_complete",
    "quarantine",
    "retry",
    "kill",
]

_ALLOWED_TRANSITIONS: dict[LifecycleStage, dict[LifecycleEvent, LifecycleStage]] = {
    "DISCOVERED": {"research_complete": "RESEARCHED", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "RESEARCHED": {"score_complete": "SCORED", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "SCORED": {"strategy_complete": "STRATEGY_READY", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "STRATEGY_READY": {"build_approved": "BUILD_READY", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "BUILD_READY": {"build_complete": "BUILDING", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "BUILDING": {"qa_pass": "QA_PASSED", "qa_fail": "QA_FAILED", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "QA_FAILED": {"retry": "BUILDING", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "QA_PASSED": {"package_complete": "PACKAGE_READY", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "PACKAGE_READY": {"release_approved": "RELEASE_CANDIDATE", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "RELEASE_CANDIDATE": {"release_complete": "RELEASED", "quarantine": "QUARANTINED", "kill": "KILLED"},
    "QUARANTINED": {"retry": "BUILDING", "kill": "KILLED"},
    "RELEASED": {},
    "KILLED": {},
}

MAX_QA_RETRIES = 3


@dataclass(slots=True)
class ReleaseManifest:
    opportunity_id: str = ""
    product_id: str = ""
    offer_id: str = ""
    proof_assets: list[str] = field(default_factory=list)
    delivery_assets: list[str] = field(default_factory=list)
    checkout_rail: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    qa_result: str = ""
    conviction_status: str = ""
    commercial_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_release_manifest(manifest: ReleaseManifest | dict[str, Any]) -> list[str]:
    """Deterministic release-manifest validation. Empty = valid."""
    if isinstance(manifest, dict):
        manifest = ReleaseManifest(
            opportunity_id=str(manifest.get("opportunity_id", "")),
            product_id=str(manifest.get("product_id", "")),
            offer_id=str(manifest.get("offer_id", "")),
            proof_assets=list(manifest.get("proof_assets", []) or []),
            delivery_assets=list(manifest.get("delivery_assets", []) or []),
            checkout_rail=str(manifest.get("checkout_rail", "")),
            evidence_ids=list(manifest.get("evidence_ids", []) or []),
            qa_result=str(manifest.get("qa_result", "")),
            conviction_status=str(manifest.get("conviction_status", "")),
            commercial_score=float(manifest.get("commercial_score", 0.0) or 0.0),
            confidence=float(manifest.get("confidence", 0.0) or 0.0),
        )
    failures: list[str] = []
    if not manifest.opportunity_id.strip():
        failures.append("manifest_missing_opportunity_id")
    if not manifest.product_id.strip():
        failures.append("manifest_missing_product_id")
    if not manifest.offer_id.strip():
        failures.append("manifest_missing_offer_id")
    if not manifest.proof_assets:
        failures.append("manifest_missing_proof_assets")
    if not manifest.delivery_assets:
        failures.append("manifest_missing_delivery_assets")
    if not manifest.checkout_rail.strip():
        failures.append("manifest_missing_checkout_rail")
    if not manifest.evidence_ids:
        failures.append("manifest_missing_evidence")
    if manifest.qa_result != "passed":
        failures.append("manifest_qa_not_passed")
    if manifest.conviction_status != "ready":
        failures.append("manifest_conviction_not_ready")
    if manifest.commercial_score <= 0:
        failures.append("manifest_commercial_score_invalid")
    if not (0.0 < manifest.confidence <= 1.0):
        failures.append("manifest_confidence_invalid")
    return failures


def transition(stage: LifecycleStage, event: LifecycleEvent) -> LifecycleStage:
    """Deterministic state transition. Unknown stage/event = FAIL CLOSED."""
    if stage not in _ALLOWED_TRANSITIONS:
        raise ValueError(f"unknown lifecycle stage: {stage}")
    targets = _ALLOWED_TRANSITIONS[stage]
    if event not in targets:
        raise ValueError(f"illegal transition: {stage} + {event}")
    return targets[event]


def activation_mode(*, armed_flag: bool = False, env: dict[str, str] | None = None) -> ActivationMode:
    """Resolve guarded activation. Defaults to OFF (fail-closed)."""
    source = env if env is not None else dict(os.environ)
    env_armed = str(source.get("FACTORY_ARMED", "")).strip() == "1"
    if armed_flag and env_armed:
        return "ARMED"
    if armed_flag or env_armed:
        # Half-armed is still DRY_RUN: both human flag AND env required.
        return "DRY_RUN"
    return "OFF"


def activation_prerequisites(mode: ActivationMode) -> list[str]:
    """Document activation prerequisites for a mode."""
    if mode == "ARMED":
        return ["human_approval_recorded", "FACTORY_ARMED=1", "release_gates_passed"]
    if mode == "DRY_RUN":
        return ["proposal_only_no_external_side_effects"]
    return ["factory_off_no_transitions"]


@dataclass(slots=True)
class QAResult:
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_qa(
    *,
    quality_failures: list[str],
    conviction_status: str,
    evidence_ids: list[str],
    evidence_quality: float,
    commercial_score: float,
    confidence: float,
) -> QAResult:
    """Deterministic QA gate aggregation. Any failure = QA_FAILED."""
    failures: list[str] = []
    failures.extend(quality_failures)
    if conviction_status != "ready":
        failures.append(f"conviction_{conviction_status}")
    if not evidence_ids:
        failures.append("qa_missing_evidence")
    if evidence_quality < 0.35:
        failures.append("qa_evidence_below_threshold")
    if commercial_score < 0.25:
        failures.append("qa_commercial_below_threshold")
    if confidence < 0.40:
        failures.append("qa_confidence_below_threshold")
    # Unknown / unsafe sentinel: explicit fail-closed.
    for marker in ("unknown", "UNSAFE", "missing"):
        for item in list(quality_failures) + [conviction_status]:
            if marker in str(item).lower() and marker == "unknown":
                if "qa_unknown_reference" not in failures:
                    failures.append("qa_unknown_reference")
    return QAResult(passed=not failures, failures=sorted(set(failures)))


def can_publish(
    *,
    qa: QAResult,
    manifest_failures: list[str],
    mode: ActivationMode,
    approval: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    """Release gate: failed gates cannot publish. Returns (allowed, reasons)."""
    reasons: list[str] = []
    if not qa.passed:
        reasons.append("qa_not_passed")
        reasons.extend(qa.failures)
    if manifest_failures:
        reasons.append("manifest_invalid")
        reasons.extend(manifest_failures)
    if mode != "ARMED":
        reasons.append(f"activation_not_armed:{mode}")
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        reasons.append("approval_missing")
    return (not reasons, reasons)


@dataclass(slots=True)
class RetryTracker:
    attempts: int = 0
    max_attempts: int = MAX_QA_RETRIES
    quarantined: bool = False

    def record_failure(self) -> str:
        """Record one QA failure. Returns next action: retry|quarantine."""
        self.attempts += 1
        if self.attempts >= self.max_attempts:
            self.quarantined = True
            return "quarantine"
        return "retry"

    def record_success(self) -> None:
        self.attempts = 0
        self.quarantined = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def should_schedule_run(mode: ActivationMode) -> tuple[bool, str]:
    """Scheduled execution guard: only DRY_RUN/OFF may run unattended.

    ARMED scheduled runs are denied unless an explicit approval record exists
    (caller must pass approval separately to can_publish).
    """
    if mode == "ARMED":
        return False, "scheduled_execution_blocked_while_armed_without_explicit_approval"
    return True, f"scheduled_execution_allowed:{mode}_proposal_only"
