# Google-Inspired JARVIS Agent Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provider-neutral agent identity, lifecycle hooks, execution receipts, and budget guards to the existing JARVIS control plane, copying the highest-value Google/Antigravity control patterns without adding cloud dependencies.

**Architecture:** Reuse the existing `policy.py`, `registry.py`, `mcp_a2a.py`, and `telemetry.py` control-plane primitives. Add a small identity contract and lifecycle hook/receipt layer at the MCP execution boundary. Keep external transports and Google Cloud services out of scope.

**Tech Stack:** Python 3, Pydantic v2, dataclasses, pytest, existing JARVIS control-plane modules.

**Spec:** Google AI/Google Cloud radar dated 2026-09-19 plus the user's implementation request.

## Global Constraints

- Base branch: current `master` at `487c2e254fa731061163727d9e9537387c3e990e`.
- No Google Cloud resource creation or credential changes.
- No live provider calls.
- MCP remains the tool/data boundary; A2A remains the agent/agent boundary.
- Policy remains the sole authorization decision point.
- Execution receipts record facts and provenance; they never infer business success.
- Existing read-only callers must remain compatible.
- Side-effecting or gated calls require a known agent identity.
- Budgets are hard limits and fail closed.

## Review Focus

1. A side-effecting MCP call without an agent identity must be rejected before handler execution.
2. A policy-denied call must still emit a denial receipt without leaking secrets.
3. A handler returning a value must be recorded as executed, not as business-success.
4. Hook failures must fail closed and must not run the handler.
5. Budget exhaustion must stop further attempts deterministically.

---

### Task 1: Agent Identity Contract

**Files:**
- Create: `jarvis_control_plane/agent_identity.py`
- Modify: `jarvis_control_plane/__init__.py`
- Test: `jarvis_control_plane/tests/test_agent_identity.py`

**Interfaces:**
- Produces `AgentIdentity`, `AgentIdentityRegistry`, `IdentityDenied`, and `require_identity()`.
- Consumes existing `ControlPlaneAgentSpec` metadata from `registry.py`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from jarvis_control_plane.agent_identity import (
    AgentIdentity,
    AgentIdentityRegistry,
    IdentityDenied,
    require_identity,
)


def test_identity_requires_stable_id_and_capabilities():
    identity = AgentIdentity(
        agent_id="glm.test_engineer",
        capabilities=["test_generation"],
        read_scope=["repo"],
        write_scope=["scoped_working_state"],
    )
    assert identity.agent_id == "glm.test_engineer"
    assert "test_generation" in identity.capabilities


def test_registry_rejects_unknown_identity():
    registry = AgentIdentityRegistry()
    with pytest.raises(IdentityDenied):
        registry.get("ghost.agent")


def test_registry_registers_and_resolves_identity():
    registry = AgentIdentityRegistry()
    identity = AgentIdentity(agent_id="jarvis.test", capabilities=["read_repo"])
    registry.register(identity)
    assert registry.get("jarvis.test") == identity


def test_require_identity_rejects_missing_value():
    with pytest.raises(IdentityDenied):
        require_identity(None)


def test_require_identity_rejects_empty_value():
    with pytest.raises(IdentityDenied):
        require_identity("")
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest jarvis_control_plane/tests/test_agent_identity.py -q`

Expected: FAIL because `jarvis_control_plane.agent_identity` does not yet exist.

- [ ] **Step 3: Implement the minimal identity contract**

```python
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class IdentityDenied(PermissionError):
    """Raised when an agent identity cannot be established."""


class AgentIdentity(BaseModel):
    agent_id: str
    capabilities: List[str] = Field(default_factory=list)
    read_scope: List[str] = Field(default_factory=list)
    write_scope: List[str] = Field(default_factory=list)


class AgentIdentityRegistry:
    def __init__(self) -> None:
        self._identities: Dict[str, AgentIdentity] = {}

    def register(self, identity: AgentIdentity) -> None:
        if not identity.agent_id.strip():
            raise IdentityDenied("agent_id must be non-empty")
        self._identities[identity.agent_id] = identity

    def get(self, agent_id: str) -> AgentIdentity:
        if not agent_id or not agent_id.strip():
            raise IdentityDenied("agent identity is required")
        try:
            return self._identities[agent_id]
        except KeyError as exc:
            raise IdentityDenied(f"unknown agent identity: {agent_id}") from exc


