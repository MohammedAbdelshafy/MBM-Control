"""
test_youtube_analytics -- standalone tests (python test_youtube_analytics.py).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from mbm_social import youtube_analytics as ya

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


def test_plan_publication() -> None:
    print("plan + publication id")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ya.VideoLedger(path=Path(tmp) / "videos.jsonl")
        v = ya.plan_video(ledger, "yt_clippingfactorymbm", "clippingfactorymbm", scheduled_for="2026-08-15T10:00:00Z")
        check("scheduled status", v.upload_status == "scheduled")
        check("scheduled_for stored", v.scheduled_for == "2026-08-15T10:00:00Z")
        check("no publication id yet", v.publication_id is None)

        try:
            ya.record_publication_id(ledger, v.video_id, "", "https://youtu.be/x")
            check("empty publication id rejected", False)
        except ya.YouTubeAnalyticsError:
            check("empty publication id rejected", True)

        row = ya.record_publication_id(ledger, v.video_id, "abcXYZ123", "https://youtu.be/abcXYZ123")
        check("publication stored", row["publication_id"] == "abcXYZ123")
        check("status uploaded", row["upload_status"] == "uploaded")


def _fake_provider(video_id: str, channel: str):
    return {
        "views": 250000,
        "avg_view_duration_s": 38.0,
        "subscribers": 1500,
        "us_audience_pct": 41.0,
        "us_watch_time_s": 1580000,
        "revenue_usd": 62.5,
        "monetized_plays": 210000,
    }


def test_analytics() -> None:
    print("analytics + revenue/min")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ya.VideoLedger(path=Path(tmp) / "videos.jsonl")
        v = ya.plan_video(ledger, "yt_clippingfactorymbm", "clippingfactorymbm")
        ya.record_publication_id(ledger, v.video_id, "vid1", "https://youtu.be/vid1")

        row = ya.verify_analytics(ledger, v.video_id, provider=_fake_provider)
        a = row["analytics"]
        check("reported views", a["reported_views"] == 250000)
        check("US audience pct", a["us_audience_pct"] == 41.0)
        check("revenue stored", a["revenue_usd"] == 62.5)
        check("source provider", a["source"] == "provider")
        rpm = 62.5 / (38.0 / 60.0)
        check("revenue/min math", abs(a["revenue_per_minute_usd"] - round(rpm, 4)) < 1e-6)

        manual_row = ya.verify_analytics(
            ledger, v.video_id,
            manual={"views": 10, "avg_view_duration_s": 30, "revenue_usd": 0.02},
        )
        check("manual source", manual_row["analytics"]["source"] == "manual")
        check("manual overrides", manual_row["analytics"]["reported_views"] == 10)

        s = ledger.summary()
        check("summary with reported", s["with_reported_analytics"] == 1)
        check("summary revenue", abs(s["sum_revenue_usd"] - 0.02) < 1e-6)
        check("summary no fabricated rows", s["videos"] == 1)


def test_no_fabrication() -> None:
    print("no fabrication without provider")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ya.VideoLedger(path=Path(tmp) / "videos.jsonl")
        v = ya.plan_video(ledger, "yt_cutedosage", "cutedosage")
        try:
            ya.verify_analytics(ledger, v.video_id, provider=None, manual=None)
            check("refuses to fabricate", False)
        except ya.YouTubeAnalyticsError:
            check("refuses to fabricate", True)
        check("analytics null before verify", ledger.get(v.video_id)["analytics"] == {})


def test_csv_export() -> None:
    print("csv export")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = ya.VideoLedger(path=Path(tmp) / "videos.jsonl")
        v = ya.plan_video(ledger, "yt_dontwatchthis", "dontwatchthis")
        ya.record_publication_id(ledger, v.video_id, "vid2", "https://youtu.be/vid2")
        ya.verify_analytics(ledger, v.video_id, manual={"views": 5000, "avg_view_duration_s": 45, "revenue_usd": 1.2})
        out = Path(tmp) / "videos.csv"
        ya.export_csv(ledger, out)
        text = out.read_text(encoding="utf-8")
        check("csv has header", "revenue_per_minute_usd" in text)
        check("csv has row", "vid2" in text and "1.2" in text)


def main() -> int:
    print("youtube_analytics tests")
    for t in (test_plan_publication, test_analytics, test_no_fabrication, test_csv_export):
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