"""Factory capability routing (policy-controlled adapter layer).

MCP Provider -> MCP Adapter -> Canonical Capability Registry
  -> Policy / Identity / Approval -> Factory Stage
  -> Audit / Evidence / Observability

Deterministic routing only. MCPs never redefine Factory policy, scoring,
release gates, or authority. Unknown capability/provider/tool = DENY.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .capability_registry import (
    CapabilitySpec,
    build_capability_registry,
    permission_to_action_class,
    unknown_capability_denied,
)
from .policy import ActionClass, PolicyVerdict, evaluate, redact

InvocationState = Literal[
    "PROPOSED", "APPROVED", "QUEUED", "EXECUTING",
    "COMPLETED", "BLOCKED", "FAILED", "MEASURED",
]


@dataclass(slots=True)
class CapabilityEvidence:
    capability: str
    provider: str
    tool: str
    invocation_id: str
    actor: str
    timestamp: str
    input_hash: str
    output_hash: str
    approval_state: str
    policy_decision: str
    success: bool
    artifact_ids: list[str] = field(default_factory=list)
    error_code: str = ""
    latency_ms: float = 0.0
    retry_count: int = 0
    state: InvocationState = "PROPOSED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha12(payload: Any) -> str:
    import json

    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def route_capability(
    capability: str,
    factory_stage: str,
    *,
    actor: str = "factory",
    approval: dict[str, Any] | None = None,
    registry: list[CapabilitySpec] | None = None,
) -> tuple[CapabilitySpec, Any]:
    """Route one Factory stage to its canonical capability.

    Returns (spec, policy_decision). Raises PermissionError when denied
    (unknown capability, wrong stage, or policy refusal). Fail-closed.
    """
    specs = registry if registry is not None else build_capability_registry()
    if unknown_capability_denied(capability, specs):
        raise PermissionError(f"unknown capability denied: {capability}")
    matches = [s for s in specs if s.capability == capability]
    if not matches:
        raise PermissionError(f"unknown capability denied: {capability}")
    spec = matches[0]
    if factory_stage not in spec.factory_stages:
        raise PermissionError(
            f"capability {capability} is not routed to stage {factory_stage}"
        )
    action_class = ActionClass(permission_to_action_class(spec.permission))
    decision = evaluate(
        f"{spec.capability} via {spec.provider}:{spec.tool} for factory stage {factory_stage}",
        approval=approval,
        action_class=action_class,
    )
    if decision.verdict is PolicyVerdict.DENY:
        raise PermissionError(f"policy denied {capability}: {decision.reason}")
    if decision.verdict is PolicyVerdict.REQUIRE_APPROVAL:
        if not isinstance(approval, dict) or approval.get("approved") is not True:
            raise PermissionError(f"approval required for {capability}: {decision.reason}")
    # UNSAFE / BLOCKED capabilities never route to execution.
    if spec.status in ("UNSAFE", "BLOCKED"):
        raise PermissionError(f"capability {capability} is {spec.status}: {spec.reason}")
    return spec, decision


def build_evidence(
    *,
    spec: CapabilitySpec,
    actor: str,
    inputs: dict[str, Any],
    outputs: Any,
    approval: dict[str, Any] | None,
    policy_decision: Any,
    success: bool,
    error_code: str = "",
    latency_ms: float = 0.0,
    retry_count: int = 0,
    state: InvocationState = "COMPLETED",
) -> CapabilityEvidence:
    return CapabilityEvidence(
        capability=spec.capability,
        provider=spec.provider,
        tool=spec.tool,
        invocation_id=f"cap-{uuid.uuid4().hex[:12]}",
        actor=actor,
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_hash=_sha12(redact(inputs)),
        output_hash=_sha12(redact(outputs)),
        approval_state="approved" if isinstance(approval, dict) and approval.get("approved") is True else "none",
        policy_decision=getattr(policy_decision, "verdict", policy_decision).value
        if hasattr(getattr(policy_decision, "verdict", None), "value")
        else str(policy_decision),
        success=success,
        error_code=error_code,
        latency_ms=round(latency_ms, 2),
        retry_count=retry_count,
        state=state,
    )


def stage_capabilities(factory_stage: str) -> list[str]:
    """List canonical capabilities routed to one Factory stage."""
    return [s.capability for s in build_capability_registry() if factory_stage in s.factory_stages]