def require_identity(agent_id: str | None) -> str:
    if not agent_id or not agent_id.strip():
        raise IdentityDenied("agent identity is required")
    return agent_id
```

- [ ] **Step 4: Run the focused tests**

Run: `pytest jarvis_control_plane/tests/test_agent_identity.py -q`

Expected: PASS with 5 tests passing.

- [ ] **Step 5: Export the public contract**

Add the new types to `jarvis_control_plane/__init__.py` without changing existing exports.

- [ ] **Step 6: Run import verification**

Run: `python -c "from jarvis_control_plane import AgentIdentity, AgentIdentityRegistry, IdentityDenied; print('ok')"`

Expected: `ok`.

---

### Task 2: Lifecycle Hooks + Execution Receipt

**Files:**
- Create: `jarvis_control_plane/lifecycle.py`
- Test: `jarvis_control_plane/tests/test_lifecycle.py`

**Interfaces:**
- Produces `ToolLifecycleHooks`, `ExecutionReceipt`, `ExecutionStatus`.
- Consumes `AgentIdentity` and existing `PolicyDecision` semantics.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from jarvis_control_plane.lifecycle import (
    ExecutionReceipt,
    ExecutionStatus,
    ToolLifecycleHooks,
)


def test_receipt_distinguishes_execution_from_business_success():
    receipt = ExecutionReceipt.executed(
        trace_id="tr-test",
        agent_id="jarvis.test",
        tool="demo",
        output={"status": "success", "business_result": "ignored"},
    )
    assert receipt.status is ExecutionStatus.EXECUTED
    assert receipt.business_outcome == "UNVERIFIED"
    assert receipt.tool == "demo"


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
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest jarvis_control_plane/tests/test_lifecycle.py -q`

Expected: FAIL because `jarvis_control_plane.lifecycle` does not yet exist.

- [ ] **Step 3: Implement minimal lifecycle/receipt primitives**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional


class ExecutionStatus(str, Enum):
    PLANNED = "PLANNED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    DENIED = "DENIED"


@dataclass
class ExecutionReceipt:
    trace_id: str
    agent_id: str
    tool: str
    status: ExecutionStatus
    business_outcome: str = "UNVERIFIED"
    output: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def executed(cls, trace_id: str, agent_id: str, tool: str, output: Any = None):
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.EXECUTED,
            output=output,
        )

    @classmethod
    def failed(cls, trace_id: str, agent_id: str, tool: str, error: str):
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.FAILED,
            error=error[:500],
        )

    @classmethod
    def denied(cls, trace_id: str, agent_id: str, tool: str, reason: str):
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.DENIED,
            error=reason[:500],
        )


BeforeHook = Callable[..., None]
AfterHook = Callable[[ExecutionReceipt], None]


class ToolLifecycleHooks:
    def __init__(self) -> None:
        self._before: List[BeforeHook] = []
        self._after: List[AfterHook] = []

    def add_before(self, hook: BeforeHook) -> None:
        self._before.append(hook)

    def add_after(self, hook: AfterHook) -> None:
        self._after.append(hook)

    def before(self, **kwargs: Any) -> None:
        for hook in self._before:
            hook(**kwargs)

    def after(self, receipt: ExecutionReceipt) -> None:
        for hook in self._after:
            hook(receipt)
