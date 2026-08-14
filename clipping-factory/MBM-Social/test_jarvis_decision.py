"""
test_jarvis_decision -- standalone tests for JARVIS capacity-aware ranking (issue #18).
Run:  python test_jarvis_decision.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from mbm_social.jarvis_decision import (
    Candidate,
    JarvisDecisionError,
    make_decision,
    rank_candidates,
    score_candidate,
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


def _cands() -> list[Candidate]:
    return [
        Candidate(
            candidate_id="c1",
            brand_id="clippingfactorymbm",
            target_platform="youtube_shorts",
            expected_net_revenue_usd=30.0,
            confidence=0.8,
            risk=0.2,
            production_minutes=20.0,
        ),
        Candidate(
            candidate_id="c2",
            brand_id="clippingfactorymbm",
            target_platform="tiktok",
            expected_net_revenue_usd=45.0,
            confidence=0.9,
            risk=0.1,
            production_minutes=30.0,
        ),
        Candidate(
            candidate_id="c3",
            brand_id="cutedosage",
            target_platform="youtube",
            expected_net_revenue_usd=10.0,
            confidence=0.5,
            risk=0.4,
            production_minutes=15.0,
        ),
    ]


def test_scoring() -> None:
    print("scoring")
    c1, c2, c3 = _cands()
    s1 = score_candidate(c1)
    s2 = score_candidate(c2)
    s3 = score_candidate(c3)
    check("scores in range", all(0.0 <= s <= 1.0 for s in (s1, s2, s3)))
    check("higher value+confidence ranks higher", s2 > s1 > s3)
    check("zero value scores zero", score_candidate(Candidate("z", "b", "youtube", 0.0, 0.8, 0.2, 10.0)) == 0.0)

    try:
        score_candidate(Candidate("x", "b", "youtube", 5.0, 1.5, 0.2, 10.0))
        check("out-of-range confidence fails closed", False)
    except JarvisDecisionError:
        check("out-of-range confidence fails closed", True)

    try:
        score_candidate(Candidate("x", "b", "youtube", -1.0, 0.8, 0.2, 10.0))
        check("negative revenue fails closed", False)
    except JarvisDecisionError:
        check("negative revenue fails closed", True)


def test_ranking_capacity() -> None:
    print("capacity-aware ranking")
    cands = _cands()
    ranked = rank_candidates(cands, daily_production_minutes=30.0)
    selected = [r for r in ranked if r["status"] == "SELECTED"]
    check("top candidate selected", selected and selected[0]["candidate_id"] == "c2")
    total_min = sum(r["production_minutes"] for r in selected)
    check("capacity respected", total_min <= 30.0)
    check("expected labelled estimate", all(r["expected_basis"] == "estimate" for r in selected))
    check("destination resolved", selected and selected[0]["account_id"].startswith(("yt_", "tt_")))

    capped = rank_candidates(cands, daily_production_minutes=100.0, max_actions=2)
    sel = [r for r in capped if r["status"] == "SELECTED"]
    check("max_actions respected", len(sel) == 2)

    none = rank_candidates(cands, daily_production_minutes=0.0)
    check("zero budget => none selected", all(r["status"] != "SELECTED" for r in none))


def test_decision_contract() -> None:
    print("decision output contract")
    d = make_decision(_cands(), daily_production_minutes=30.0)
    check("status success", d["status"] == "success")
    check("next_action publish", d["next_action"].startswith("publish "))
    check("outputs.selected non-empty", len(d["outputs"]["selected"]) == 1)
    check("owner system", d["owner"] == "system")
    check("timestamp present", bool(d["timestamp"]))
    check("errors empty", d["errors"] == [])

    d2 = make_decision([], daily_production_minutes=30.0)
    check("empty => skipped", d2["status"] == "skipped")
    check("empty next_action", "no candidates" in d2["next_action"])


def test_unroutable_fails_closed() -> None:
    print("unroutable fails closed")
    cand = Candidate(
        candidate_id="ghost",
        brand_id="nonexistentbrand",
        target_platform="youtube",
        expected_net_revenue_usd=100.0,
        confidence=0.9,
        risk=0.1,
        production_minutes=10.0,
    )
    ranked = rank_candidates([cand], daily_production_minutes=100.0)
    check("unroutable surfaced", ranked[0]["status"] == "UNROUTABLE")
    check("reason recorded", bool(ranked[0].get("reason")))
    d = make_decision([cand], daily_production_minutes=100.0)
    check("decision blocked", d["status"] == "blocked")
    check("error surfaced", len(d["errors"]) == 1)


def main() -> int:
    print("jarvis_decision tests")
    for t in (test_scoring, test_ranking_capacity, test_decision_contract, test_unroutable_fails_closed):
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