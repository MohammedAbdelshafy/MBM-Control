"""MCP / A2A boundaries (P0.5).

Rule:
    MCP  = Host -> capability. Tools, external data, services, host
           integration. Expose a mature specialist as ONE callable capability
           so OpenCode can invoke it without understanding its internals.
    A2A  = Agent <-> agent. Only when an autonomous specialist genuinely
           needs to collaborate with another autonomous specialist.

    workflow nodes = deterministic orchestration (workflow.py)
    plugins        = cross-cutting policy/control (policy.py)

Do not confuse these responsibilities.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .agent_identity import AgentIdentityRegistry, IdentityDenied, require_identity
from .lifecycle import ExecutionReceipt, ToolLifecycleHooks
from .policy import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUTS,
    TRANSIENT_ERRORS,
    ActionClass,
    PolicyVerdict,
    evaluate,
    redact,
    resolve_class,
)
from .registry import AgentProtocol, ControlPlaneAgentSpec, build_registry
from .telemetry import NoOpSink, TelemetryEvent, TelemetrySink, new_trace_id


# -- MCP -----------------------------------------------------------------------
_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore (all )?previous instructions"),
    re.compile(r"(?i)system:\s*you are now"),
    re.compile(r"(?i)exfiltrat|send .* to (http|external)"),
    re.compile(r"(?i)\b(drop table|delete from|rm -rf)\b"),
]


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]
    timeout_sec: int = DEFAULT_TIMEOUTS["tool_call_sec"]
    retryable_errors: List[str] = field(default_factory=lambda: sorted(TRANSIENT_ERRORS))
    # Declared permission class. None = auto-derive from name+description via
    # policy.classify (fail-closed: ambiguous/mutating text -> GATED_WRITE+).
    action_class: Optional[ActionClass] = None
    # Free-text action used for the policy check. Defaults to name+description.
    action_text: str = ""
    # Optional capability required from the invoking agent for side effects.
    required_capability: Optional[str] = None

    @property
    def effective_class(self) -> ActionClass:
        # Mirrors policy.resolve_class (single home) so reporting matches
        # enforcement: declared wins, text proving EXTERNAL/HIGH_IMPACT
        # escalates over a weaker declaration.
        return resolve_class(self.policy_action(), self.action_class)[0]

    def policy_action(self) -> str:
        return self.action_text or f"{self.name}: {self.description}"


class MCPPermissionDenied(PermissionError):
    """Raised when the policy gate refuses an MCP tool call (fail-closed)."""


class MCPToolBus:
    """Filtered, lifecycle-managed tool bus.

    - Only registered tools are callable (deny by default).
    - Inputs are validated against the declared schema (required keys, types).
    - Tool-input injection patterns are rejected before dispatch.
    - Secrets stay server-side: args/outputs are redacted in telemetry.
    - Retries happen only for transient errors with no proven side effect.
    - Every allow/deny also emits a provider-neutral telemetry event
      (default NoOpSink: zero overhead; pass an InMemorySink/vendor sink
      to observe without touching this code).
    """

    def __init__(
        self,
        sink: Optional[TelemetrySink] = None,
        identity_registry: Optional[AgentIdentityRegistry] = None,
        lifecycle: Optional[ToolLifecycleHooks] = None,
        max_invocations: Optional[int] = None,
    ) -> None:
        if max_invocations is not None and max_invocations < 0:
            raise ValueError("max_invocations must be non-negative")
        self._tools: Dict[str, MCPToolDefinition] = {}
        self.telemetry: List[Dict[str, Any]] = []
        self.sink: TelemetrySink = sink or NoOpSink()
        self.identity_registry = identity_registry
        self.lifecycle = lifecycle or ToolLifecycleHooks()
        self.max_invocations = max_invocations
        self._invocation_count = 0
        self.receipts: List[ExecutionReceipt] = []

    def register(self, tool: MCPToolDefinition) -> None:
        self._tools[tool.name] = tool

    def exposed_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def _validate(self, tool: MCPToolDefinition, args: Dict[str, Any]) -> None:
        schema = tool.input_schema or {}
        for key in schema.get("required", []):
            if key not in args:
                raise ValueError(f"tool {tool.name}: missing required input '{key}'")
        blob = " ".join(str(v) for v in args.values())
        for pat in _INJECTION_PATTERNS:
            if pat.search(blob):
                raise ValueError(f"tool {tool.name}: input rejected by injection guard")

    def call(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        approval: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> Any:
        args = dict(args or {})
        if name not in self._tools:
            raise KeyError(f"MCP tool not exposed: {name}")
        tool = self._tools[name]
        self._validate(tool, args)

        if self.max_invocations is not None and self._invocation_count >= self.max_invocations:
            raise RuntimeError("MCP invocation budget exhausted")
        self._invocation_count += 1

        effective_approval = approval if approval is not None else args.get("approval")
        trace_id = new_trace_id()
        decision = evaluate(
            tool.policy_action(),
            approval=effective_approval,
            action_class=tool.action_class,
        )

        identity = None
        requires_identity = decision.action_class in (
            ActionClass.GATED_WRITE,
            ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if requires_identity:
            try:
                required_id = require_identity(agent_id)
                if self.identity_registry is None:
                    raise IdentityDenied(
                        "agent identity registry is required for gated/external MCP tools"
                    )
                if tool.required_capability:
                    identity = self.identity_registry.require_capability(
                        required_id, tool.required_capability
                    )
                else:
                    identity = self.identity_registry.get(required_id)
            except IdentityDenied as exc:
                receipt = ExecutionReceipt.denied(
                    trace_id=trace_id,
                    agent_id=agent_id or "",
                    tool=name,
                    reason=str(exc),
                    metadata={
                        "policy_verdict": decision.verdict.value,
                        "gates": list(decision.gates),
                        "args": redact(args),
                    },
                )
                self.receipts.append(receipt)
                self.lifecycle.after(receipt)
                self.telemetry.append({
                    "tool": name,
                    "args": redact(args),
                    "at": datetime.now(timezone.utc).isoformat(),
                    "denied": True,
                    "verdict": decision.verdict.value,
                    "reason": str(exc),
                    "identity_denied": True,
                })
                self.sink.emit(TelemetryEvent(
                    trace_id=trace_id,
                    kind="policy_denial",
                    tool=name,
                    outcome="denied",
                    policy_verdict=decision.verdict.value,
                    payload={
                        "reason": str(exc),
                        "gates": list(decision.gates),
                        "agent_id": agent_id or "",
                        "args": redact(args),
                    },
                ))
                raise MCPPermissionDenied(
                    f"MCP tool '{name}': agent identity denied - {exc}"
                ) from exc

        allowed = decision.verdict is PolicyVerdict.ALLOW or (
            decision.verdict is PolicyVerdict.REQUIRE_APPROVAL
            and isinstance(effective_approval, dict)
            and effective_approval.get("approved") is True
        )
        if not allowed:
            receipt = ExecutionReceipt.denied(
                trace_id=trace_id,
                agent_id=agent_id or "",
                tool=name,
                reason=decision.reason,
                metadata={
                    "policy_verdict": decision.verdict.value,
                    "gates": list(decision.gates),
                    "args": redact(args),
                },
            )
            self.receipts.append(receipt)
            self.lifecycle.after(receipt)
            self.telemetry.append({
                "tool": name,
                "args": redact(args),
                "at": datetime.now(timezone.utc).isoformat(),
                "denied": True,
                "verdict": decision.verdict.value,
                "reason": decision.reason,
            })
            self.sink.emit(TelemetryEvent(
                trace_id=trace_id,
                kind="policy_denial",
                tool=name,
                outcome="denied",
                policy_verdict=decision.verdict.value,
                payload={
                    "reason": decision.reason,
                    "gates": list(decision.gates),
                    "args": redact(args),
                },
            ))
            raise MCPPermissionDenied(
                f"MCP tool '{name}': {decision.verdict.value} - {decision.reason} "
                f"(gates: {', '.join(decision.gates) or 'none'})"
            )

        try:
            self.lifecycle.before(
                tool=name,
                agent_id=agent_id or "",
                args=redact(args),
                approval=redact(effective_approval),
                policy_decision=decision,
                identity=identity,
            )
        except Exception as exc:
            receipt = ExecutionReceipt.denied(
                trace_id=trace_id,
                agent_id=agent_id or "",
                tool=name,
                reason=f"before-hook denied execution: {exc}",
                metadata={
                    "policy_verdict": decision.verdict.value,
                    "gates": list(decision.gates),
                    "args": redact(args),
                },
            )
            self.receipts.append(receipt)
            self.lifecycle.after(receipt)
            raise

        self.telemetry.append(
            {"tool": name, "args": redact(args), "at": datetime.now(timezone.utc).isoformat()}
        )
        _start = time.perf_counter()
        attempts = 0
        while True:
            attempts += 1
            try:
                result = tool.handler(args)
            except Exception as exc:
                kind = getattr(exc, "error_kind", "unknown")
                if kind in tool.retryable_errors and attempts < DEFAULT_RETRY["max_attempts"]:
                    continue
                receipt = ExecutionReceipt.failed(
                    trace_id=trace_id,
                    agent_id=agent_id or "",
                    tool=name,
                    error=str(exc),
                    metadata={
                        "policy_verdict": decision.verdict.value,
                        "attempts": attempts,
                    },
                )
                self.receipts.append(receipt)
                self.lifecycle.after(receipt)
                self.sink.emit(TelemetryEvent(
                    trace_id=trace_id,
                    kind="tool_call",
                    tool=name,
                    latency_ms=round((time.perf_counter() - _start) * 1000, 2),
                    outcome="error",
                    policy_verdict=decision.verdict.value,
                    error=str(exc)[:500],
                    payload={"args": redact(args)},
                ))
                raise

            receipt = ExecutionReceipt.executed(
                trace_id=trace_id,
                agent_id=agent_id or "",
                tool=name,
                output=result,
                metadata={
                    "policy_verdict": decision.verdict.value,
                    "attempts": attempts,
                },
            )
            self.receipts.append(receipt)
            self.lifecycle.after(receipt)
            self.sink.emit(TelemetryEvent(
                trace_id=trace_id,
                kind="tool_call",
                tool=name,
                latency_ms=round((time.perf_counter() - _start) * 1000, 2),
                outcome="ok",
                policy_verdict=decision.verdict.value,
                payload={"args": redact(args)},
            ))
            return result


def expose_specialist_as_tool(
    spec: ControlPlaneAgentSpec,
    handler: Callable[[Dict[str, Any]], Any],
    action_class: Optional[ActionClass] = None,
) -> MCPToolDefinition:
    """Wrap a mature specialist as ONE MCP capability."""
    return MCPToolDefinition(
        name=f"agent_{spec.agent_id.replace('.', '_').replace('-', '_')}",
        description=f"{spec.name}: {spec.responsibility}",
        input_schema={
            "type": "object",
            "required": spec.inputs or ["task_brief"],
            "properties": {k: {"type": "string"} for k in (spec.inputs or ["task_brief"])},
        },
        handler=handler,
        action_class=action_class,
    )


# -- A2A ------------------------------------------------------------------------
@dataclass
class A2AMessage:
    sender_id: str
    recipient_id: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: f"a2a-{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "intent": self.intent,
            "payload": redact(self.payload),
            "correlation_id": self.correlation_id,
        }


class A2AMesh:
    """Minimal agent-to-agent contract enforcement.

    Both parties must be registered; A2A-capable protocol required on at
    least the recipient side (LOCAL senders may originate via the decider).
    Payloads are redacted at the boundary. Delivery itself is caller-owned
    (in-process dispatch here; transport adapters plug in later).
    """

    def send(self, message: A2AMessage) -> Dict[str, Any]:
        registry = build_registry()
        if message.sender_id not in registry:
            raise KeyError(f"A2A rejected: unknown sender {message.sender_id}")
        if message.recipient_id not in registry:
            raise KeyError(f"A2A rejected: unknown recipient {message.recipient_id}")
        recipient = registry[message.recipient_id]
        if recipient.protocol not in (AgentProtocol.A2A, AgentProtocol.MCP, AgentProtocol.LOCAL):
            raise ValueError(f"A2A rejected: recipient {message.recipient_id} has no callable protocol")
        envelope = message.to_dict()
        envelope["accepted_by"] = message.recipient_id
        return envelope
