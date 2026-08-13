"""
test_agent_economics -- standalone tests (python test_agent_economics.py).
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from mbm_social import agent_economics as ae

PASS = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAILURES
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL {name} {detail}")


def test_cost_estimate() -> None:
    print("cost estimate")
    cost, basis = ae.estimate_cost("qwen2.5-coder:7b", 1000, 1000)
    check("local cost ~0", cost == (2000 / 1000.0) * ae.MODEL_COST_PER_1K["qwen2.5-coder:7b"])
    check("basis labels estimate", "tokens_x_" in basis)
    cost2, _ = ae.estimate_cost("gpt-4o", 1000, 1000)
    check("remote costed higher", cost2 > cost)
    cost3, _ = ae.estimate_cost("unknown-model", 1000, 0, cost_table={"unknown-model": 0.5})
    check("custom table override", cost3 == 0.5)


def test_per_minute() -> None:
    print("revenue per minute")
    check("null minutes -> None", ae._per_minute(10.0, None) is None)
    check("zero minutes -> None", ae._per_minute(10.0, 0) is None)
    check("math", ae._per_minute(10.0, 20.0) == 0.5)


def test_timer_and_ledger() -> None:
    print("timer + ledger")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ae.EconomicsLedger(path=Path(tmp) / "econ.jsonl")

        with ae.TaskTimer("hook_scoring", "qwen2.5-coder:7b") as t:
            t.set_tokens(500, 300)
            t.add_tool_call()
            time.sleep(0.01)
        rec = t.record(ledger, tests="pytest", business_outcome="2/3 hooks gated")
        check("row id", rec.row_id)
        check("latency captured", rec.latency_ms > 0)
        check("tokens captured", rec.prompt_tokens == 500 and rec.completion_tokens == 300)
        check("tool call counted", rec.tool_calls == 1)
        check("no failure", rec.failure is False)
        check("cost positive", rec.estimated_cost_usd > 0)
        check("outcome recorded", rec.business_outcome == "2/3 hooks gated")
        check("revenue None by default", rec.revenue_usd is None and rec.revenue_per_minute_usd is None)

        with ae.TaskTimer("caption_generation", "qwen2.5-coder:7b") as t2:
            t2.set_tokens(200, 100)
            t2.retries_used = 2
        rec2 = t2.record(ledger, revenue_usd=4.5, revenue_minutes=15.0)
        check("retries recorded", rec2.retries == 2)
        check("revenue captured", rec2.revenue_usd == 4.5)
        check("revenue/min", rec2.revenue_per_minute_usd == 0.3)

        s = ledger.summary()
        check("summary rows", s["rows"] == 2)
        check("summary revenue", s["sum_revenue_usd"] == 4.5)
        check("summary cost aggregated", s["sum_estimated_cost_usd"] > 0)
        check("summary failures", s["failures"] == 0)

        cbt = ledger.cost_by_task()
        check("cost by task keys", set(cbt.keys()) == {"hook_scoring", "caption_generation"})

        best = ledger.recommend_cheapest_model("caption_generation")
        check("cheapest model recommend", best == "qwen2.5-coder:7b")

        try:
            ledger.recommend_cheapest_model("never_seen_task")
            check("unknown task fails closed", False)
        except ae.AgentEconomicsError:
            check("unknown task fails closed", True)


def test_failure_flag() -> None:
    print("failure flag")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ae.EconomicsLedger(path=Path(tmp) / "econ.jsonl")
        try:
            with ae.TaskTimer("strategy", "qwen2.5-coder:14b") as t:
                t.set_tokens(10, 10)
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        rec = t.record(ledger)
        check("failure flagged", rec.failure is True)
        check("summary counts failure", ledger.summary()["failures"] == 1)


def main() -> int:
    print("agent_economics tests")
    for t in (test_cost_estimate, test_per_minute, test_timer_and_ledger, test_failure_flag):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {e!r}")
            print(f"  FAIL {t.__name__} raised {e!r}")
    print(f"\nPASS: {PASS}  FAIL: {len(FAILURES)}")
    if FAILURES:
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())