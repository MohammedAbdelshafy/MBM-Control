"""
test_content_rewards -- standalone tests for the Content Rewards slice.
Run:  python test_content_rewards.py   (no pytest required)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from mbm_social import content_rewards as cr
from mbm_social.content_rewards import (
    RevenueLedger,
    _ledger_row,
    campaign_eligible,
    discover_campaigns,
    estimate_forecast,
    normalize_campaign,
    plan_campaigns,
    qa_candidate,
    record_verification,
    score_clip_candidate,
    submit,
    update_rpm_priors,
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


RAW = {
    "brand": "dontwatchthis",
    "topic": "mystery",
    "title": "The Vanishing Light",
    "hook": "What you see next is not what it seems.",
    "source_url": "https://example.com/source",
    "transcript_snippet": "and then the lights went out",
    "timestamp_accuracy": 0.95,
    "hook_score": 0.8,
    "estimated_duration_s": 55,
    "target_platform": "youtube",
    "production_minutes": 15.0,
}


def test_normalize() -> None:
    print("normalize")
    c = normalize_campaign(RAW)
    check("brand lowercased", c.brand == "dontwatchthis")
    check("topic normalized", c.topic == "mystery")
    check("id stable", c.id == normalize_campaign(RAW).id)
    check("platform lowered", c.target_platform == "youtube")
    try:
        normalize_campaign({"topic": "x"})
        check("missing brand fails closed", False)
    except cr.ContentRewardsError:
        check("missing brand fails closed", True)


def test_discover() -> None:
    print("discover")
    explicit = discover_campaigns([RAW, {"brand": "cutedosage", "topic": "cute", "hook_score": 0.9}])
    check("explicit discovery count", len(explicit) == 2)
    check("explicit normalized", all(c.brand for c in explicit))
    derived = discover_campaigns()
    check("rule-derived discovery is list", isinstance(derived, list))
    if derived:
        check("rule-derived has brands", all(c.brand and c.topic for c in derived))


def test_eligibility() -> None:
    print("eligibility")
    c = normalize_campaign(RAW)
    ok, reasons = campaign_eligible(c, brand_active=True)
    check("active brand passes", ok and not reasons)
    ok, _ = campaign_eligible(c, brand_active=False)
    check("inactive brand blocks", not ok)
    ok, reasons = campaign_eligible(
        c,
        rule={
            "eligible_topics": ["mystery"],
            "exclude_topics": ["sports"],
            "min_hook_score": 0.6,
        },
    )
    check("topic+hook pass", ok)
    ok, _ = campaign_eligible(c, rule={"eligible_topics": ["cute"]})
    check("topic outside blocks", not ok)
    ok, _ = campaign_eligible(c, rule={"exclude_topics": ["mystery"]})
    check("excluded topic blocks", not ok)
    ok, _ = campaign_eligible(c, rule={"min_hook_score": 0.9})
    check("low hook blocks", not ok)
    ch = {"brand_id": "dontwatchthis", "publish_enabled": True}
    ok, _ = campaign_eligible(c, channel=ch)
    check("channel enabled passes", ok)
    ch2 = {"brand_id": "dontwatchthis", "publish_enabled": False}
    ok, _ = campaign_eligible(c, channel=ch2)
    check("channel disabled blocks", not ok)
    ch3 = {"brand_id": "cutedosage", "publish_enabled": True}
    ok, _ = campaign_eligible(c, channel=ch3)
    check("channel brand mismatch blocks", not ok)


def _fake_views(c: cr.Campaign):
    return (40000.0, 0.7, "channel_rpm_prior")


def test_economics() -> None:
    print("economics")
    c = normalize_campaign(RAW)

    honest = estimate_forecast(c)
    check("no views model => 0 views", honest.estimated_views == 0.0)
    check("no views model => basis no_views_model", honest.basis == "no_views_model")
    check("no views model => 0 net/min", honest.net_revenue_per_production_minute_usd == 0.0)

    f = estimate_forecast(c, views_provider=_fake_views, priors={"dontwatchthis": 6.0})
    check("views from provider", f.estimated_views == 40000.0)
    check("confidence carried", f.confidence == 0.7)
    check("basis carried", f.basis == "channel_rpm_prior")
    check("rpm from prior", f.rpm_estimate_usd == 6.0)
    gross = 40000.0 / 1000.0 * 6.0
    check("gross math", abs(f.expected_gross_revenue_usd - gross) < 1e-6)
    net = gross * 0.7 - 15.0 * 0.10
    check("net math", abs(f.expected_net_revenue_usd - net) < 1e-6)
    per_min = max(net, 0.0) / 15.0
    check("net/min math", abs(f.net_revenue_per_production_minute_usd - per_min) < 1e-9)

    no_prior = estimate_forecast(c, views_provider=_fake_views)
    check("default rpm when no prior", no_prior.rpm_estimate_usd == 1.50)
    check("forecast confidence is views-model confidence", no_prior.confidence == 0.7)


def test_clip_qa() -> None:
    print("clip + qa")
    c = normalize_campaign(RAW)
    clip = score_clip_candidate(c, {"hook_score": 0.8, "has_captions": True, "transcript_evidence": 0.9})
    check("clip total in range", 0.0 <= clip.total <= 1.0)
    check("clip gated", clip.total >= 0.5)
    qa = qa_candidate(c, clip)
    check("qa passes with evidence", qa.passed and not qa.issues)

    bad = normalize_campaign({**RAW, "hook": "", "transcript_snippet": "", "timestamp_accuracy": 0.0})
    qa2 = qa_candidate(bad, score_clip_candidate(bad))
    check("qa fails closed", not qa2.passed and len(qa2.issues) >= 3)

    short = normalize_campaign({**RAW, "estimated_duration_s": 300})
    qa3 = qa_candidate(short, score_clip_candidate(short))
    check("duration out of bounds blocked", not qa3.passed)


def _patch_routing(monkeypatch_submit):
    """Route without touching the real RoutingRegistry."""
    import mbm_social.routing as routing

    class Dst:
        account_id = "yt_dontwatchthis"
        platform = "youtube"
        channel = "@DONTWATCHTHIS1"
        asset_id = "abc123"

    orig = routing.assert_routing_ok
    routing.assert_routing_ok = lambda pkg, fp=None: Dst()
    try:
        return monkeypatch_submit()
    finally:
        routing.assert_routing_ok = orig


def test_submit_verify_ledger() -> None:
    print("submit -> ledger -> verify")
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        ledger = RevenueLedger(path=tmpd / "ledger.jsonl")

        c = normalize_campaign(RAW)
        f = estimate_forecast(c, views_provider=_fake_views, priors={"dontwatchthis": 6.0})

        def run():
            order = submit(c, f, ledger=ledger, submissions_dir=tmpd / "subs")
            check("order queued", order.status == "queued")
            check("order id prefix", order.submission_id.startswith("CR-"))
            check("order routed account", order.account_id == "yt_dontwatchthis")
            row = ledger.find(order.submission_id)
            check("ledger row planned", row is not None and row["stage"] == "planned")
            check("ledger keeps estimates separate", row["verified_views"] is None and row["actual_revenue_usd"] is None)

            try:
                record_verification(ledger, order.submission_id, 50000.0, 8.4, source="")
                check("verification rejects empty source", False)
            except cr.ContentRewardsError:
                check("verification rejects empty source", True)

            row2 = record_verification(ledger, order.submission_id, 50000.0, 8.4, source="youtube_analytics")
            check("row verified", row2.stage == "verified")
            check("verified views recorded", row2.verified_views == 50000.0)
            check("actual revenue recorded", row2.actual_revenue_usd == 8.4)
            check("verification source stored", row2.verification_source == "youtube_analytics")

            s = ledger.summary()
            check("summary counts", s["rows"] == 1 and s["verified"] == 1)
            check("summary separates actual", s["sum_actual_revenue_usd"] == 8.4)
            check("summary estimated untouched", s["sum_estimated_views"] > 0)

            priors = update_rpm_priors({}, ledger)
            rpm = (8.4 / 50000.0) * 1000.0
            check("EWMA prior set", abs(priors["dontwatchthis"] - round(0.25 * rpm + 0.75 * rpm, 4)) < 1e-6)

        _patch_routing(run)


def test_plan() -> None:
    print("planning")
    c = normalize_campaign(RAW)
    c2 = normalize_campaign({**RAW, "topic": "mystery2"})
    ranked = plan_campaigns(
        [c, c2],
        priors={"dontwatchthis": 6.0},
        views_provider=_fake_views,
    )
    check("plan returns tuples", len(ranked) == 2 and all(isinstance(t[1], cr.EconomicForecast) for t in ranked))
    check("plan sorted desc", ranked[0][1].net_revenue_per_production_minute_usd >= ranked[1][1].net_revenue_per_production_minute_usd)


def main() -> int:
    print("content_rewards tests")
    tests = [
        test_normalize,
        test_discover,
        test_eligibility,
        test_economics,
        test_clip_qa,
        test_submit_verify_ledger,
        test_plan,
    ]
    for t in tests:
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