"""
test_moneybeast_engine -- standalone tests for the MoneyBeast refresh pipeline
(jarvis-mbm#8). Covers: scoring, dedupe, stale-source handling, market-vs-property
evidence separation, pipeline ranking, no-fabrication rules.
Run:  python test_moneybeast_engine.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from moneybeast_engine import (
    DEFAULT_SOURCE,
    MoneyBeastRecord,
    audit,
    compute_intent,
    compute_signals,
    compute_urgency,
    dedupe,
    export_csv,
    ingest,
    rank_hot100_growth200,
    refresh,
    score_record,
    transform,
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


VERIFIED = {
    "deal_id": "RE-1",
    "property_address": "123 Main St, Cleveland, OH",
    "city": "Cleveland",
    "county": "Cuyahoga",
    "state": "OH",
    "owner_name_if_publicly_available": "JANE DOE",
    "phone": "+12165550123",
    "motivation_signals": ["foreclosure", "absentee", "out_of_state"],
    "verified_source": "skip_trace_verified",
    "source_url": "https://county.cuyahoga.gov/record/1",
    "source_date": "2026-08-01",
    "observed_date": "2026-08-02",
}


def test_no_fabrication() -> None:
    print("no-fabrication rules")
    blank = transform({"phone": "+19990000000"})
    check("blank record has empty signals", blank.signals == [])
    check("blank composite is 0", blank.composite_score == 0)
    check("blank status REQUIRES_VERIFICATION", blank.status == "REQUIRES_VERIFICATION")
    check("no invented owner", blank.owner_name == "")
    check("no invented address", blank.address == "")


def test_scoring() -> None:
    print("scoring framework")
    r = transform(VERIFIED)
    check("composite in range", 0 <= r.composite_score <= 100)
    check("signals extracted", set(r.signals) == {"foreclosure", "absentee", "out_of_state"})
    check("urgency high for foreclosure", r.urgency_score >= 85)
    check("intent in range", 0 <= r.intent_score <= 100)
    check("status VERIFIED", r.status == "VERIFIED")

    weak = transform({"phone": "+19990000001", "motivation_signals": ["code_concern"]})
    check("weak single signal lower than stacked", weak.composite_score < r.composite_score)

    scores = score_record(VERIFIED)
    total = sum(scores[k] * 1 for k in () )
    check("distress component present", scores["distress_severity"] > 0)
    check("all framework keys", all(k in scores for k in (
        "distress_severity", "recency_urgency", "multi_signal_overlap",
        "seller_fatigue_friction", "property_liquidation_practicality",
        "evidence_confidence", "composite",
    )))


def test_market_vs_property_separation() -> None:
    print("market vs property evidence")
    # Market-only record (no address/parcel) must be capped below Hot100.
    market_only = transform({"phone": "+19990000002", "motivation_signals": ["foreclosure"]})
    check("market-only capped below 40", market_only.composite_score < 40)
    check("market-only flagged", market_only.status == "REQUIRES_VERIFICATION")

    property_level = transform(VERIFIED)
    check("property-level not capped", property_level.composite_score >= 40)


def test_dedupe() -> None:
    print("dedupe")
    a = transform(VERIFIED)
    b = transform({**VERIFIED, "property_address": "123 Main St, Cleveland OH"})
    unique = dedupe([a, b])
    check("same address dedupes", len(unique) == 1)

    c = transform({"phone": "+19990000003"})
    d = transform({"phone": "+19990000003"})
    unique2 = dedupe([c, d])
    check("same phone dedupes", len(unique2) == 1)


def test_stale_source() -> None:
    print("stale source handling")
    stale = transform({**VERIFIED, "status": "STALE", "source_date": "2024-01-01"})
    check("explicit stale kept", stale.status == "STALE")
    scores = score_record({**VERIFIED, "source_date": "2024-01-01"})
    fresh = score_record({**VERIFIED, "source_date": "2026-08-10"})
    check("fresh recency higher", fresh["recency_urgency"] > scores["recency_urgency"])


def test_ranking() -> None:
    print("pipeline ranking")
    strong = transform(VERIFIED)
    weak = transform({"phone": "+19990000005", "motivation_signals": ["code_concern"], "property_address": "456 Oak Ave, Columbus, OH", "state": "OH", "verified_source": "skip_trace_verified"})
    hot, growth = rank_hot100_growth200([weak, strong])
    check("strong in hot100", any(r.lead_id == strong.lead_id for r in hot))
    check("weak in growth or skipped", all(r.lead_id != weak.lead_id for r in hot))
    check("rank is sequential", all(r.rank == i for i, r in enumerate(hot, 1)))


def test_ingest_refresh_export() -> None:
    print("ingest + refresh + export")
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        src = tmpd / "source.json"
        src.write_text(json.dumps([VERIFIED, {"phone": "+19990000006", "motivation_signals": ["probate"]}]), encoding="utf-8")
        report = refresh(source=src, out_dir=tmpd)
        check("ingested count", report["counts"]["ingested"] == 2)
        check("artifacts written", (tmpd / "moneybeast_hot100.csv").exists())
        check("report has top ranked", isinstance(report["top_ranked"], list) and len(report["top_ranked"]) >= 1)
        check("evidence separation keys", "property_level" in report["evidence_separation"])

        aud = audit(source=src)
        check("audit no-write works", aud["counts"]["ingested"] == 2)

        csv_path = tmpd / "export.csv"
        export_csv([strong for strong in [transform(VERIFIED)]], csv_path)
        check("csv written", csv_path.exists() and csv_path.stat().st_size > 0)


def test_missing_source_blocker() -> None:
    print("missing source blocked")
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.json"
        report = refresh(source=missing)
        check("blocked source recorded", len(report["counts"]["blocked_sources"]) == 1)
        check("ingested zero", report["counts"]["ingested"] == 0)


def main() -> int:
    print("moneybeast_engine tests")
    for t in (
        test_no_fabrication,
        test_scoring,
        test_market_vs_property_separation,
        test_dedupe,
        test_stale_source,
        test_ranking,
        test_ingest_refresh_export,
        test_missing_source_blocker,
    ):
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