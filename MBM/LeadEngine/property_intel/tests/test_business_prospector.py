"""business_prospector tests — deterministic scoring + file-source pipeline."""
import json

from property_intel.business_prospector import (
    DEFAULT_QUERIES,
    FileBusinessSource,
    GoogleMapsBusinessSource,
    NullPersonSource,
    score_business,
    to_prospect,
    run_prospecting,
)

ROOFING = {
    "name": "Metro Roofing & Restoration LLC",
    "category": "Roofing contractor",
    "website": "https://www.metroroofing.example",
    "phone_number": "+1 555-010-1001",
    "rating": 4.7,
    "review_count": 214,
    "city": "Dallas",
    "state": "TX",
}


def test_score_business_labor_intensive_category_boosts():
    s = score_business(ROOFING)
    assert s["component_scores"]["operational_pain"] >= 60
    assert s["component_scores"]["service_fit"] >= 50
    assert 0 <= s["total"] <= 100
    assert s["category"] == "Roofing contractor"
    assert any("labor-intensive" in r for r in s["reasons"])


def test_score_business_no_website_modernization_candidate():
    row = dict(ROOFING)
    row["website"] = ""
    s = score_business(row)
    assert s["component_scores"]["outdated_website"] == 85
    assert any("no website" in r for r in s["reasons"])


def test_score_business_template_site_flagged():
    row = dict(ROOFING)
    row["website"] = "https://roofing.wordpress.com"
    s = score_business(row)
    assert s["component_scores"]["outdated_website"] == 65


def test_to_prospect_builds_record_with_phone_verified():
    p = to_prospect(ROOFING, "file-export", "roofing company dallas tx")
    assert p.company_name == "Metro Roofing & Restoration LLC"
    assert p.business_phone == "+1 555-010-1001"
    assert p.verification_status == "VERIFIED"
    assert p.confidence == 0.9
    assert p.prospect_id.startswith("BIZ-")
    assert p.raw == {"query": "roofing company dallas tx"}


def test_to_prospect_no_phone_partial():
    row = dict(ROOFING)
    row["phone_number"] = ""
    p = to_prospect(row, "file-export", "q")
    assert p.verification_status == "PARTIAL"
    assert p.confidence == 0.5


def test_null_person_source_never_invents():
    src = NullPersonSource()
    rows, diag = src.fetch("any")
    assert rows == []
    assert diag["blocked"] is True


def test_google_maps_source_requires_key_when_missing(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "")
    src = GoogleMapsBusinessSource(api_key="")
    assert src.requires_key() is True


def test_google_maps_source_no_key_blocked(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "")
    src = GoogleMapsBusinessSource(api_key="")
    rows, diag = src.fetch("roofing dallas")
    assert rows == []
    assert "RAPIDAPI_KEY" in diag["error"]


def test_file_source_fetch(tmp_path):
    p = tmp_path / "biz.json"
    p.write_text(json.dumps({"businesses": [ROOFING]}), encoding="utf-8")
    src = FileBusinessSource(p)
    assert src.requires_key() is False
    rows, diag = src.fetch("x")
    assert len(rows) == 1
    assert diag["rows"] == 1


def test_run_prospecting_file_source(tmp_path):
    p = tmp_path / "biz.json"
    p.write_text(json.dumps({"businesses": [ROOFING]}), encoding="utf-8")
    report = run_prospecting(["roofing dallas"], source=FileBusinessSource(p))
    assert report["status"] == "success"
    assert report["outputs"]["prospects"] == 1
    assert report["outputs"]["raw_rows"] == 1


def test_run_prospecting_requires_key_blocked():
    report = run_prospecting(["x"], source=NullPersonSource())
    assert report["status"] == "blocked"
    assert report["outputs"]["prospects"] == []


def test_default_queries_are_business_buyer_segments():
    assert len(DEFAULT_QUERIES) >= 10
    assert any("roofing" in q for q in DEFAULT_QUERIES)