"""Provider-neutral telemetry interface (factory observability primitive).

Pipeline:
    Agent -> Control Plane -> Model / Tool / MCP -> TelemetrySink

Sinks are the ONLY integration point for vendors. The factory never imports
Langfuse (or any vendor SDK) directly; a Langfuse adapter implements
TelemetrySink in deployment code that owns the SDK dependency and keys.

Captured: trace/correlation ids, agent, task, model, tool, latency,
outcome, policy verdict, token/cost metadata where available.
NEVER captured: API keys, passwords, raw credentials, unnecessary PII.
All free-form payloads pass through policy.redact (which also strips
phone-number patterns) before storage or emission.

Langfuse mapping (for the future adapter; keys live in deployment env only):
    trace_id        -> langfuse trace id
    agent + task    -> trace name / metadata
    model + usage   -> generation (model, input/output tokens, cost)
    tool + latency  -> span (name, latency, level ERROR on failure)
    policy_verdict  -> span metadata / score
    LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST stay in env.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .policy import PolicyVerdict, redact


def new_trace_id() -> str:
    return f"tr-{uuid.uuid4().hex[:16]}"


@dataclass
class TelemetryEvent:
    trace_id: str
    kind: str  # "tool_call" | "model_call" | "policy_denial" | "agent_step"
    agent: str = ""
    task: str = ""
    model: str = ""
    tool: str = ""
    latency_ms: Optional[float] = None
    outcome: str = ""  # "ok" | "error" | "denied"
    policy_verdict: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)  # tokens/cost, never secrets
    payload: Dict[str, Any] = field(default_factory=dict)  # redacted at emit time
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TelemetrySink(Protocol):
    def emit(self, event: TelemetryEvent) -> None: ...


class NoOpSink:
    """Default sink: zero overhead, zero dependencies, zero exfiltration."""

    def emit(self, event: TelemetryEvent) -> None:
        return None


class InMemorySink:
    """Test/audit sink. Everything stored is pre-redacted."""

    def __init__(self) -> None:
        self.events: List[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        event.payload = redact(event.payload)
        event.usage = redact(event.usage)
        self.events.append(event)

    def denied(self) -> List[TelemetryEvent]:
        return [e for e in self.events if e.outcome == "denied"]


class _Timer:
    def __init__(self, sink: TelemetrySink, event: TelemetryEvent):
        self._sink = sink
        self._event = event
        self._start = 0.0

    def __enter__(self) -> TelemetryEvent:
        self._start = time.perf_counter()
        return self._event

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._event.latency_ms = round((time.perf_counter() - self._start) * 1000, 2)
        if exc_type is None:
            self._event.outcome = self._event.outcome or "ok"
        else:
            self._event.outcome = "error"
            self._event.error = str(exc)[:500]
        self._sink.emit(self._event)
        return False  # never swallow


def timed(sink: TelemetrySink, event: TelemetryEvent) -> _Timer:
    """Context manager: measures latency, records outcome, emits on exit."""
    return _Timer(sink, event)
