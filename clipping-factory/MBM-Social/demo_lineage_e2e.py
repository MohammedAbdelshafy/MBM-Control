"""
demo_lineage_e2e -- deterministic mock/local E2E for issue #18.

Chain demonstrated (acceptance scenario):
  source -> asset -> campaign -> account -> publication -> metrics -> revenue
plus an economics event and a JARVIS-ranked next action.

Everything runs in a temp dir; nothing touches the real registry/ledgers. Uses
the REAL RoutingRegistry (fails closed) for deterministic destination
resolution. Exits 1 on any assertion failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from mbm_social import asset_lineage as al
from mbm_social import content_rewards as cr
from mbm_social.jarvis_decision import Candidate, make_decision

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL {name} {detail}")


def main() -> int:
    print("=" * 80)
    print("LINEAGE E2E — source -> asset -> campaign -> account -> publication -> metrics -> revenue")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        lineage = al.LineageLedger(path=tmpd / "lineage.jsonl")
        ledger = cr.RevenueLedger(path=tmpd / "ledger.jsonl")

        # 1. SOURCE
        src = al.record_source(
            lineage,
            "https://example.com/source-clip",
            "transcript of the original source material",
        )
        check("source recorded", src.kind == "source" and src.asset_id.startswith("AS-"))

        # 2. ASSET (clip derived from source, keeps family source_id)
        clip = al.derive_asset(
            lineage, src, "clip", filepath=str(tmpd / "clip_cutedosage_15min.mp4")
        )
        check("asset derived", clip.parent_asset_id == src.asset_id and clip.source_id == src.source_id)
        al.set_qa(lineage, clip.asset_id, passed=True)

        # 3. CAMPAIGN + ECONOMICS (estimate only; verified stays empty)
        camp = cr.normalize_campaign(
            {
                "brand": "cutedosage",
                "topic": "cute",
                "title": "Adorable Rescue",
                "hook": "You will smile.",
                "source_url": src.source_id,
                "transcript_snippet": "transcript of the original source material",
                "timestamp_accuracy": 0.9,
                "hook_score": 0.85,
                "estimated_duration_s": 55,
                "target_platform": "youtube_shorts",
                "production_minutes": 15.0,
            }
        )
        forecast = cr.estimate_forecast(camp)
        planned = cr.economics_event("campaign_planned", campaign=camp, forecast=forecast)
        check("economics event planned", planned["event"] == "campaign_planned")
        check("expected labelled estimate", planned["expected_net_revenue_usd"] >= 0 and "actual_revenue_usd" not in planned)

        # 4. ACCOUNT (deterministic routing, real registry, fails closed)
        order = cr.submit(camp, forecast, ledger=ledger, submissions_dir=tmpd / "subs")
        check("campaign routed to account", order.account_id == "yt_cutedosage")
        check("publication planned", order.status == "queued")

        # 5. PUBLICATION (real evidence: upload_id + url)
        pub = al.record_publication(
            lineage, clip.asset_id, "upload_987654321", "youtube", "https://youtube.com/watch?v=abc123"
        )
        check("publication evidence", pub["publication_evidence"]["url"].startswith("https://"))

        # 6. METRICS (platform-reported views, honest separate field)
        cr.transition_submission(ledger, order.submission_id, "submitted")
        verified = cr.transition_submission(
            ledger,
            order.submission_id,
            "verified",
            verified_views=50000.0,
            actual_revenue_usd=12.5,
            source="youtube_analytics",
        )
        check("metrics verified", verified["verified_views"] == 50000.0)
        check("revenue verified separately", verified["actual_revenue_usd"] == 12.5)
        verified_ev = cr.economics_event("campaign_verified", row=verified)
        check("verified event actual", verified_ev["actual_revenue_usd"] == 12.5)

        # 7. REVENUE + JARVIS next action
        decision = make_decision(
            [
                Candidate(
                    candidate_id=clip.asset_id,
                    brand_id="cutedosage",
                    target_platform="youtube_shorts",
                    expected_net_revenue_usd=forecast.expected_net_revenue_usd,
                    confidence=forecast.confidence or 0.5,
                    risk=0.15,
                    production_minutes=forecast.production_minutes,
                )
            ],
            daily_production_minutes=120.0,
        )
        check("JARVIS decision success", decision["status"] == "success")
        check("JARVIS next action", decision["next_action"].startswith("publish "))
        check("JARVIS routes same account", decision["outputs"]["ranked"][0]["account_id"] == "yt_cutedosage")

        # 8. Full family report
        report = al.family_report(lineage, src.source_id)
        check("family report published", report["published"] == 1 and report["assets"] == 2)

        summary = ledger.summary()
        check("ledger revenue separation", summary["sum_actual_revenue_usd"] == 12.5 and summary["verified"] == 1)

    print("\n" + "=" * 80)
    if FAILURES:
        for f in FAILURES:
            print("  FAIL", f)
        print(f"E2E FAILED: {len(FAILURES)} failure(s)")
        return 1
    print("E2E PASSED: full deterministic lineage -> economics -> routing -> JARVIS chain")
    return 0


if __name__ == "__main__":
    sys.exit(main())