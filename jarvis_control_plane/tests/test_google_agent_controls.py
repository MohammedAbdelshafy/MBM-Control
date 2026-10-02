"""Hermetic tests for Google-inspired JARVIS agent controls."""

import pytest

from jarvis_control_plane.agent_identity import (
    AgentIdentity,
    AgentIdentityRegistry,
    IdentityDenied,
    require_identity,
)
from jarvis_control_plane.lifecycle import (
    ExecutionReceipt,
    ExecutionStatus,
    ToolLifecycleHooks,
)
from jarvis_control_plane.mcp_a2a import MCPToolBus, MCPToolDefinition
from jarvis_control_plane.policy import ActionClass
from jarvis_control_plane.telemetry import InMemorySink


def test_identity_contract_requires_stable_id_and_capabilities():
    identity = AgentIdentity(
        agent_id="glm.test_engineer",
        capabilities=["test_generation"],
        read_scope=["repo"],
        write_scope=["scoped_working_state"],
    )
    assert identity.agent_id == "glm.test_engineer"
    assert "test_generation" in identity.capabilities


def test_identity_registry_rejects_unknown_agent():
    registry = AgentIdentityRegistry()
    with pytest.raises(IdentityDenied):
        registry.get("ghost.agent")


def test_identity_registry_registers_and_resolves_agent():
    registry = AgentIdentityRegistry()
    identity = AgentIdentity(agent_id="jarvis.test", capabilities=["read_repo"])
    registry.register(identity)
    assert registry.get("jarvis.test") == identity


def test_require_identity_rejects_missing_or_empty_value():
    with pytest.raises(IdentityDenied):
        require_identity(None)
    with pytest.raises(IdentityDenied):
        require_identity("")


def test_receipt_distinguishes_execution_from_business_success():
    receipt = ExecutionReceipt.executed(
        trace_id="tr-test",
        agent_id="jarvis.test",
        tool="demo",
        output={"status": "success", "business_result": "ignored", "token": "TEST_TOKEN_PLACEHOLDER"},
    )
    assert receipt.status is ExecutionStatus.EXECUTED
    assert receipt.business_outcome == "UNVERIFIED"
    assert receipt.tool == "demo"
    assert "TEST_TOKEN_PLACEHOLDER" not in str(receipt.to_dict())


def test_denied_receipt_is_not_execution():
    receipt = ExecutionReceipt.denied(
        trace_id="tr-test",
        agent_id="jarvis.test",
        tool="demo",
        reason="approval required",
    )
    assert receipt.status is ExecutionStatus.DENIED
    assert receipt.business_outcome == "UNVERIFIED"


def test_before_hook_failure_blocks_execution():
    hooks = ToolLifecycleHooks()
    hooks.add_before(lambda **kwargs: (_ for _ in ()).throw(PermissionError("blocked")))
    with pytest.raises(PermissionError):
        hooks.before(tool="demo", agent_id="jarvis.test", args={})


def test_after_hook_receives_receipt():
    hooks = ToolLifecycleHooks()
    seen = []
    hooks.add_after(lambda receipt: seen.append(receipt.status.value))
    receipt = ExecutionReceipt.failed(
        trace_id="tr-test",
        agent_id="jarvis.test",
        tool="demo",
        error="boom",
    )
    hooks.after(receipt)
    assert seen == ["FAILED"]


def test_mcp_side_effect_requires_registered_agent_identity():
    bus = MCPToolBus()
    bus.register(
        MCPToolDefinition(
            name="email_sender",
            description="send email",
            input_schema={"type": "object"},
            handler=lambda args: {"accepted": True},
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
            required_capability="send_email",
        )
    )
    with pytest.raises(PermissionError):
        bus.call(
            "email_sender",
            {},
            approval={"approved": True, "approver": "human"},
        )


