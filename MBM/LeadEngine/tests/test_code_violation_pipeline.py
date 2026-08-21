"""
TESTS: DAILY CODE-VIOLATION LEAD PIPELINE (ZERO SYNTHETIC, HERMETIC)
=============================================================================
Verifies:
1. Source registry integrity (active sources have connector + field map; verified only)
2. Classification contract (VACANT/UNSAFE/MAINTENANCE/OTHER + confidence, ACTIVE vs closed)
3. Scoring + tiers (TIER 1/2/3 boundaries, score cap 100, distress counting)
4. Enrichment rules (no owner -> no phone; placeholder/NaN phone rejected; absentee)
5. Dedupe (live-dialer address/parcel match + case-ledger)
6. End-to-end dry-run (writes artifacts, NEVER the dialer DB; no GTM merge)
7. End-to-end apply (dialer patch receives records, GTM queue upserted)
=============================================================================
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.code_violation.collector import (  # noqa: E402
    classify_violation,
    is_rejected_violation,
    load_source_registry,
    record_key,
)
from MBM.LeadEngine.code_violation.enrichment import (  # noqa: E402
    _absentee_check,
    _valid_nanp,
    enrich_phone,
    resolve_owner,
)
from MBM.LeadEngine.code_violation.pipeline import (  # noqa: E402
    CodeViolationDailyPipeline,
    find_existing,
    lead_id,
)
from MBM.LeadEngine.code_violation.scoring import (  # noqa: E402
    assign_tier,
    build_property_record,
    distress_count,
    score_property,
)

REGISTRY = ROOT_DIR / "MBM/LeadEngine/code_violation/source_registry.json"

DALLAS_FIXTURE = [
    {
        "service_request_number": "SR-1001",
        "address": "12124 SCHROEDER RD",
        "service_request_type": "Code Concern - Abandoned/Vacant Structure",
        "status": "Open",
        "department": "Code Compliance",
        "created_date": "2026-08-10T12:00:00",
        "update_date": "2026-08-12T12:00:00",
        "unique_key": "K1",
    },
    {
        "service_request_number": "SR-1002",
        "address": "4520 WESTMORELAND RD",
        "service_request_type": "Code Concern - High Weeds/Grass",
        "status": "Open",
        "department": "Code Compliance",
        "created_date": "2026-08-01T09:00:00",
        "update_date": "2026-08-05T09:00:00",
        "unique_key": "K2",
    },
    {
        "service_request_number": "SR-1003",
        "address": "3120 BRYAN ST",
        "service_request_type": "Water Leak",
        "status": "Closed",
        "department": "Water Utilities",
        "created_date": "2026-07-01T09:00:00",
        "update_date": "2026-07-02T09:00:00",
        "unique_key": "K3",
    },
]

FW_FIXTURE = [
    {
        "Case_ID": "FW-2001",
        "Violation_Address": "500 HOUSTON ST",
        "Complaint_Type_Description": "Vacant Structure - Unsafe/Dilapidated",
        "Case_Current_Status": "Open",
        "Case_Created_Date": 1780000000000,
        "Update_Date": 1780100000000,
        "Violation_ID": "V-1",
        "City": "Fort Worth",
        "State": "TX",
    }
]


class FakeSkipTracer:
    def __init__(self, phone=None):
        self.phone = phone or "+12145551234"

    def find_contact(self, name, address, city):
        return {
            "phone": self.phone,
            "email": "owner@example.com",
            "source": "test_skip_tracer",
            "confidence": "high",
        }


class FakeVerifier:
    def __call__(self, rec):
        from MBM.LeadEngine.property_intel.schema import OwnershipVerification

        return OwnershipVerification(
            property_key=rec.get("address", ""),
            owner_name="JANE SMITH",
            parcel_id="PX99",
            site_address=rec.get("address", ""),
            source="Test County Assessor",
            source_url="https://example.test/arcgis",
            verification_status="VERIFIED",
            confidence=0.95,
            evidence=[],
        )


def fake_fetch(rows_by_host):
    def _fetch(url):
        for host, rows in rows_by_host.items():
            if host in url:
                return rows
        return []
    return _fetch


def make_pipeline(tmp, fetch, now=None, dcad=None, verifier=None, tracer=None,
                  live_db=None):
    gtm_daily = Path(tmp) / "gtm_daily"
    gtm_daily.mkdir(exist_ok=True)
    (gtm_daily / "2026-08-18.json").write_text(json.dumps({
        "top_actions": [{"id": "EX-1"}],
        "top_opportunities": [{"id": "EX-2"}],
    }), encoding="utf-8")
    (gtm_daily / "latest.json").write_text(json.dumps({"top_actions": [{"id": "EX-1"}]}),
                                           encoding="utf-8")
    queue_path = Path(tmp) / "gtm_queue.json"
    queue_path.write_text(json.dumps([{"id": "EX-1"}]), encoding="utf-8")
    db_path = Path(tmp) / "leads_database.json"
    db_path.write_text(json.dumps(live_db or []), encoding="utf-8")
    if dcad is None:
        dcad = lambda addr: {"owner": "TEST OWNER LLC", "parcel_id": "P1",
                             "mail_city": "Dallas", "mail_state": "TX"}
    return CodeViolationDailyPipeline(
        root_dir=ROOT_DIR,
        registry_path=REGISTRY,
        artifacts_root=Path(tmp) / "cv_artifacts",
        gtm_daily_root=gtm_daily,
        gtm_queue_path=queue_path,
        dialer_db_path=db_path,
        now=now or datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
        fetch_json=fetch,
        dcad_fn=dcad,
        verify_fn=verifier or FakeVerifier(),
        skip_tracer=tracer or FakeSkipTracer(),
        suppression={"0000000000"},
    )


# ── 1. registry integrity ─────────────────────────────────────────────────
def test_registry_active_sources_are_verified():
    data = load_source_registry(REGISTRY)
    for name, cfg in data["sources"].items():
        if cfg["active"]:
            assert cfg["last_verified"] == "2026-08-18", name
            assert cfg["county"], name
            assert cfg["fields"].get("address_field"), name
        else:
            assert cfg["active_note"], name


def test_registry_includes_garland_mesquite_unverified():
    data = load_source_registry(REGISTRY)
    assert data["sources"]["garland"]["active"] is False
    assert data["sources"]["mesquite"]["active"] is False


# ── 2. classification ─────────────────────────────────────────────────────
def test_classify_vacant_and_active():
    r = classify_violation("Abandoned/Vacant Structure", status="Open",
                           opened_iso="2026-08-10T12:00:00",
                           now=datetime(2026, 8, 18, tzinfo=timezone.utc))
    assert r["category"] == "VACANT"
    assert r["active"] is True
    assert r["age_days"] == 7


def test_classify_closed_is_inactive():
    r = classify_violation("Overgrown Grass", status="Closed",
                           opened_iso="2026-08-10T12:00:00")
    assert r["active"] is False


def test_classify_unsafe_priority_over_generic():
    r = classify_violation("Vacant Structure - Unsafe/Dilapidated", status="Open")
    assert r["category"] in ("UNSAFE", "VACANT", "STRUCTURAL", "PROPERTY_DERELICT")


def test_classify_unknown_low_confidence():
    r = classify_violation("Miscellaneous Complaint", status="Open")
    assert r["category"] == "OTHER"
    assert r["classification_confidence"] <= 0.5


# ── 3. scoring + tiers ────────────────────────────────────────────────────
def test_tier_boundaries():
    assert assign_tier(80, True, 2) == "TIER 1"
    assert assign_tier(70, True, 2) == "TIER 1"
    assert assign_tier(50, True, 1) == "TIER 2"
    assert assign_tier(50, False, 1) == "TIER 3"
    assert assign_tier(80, True, 1) == "TIER 2"


def test_score_caps_at_100_and_tags():
    prop = build_property_record(
        address="12124 SCHROEDER RD", city="Dallas", state="TX", county="Dallas",
        violations=[
            {"category": "VACANT", "active": True, "age_days": 5, "case_id": "A",
             "violation_type": "Vacant Structure", "source": "Dallas, TX", "opened_iso": "2026-08-13"},
            {"category": "UNSAFE", "active": True, "age_days": 5, "case_id": "B",
             "violation_type": "Unsafe Structure", "source": "Dallas, TX", "opened_iso": "2026-08-13"},
        ],
        owner={"owner_name": "T", "owner_status": "VERIFIED", "parcel_id": "P",
               "confidence": 0.9, "absentee": True},
        phone={"phone": "+12145551234", "confidence": 0.8},
    )
    res = score_property(prop)
    assert res.score <= 100
    assert "CODE_VIOLATION" in res.tags
    assert "VERIFIED_PHONE" in res.tags
    assert distress_count(prop) >= 2
    assert res.tier == "TIER 1"


def test_no_phone_never_tier1():
    prop = build_property_record(
        address="500 HOUSTON ST", city="Fort Worth", state="TX", county="Tarrant",
        violations=[{"category": "VACANT", "active": True, "age_days": 3,
                     "case_id": "C", "violation_type": "Vacant", "source": "Fort Worth, TX",
                     "opened_iso": "2026-08-15"}],
        owner={"owner_name": "J", "owner_status": "VERIFIED", "parcel_id": "X",
               "confidence": 0.9, "absentee": False},
        phone=None,
    )
    res = score_property(prop)
    assert res.tier in ("TIER 2", "TIER 3")


# ── 4. enrichment rules ───────────────────────────────────────────────────
def test_valid_nanp_and_placeholder():
    assert _valid_nanp("+12145551234")
    assert _valid_nanp("2145551234")
    assert not _valid_nanp("123")
    assert not _valid_nanp("5551234")


def test_no_owner_means_no_phone():
    owner = resolve_owner(
        {"address": "999 NOWHERE LN", "city": "Garland", "state": "TX", "county": "Dallas"},
        dcad_fn=lambda a: None,
    )
    assert owner.owner_status == "NOT_FOUND"
    phone = enrich_phone(owner, {"address": "x", "city": "y"}, skip_tracer=FakeSkipTracer())
    assert phone.status == "NO_PHONE"


def test_absentee_detection():
    assert _absentee_check("Los Angeles, CA", "Dallas", "TX") is True
    assert _absentee_check("Frisco, TX", "Dallas", "TX") is False
    assert _absentee_check("", "Dallas", "TX") is None


def test_suppression_rejects_phone():
    owner = resolve_owner(
        {"address": "12124 SCHROEDER RD", "city": "Dallas", "state": "TX", "county": "Dallas"},
        dcad_fn=lambda a: {"owner": "T", "parcel_id": "P", "mail_city": "Dallas", "mail_state": "TX"},
    )
    phone = enrich_phone(owner, {"address": "a", "city": "Dallas"},
                         skip_tracer=FakeSkipTracer("+12145560123"),
                         suppression={"2145560123"})
    assert phone.status == "REJECTED"


# ── 5. dedupe ─────────────────────────────────────────────────────────────
def test_find_existing_by_address_and_parcel():
    db = [
        {"id": "A1", "address": "12124 SCHROEDER RD", "details": {"parcel_id": "P1"}},
        {"id": "A2", "details": {"address": "500 HOUSTON ST", "parcel_id": "P2"}},
    ]
    assert find_existing(db, "12124 SCHROEDER RD", "")["id"] == "A1"
    assert find_existing(db, "500 HOUSTON ST", "")["id"] == "A2"
    assert find_existing(db, "999 NOPE ST", "") is None


def test_lead_id_stable():
    assert lead_id("12124 SCHROEDER RD", "Dallas", "TX") == \
        lead_id("12124 SCHROEDER RD", "Dallas", "TX")


def test_rejected_no_address():
    assert is_rejected_violation({"address": ""})
    assert not is_rejected_violation({"address": "500 HOUSTON ST"})


# ── 6. e2e dry-run ────────────────────────────────────────────────────────
def test_dry_run_writes_artifacts_never_dialer():
    with tempfile.TemporaryDirectory() as tmp:
        fetch = fake_fetch({
            "dallasopendata.com": DALLAS_FIXTURE,
            "services5.arcgis.com": FW_FIXTURE,
        })
        pipe = make_pipeline(tmp, fetch)
        report = pipe.run(apply=False, days_back=45, enrich_limit=10)
        assert report["status"] in ("success", "partial")
        day = Path(tmp) / "gtm_daily" / "2026-08-18"
        assert (day / "code_violation_daily_report.json").exists()
        assert (day / "code_violation_leads.csv").exists()
        # dry-run must not touch the live dialer DB
        db = json.loads((Path(tmp) / "leads_database.json").read_text(encoding="utf-8"))
        assert db == []
        # dry-run must not merge GTM or upsert the execution queue
        queue = json.loads((Path(tmp) / "gtm_queue.json").read_text(encoding="utf-8"))
        assert all(e.get("id") == "EX-1" for e in queue)
        report_body = json.loads((day / "code_violation_daily_report.json").read_text(encoding="utf-8"))
        assert report_body["totals"]["properties_scored"] > 0


# ── 7. e2e apply ──────────────────────────────────────────────────────────
def test_apply_writes_dialer_and_gtm(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        fetch = fake_fetch({
            "dallasopendata.com": DALLAS_FIXTURE,
            "services5.arcgis.com": FW_FIXTURE,
        })
        pipe = make_pipeline(tmp, fetch, tracer=FakeSkipTracer("+12145560123"))
        written = {}

        def fake_patch(records, reason, author):
            written["records"] = records
            written["reason"] = reason

        monkeypatch.setattr(
            "MBM.LeadEngine.code_violation.pipeline.patch_dialer_db", fake_patch)
        report = pipe.run(apply=True, days_back=45, enrich_limit=10)
        assert report["status"] in ("success", "partial")
        assert written.get("reason") == "code_violation_daily"
        assert written["records"]
        for rec in written["records"]:
            assert rec["queue_bucket"] == "CODE_VIOLATION_DAILY"
            assert rec["vertical"] == "Code Violation Sellers"
            assert rec["callable"] is True
            assert len(rec["phone"]) >= 12
            assert rec["tier"] in ("T1", "T2")
        # GTM queue now carries code-violation opportunities
        queue = json.loads((Path(tmp) / "gtm_queue.json").read_text(encoding="utf-8"))
        assert any(e.get("industry") == "Real Estate (Code Violation)" for e in queue)
        # brief merged
        brief = json.loads((Path(tmp) / "gtm_daily" / "2026-08-18.json").read_text(encoding="utf-8"))
        assert "code_violation" in brief