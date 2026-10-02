"""Provider-neutral tool lifecycle hooks and execution receipts.

The lifecycle mirrors the useful part of modern agent harnesses: a
pre-execution policy hook, real tool execution, a post-execution receipt, and
telemetry. A receipt records execution facts only. It never upgrades a tool
return value into business success.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List

from .policy import redact


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
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def executed(
        cls,
        trace_id: str,
        agent_id: str,
        tool: str,
        output: Any = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExecutionReceipt":
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.EXECUTED,
            output=redact(output),
            metadata=redact(metadata or {}),
        )

    @classmethod
    def failed(
        cls,
        trace_id: str,
        agent_id: str,
        tool: str,
        error: str,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExecutionReceipt":
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.FAILED,
            error=str(redact(error))[:500],
            metadata=redact(metadata or {}),
        )

    @classmethod
    def denied(
        cls,
        trace_id: str,
        agent_id: str,
        tool: str,
        reason: str,
        metadata: Dict[str, Any] | None = None,
    ) -> "ExecutionReceipt":
        return cls(
            trace_id=trace_id,
            agent_id=agent_id,
            tool=tool,
            status=ExecutionStatus.DENIED,
            error=str(redact(reason))[:500],
            metadata=redact(metadata or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return redact(data)


BeforeHook = Callable[..., None]
AfterHook = Callable[[ExecutionReceipt], None]


class ToolLifecycleHooks:
    """Ordered hook collection around tool execution."""

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
