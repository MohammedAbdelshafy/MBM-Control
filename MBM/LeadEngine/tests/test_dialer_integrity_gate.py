"""
REGRESSION TESTS: DIALER INTEGRITY & SINGLE-WRITER GATE (M-026 mission gates)
=============================================================================
Guards the production leads_database.json integrity recovery end-state:
 1. DB is valid JSON list of dicts
 2. Every NPI artifact is present in the dialer (0 missing)
 3. No NPI beyond the artifact set (0 extra)
 4. Zero duplicate NPI numbers (provenance dedupe)
 5. Zero synthetic GEN-* rows in the dialer
 6. Synthetic daily_lead_factory file is quarantined (not in production path)
 7. Gateway read_leads returns a valid list
 8. full_replace refuses silent dataset shrinkage
 9. full_replace works with explicit allow_shrink=True (authorized purge)
10. commit_update upserts without dropping existing rows
11. Invalid-JSON DB is preserved to .corrupt and restored from backup
12. Reporting derives verified counts from live dialer, never the synthetic factory
=============================================================================
"""

import sys
import json
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH, BACKUP_DIR

ARTIFACTS_DAILY_DIR = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "daily"


def _norm_phone(p):
    """10-digit normalized phone body (strip +1 country code / trunk prefix)."""
    digits = "".join(c for c in str(p or "") if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _npi_artifact_records():
    """Canonical VALID NPI artifact set = union across ALL daily artifact dirs,
    filtered through the production validation gate.

    Fabricated/synthetic artifacts (e.g. sequential-numbered companies) fail
    the gate and are EXCLUDED from the strict 1:1 dialer requirement — they
    must never be counted as canonical artifacts nor synced into the dialer.
    """
    from MBM.LeadEngine.sync_npi_artifacts import validate_artifacts

    records = {}
    for day_dir in sorted((p for p in ARTIFACTS_DAILY_DIR.glob("2026-08-*") if p.is_dir()), reverse=True):
        day_records = []
        for f in day_dir.glob("lead_NPI-*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id"):
                day_records.append(data)
        if not day_records:
            continue
        validation = validate_artifacts(day_records, day_dir.name)
        for v in validation["valid"]:
            if v["id"] and v["id"] not in records:
                records[v["id"]] = next(r for r in day_records if str(r.get("id")) == v["id"])
    return records


def _npi_artifact_phones():
    """Set of 10-digit phone bodies across all canonical (valid) NPI artifacts."""
    phones = set()
    for rec in _npi_artifact_records().values():
        p = _norm_phone(rec.get("phone"))
        if p:
            phones.add(p)
    return phones


def test_fabricated_sequential_artifacts_rejected():
    """Fabricated artifacts (sequential NPI + numbered company) fail the gate."""
    from MBM.LeadEngine.dialer_gateway import validate_records
    from MBM.LeadEngine.lead_provenance import is_sequential_numbered_company
    assert is_sequential_numbered_company("Family Dental Care 112") is True
    assert is_sequential_numbered_company("ABB DENTAL GROUP LLC") is False
    fake = [
        {"id": "NPI-1000000001", "company": "Urgent Care Clinic 001",
         "contact": "Dr. Marcus Nguyen", "phone": "+12148000001",
         "source": "CMS NPI Registry API v2.1", "verification_method": "npi_registry_api",
         "verification_status": "VERIFIED"},
        {"id": "NPI-1000000003", "company": "Family Dental Care 003",
         "contact": "Dr. Sarah Lin", "phone": "+12148000003",
         "source": "CMS NPI Registry API v2.1", "verification_method": "npi_registry_api",
         "verification_status": "VERIFIED"},
    ]
    res = validate_records(fake)
    assert res["rejected_synthetic"] == 2, f"Fabricated rows must be rejected: {res}"
    assert len(res["clean"]) == 0


def test_db_is_valid_json_list():
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    assert isinstance(leads, list)
    assert len(leads) >= 1000
    for l in leads:
        assert isinstance(l, dict)
        assert l.get("id")


def test_all_npi_artifacts_present_in_dialer():
    """STRICT production gate: every canonical NPI artifact has a dialer record.

    Presence is enforced by NPI id (1:1 across ALL artifact days). Phone
    equality is enforced for the CURRENT day's artifacts (the sync guarantees
    registry phone preservation); for older batches the dialer phone may be a
    legitimately skip-trace-enriched number, which the verification gate
    (test below) still proves valid.
    """
    artifacts = _npi_artifact_records()
    assert len(artifacts) >= 100, f"Expected >=100 canonical NPI artifacts, got {len(artifacts)}"
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_ids = {str(l.get("id")) for l in leads}
    db_phones = {_norm_phone(l.get("phone")) for l in leads if l.get("phone")}
    missing_by_id = set(artifacts.keys()) - db_ids
    assert missing_by_id == set(), f"MISSING_FROM_DIALER_BY_ID: {sorted(missing_by_id)[:5]}"

    # Current-day artifacts must preserve their registry phone (strict sync).
    day_dirs = sorted((p for p in ARTIFACTS_DAILY_DIR.glob("2026-08-*") if p.is_dir()), reverse=True)
    assert day_dirs, "No daily artifact dirs present"
    latest_day = day_dirs[0].name
    current_day = {}
    for f in (ARTIFACTS_DAILY_DIR / latest_day).glob("lead_NPI-*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("id"):
            current_day[d["id"]] = d
    if current_day:
        current_phones = {_norm_phone(a.get("phone")) for a in current_day.values()}
        missing_phone = current_phones - db_phones
        assert missing_phone == set(), (
            f"CURRENT_DAY({latest_day}) MISSING_FROM_DIALER_BY_PHONE: {sorted(missing_phone)[:5]}"
        )

    for npi_id, art in artifacts.items():
        assert npi_id.startswith("NPI-"), f"Artifact id {npi_id} not NPI-"
        assert "NPI" in str(art.get("source", "")), f"Artifact {npi_id} missing NPI provenance"
        assert len(_norm_phone(art.get("phone"))) >= 10, f"Artifact {npi_id} has short phone"


def test_no_extra_npi_beyond_artifacts():
    """STRICT production gate: every dialer NPI record traces to an artifact."""
    artifacts = _npi_artifact_records()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_npi = {str(l.get("id")) for l in leads if str(l.get("id", "")).startswith("NPI-")}
    assert len(db_npi) >= 242, f"Expected >=242 NPI rows in dialer, got {len(db_npi)}"
    extra = db_npi - set(artifacts.keys())
    assert extra == set(), f"EXTRA_NPI_BEYOND_ARTIFACTS: {sorted(extra)[:5]}"


def test_all_dialer_npi_rows_pass_verification_gate():
    """Every dialer NPI row must clear the verification gate (phone+name+verify)."""
    from MBM.LeadEngine.dialer_verification_gate import check_lead
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_npi = [l for l in leads if str(l.get("id", "")).startswith("NPI-")]
    failed = []
    for l in db_npi:
        r = check_lead(l)
        if not r["passed"]:
            failed.append((l.get("id"), r["rejection_reasons"]))
    assert failed == [], f"NPI rows failing verification gate: {failed[:5]}"


def test_zero_duplicate_npi_numbers():
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    seen = set()
    dups = []
    for l in leads:
        if not str(l.get("id", "")).startswith("NPI-"):
            continue
        npi = str((l.get("details") or {}).get("npi_number") or l.get("id"))
        if npi in seen:
            dups.append(npi)
        seen.add(npi)
    assert dups == [], f"DUPLICATE_NPI_COUNT: {len(dups)} -> {dups[:5]}"


def test_zero_synthetic_in_dialer():
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    synthetic = [l for l in leads if str(l.get("id", "")).startswith(("GEN-NEW", "GEN-FAC", "GEN-"))]
    assert synthetic == [], f"SYNTHETIC_RECORDS_IN_DIALER: {len(synthetic)}"


def test_synthetic_factory_quarantined():
    prod_factory = ROOT_DIR / "MBM" / "Artifacts" / "daily_lead_factory_2026-08-16.json"
    assert not prod_factory.exists(), "Synthetic daily_lead_factory still in production path"
    quarantine_dir = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "quarantine"
    bundles = list(quarantine_dir.glob("*/daily_lead_factory_2026-08-16.json"))
    assert len(bundles) >= 1, "Synthetic factory not preserved in a quarantine bundle"


def test_gateway_read_leads_valid():
    writer = DialerSingleWriter()
    leads = writer.read_leads()
    assert isinstance(leads, list)
    assert len(leads) >= 1000
    for l in leads:
        assert isinstance(l, dict)


def test_full_replace_blocks_shrink(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text(json.dumps([{"id": "NPI-A", "phone": "+17873068356"}] * 1, ensure_ascii=False), encoding="utf-8")
    writer = DialerSingleWriter(db_path=db)
    writer.backup_dir = tmp_path / "backups"
    with pytest.raises(Exception, match="shrinkage"):
        writer.full_replace([], author="TEST")
    # Dataset unchanged after blocked write.
    assert len(json.loads(db.read_text(encoding="utf-8"))) == 1


def test_full_replace_allow_shrink_works(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text(json.dumps([{"id": "NPI-A", "phone": "+17873068356"}], ensure_ascii=False), encoding="utf-8")
    writer = DialerSingleWriter(db_path=db)
    writer.backup_dir = tmp_path / "backups"
    writer.backup_dir.mkdir(parents=True, exist_ok=True)
    res = writer.full_replace([{"id": "NPI-B", "phone": "+17873068357"}], author="TEST_PURGE", allow_shrink=True)
    assert res["ok"] is True
    assert res["final_count"] == 1


def test_commit_update_upserts_without_dropping(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text(json.dumps([{"id": "NPI-A", "phone": "+17873068356", "existing": True}], ensure_ascii=False), encoding="utf-8")
    writer = DialerSingleWriter(db_path=db)
    writer.backup_dir = tmp_path / "backups"
    writer.backup_dir.mkdir(parents=True, exist_ok=True)
    res = writer.commit_update([{"id": "NPI-B", "phone": "+17873068357"}], author="TEST_UPSERT")
    assert res["added_count"] == 1
    assert res["final_count"] == 2
    # Existing field preserved on NPI-A.
    leads = json.loads(db.read_text(encoding="utf-8"))
    by_id = {l["id"]: l for l in leads}
    assert by_id["NPI-A"].get("existing") is True


def test_invalid_json_preserved_and_restored(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text(json.dumps([{"id": "NPI-A", "phone": "+17873068356"}], ensure_ascii=False), encoding="utf-8")
    writer = DialerSingleWriter(db_path=db)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    writer.backup_dir = backup_dir
    (backup_dir / "leads_database_backup_20260816.json").write_text(
        json.dumps([{"id": "NPI-B", "phone": "+17873068357"}], ensure_ascii=False), encoding="utf-8"
    )
    # Corrupt the live DB mid-write.
    db.write_text("{ not valid json !!!", encoding="utf-8")
    restored = writer.read_leads()
    assert len(restored) == 1
    assert restored[0]["id"] == "NPI-B"
    corrupt_files = list(tmp_path.glob("leads_database.json.corrupt_*"))
    assert len(corrupt_files) == 1, "Corrupt DB must be preserved to a .corrupt backup"


def test_reporting_derives_from_live_dialer():
    from MBM.LeadEngine.gtm_quick_brief import GtmQuickBrief
    brief = GtmQuickBrief()
    factory = brief._latest_daily_factory()
    # Factory report must NOT be the synthetic 150-row file.
    assert factory.get("verified_new", 0) != 150
    assert len(factory.get("verified_leads", [])) != 150
    live = brief._live_dialer_counts()
    assert live.get("verified", 0) >= 242
    assert live.get("synthetic_in_dialer", -1) == 0


def test_day17_sync_exact():
    """STRICT current-day sync gate: every valid current-day artifact must have
    a 1:1 dialer record, verified by BOTH NPI id and normalized phone.

    The canonical sync gate is strict: a "fresh-batch pending" state (artifact
    exists, sync not yet run) is NOT an acceptable production end-state — it is
    a diagnostic window only. Counts are resolved dynamically from the latest
    daily artifact dir (the hourly NPI job may add fresh pulls at any time).
    """
    from MBM.LeadEngine.sync_npi_artifacts import validate_artifacts

    days = sorted((p.name for p in ARTIFACTS_DAILY_DIR.glob("2026-08-*") if p.is_dir() and list(p.glob("lead_NPI-*.json"))))
    assert days, "No daily artifact dirs present"
    latest_day = days[-1]
    day17_dir = ARTIFACTS_DAILY_DIR / latest_day
    assert day17_dir.exists(), f"Daily artifact dir missing: {latest_day}"
    raw_artifacts = {}
    for f in sorted(day17_dir.glob("lead_NPI-*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("id"):
            raw_artifacts[data["id"]] = data
    assert len(raw_artifacts) >= 1, f"No NPI artifacts in {latest_day}"

    # Every artifact must pass the production gate (provenance + method + phone).
    validation = validate_artifacts(list(raw_artifacts.values()), latest_day)
    assert len(validation["invalid"]) == 0, (
        f"Expected all Day artifacts valid, got invalid: {[r['id'] for r in validation['invalid']]}"
    )
    artifacts = {v["id"]: raw_artifacts[v["id"]] for v in validation["valid"]}
    assert len(artifacts) == len(raw_artifacts)
    assert validation["dup_npi"] == {}, f"DUPLICATE_NPI: {validation['dup_npi']}"
    assert validation["dup_phone"] == {}, f"DUPLICATE_PHONE: {validation['dup_phone']}"

    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_ids = {str(l.get("id")) for l in leads}
    db_phones = {_norm_phone(l.get("phone")) for l in leads if l.get("phone")}
    art_ids = set(artifacts.keys())
    art_phones = {_norm_phone(a.get("phone")) for a in artifacts.values()}

    missing_by_id = art_ids - db_ids
    missing_by_phone = art_phones - db_phones
    assert missing_by_id == set(), f"DAY_MISSING_FROM_DIALER_BY_ID: {sorted(missing_by_id)}"
    assert missing_by_phone == set(), f"DAY_MISSING_FROM_DIALER_BY_PHONE: {sorted(missing_by_phone)}"

    # The synced records must be stamped canonically.
    new_rows = [l for l in leads if str(l.get("id")) in art_ids]
    assert len(new_rows) == len(artifacts)
    assert all(l.get("new_today") is True for l in new_rows)
    assert all(l.get("first_seen_at") == latest_day for l in new_rows)
    assert all(l.get("verification_method") == "npi_registry_api" for l in new_rows)
    assert all(str(l.get("verification_status", "")).startswith("VERIFIED") for l in new_rows)

    # No suppressed / synthetic / unverified phones among the current-day leads.
    from MBM.LeadEngine.dialer_gateway import load_suppression_index
    from MBM.LeadEngine.dialer_verification_gate import check_lead
    from MBM.LeadEngine.lead_provenance import is_placeholder_phone
    suppressed = load_suppression_index()
    for a in artifacts.values():
        body = _norm_phone(a.get("phone"))
        assert body not in suppressed, f"SUPPRESSED_PHONE: {a.get('id')}"
        assert not is_placeholder_phone(a.get("phone")), f"PLACEHOLDER_PHONE: {a.get('id')}"
        gate = check_lead(a)
        assert gate["verified_ok"], f"UNVERIFIED: {a.get('id')}"