def test_mcp_side_effect_requires_capability_and_approval():
    registry = AgentIdentityRegistry()
    registry.register(
        AgentIdentity(agent_id="jarvis.sender", capabilities=["send_email"])
    )
    bus = MCPToolBus(identity_registry=registry)
    bus.register(
        MCPToolDefinition(
            name="email_sender",
            description="send email",
            input_schema={"type": "object"},
            handler=lambda args: {"accepted": True},
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
            required_capability="send_email",
        )
    )

    with pytest.raises(PermissionError):
        bus.call("email_sender", {}, agent_id="jarvis.sender")

    with pytest.raises(PermissionError):
        bus.call(
            "email_sender",
            {},
            agent_id="jarvis.wrong",
            approval={"approved": True, "approver": "human"},
        )

    assert bus.call(
        "email_sender",
        {},
        agent_id="jarvis.sender",
        approval={"approved": True, "approver": "human"},
    ) == {"accepted": True}


def test_mcp_records_execution_receipt_and_does_not_call_it_business_success():
    registry = AgentIdentityRegistry()
    registry.register(AgentIdentity(agent_id="jarvis.sender", capabilities=["send_email"]))
    hooks = ToolLifecycleHooks()
    sink = InMemorySink()
    bus = MCPToolBus(identity_registry=registry, lifecycle=hooks, sink=sink)
    bus.register(
        MCPToolDefinition(
            name="email_sender",
            description="send email",
            input_schema={"type": "object"},
            handler=lambda args: {"status": "success", "token": "TEST_TOKEN_PLACEHOLDER"},
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
            required_capability="send_email",
        )
    )
    result = bus.call(
        "email_sender",
        {"note": "safe"},
        agent_id="jarvis.sender",
        approval={"approved": True, "approver": "human"},
    )
    assert result["status"] == "success"
    assert bus.receipts[-1].status is ExecutionStatus.EXECUTED
    assert bus.receipts[-1].business_outcome == "UNVERIFIED"
    assert "TEST_TOKEN_PLACEHOLDER" not in str(bus.receipts[-1].to_dict())


def test_mcp_denial_receipt_is_redacted():
    sink = InMemorySink()
    bus = MCPToolBus(sink=sink)
    bus.register(
        MCPToolDefinition(
            name="unsafe",
            description="send email",
            input_schema={"type": "object"},
            handler=lambda args: {"status": "success"},
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
            required_capability="send_email",
        )
    )
    with pytest.raises(PermissionError):
        bus.call("unsafe", {"token": "TEST_TOKEN_PLACEHOLDER"})
    assert bus.receipts[-1].status is ExecutionStatus.DENIED
    assert "TEST_TOKEN_PLACEHOLDER" not in str(bus.receipts[-1].to_dict())


def test_mcp_after_hook_receives_execution_receipt():
    seen = []
    hooks = ToolLifecycleHooks()
    hooks.add_after(lambda receipt: seen.append(receipt.status.value))
    bus = MCPToolBus(lifecycle=hooks)
    bus.register(
        MCPToolDefinition(
            name="reader",
            description="read-only lookup",
            input_schema={"type": "object"},
            handler=lambda args: {"value": "ok"},
            action_class=ActionClass.READ,
        )
    )
    assert bus.call("reader", {}) == {"value": "ok"}
    assert seen == ["EXECUTED"]


def test_mcp_invocation_budget_is_hard_and_fail_closed():
    calls = []
    bus = MCPToolBus(max_invocations=1)
    bus.register(
        MCPToolDefinition(
            name="reader",
            description="read-only lookup",
            input_schema={"type": "object"},
            handler=lambda args: calls.append(args) or {"ok": True},
            action_class=ActionClass.READ,
        )
    )
    assert bus.call("reader", {}) == {"ok": True}
    with pytest.raises(RuntimeError):
        bus.call("reader", {})
    assert len(calls) == 1


def test_mcp_read_only_call_remains_backward_compatible():
    bus = MCPToolBus()
    bus.register(
        MCPToolDefinition(
            name="reader",
            description="read-only lookup",
            input_schema={"type": "object"},
            handler=lambda args: {"value": args.get("value", "ok")},
            action_class=ActionClass.READ,
        )
    )
    assert bus.call("reader", {}) == {"value": "ok"}
