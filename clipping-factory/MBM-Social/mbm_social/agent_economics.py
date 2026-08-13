"""
agent_economics -- capture model/task economics for MBM-Social (issue #18).

For every agent task we record:
  model, task, tokens (prompt + completion), tool_calls, latency_ms,
  retries, failure, estimated_cost_usd, tests, business_outcome,
  revenue_usd (when a real outcome is known) and revenue_per_minute.

RULE: estimated_cost_usd is always an ESTIMATE computed from token counts and
the per-model cost table (`MODEL_COST_PER_1K`). revenue_usd is ONLY set when a
real, source-backed outcome is supplied; nothing is invented. The ledger is
append-only JSON-lines, mirroring ContentRewards/ledger.jsonl.

`TaskTimer` is a context manager that captures latency + retries around any
callable, so any existing task can be wrapped with 2 lines.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
ECON_DIR = ROOT / "AgentEconomics"
LEDGER_PATH = ECON_DIR / "econ.jsonl"

# Estimated USD per 1K tokens (prompt + completion). Local open-weight models
# cost ~0 in $, we charge a tiny amortized GPU epsilon so relative costs are
# comparable; remote models use real list pricing.
MODEL_COST_PER_1K: dict[str, float] = {
    "qwen2.5-coder:7b": 0.00001,
    "qwen2.5-coder:14b": 0.00002,
    "llava:7b": 0.00002,
    "nomic-embed-text:latest": 0.000005,
    "gemini-2.5-flash": 0.0001,
    "gpt-4o-mini": 0.0010,
    "gpt-4o": 0.0050,
}
DEFAULT_COST_PER_1K = 0.00001
DEFAULT_OUTCOME_CLAIM = "not_recorded"  # honest default: no invented outcome


class AgentEconomicsError(Exception):
    """Raised when an economics invariant is violated."""


@dataclass
class TaskRecord:
    row_id: str
    timestamp_iso: str
    task: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    tool_calls: int
    latency_ms: float
    retries: int
    failure: bool
    estimated_cost_usd: float
    cost_basis: str
    tests: str
    business_outcome: str
    revenue_usd: Optional[float]
    revenue_minutes: Optional[float]
    revenue_per_minute_usd: Optional[float]

    def as_dict(self) -> dict:
        return asdict(self)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_table: Optional[dict[str, float]] = None,
) -> tuple[float, str]:
    """Estimate USD cost from tokens. Always labelled as an estimate."""
    table = dict(MODEL_COST_PER_1K)
    if cost_table:
        table.update(cost_table)
    rate = table.get(model, DEFAULT_COST_PER_1K)
    return (prompt_tokens + completion_tokens) / 1000.0 * rate, f"tokens_x_{rate:.7f}/1k"


def _per_minute(revenue: float, minutes: Optional[float]) -> Optional[float]:
    if minutes is None or minutes <= 0:
        return None
    return round(revenue / minutes, 4)


class TaskTimer:
    """Context manager: run a task, capture latency; re-run on retry up to n."""

    def __init__(self, task: str, model: str, retries: int = 0) -> None:
        self.task = task
        self.model = model
        self.max_retries = retries
        self.latency_ms = 0.0
        self.retries_used = 0
        self.failure = False
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tool_calls = 0
        self.result: Any = None

    def __enter__(self) -> "TaskTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.latency_ms = (time.perf_counter() - self._start) * 1000.0
        if exc_type is not None:
            self.failure = True
        return False  # propagate exceptions; caller decides

    def set_tokens(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = int(prompt)
        self.completion_tokens = int(completion)

    def add_tool_call(self, count: int = 1) -> None:
        self.tool_calls += int(count)

    def record(
        self,
        ledger: Optional["EconomicsLedger"] = None,
        *,
        tests: str = "",
        business_outcome: str = DEFAULT_OUTCOME_CLAIM,
        revenue_usd: Optional[float] = None,
        revenue_minutes: Optional[float] = None,
        cost_table: Optional[dict[str, float]] = None,
    ) -> TaskRecord:
        cost, basis = estimate_cost(
            self.model, self.prompt_tokens, self.completion_tokens, cost_table
        )
        rec = TaskRecord(
            row_id=str(uuid.uuid4()),
            timestamp_iso=_iso_now(),
            task=self.task,
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            tool_calls=self.tool_calls,
            latency_ms=round(self.latency_ms, 2),
            retries=self.retries_used,
            failure=self.failure,
            estimated_cost_usd=round(cost, 7),
            cost_basis=basis,
            tests=tests,
            business_outcome=business_outcome,
            revenue_usd=revenue_usd,
            revenue_minutes=revenue_minutes,
            revenue_per_minute_usd=_per_minute(revenue_usd, revenue_minutes)
            if revenue_usd is not None
            else None,
        )
        if ledger is not None:
            ledger.append(rec)
        return rec


class EconomicsLedger:
    """Append-only JSON-lines ledger for agent economics."""

    def __init__(self, path: Path = LEDGER_PATH) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def append(self, rec: TaskRecord) -> None:
        rows = self._load()
        rows.append(rec.as_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

    def summary(self) -> dict:
        rows = self._load()
        failures = [r for r in rows if r["failure"]]
        costed = sum(r["estimated_cost_usd"] for r in rows)
        tokens = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows)
        latency = [r["latency_ms"] for r in rows]
        with_revenue = [r for r in rows if r["revenue_usd"] is not None]
        return {
            "rows": len(rows),
            "failures": len(failures),
            "sum_estimated_cost_usd": round(costed, 7),
            "sum_tokens": tokens,
            "avg_latency_ms": round(sum(latency) / len(latency), 2) if latency else 0.0,
            "sum_revenue_usd": round(sum(r["revenue_usd"] or 0.0 for r in with_revenue), 2),
            "with_revenue_records": len(with_revenue),
        }

    def cost_by_task(self) -> dict[str, float]:
        rows = self._load()
        out: dict[str, float] = {}
        for r in rows:
            out[r["task"]] = round(out.get(r["task"], 0.0) + r["estimated_cost_usd"], 7)
        return out

    def recommend_cheapest_model(
        self, task: str, candidates: Optional[list[str]] = None
    ) -> str:
        """Cheapest recorded model that has succeeded on this task."""
        rows = [r for r in self._load() if r["task"] == task and not r["failure"]]
        if not rows:
            raise AgentEconomicsError(
                f"no successful records for task '{task}' — cannot recommend"
            )
        pool = candidates or [r["model"] for r in rows]
        pool = set(pool)
        best = min(
            (r for r in rows if r["model"] in pool),
            key=lambda r: r["estimated_cost_usd"],
        )
        return best["model"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Agent economics ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="print aggregate summary")
    sub.add_parser("cost-by-task", help="print cost grouped by task")
    sub.add_parser("rows", help="print raw rows")
    args = parser.parse_args(argv)

    ledger = EconomicsLedger()
    if args.command == "summary":
        print(json.dumps(ledger.summary(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "cost-by-task":
        print(json.dumps(ledger.cost_by_task(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "rows":
        for r in ledger._load():
            print(json.dumps(r, ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())