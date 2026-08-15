"""pipeline tests — end-to-end vertical slice, hermetic (offline)."""
import json

from property_intel.pipeline import load_history, run_pipeline

from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "sample_auction_records.json"


def test_pipeline_offline_never_touches_network():
    report = run_pipeline(SAMPLES, verify_live=False)
    assert report["status"] == "success"
    counts = report["outputs"]["counts"]
    assert counts["ingested"] == 3
    assert counts["normalized"] == 3
    # offline verify -> ownership NOT_FOUND, prime queue must stay empty
    assert counts["prime_queue"] == 0
    for r in report["outputs"]["top_ranked"]:
        assert r["ownership_status"] == "NOT_FOUND"
        assert r["owner"] == ""
    assert report["outputs"]["verification_rate"] == 0.0


def test_pipeline_dedupes_duplicate_records(tmp_path):
    rows = {
        "listings": [
            {"address": "12124 Schroeder Rd, Dallas, TX", "parcel_id": "P1", "source_date": "2026-08-01"},
            {"address": "12124 Schroeder Rd, Dallas, TX", "parcel_id": "P1", "source_date": "2026-08-10"},
        ]
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    report = run_pipeline(p, verify_live=False)
    assert report["outputs"]["counts"]["deduped_removed"] == 1
    assert report["outputs"]["records"] == 1


def test_pipeline_missing_source_reports_blocker(tmp_path):
    report = run_pipeline(tmp_path / "missing.json", verify_live=False)
    assert report["status"] == "skipped"  # nothing normalized, blocker attached
    assert len(report["outputs"]["counts"]["blocked_sources"]) == 1


def test_pipeline_ranks_verified_owner_above_unverified(tmp_path):
    rows = {
        "listings": [
            {"address": "12124 Schroeder Rd, Dallas, TX 75243", "parcel_id": "00000719884000000",
             "auction_date": "2026-08-22", "auction_status": "foreclosure",
             "opening_bid": "225000", "estimated_value": "450000",
             "occupancy_signal": "vacant", "source": "sample-fixture",
             "source_url": "https://auction.com", "source_date": "2026-08-15"},
            {"address": "1 Other Rd, Dallas, TX 75204", "parcel_id": "P9",
             "auction_date": "2026-08-22", "auction_status": "foreclosure",
             "opening_bid": "100000", "estimated_value": "200000",
             "occupancy_signal": "unknown", "source": "sample-fixture",
             "source_url": "https://auction.com", "source_date": "2026-08-15"},
        ]
    }
    p = tmp_path / "two.json"
    p.write_text(json.dumps(rows), encoding="utf-8")

    from property_intel.ownership_verifier import ArcGisAssessorAdapter

    class FakeVerifier(ArcGisAssessorAdapter):
        def verify(self, rec):
            from property_intel.schema import OwnershipVerification
            return OwnershipVerification(
                property_key=rec["dedupe_key"],
                owner_name="CHANDLER TAMECA",
                owner_type="individual",
                parcel_id="00000719884000000",
                verification_status="VERIFIED",
                confidence=0.95,
            )

    # route_pipeline uses verify_ownership() singleton; monkeypatch its internals
    import property_intel.pipeline as pl

    def fake_verify(rec, live=True):
        if rec.get("parcel_id") == "00000719884000000":
            return FakeVerifier("x", "x", {}).verify(rec)
        from property_intel.schema import OwnershipVerification
        return OwnershipVerification(
            property_key=rec["dedupe_key"],
            owner_name="",
            verification_status="NOT_FOUND",
            confidence=0.0,
        )

    pl.verify_ownership = fake_verify
    try:
        report = run_pipeline(p, verify_live=True)
    finally:
        del pl.verify_ownership

    assert report["outputs"]["verification_rate"] == 50.0
    top = report["outputs"]["top_ranked"][0]
    assert top["dedupe_key"].startswith("parcel:00000719884000000")
    assert top["owner"] == "CHANDLER TAMECA"


def test_load_history_variants(tmp_path):
    assert load_history(tmp_path / "missing.json") == []
    p = tmp_path / "hist.json"
    p.write_text(json.dumps({"calls": [{"disposition": "INTERESTED"}]}), encoding="utf-8")
    assert load_history(p) == [{"disposition": "INTERESTED"}]
    p2 = tmp_path / "hist2.json"
    p2.write_text(json.dumps([{"disposition": "SOLD"}]), encoding="utf-8")
    assert load_history(p2) == [{"disposition": "SOLD"}]