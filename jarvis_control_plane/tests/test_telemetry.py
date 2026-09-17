"""Telemetry interface proofs (factory observability primitive).

Hermetic: InMemorySink only, no vendor SDK, no network.
Proves: allow/deny/error events are emitted with latency, secrets and phone
numbers never land in events, default bus emits nowhere (NoOp).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_control_plane import mcp_a2a as M
from jarvis_control_plane import telemetry as T


def _bus_with_sink():
    sink = T.InMemorySink()
    bus = M.MCPToolBus(sink=sink)
    bus.register(M.MCPToolDefinition(
        name="lead_lookup",
        description="Read-only lead lookup.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: {"ok": True},
    ))
    bus.register(M.MCPToolDefinition(
        name="boom",
        description="Read-only probe that fails.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: (_ for _ in ()).throw(RuntimeError("kaput")),
    ))
    return bus, sink


def test_allow_emits_ok_event_with_latency():
    bus, sink = _bus_with_sink()
    assert bus.call("lead_lookup", {}) == {"ok": True}
    assert len(sink.events) == 1
    evt = sink.events[0]
    assert evt.kind == "tool_call" and evt.outcome == "ok"
    assert evt.tool == "lead_lookup"
    assert evt.latency_ms is not None and evt.latency_ms >= 0


def test_error_emits_error_event_and_reraises():
    bus, sink = _bus_with_sink()
    with pytest.raises(RuntimeError):
        bus.call("boom", {})
    assert len(sink.events) == 1
    assert sink.events[0].outcome == "error"
    assert "kaput" in sink.events[0].error


def test_denial_emits_denied_event_without_secrets_or_pii():
    sink = T.InMemorySink()
    bus = M.MCPToolBus(sink=sink)
    bus.register(M.MCPToolDefinition(
        name="update_lead_record",
        description="Update the canonical lead store record.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: {"ok": True},
    ))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("update_lead_record", {"api_key": "sk-live-999", "phone": "+12125550101"})
    denied = sink.denied()
    assert len(denied) == 1
    blob = str(denied[0].to_dict())
    assert "sk-live-999" not in blob
    assert "+12125550101" not in blob and "12125550101" not in blob


def test_default_bus_is_noop_and_records_local_telemetry_only():
    bus = M.MCPToolBus()
    assert isinstance(bus.sink, T.NoOpSink)
    bus.register(M.MCPToolDefinition(
        name="lead_lookup",
        description="Read-only lead lookup.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: {"ok": True},
    ))
    assert bus.call("lead_lookup", {}) == {"ok": True}
    assert len(bus.telemetry) == 1  # local redacted ledger still works


def test_timed_helper_measures_and_emits():
    sink = T.InMemorySink()
    with T.timed(sink, T.TelemetryEvent(trace_id=T.new_trace_id(), kind="agent_step",
                                        agent="probe", task="demo")) as evt:
        evt.model = "deterministic"
    assert len(sink.events) == 1
    assert sink.events[0].outcome == "ok"
    assert sink.events[0].latency_ms >= 0
