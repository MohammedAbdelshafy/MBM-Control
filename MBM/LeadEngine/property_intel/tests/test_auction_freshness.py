"""auction_freshness tests — parsing, scoring, normalization (no network)."""
from datetime import datetime, timedelta, timezone

from property_intel.auction_freshness import (
    days_until_auction,
    load_source,
    rows_to_properties,
    score_freshness,
)
from property_intel.normalize import normalize_record

FUTURE = (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat()


def test_days_until_auction_parse():
    assert days_until_auction(FUTURE) >= 4  # within ~5 days
    assert days_until_auction("garbage") is None
    assert days_until_auction("") is None


def test_days_until_auction_handles_z_suffix():
    dt = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    assert days_until_auction(dt.replace("+00:00", "Z")) is not None


def test_score_freshness_recency_near():
    s = score_freshness({"auction_date": FUTURE, "auction_status": "foreclosure"})
    assert s["components"]["recency"] >= 90
    assert s["components"]["status"] >= 25
    assert any("within 7 days" in r for r in s["reasons"])


def test_score_freshness_no_date_scores_low():
    s = score_freshness({"auction_status": "foreclosure"})
    assert s["components"]["recency"] == 20
    assert any("no auction date" in r for r in s["reasons"])


def test_score_freshness_apn_and_evidence_boost():
    s = score_freshness({"auction_date": FUTURE, "auction_status": "foreclosure",
                         "parcel_id": "P1", "source": "auction.com", "source_url": "https://auction.com"})
    assert s["components"]["apn"] == 100
    assert s["components"]["evidence"] == 100


def test_rows_to_properties_normalizes_and_scores():
    rows = [{
        "address": "12124 Schroeder Rd, Dallas, TX 75243",
        "auction_date": FUTURE,
        "auction_status": "foreclosure",
        "opening_bid": "225000",
        "estimated_value": "450000",
        "parcel_id": "00000719884000000",
        "source": "sample-fixture",
        "source_url": "https://auction.com",
    }]
    props = rows_to_properties(rows)
    assert len(props) == 1
    p = props[0]
    assert p["dedupe_key"] == "parcel:00000719884000000"
    assert p["auction_status"] == "foreclosure"
    assert 0 <= p["freshness_score"] <= 100
    assert "freshness_components" in p


def test_rows_to_properties_defaults_status_to_foreclosure():
    props = rows_to_properties([{"address": "3134 Arizona Ave, Dallas, TX"}])
    assert props[0]["auction_status"] == "foreclosure"


def test_load_source_json_list(tmp_path):
    p = tmp_path / "rows.json"
    p.write_text('[{"address": "1 Main St"}]', encoding="utf-8")
    assert load_source(p) == [{"address": "1 Main St"}]


def test_load_source_json_wrapped(tmp_path):
    p = tmp_path / "rows.json"
    p.write_text('{"listings": [{"address": "1 Main St"}]}', encoding="utf-8")
    assert load_source(p) == [{"address": "1 Main St"}]


def test_load_source_missing_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        load_source(tmp_path / "nope.json")


def test_normalize_record_status_mapping():
    rec = normalize_record({"property_address": "1 Main St, Dallas, TX", "auction_status": "tax sale"})
    assert rec["auction_status"] == "tax_deed"