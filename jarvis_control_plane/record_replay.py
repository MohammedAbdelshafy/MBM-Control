"""Deterministic record / replay (P0.6).

Every control-plane run records a redacted event trail (inspired by Google's
Race Condition cached-replay pattern):

    run_id / parent_run_id / timestamp / input / workflow_state / decision /
    agent_selected / tool_called / tool_arguments_redacted / policy_decision /
    approval / output / error / state_transition

Secrets are NEVER recorded (policy.redact is applied to args/outputs/errors).

Execution modes — the same workflow runs under all four without code changes:

    LIVE     — real tools, real side effects (policy-gated as usual)
    MOCK     — registered mock handlers answer tool calls (no credits spent)
    REPLAY   — recorded outputs are served back deterministically
    DRY_RUN  — planning + gating only; tools are resolved but never invoked
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .policy import redact


class RunMode(str, Enum):
    LIVE = "LIVE"
    MOCK = "MOCK"
    REPLAY = "REPLAY"
    DRY_RUN = "DRY_RUN"


@dataclass
class RunEvent:
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_run_id: Optional[str] = None
    input: Any = None
    workflow_state: str = ""
    decision: Optional[Dict[str, Any]] = None
    agent_selected: str = ""
    tool_called: str = ""
    tool_arguments_redacted: Any = None
    policy_decision: str = ""
    approval: Optional[Dict[str, Any]] = None
    output: Any = None
    error: str = ""
    state_transition: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunEvent":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RunRecorder:
    """Append-only JSONL recorder. Redacts on write; fail-closed on I/O errors."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: RunEvent) -> RunEvent:
        event.tool_arguments_redacted = redact(event.tool_arguments_redacted)
        event.output = redact(event.output)
        if event.approval:
            event.approval = redact(event.approval)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
        return event

    def load(self, run_id: Optional[str] = None) -> List[RunEvent]:
        if not self.path.exists():
            return []
        events = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                ev = RunEvent.from_dict(json.loads(line))
                if run_id is None or ev.run_id == run_id:
                    events.append(ev)
        return events


ToolHandler = Callable[[Dict[str, Any]], Any]


class ReplayHarness:
    """Execute tool calls under a selected RunMode.

    LIVE: calls the real handler. MOCK: calls a registered mock. REPLAY:
    serves the recorded output for (tool, redacted-args) in order. DRY_RUN:
    returns a planned marker without invoking anything.
    """

    def __init__(
        self,
        mode: RunMode = RunMode.DRY_RUN,
        recorder: Optional[RunRecorder] = None,
        run_id: Optional[str] = None,
    ):
        self.mode = mode
        self.recorder = recorder
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        self._live: Dict[str, ToolHandler] = {}
        self._mocks: Dict[str, ToolHandler] = {}
        self._replay_cursor: Dict[str, int] = {}
        self.invocations: List[Dict[str, Any]] = []  # what was *attempted*

    def register(self, tool: str, handler: ToolHandler, mock: Optional[ToolHandler] = None) -> None:
        self._live[tool] = handler
        if mock is not None:
            self._mocks[tool] = mock

    def call(self, tool: str, args: Optional[Dict[str, Any]] = None, **meta: Any) -> Dict[str, Any]:
        args = dict(args or {})
        attempt = {"tool": tool, "args": redact(args), "mode": self.mode.value}
        self.invocations.append(attempt)

        if self.mode is RunMode.DRY_RUN:
            result: Dict[str, Any] = {"status": "planned_not_executed", "tool": tool, "mode": "DRY_RUN"}
        elif self.mode is RunMode.MOCK:
            if tool not in self._mocks:
                raise KeyError(f"no mock registered for tool: {tool}")
            result = {"status": "ok", "tool": tool, "mode": "MOCK", "output": self._mocks[tool](args)}
        elif self.mode is RunMode.REPLAY:
            result = {"status": "ok", "tool": tool, "mode": "REPLAY", "output": self._replay_next(tool, args)}
        else:  # LIVE
            if tool not in self._live:
                raise KeyError(f"no handler registered for tool: {tool}")
            result = {"status": "ok", "tool": tool, "mode": "LIVE", "output": self._live[tool](args)}

        if self.recorder is not None and self.mode is not RunMode.REPLAY:
            # REPLAY never re-records: serving history must not extend it,
            # otherwise exhaustion checks could never trigger deterministically.
            self.recorder.record(
                RunEvent(
                    run_id=self.run_id,
                    input=redact(args),
                    workflow_state=str(meta.get("workflow_state", "")),
                    decision=meta.get("decision"),
                    agent_selected=str(meta.get("agent_selected", "")),
                    tool_called=tool,
                    tool_arguments_redacted=args,
                    policy_decision=str(meta.get("policy_decision", "")),
                    approval=meta.get("approval"),
                    output=result.get("output"),
                    error="" if result.get("status") in ("ok", "planned_not_executed") else str(result.get("output")),
                    state_transition=str(meta.get("state_transition", "")),
                )
            )
        return result

    def _replay_next(self, tool: str, args: Dict[str, Any]) -> Any:
        if self.recorder is None:
            raise ValueError("REPLAY mode requires a recorder with recorded events")
        prior = [e for e in self.recorder.load(self.run_id) if e.tool_called == tool]
        idx = self._replay_cursor.get(tool, 0)
        if idx >= len(prior):
            raise LookupError(f"replay exhausted for tool {tool} at index {idx}")
        self._replay_cursor[tool] = idx + 1
        return prior[idx].output
