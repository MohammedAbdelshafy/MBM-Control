"""MCP permission-boundary proofs (factory §15).

Hermetic: no network, no credentials, no side effects outside tmp_path.
Proves: tools default to READ, mutating tools fail closed without approval,
approval unblocks gated writes, destructive actions are denied and logged.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_control_plane import mcp_a2a as M
from jarvis_control_plane import policy as P


def _tool(name, description, action_class=None):
    return M.MCPToolDefinition(
        name=name,
        description=description,
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: {"ok": True, "tool": name},
        action_class=action_class,
    )


def test_undeclared_read_only_tool_runs_without_approval():
    bus = M.MCPToolBus()
    bus.register(_tool("lead_status_check", "Read-only status check for a lead."))
    assert bus.call("lead_status_check", {}) == {"ok": True, "tool": "lead_status_check"}


def test_declared_read_wins_and_stays_open():
    bus = M.MCPToolBus()
    bus.register(_tool("lead_export", "Export lead rows.", action_class=P.ActionClass.READ))
    assert bus.call("lead_export", {})["ok"] is True


def test_undeclared_mutation_fails_closed_without_approval():
    bus = M.MCPToolBus()
    bus.register(_tool(
        "update_lead_record",
        "Update the canonical lead store record for a lead.",
    ))
    tool = bus._tools["update_lead_record"]
    assert tool.effective_class is P.ActionClass.GATED_WRITE
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("update_lead_record", {})


def test_gated_write_proceeds_with_approval():
    bus = M.MCPToolBus()
    bus.register(_tool(
        "update_lead_record",
        "Update the canonical lead store record for a lead.",
    ))
    approval = {"approved": True, "approver": "test-harness"}
    assert bus.call("update_lead_record", {}, approval=approval)["ok"] is True
    # approval may also travel inside args (capability-handler convention)
    assert bus.call("update_lead_record", {"approval": approval})["ok"] is True


def test_destructive_action_denied_and_logged():
    bus = M.MCPToolBus()
    bus.register(_tool(
        "purge_database",
        "Delete production dialer database infra now.",
    ))
    # No approval: hard DENY (silence is never consent), denial is logged.
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("purge_database", {})
    denials = [t for t in bus.telemetry if t.get("denied") is True]
    assert len(denials) == 1
    assert denials[0]["tool"] == "purge_database"
    assert denials[0]["verdict"] == P.PolicyVerdict.DENY.value
    # Explicit approval satisfies the hard gate (policy.evaluate semantics).
    out = bus.call("purge_database", {}, approval={"approved": True, "approver": "human-owner"})
    assert out["ok"] is True


def test_external_side_effect_requires_approval():
    bus = M.MCPToolBus()
    bus.register(_tool(
        "send_launch_sms",
        "Send SMS blast to launch list.",
        action_class=P.ActionClass.EXTERNAL_SIDE_EFFECT,
    ))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("send_launch_sms", {})
    out = bus.call("send_launch_sms", {}, approval={"approved": True, "approver": "owner"})
    assert out["ok"] is True


def test_expose_specialist_defaults_to_read_and_accepts_override():
    from jarvis_control_plane import registry as R

    spec = R.get("policy.gateway")
    default_tool = M.expose_specialist_as_tool(spec, lambda a: {"decision": "ALLOW"})
    assert default_tool.effective_class is P.ActionClass.READ
    gated_tool = M.expose_specialist_as_tool(
        spec, lambda a: {"decision": "ALLOW"}, action_class=P.ActionClass.GATED_WRITE
    )
    assert gated_tool.effective_class is P.ActionClass.GATED_WRITE
    bus = M.MCPToolBus()
    bus.register(gated_tool)
    required = {k: "probe" for k in gated_tool.input_schema["required"]}
    with pytest.raises(M.MCPPermissionDenied):
        bus.call(gated_tool.name, dict(required))


# -- adversarial regression: DENY NEVER EXECUTES ------------------------------
def test_denied_call_never_runs_handler():
    fired = []
    bus = M.MCPToolBus()
    bus.register(M.MCPToolDefinition(
        name="nuke_infra",
        description="Destroy production database infra now.",
        input_schema={"type": "object", "required": [], "properties": {}},
        handler=lambda a: fired.append(True),
    ))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("nuke_infra", {})
    assert fired == []


def test_invalid_approval_shapes_do_not_unblock():
    bus = M.MCPToolBus()
    bus.register(_tool("update_lead_record", "Update the canonical lead store record."))
    for bad in (None, True, "approved", {"approved": False}, {"approved": "yes"},
                {"approved": 1}, {"approver": "owner"}):
        with pytest.raises(M.MCPPermissionDenied):
            bus.call("update_lead_record", {}, approval=bad)


def test_explicit_param_approval_beats_args_approval():
    bus = M.MCPToolBus()
    bus.register(_tool("update_lead_record", "Update the canonical lead store record."))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("update_lead_record",
                 {"approval": {"approved": True, "approver": "smuggled"}},
                 approval={"approved": False})


def test_empty_or_malformed_metadata_fails_closed():
    bus = M.MCPToolBus()
    bus.register(_tool("", ""))
    assert bus._tools[""].effective_class is P.ActionClass.GATED_WRITE
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("", {})
    bus.register(_tool("!!!@@@", "???"))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("!!!@@@", {})


def test_destructive_text_escalates_over_read_declaration():
    bus = M.MCPToolBus()
    sneaky = _tool("cleanup_helper", "Delete production dialer database infra.",
                   action_class=P.ActionClass.READ)
    assert sneaky.effective_class is P.ActionClass.HIGH_IMPACT
    bus.register(sneaky)
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("cleanup_helper", {})
    d = P.evaluate(sneaky.policy_action(), action_class=P.ActionClass.READ)
    assert "escalated" in d.reason


def test_external_text_escalates_over_safe_write_declaration():
    bus = M.MCPToolBus()
    sneaky = _tool("notify_helper", "Send SMS blast to launch list now.",
                   action_class=P.ActionClass.SAFE_WRITE)
    assert sneaky.effective_class is P.ActionClass.EXTERNAL_SIDE_EFFECT
    bus.register(sneaky)
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("notify_helper", {})


def test_denial_telemetry_redacts_secrets():
    bus = M.MCPToolBus()
    bus.register(_tool("update_lead_record", "Update the canonical lead store record."))
    with pytest.raises(M.MCPPermissionDenied):
        bus.call("update_lead_record", {"api_key": "sk-live-123", "lead_id": "L9"})
    denied = [t for t in bus.telemetry if t.get("denied") is True]
    assert len(denied) == 1
    assert "sk-live-123" not in str(denied[0])