```

- [ ] **Step 4: Run the focused tests**

Run: `pytest jarvis_control_plane/tests/test_lifecycle.py -q`

Expected: PASS with 4 tests passing.

---

### Task 3: Integrate Identity, Hooks and Receipts into MCPToolBus

**Files:**
- Modify: `jarvis_control_plane/mcp_a2a.py`
- Modify: `jarvis_control_plane/__init__.py`
- Test: `jarvis_control_plane/tests/test_control_plane.py`

**Interfaces:**
- `MCPToolDefinition.required_capability`: optional capability string.
- `MCPToolBus.__init__(sink=None, lifecycle=None)`.
- `MCPToolBus.call(..., agent_id=None)` remains backward compatible for READ tools.
- GATED_WRITE and EXTERNAL_SIDE_EFFECT calls require registered identity when `required_capability` is set.
- Receipts are stored as `bus.receipts`.

- [ ] **Step 1: Add failing regression tests**

Append tests:

```python
def test_mcp_side_effect_requires_agent_identity_and_capability():
    from jarvis_control_plane import (
        AgentIdentity,
        AgentIdentityRegistry,
        MCPToolBus,
        MCPToolDefinition,
    )
    from jarvis_control_plane.policy import ActionClass

    registry = AgentIdentityRegistry()
    registry.register(AgentIdentity(
        agent_id="jarvis.sender",
        capabilities=["send_email"],
    ))

    bus = MCPToolBus(identity_registry=registry)
    bus.register(MCPToolDefinition(
        name="email_sender",
        description="send email",
        input_schema={"type": "object"},
        handler=lambda args: {"accepted": True},
        action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        required_capability="send_email",
    ))

    with pytest.raises(PermissionError):
        bus.call("email_sender", {}, approval={"approved": True, "approver": "human"})

    with pytest.raises(PermissionError):
        bus.call(
            "email_sender",
            {},
            agent_id="jarvis.sender",
        )

    receipt_before = len(bus.receipts)
    with pytest.raises(Exception):
        bus.call(
            "email_sender",
            {},
            approval={"approved": True, "approver": "human"},
            agent_id="jarvis.sender",
        )

    assert len(bus.receipts) == receipt_before + 1
    assert bus.receipts[-1].status.value == "EXECUTED"


def test_mcp_denial_receipt_is_recorded_without_secret_leakage():
    from jarvis_control_plane import (
        AgentIdentityRegistry,
        InMemorySink,
        MCPToolBus,
        MCPToolDefinition,
    )
    from jarvis_control_plane.policy import ActionClass

    sink = InMemorySink()
    bus = MCPToolBus(sink=sink, identity_registry=AgentIdentityRegistry())
    bus.register(MCPToolDefinition(
        name="unsafe",
        description="send email",
        input_schema={"type": "object"},
        handler=lambda args: {"status": "success"},
        action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
    ))

    with pytest.raises(PermissionError):
        bus.call("unsafe", {"token": "sk-test-secret"})

    assert bus.receipts[-1].status.value == "DENIED"
    assert "sk-test-secret" not in str(bus.receipts[-1].metadata)


def test_mcp_after_hook_failure_does_not_convert_execution_into_success():
    from jarvis_control_plane import MCPToolBus, MCPToolDefinition, ToolLifecycleHooks

    hooks = ToolLifecycleHooks()
    seen = []
    hooks.add_after(lambda receipt: seen.append(receipt.status.value))

    bus = MCPToolBus(lifecycle=hooks)
    bus.register(MCPToolDefinition(
        name="reader",
        description="read-only lookup",
        input_schema={"type": "object"},
        handler=lambda args: {"value": "ok"},
    ))

    assert bus.call("reader", {}) == {"value": "ok"}
    assert seen == ["EXECUTED"]
