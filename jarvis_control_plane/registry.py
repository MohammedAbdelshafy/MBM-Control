"""Canonical machine-readable agent registry (P0.2).

Wraps the existing GLM registry (MBM/GLM/agent_registry.py) — the source of
truth for specialist roles — and projects every entry onto the control-plane
contract:

    agent_id / name / responsibility / inputs / outputs / tools /
    capabilities / read_scope / write_scope / side_effects /
    approval_required / protocol / health / confidence_requirements /
    validation_requirements / fallback

Protocols: local | mcp | a2a. Specialists start as LOCAL (in-process wrap);
a mature specialist may additionally be exposed over MCP (see mcp_a2a.py) or
collaborate over A2A. Nothing here creates autonomous agents — it describes
existing functionality so JARVIS/OpenCode can route without rediscovery.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentProtocol(str, Enum):
    LOCAL = "local"
    MCP = "mcp"
    A2A = "a2a"


class AgentHealth(str, Enum):
    REGISTERED = "registered"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class ControlPlaneAgentSpec(BaseModel):
    agent_id: str
    name: str
    responsibility: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    read_scope: List[str] = Field(default_factory=list)
    write_scope: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    approval_required: bool = False
    protocol: AgentProtocol = AgentProtocol.LOCAL
    health: AgentHealth = AgentHealth.REGISTERED
    confidence_requirements: Dict[str, Any] = Field(default_factory=dict)
    validation_requirements: List[str] = Field(default_factory=list)
    fallback: str = ""


# Control-plane-native entries (orchestration substrate, not business agents).
_NATIVE_SPECS: List[ControlPlaneAgentSpec] = [
    ControlPlaneAgentSpec(
        agent_id="jarvis.decider",
        name="JARVIS Root Decider",
        responsibility="Top-level decision authority. Owns mission priority, approvals, and escalations. Never replaced by worker frameworks.",
        inputs=["mission_brief", "policy_decision", "evaluation_verdict"],
        outputs=["routing_decision", "approval", "escalation"],
        tools=["workflow_engine", "policy_gateway", "agent_registry"],
        capabilities=["prioritize", "approve", "escalate", "halt"],
        read_scope=["missions", "ledger", "artifacts"],
        write_scope=["decisions", "approvals"],
        approval_required=False,
        protocol=AgentProtocol.LOCAL,
        health=AgentHealth.HEALTHY,
        validation_requirements=["human_override_available"],
        fallback="human operator assumes decider role",
    ),
    ControlPlaneAgentSpec(
        agent_id="workflow.engine",
        name="Workflow Control Plane",
        responsibility="Owns 7-phase workflow state (UNDERSTAND..VALIDATE). Deterministic transitions, resumability, audit trail.",
        inputs=["objective", "transition"],
        outputs=["workflow_state", "transition_record"],
        tools=[],
        capabilities=["start_run", "transition", "resume", "audit"],
        read_scope=["runs"],
        write_scope=["operational_run_state"],
        protocol=AgentProtocol.LOCAL,
        health=AgentHealth.HEALTHY,
        validation_requirements=["invalid_transition_rejected"],
        fallback="restart run from last audited phase",
    ),
    ControlPlaneAgentSpec(
        agent_id="policy.gateway",
        name="Policy Gateway",
        responsibility="Central authorization, approval/HITL, audit, redaction, budgets. Single source of side-effect rules.",
        inputs=["action", "context", "approval"],
        outputs=["policy_decision"],
        tools=[],
        capabilities=["classify", "evaluate", "redact", "audit"],
        read_scope=["policy_rules"],
        write_scope=["audit_log"],
        protocol=AgentProtocol.LOCAL,
        health=AgentHealth.HEALTHY,
        validation_requirements=["fail_closed_on_unknown_mutation"],
        fallback="deny by default; escalate to human",
    ),
]


def _project_glm_role(role: Any, spec: Any) -> ControlPlaneAgentSpec:
    """Project one GLM AgentSpec onto the control-plane contract (read-only wrap)."""
    role_name = getattr(role, "value", str(role))
    agent_id = f"glm.{role_name.lower()}"
    read_only = bool(getattr(spec, "read_only_by_default", False))
    capabilities = list(getattr(spec, "capabilities", []) or [])
    return ControlPlaneAgentSpec(
        agent_id=agent_id,
        name=getattr(spec, "name", role_name),
        responsibility=getattr(spec, "description", ""),
        inputs=["task_brief"],
        outputs=["recommendation", "evidence_refs"],
        tools=[],
        capabilities=capabilities,
        read_scope=["repo", "artifacts"],
        write_scope=[] if read_only else ["scoped_working_state"],
        side_effects=[] if read_only else ["scoped_writes"],
        approval_required=not read_only,
        protocol=AgentProtocol.LOCAL,
        health=AgentHealth.REGISTERED,
        confidence_requirements={"min_confidence": 0.5},
        validation_requirements=["diff_review", "hermetic_tests"] if not read_only else ["read_only_audit"],
        fallback="jarvis.decider re-routes to human or peer specialist",
    )


def _project_ecosystem_provider(p: Dict[str, Any]) -> ControlPlaneAgentSpec:
    """Project one ecosystem provider onto the control-plane contract."""
    agent_id = f"ecosystem.{p.get('provider_id', 'unknown')}"
    return ControlPlaneAgentSpec(
        agent_id=agent_id,
        name=f"Ecosystem: {p.get('provider_id', 'unknown')}",
        responsibility=f"External capability provider from {p.get('repository', 'unknown')}",
        inputs=["mission_intent"],
        outputs=["execution_result", "evidence"],
        tools=[],
        capabilities=p.get("capabilities", []),
        read_scope=["mission", "artifacts"],
        write_scope=["evidence", "artifacts"] if "FILE_WRITE" in p.get("permissions", []) else [],
        side_effects=["external_api_calls", "browser_automation"] if "BROWSER_NAVIGATE" in p.get("permissions", []) else [],
        approval_required=p.get("approval_required", True),
        protocol=AgentProtocol.LOCAL,
        health=AgentHealth.REGISTERED if p.get("status") in ["ADOPT", "ADAPTER"] else AgentHealth.DEGRADED,
        confidence_requirements={"min_confidence": 0.8},
        validation_requirements=["evidence_verification", "policy_gateway_approval"],
        fallback="fallback_chain via provider_router",
    )



_registry_cache: Optional[Dict[str, ControlPlaneAgentSpec]] = None


def build_registry() -> Dict[str, ControlPlaneAgentSpec]:
    """Build the full registry: native control-plane entries + wrapped GLM roles."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    registry: Dict[str, ControlPlaneAgentSpec] = {s.agent_id: s for s in _NATIVE_SPECS}
    try:
        from MBM.GLM.agent_registry import AGENT_REGISTRY as _GLM

        for role, spec in _GLM.items():
            projected = _project_glm_role(role, spec)
            registry[projected.agent_id] = projected
    except Exception as exc:  # registry must never crash routing; record blockage
        blocked = ControlPlaneAgentSpec(
            agent_id="glm.bridge",
            name="GLM Registry Bridge",
            responsibility="Bridge to MBM/GLM/agent_registry.py (currently unreachable).",
            health=AgentHealth.BLOCKED,
            validation_requirements=[],
            fallback=f"route via native specs only; bridge error: {type(exc).__name__}",
        )
        registry[blocked.agent_id] = blocked
        
    try:
        from .provider_router import load_registry as _load_ecosystem
        for p in _load_ecosystem():
            if p.get("status") in ["ADOPT", "ADAPTER", "VENDOR"]:
                projected = _project_ecosystem_provider(p)
                registry[projected.agent_id] = projected
    except Exception as exc:
        blocked = ControlPlaneAgentSpec(
            agent_id="ecosystem.bridge",
            name="Ecosystem Registry Bridge",
            responsibility="Bridge to ecosystem providers.",
            health=AgentHealth.BLOCKED,
            validation_requirements=[],
            fallback=f"error: {type(exc).__name__}",
        )
        registry[blocked.agent_id] = blocked
        
    _registry_cache = registry
    return registry


def get(agent_id: str) -> ControlPlaneAgentSpec:
    registry = build_registry()
    if agent_id not in registry:
        raise KeyError(f"unknown agent_id: {agent_id}")
    return registry[agent_id]


def list_by_capability(capability: str) -> List[ControlPlaneAgentSpec]:
    needle = capability.lower()
    return [
        s for s in build_registry().values()
        if any(needle in c.lower() for c in s.capabilities)
        or needle in s.responsibility.lower()
        or needle in s.name.lower()
    ]


def route(intent: str) -> List[ControlPlaneAgentSpec]:
    """Keyword routing over responsibility/capabilities. Advisory only —
    JARVIS makes the final decision."""
    words = [w for w in intent.lower().split() if len(w) > 2]
    scored = []
    for spec in build_registry().values():
        hay = f"{spec.name} {spec.responsibility} {' '.join(spec.capabilities)}".lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, spec))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [s for _, s in scored]
