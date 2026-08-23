#!/usr/bin/env python3
"""
TESTS: P0 DAILY LEAD VERIFICATION + DIALER INGESTION
======================================================================
Regression coverage (one test per required case):
  1.  valid new lead            -> verified, classified, scripted, persisted
  2.  duplicate phone           -> merged WITHOUT wiping attempts/disposition/history
  3.  suppressed phone          -> never enters the queue
  4.  DNC                       -> blocked at suppression stage
  5.  synthetic number/record   -> rejected before classification
  6.  malformed record          -> rejected at raw ingest / phone gate
  7.  missing classification    -> NEEDS_REVIEW, never force-fit
  8.  script assignment         -> segment/script_id/Call_Script match classification
  9.  canonical persistence     -> bare JSON list written via approved writer only
  10. no-shrink                 -> destructive write refused
  11. revision increment        -> sidecar bumped + audit event recorded
  12. idempotent rerun          -> zero new, zero-yield documented, no revision churn
  13. live verification mismatch -> release FAILED, heartbeat NOT updated

Plus: newest-first ordering, PARTIAL_SUCCESS dry-run contract, BLOCKED source.
All tests are hermetic: temp DB + temp artifacts + fake live client.
"""

import sys
import json
import pytest
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import SingleWriterViolation, sidecar_paths
from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock
from MBM.LeadEngine.daily_lead_ingest import (
    DailyLeadIngestion,
    EXIT_CODES,
    STATUS_SUCCESS,
    STATUS_PARTIAL,
    STATUS_QUARANTINED,
    STATUS_BLOCKED,
    STATUS_FAILED,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

OFFICIALS = ["Arcilio Alvarado", "Dmitri Volkov", "Ingrid Halvorsen",
             "Tetsuo Kobayashi", "Leocadia Ferrer", "Bogdan Ionescu"]


def make_npi_row(i: int, phone: str = None, company: str = None) -> dict:
    """Realistic CMS NPI callsheet row (hermetic deterministic values)."""
    return {
        "npi": str(1500000000 + i),
        "company_name": company or f"Bayfront Family Dental {i} LLC",
        "taxonomy": "Dentist",
        "phone": phone or f"+1214376{8000 + i * 7:04d}",
        "address": f"{100 + i} Harbor Blvd",
        "city": "DALLAS",
        "state": "TX",
        "authorized_official_name": OFFICIALS[i % len(OFFICIALS)],
        "authorized_official_title": "CEO/PRESIDENT",
        "source": "CMS NPI Registry API v2.1",
        "vertical_tag": "DENTAL",
    }


def write_source(tmp_path: Path, rows: list) -> Path:
    src = tmp_path / "source_callsheet.json"
    src.write_text(json.dumps({
        "generated_at": "2026-08-23T00:00:00+00:00",
        "total": len(rows),
        "leads": rows,
    }), encoding="utf-8")
    return src


class FakeLiveClient:
    """Live dialer stand-in. Reads the actual tmp DB so counts match on a
    healthy run; `serve_rows` can override to simulate a stale/broken runtime."""

    def __init__(self, db_path: Path, serve_rows=None, ui_ok: bool = True):
        self.db_path = db_path
        self.serve_rows = serve_rows
        self.ui_ok = ui_ok
        self.base_url = "http://fake-dialer.test"

    def fetch_db(self):
        if self.serve_rows is not None:
            return self.serve_rows
        return json.loads(self.db_path.read_text(encoding="utf-8"))

    def fetch_ui(self):
        return self.ui_ok


def make_engine(tmp_path: Path, source: Path, live_client=None) -> DailyLeadIngestion:
    db = tmp_path / "leads_database.json"
    return DailyLeadIngestion(
        db_path=db,
        artifacts_dir=tmp_path / "artifacts",
        source_path=source,
        live_client=live_client or FakeLiveClient(db),
    )


def seed_db(db_path: Path, rows: list) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def read_db(engine: DailyLeadIngestion) -> list:
    """Read the canonical DB; a zero-write run may legitimately not create it."""
    if not engine.db_path.exists():
        return []
    data = json.loads(Path(engine.db_path).read_text(encoding="utf-8"))
    assert isinstance(data, list), "canonical DB must remain a bare JSON list"
    return data


@pytest.fixture(autouse=True)
def _no_real_suppression(monkeypatch):
    """Default: empty permanent-suppression index (tests opt in explicitly)."""
    monkeypatch.setattr(
        "MBM.LeadEngine.daily_lead_ingest.load_suppression_index", lambda: set()
    )


# ---------------------------------------------------------------------------
# 1. Valid new lead â€” full pipeline to persisted dialer row
# ---------------------------------------------------------------------------

def test_valid_new_lead_verified_classified_scripted_persisted(tmp_path):
    src = write_source(tmp_path, [make_npi_row(1), make_npi_row(2), make_npi_row(3)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["status"] == STATUS_SUCCESS
    assert report["raw_count"] == 3
    assert report["accepted_count"] == 3
    assert report["new_count"] == 3
    assert report["rejected_count"] == 0
    assert report["needs_review_count"] == 0
    assert report["canonical_count_before"] == 0
    assert report["canonical_count"] == 3

    rows = read_db(engine)
    assert isinstance(rows, list) and len(rows) == 3
    for row in rows:
        assert row["verification_status"] == "VERIFIED"
        assert row["segment"] == "HEALTHCARE_CLINIC"
        assert row["script_id"].startswith("SCRIPT-HEALTHCARE_CLINIC-NPI-")
        assert row["Call_Script"] and "HIPAA" in row["Call_Script"]
        assert row["sales_strategy"]["segment"] == row["segment"]
        assert row["new_today"] is True and row["callable"] is True
        assert row["source_type"] == "government_registry"
    assert report["script_coverage"] == 100.0
    # heartbeat written only after full health
    hb = engine.artifacts_dir / "GTM" / "daily" / report["run_date"] / "scheduler_heartbeat.json"
    assert hb.exists() and json.loads(hb.read_text(encoding="utf-8"))["healthy"] is True


# ---------------------------------------------------------------------------
# 2. Duplicate phone â€” merge preserves attempts/disposition/notes/stage/history
# ---------------------------------------------------------------------------

def test_duplicate_phone_merges_without_wiping_history(tmp_path):
    existing = {
        "id": "NPI-1200000000",
        "company": "Legacy Dental Practice",
        "contact": "Arcilio Alvarado",
        "vertical": "Dental Clinics & Orthodontics",
        "phone": "+12143768001",
        "attempts": 4,
        "disposition": "CALLBACK",
        "notes": "wants a call after Labor Day",
        "last_touch": "2026-08-01T10:00:00+00:00",
        "stage": "NURTURE",
        "status": "IN_PROGRESS",
        "history": [{"event": "call", "at": "2026-08-01", "note": "voicemail"}],
        "new_today": False,
        "freshness": "OLDER",
    }
    db = tmp_path / "leads_database.json"
    seed_db(db, [existing])
    # New NPI row, SAME phone, different NPI id -> must dedupe into existing.
    src = write_source(tmp_path, [make_npi_row(2, phone="+12143768001")])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["duplicate_count"] == 1
    assert report["new_count"] == 0
    assert report["status"] == STATUS_SUCCESS

    rows = read_db(engine)
    assert len(rows) == 1  # merged in place, no duplicate row created
    merged = rows[0]
    # preserved state
    assert merged["attempts"] == 4
    assert merged["disposition"] == "CALLBACK"
    assert merged["notes"] == "wants a call after Labor Day"
    assert merged["stage"] == "NURTURE"
    assert merged["status"] == "IN_PROGRESS"
    assert any(h.get("event") == "call" for h in merged["history"])
    # stronger enrichment merged in
    assert merged["script_id"] and merged["segment"] == "HEALTHCARE_CLINIC"
    assert any(h.get("event") == "daily_ingest_merge" for h in merged["history"])
    assert merged["new_today"] is False  # lifecycle flags not clobbered


# ---------------------------------------------------------------------------
# 3. Suppressed phone
# ---------------------------------------------------------------------------

def test_suppressed_phone_never_enters_queue(tmp_path, monkeypatch):
    suppressed_row = make_npi_row(2)   # phone -> +12143768014
    clean_row = make_npi_row(5)        # phone -> +12143768035
    assert normalize(suppressed_row["phone"]) == "2143768014"
    monkeypatch.setattr(
        "MBM.LeadEngine.daily_lead_ingest.load_suppression_index",
        lambda: {"2143768014"},
    )
    src = write_source(tmp_path, [suppressed_row, clean_row])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["suppressed_count"] == 1
    assert report["accepted_count"] == 1
    rows = read_db(engine)
    assert {f"NPI-{suppressed_row['npi']}", f"NPI-{clean_row['npi']}"} >= {r["id"] for r in rows}
    assert f"NPI-{suppressed_row['npi']}" not in {r["id"] for r in rows}
    assert f"NPI-{clean_row['npi']}" in {r["id"] for r in rows}


def normalize(phone: str) -> str:
    from MBM.LeadEngine.daily_lead_ingest import normalize_phone

    return normalize_phone(phone)


# ---------------------------------------------------------------------------
# 4. DNC records blocked
# ---------------------------------------------------------------------------

def test_dnc_record_blocked_at_suppression_stage(tmp_path):
    dnc_row = {
        "id": "MANUAL-DNC-1",
        "company": "Opted Out Roofing Co",
        "vertical": "Roofing & Exterior Contractors",
        "contact": "Dmitri Volkov",
        "phone": "+12143768021",
        "disposition": "DO_NOT_CALL",
        **_prov("ref-manual-dnc-1"),
    }
    src = write_source(tmp_path, [dnc_row])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["suppressed_count"] == 1
    assert report["accepted_count"] == 0
    assert read_db(engine) == []


def _prov(ref: str) -> dict:
    from MBM.LeadEngine.lead_provenance import build_provenance_fields

    return build_provenance_fields(
        source="CMS NPI Registry API v2.1",
        source_reference=ref,
        source_type="government_registry",
        verification_method="npi_registry_api",
    )


# ---------------------------------------------------------------------------
# 5. Synthetic record rejected
# ---------------------------------------------------------------------------

def test_synthetic_record_rejected(tmp_path):
    synthetic = {
        "id": "GEN-FAC-00742",
        "company": "Summit Peak Solutions LLC",
        "contact": "Ashley Mercer",
        "vertical": "Business Services",
        "phone": "+12143768031",
        **_prov("gen-fac-ref"),
    }
    src = write_source(tmp_path, [synthetic, make_npi_row(9)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["rejected_count"] >= 1
    ids = {r["id"] for r in read_db(engine)}
    assert "GEN-FAC-00742" not in ids


# ---------------------------------------------------------------------------
# 6. Malformed records rejected
# ---------------------------------------------------------------------------

def test_malformed_records_rejected(tmp_path):
    no_id = {"company": "No Id Clinic", "phone": "+12143768041"}
    no_phone = {"id": "X-NO-PHONE", "company": "Phoneless Clinic",
                "vertical": "Medical Clinics & Urgent Care", **_prov("ref-nophone")}
    bad_phone = make_npi_row(7, phone="+12145550011")  # reserved 555 exchange
    good = make_npi_row(8)
    src = write_source(tmp_path, [no_id, no_phone, bad_phone, good])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["raw_count"] == 4
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 3
    ids = {r["id"] for r in read_db(engine)}
    assert ids == {f"NPI-{good['npi']}"}


# ---------------------------------------------------------------------------
# 7. Missing classification -> NEEDS_REVIEW
# ---------------------------------------------------------------------------

def test_missing_classification_needs_review_not_force_fit(tmp_path):
    unclassifiable = {
        "id": "X-NOCATEGORY",
        "company": "",
        "vertical": "",
        "contact": "Ingrid Halvorsen",
        "phone": "+12143768051",
        **_prov("ref-nocategory"),
    }
    src = write_source(tmp_path, [unclassifiable])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["needs_review_count"] == 1
    assert "X-NOCATEGORY" in report["needs_review_ids"]
    assert report["accepted_count"] == 0
    assert read_db(engine) == []
    assert report["stages"]["classification"]["completed"] is True


# ---------------------------------------------------------------------------
# 8. Script assignment matches actual classification
# ---------------------------------------------------------------------------

def test_script_assignment_matches_segment(tmp_path):
    contractor = {
        "id": "CONT-1",
        "company": "Ironline Mechanical Contractors",
        "vertical": "HVAC & Mechanical Contractors",
        "contact": "Tetsuo Kobayashi",
        "phone": "+12143768061",
        **_prov("cont-ref-1"),
    }
    seller = {
        "id": "SELLER-PCL-77",
        "company": "1420 Elm Street",
        "vertical": "Real Estate Sellers",
        "contact": "Leocadia Ferrer",
        "phone": "+12143768062",
        **_prov("parcel:77"),
    }
    src = write_source(tmp_path, [contractor, seller])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    assert report["accepted_count"] == 2
    by_seg = {r["segment"]: r for r in read_db(engine)}
    assert by_seg["CONTRACTOR"]["script_id"].startswith("SCRIPT-CONTRACTOR-")
    assert "contractor" in by_seg["CONTRACTOR"]["Call_Script"].lower()
    assert by_seg["DISTRESSED_SELLER"]["script_id"].startswith("SCRIPT-DISTRESSED_SELLER-")
    assert "owner" in by_seg["DISTRESSED_SELLER"]["Call_Script"].lower()
    # healthcare script NEVER used as generic fallback
    assert "HEALTHCARE_CLINIC" not in by_seg


# ---------------------------------------------------------------------------
# 9. Canonical persistence â€” bare JSON list through the approved writer
# ---------------------------------------------------------------------------

def test_canonical_persistence_bare_list_and_id_fields(tmp_path):
    src = write_source(tmp_path, [make_npi_row(i) for i in range(11, 15)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    raw_text = engine.db_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    assert isinstance(data, list)  # MUST remain a bare JSON list
    assert report["dataset_hash"]
    assert all(r.get("id") and r.get("phone") for r in data)
    # every accepted lead reached the DB (nothing silently dropped)
    assert len(data) == report["accepted_count"]


# ---------------------------------------------------------------------------
# 10. No-shrink invariant enforced on the canonical writer
# ---------------------------------------------------------------------------

def test_no_shrink_destructive_write_refused(tmp_path):
    db = tmp_path / "leads_database.json"
    seed_db(db, [{"id": f"E-{i}", "phone": f"+12143768{i:03d}",
                  "company": f"Existing {i}", "vertical": "Medical Clinics"} for i in range(3)])
    lock = DialerDatabaseLock(db_path=db)
    with pytest.raises(SingleWriterViolation):
        with lock:
            lock.write([{"id": "E-0", "phone": "+12143768000"}], allow_shrink=False)
    # dataset untouched after refusal
    assert len(json.loads(db.read_text(encoding="utf-8"))) == 3


# ---------------------------------------------------------------------------
# 11. Revision increment + audit event
# ---------------------------------------------------------------------------

def test_revision_increment_and_audit_event(tmp_path):
    src = write_source(tmp_path, [make_npi_row(21)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)

    rev_file, audit_file = sidecar_paths(engine.db_path)
    assert report["canonical_revision_before"] == 0
    assert report["canonical_revision"] == 1
    assert json.loads(rev_file.read_text(encoding="utf-8"))["revision"] == 1
    last_audit = json.loads(audit_file.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert last_audit["operation_id"] == report["run_id"]
    assert last_audit["author"] == "DAILY_LEAD_INGEST"

    # a second batch on the same DB increments the revision again
    second_source = tmp_path / "source_callsheet_2.json"
    second_source.write_text(json.dumps({
        "generated_at": "2026-08-23T01:00:00+00:00",
        "leads": [make_npi_row(23)],
    }), encoding="utf-8")
    engine2 = DailyLeadIngestion(
        db_path=engine.db_path,
        artifacts_dir=engine.artifacts_dir,
        source_path=second_source,
        live_client=FakeLiveClient(engine.db_path),
    )
    report2 = engine2.run(apply=True)
    assert report2["canonical_revision"] == 2


# ---------------------------------------------------------------------------
# 12. Idempotent rerun â€” zero new, documented zero-yield, no revision churn
# ---------------------------------------------------------------------------

def test_idempotent_rerun_no_duplicate_growth(tmp_path):
    src = write_source(tmp_path, [make_npi_row(31), make_npi_row(32)])
    engine = make_engine(tmp_path, src)
    r1 = engine.run(apply=True)
    assert r1["new_count"] == 2 and r1["status"] == STATUS_SUCCESS

    hash_after_r1 = r1["dataset_hash"]
    rev_after_r1 = r1["canonical_revision"]

    r2 = engine.run(apply=True)  # SAME source again
    assert r2["new_count"] == 0
    assert r2["duplicate_count"] == 2
    assert r2["zero_yield_reason"] != ""
    assert r2["canonical_revision"] == rev_after_r1  # untouched
    assert r2["dataset_hash"] == hash_after_r1       # byte-stable
    assert r2["status"] == STATUS_SUCCESS
    rows = read_db(engine)
    assert len(rows) == 2  # no duplicate rows ever created


# ---------------------------------------------------------------------------
# 13. Live verification mismatch fails the release
# ---------------------------------------------------------------------------

def test_live_verification_mismatch_fails_release(tmp_path):
    src = write_source(tmp_path, [make_npi_row(41), make_npi_row(42)])
    db = tmp_path / "leads_database.json"
    stale_runtime = FakeLiveClient(db, serve_rows=[], ui_ok=False)  # runtime serves nothing
    engine = make_engine(tmp_path, src, live_client=stale_runtime)
    report = engine.run(apply=True)

    assert report["live_verified"] is False
    assert report["status"] == STATUS_FAILED
    assert any("live_verification_failed" in e for e in report["errors"])
    # canonical persistence DID happen; release still FAILED
    assert report["write_performed"] is True
    assert len(json.loads(db.read_text(encoding="utf-8"))) == 2
    day_dir = engine.artifacts_dir / "GTM" / "daily" / report["run_date"]
    assert not (day_dir / "scheduler_heartbeat.json").exists()


def test_live_sample_trace_incomplete_fails_release(tmp_path):
    src = write_source(tmp_path, [make_npi_row(i) for i in range(43, 48)])
    db = tmp_path / "leads_database.json"

    class PartialRuntime(FakeLiveClient):
        def fetch_db(self):
            rows = super().fetch_db()
            return rows[:-1]  # one sample missing from the live API

    engine = make_engine(tmp_path, src, live_client=PartialRuntime(db))
    report = engine.run(apply=True)
    assert report["status"] == STATUS_FAILED
    assert report["live"]["samples_ok"] is False


def test_idempotent_rerun_still_traces_todays_cohort_live(tmp_path):
    """After a FAILED live check, a fixed-runtime rerun (no new leads) must
    still prove end-to-end visibility of TODAY'S ingested cohort."""
    src = write_source(tmp_path, [make_npi_row(i) for i in range(71, 74)])
    db = tmp_path / "leads_database.json"
    broken = FakeLiveClient(db, serve_rows=[], ui_ok=False)
    r1 = make_engine(tmp_path, src, live_client=broken).run(apply=True)
    assert r1["status"] == STATUS_FAILED

    r2 = make_engine(tmp_path, src).run(apply=True)  # healthy runtime now
    assert r2["status"] == STATUS_SUCCESS
    assert r2["new_count"] == 0
    assert len(r2["sample_traces"]) == 3
    for t in r2["sample_traces"]:
        assert t["in_canonical"] and t["in_live_api"] and t["ui_served"]
        assert t["lead_id"].startswith("NPI-")


# ---------------------------------------------------------------------------
# Extra contracts: newest-first ordering, dry-run partial, blocked source
# ---------------------------------------------------------------------------

def test_newest_first_ordering_new_leads_on_top(tmp_path):
    src = write_source(tmp_path, [make_npi_row(i) for i in range(51, 54)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=True)
    new_ids = set()
    rows = read_db(engine)
    top = rows[: report["new_count"]]
    assert {r["id"] for r in top} == {r["id"] for r in rows if r.get("first_seen_date") == report["run_date"]}
    snapshot = json.loads(
        (engine.artifacts_dir / "GTM" / "daily" / report["run_date"] / "queue_snapshot.json")
        .read_text(encoding="utf-8")
    )
    page_one_ids = {entry["id"] for entry in snapshot["pages"][0]}
    assert new_ids or page_one_ids  # snapshot produced and paginated
    assert snapshot["pages"][0][0]["rank"] == 1


def test_dry_run_is_partial_success_with_exact_partial_contract(tmp_path):
    src = write_source(tmp_path, [make_npi_row(61)])
    engine = make_engine(tmp_path, src)
    report = engine.run(apply=False)

    assert report["status"] == STATUS_PARTIAL
    assert set(report["partial"].keys()) == {
        "raw", "accepted", "rejected", "duplicates",
        "suppressed", "needs_review", "persisted", "not_persisted",
    }
    assert report["partial"]["persisted"] == 0
    assert report["partial"]["not_persisted"] == 1
    assert not engine.db_path.exists()  # dry-run wrote nothing


def test_source_fetch_failure_is_blocked(tmp_path):
    engine = make_engine(tmp_path, tmp_path / "missing_source.json")
    report = engine.run(apply=True)
    assert report["status"] == STATUS_BLOCKED
    assert report["stages"]["source_fetch"]["completed"] is False
    assert any("source_fetch_failed" in e for e in report["errors"])


def test_exit_code_map_covers_all_states():
    assert EXIT_CODES[STATUS_SUCCESS] == 0
    assert EXIT_CODES[STATUS_FAILED] == 1
    assert EXIT_CODES[STATUS_PARTIAL] == 2
    assert EXIT_CODES[STATUS_QUARANTINED] == 3
    assert EXIT_CODES[STATUS_BLOCKED] == 4