```

- [ ] **Step 2: Run the focused control-plane tests**

Run: `pytest jarvis_control_plane/tests/test_control_plane.py -q`

Expected: FAIL because the MCP bus does not yet accept the new identity/lifecycle arguments.

- [ ] **Step 3: Implement the smallest MCP integration**

Requirements:

1. Import `require_identity`, identity registry, lifecycle hooks and receipts.
2. Add `required_capability: Optional[str] = None` to `MCPToolDefinition`.
3. Add optional `identity_registry` and `lifecycle` to `MCPToolBus.__init__`.
4. Add `self.receipts = []`.
5. Extend `call(..., agent_id=None)`.
6. Resolve policy before handler.
7. For EXTERNAL_SIDE_EFFECT or GATED_WRITE tools with `required_capability`, require:
   - non-empty `agent_id`
   - known identity
   - capability membership
8. Invoke `lifecycle.before` immediately before handler execution.
9. On denial, append a DENIED receipt and emit redacted telemetry.
10. On handler success, append an EXECUTED receipt, explicitly keeping `business_outcome="UNVERIFIED"`.
11. On handler exception, append FAILED receipt before re-raising.
12. Run after-hooks with the receipt.
13. Never inspect a handler's `{"status": "success"}` as proof of business success.

- [ ] **Step 4: Run the entire JARVIS control-plane suite**

Run: `pytest jarvis_control_plane/tests -q`

Expected: all existing tests plus the new tests pass.

---

### Task 4: Add Hard Budget Guards

**Files:**
- Modify: `jarvis_control_plane/mcp_a2a.py`
- Test: `jarvis_control_plane/tests/test_control_plane.py`

**Interfaces:**
- `MCPToolBus.__init__(..., max_invocations: Optional[int] = None)`.
- Once the invocation limit is reached, the bus raises `RuntimeError` before handler execution.

- [ ] **Step 1: Add failing budget test**

```python
def test_mcp_invocation_budget_is_hard_and_fail_closed():
    from jarvis_control_plane import MCPToolBus, MCPToolDefinition

    calls = []

    bus = MCPToolBus(max_invocations=1)
    bus.register(MCPToolDefinition(
        name="reader",
        description="read-only lookup",
        input_schema={"type": "object"},
        handler=lambda args: calls.append(args) or {"ok": True},
    ))

    assert bus.call("reader", {}) == {"ok": True}
    with pytest.raises(RuntimeError):
        bus.call("reader", {})

    assert len(calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest jarvis_control_plane/tests/test_control_plane.py::test_mcp_invocation_budget_is_hard_and_fail_closed -q`

Expected: FAIL because `max_invocations` is not supported.

- [ ] **Step 3: Implement budget guard**

Track invocation count separately from handler attempts.

Before policy/handler execution:

```python
if self.max_invocations is not None and self._invocation_count >= self.max_invocations:
    raise RuntimeError("MCP invocation budget exhausted")
```

Increment the count exactly once per accepted call attempt.

Do not reset the counter on retries.

- [ ] **Step 4: Run focused and full suites**

Run:
- `pytest jarvis_control_plane/tests/test_control_plane.py::test_mcp_invocation_budget_is_hard_and_fail_closed -q`
- `pytest jarvis_control_plane/tests -q`

Expected: both pass.

---

### Task 5: Final Verification

**Files:**
- No new source files.
- Modify only files covered by Tasks 1-4.

- [ ] **Step 1: Search for fabricated execution claims**

Run:

```bash
git grep -n -E 'status["'"']?[[:space:]]*:[[:space:]]*["'"']success|time\.sleep\(2\)|revenue_impact.*1000|status=["'"']PRODUCTIVE["'"']|deployment_status=["'"']DEPLOYED["'"']' -- jarvis_control_plane MBM
```

Expected: no newly introduced fake-success matches in the touched control-plane code.

- [ ] **Step 2: Run the full JARVIS test suite**

Run: `pytest jarvis_control_plane/tests -q`

Expected: 0 failures.

- [ ] **Step 3: Run Python syntax compilation for touched Python files**

Run:

```bash
python -m py_compile   jarvis_control_plane/agent_identity.py   jarvis_control_plane/lifecycle.py   jarvis_control_plane/mcp_a2a.py   jarvis_control_plane/__init__.py
```

Expected: exit 0 with no syntax errors.

- [ ] **Step 4: Inspect the diff**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 5: Create the pull request**

Open a PR from:

`feat/jarvis-google-agent-controls-20260919`

to:

`master`

Title:

`feat: add Google-inspired JARVIS agent controls`

PR body must state:

- provider-neutral implementation
- no Google Cloud resource changes
- no credential changes
- no live provider calls
- identity + lifecycle hooks + execution receipts + budget guards
- execution receipt does not imply business success
- exact tests/CI results

Do not merge the PR.

---

## Completion Gate

The branch is considered ready for review only when:

- agent identity is explicit for capability-gated side effects
- policy remains authoritative
- lifecycle hooks execute around tool calls
- receipts distinguish EXECUTED from business outcome
- denial/failure receipts are redacted
- invocation budgets fail closed
- all touched tests pass
- GitHub CI provides fresh evidence
- no live side effects occurred
