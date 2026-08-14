"""
test_profit_engine -- standalone tests for the YouTube profit engine (jarvis-mbm #18).
Run:  python test_profit_engine.py
"""
from __future__ import annotations

import sys

from mbm_social.profit_engine import (
    USAudienceInput,
    MonetizationRiskInput,
    ProfitOpportunity,
    ProfitEngineError,
    monetization_risk_score,
    profit_dashboard,
    profit_per_minute,
    rank_profit,
    us_audience_score,
)

PASS = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAILURES
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL {name} {detail}")


def test_us_audience() -> None:
    print("us audience score (measured only)")
    none = us_audience_score(USAudienceInput())
    check("no data => low score", none["score"] < 40)
    check("no data => 0 measured dims", none["measured_analytics_dimensions"] == 0)

    measured = us_audience_score(
        USAudienceInput(us_view_share=0.55, us_watch_time_share=0.5, retention=0.6)
    )
    check("measured score higher", measured["score"] > none["score"])
    check("measured dims counted", measured["measured_analytics_dimensions"] == 3)
    check("score in range", 0 <= measured["score"] <= 100)
    check("components present", "us_view_share" in measured["components"])

    try:
        us_audience_score(USAudienceInput(us_view_share=1.5))
        check("out-of-range share fails closed", False)
    except ProfitEngineError:
        check("out-of-range share fails closed", True)


def test_monetization_risk() -> None:
    print("monetization risk gate")
    safe = monetization_risk_score(MonetizationRiskInput())
    check("clean asset not blocked", not safe["blocked"] and safe["score"] == 0)

    risky = MonetizationRiskInput(
        reused_verbatim_source=True,
        no_original_commentary=True,
        no_editorial_framing=True,
        rights_unclear=True,
    )
    check("hard block triggered", risky_score_blocks(risky))
    check("reasons listed", len(risky_reasons(risky)) >= 4)

    worst = MonetizationRiskInput(
        reused_verbatim_source=True,
        no_original_commentary=True,
        mass_produced_identical=True,
        inauthentic_engagement=True,
    )
    r = monetization_risk_score(worst)
    check("score capped at 100", r["score"] == 100 and r["blocked"])


def risky_score_blocks(inp: MonetizationRiskInput) -> bool:
    return monetization_risk_score(inp)["blocked"]


def risky_reasons(inp: MonetizationRiskInput) -> list:
    return monetization_risk_score(inp)["reasons"]


def test_fast_profit() -> None:
    print("fast-profit ranking")
    cc = ProfitOpportunity("cc-1", "content_rewards", 45.0, 15.0, 0.8, 0.1, True)
    direct = ProfitOpportunity("direct-1", "direct_client", 120.0, 30.0, 0.6, 0.2, True)
    ypp = ProfitOpportunity("ypp-1", "content_rewards", 100.0, 20.0, 0.3, 0.5, False)

    check("per-minute formula", profit_per_minute(cc) > 0)
    ranked = rank_profit([ypp, cc, direct])
    check("cash-realizable first", ranked[0]["cash_realizable"] and ranked[0]["opportunity_id"] in ("cc-1", "direct-1"))
    check("speculative ranked last", ranked[-1]["opportunity_id"] == "ypp-1")
    check("deterministic", [r["opportunity_id"] for r in rank_profit([ypp, cc, direct])] == [r["opportunity_id"] for r in ranked])
    check("expected labelled", all(r["expected_basis"] == "estimate" for r in ranked))

    try:
        profit_per_minute(ProfitOpportunity("x", "content_rewards", 10.0, 0.0, 0.5, 0.1, True))
        check("zero minutes fails closed", False)
    except ProfitEngineError:
        check("zero minutes fails closed", True)


def test_dashboard() -> None:
    print("profit dashboard")
    opps = [
        ProfitOpportunity("cc-1", "content_rewards", 45.0, 15.0, 0.8, 0.1, True),
        ProfitOpportunity("ypp-1", "content_rewards", 100.0, 20.0, 0.3, 0.5, False),
    ]
    d = profit_dashboard(opps)
    check("cash pipeline separated", len(d["cash_realizable_pipeline"]) == 1)
    check("speculative separated", len(d["speculative_platform_revenue"]) == 1)
    check("next action concrete", "cc-1" in d["next_action"])
    check("generated_at present", bool(d["generated_at"]))

    d2 = profit_dashboard([ProfitOpportunity("ypp-2", "content_rewards", 50.0, 10.0, 0.2, 0.5, False)])
    check("no cash => guidance next action", "no cash-realizable" in d2["next_action"])


def main() -> int:
    print("profit_engine tests")
    for t in (test_us_audience, test_monetization_risk, test_fast_profit, test_dashboard):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__} raised: {e!r}")
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