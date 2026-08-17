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


def _npi_artifact_records():
    records = {}
    for day_dir in sorted(ARTIFACTS_DAILY_DIR.glob("2026-08-*"), reverse=True):
        for f in day_dir.glob("lead_NPI-*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id"):
                records[data["id"]] = data
        if records:
            break
    return records


def test_db_is_valid_json_list():
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    assert isinstance(leads, list)
    assert len(leads) >= 1000
    for l in leads:
        assert isinstance(l, dict)
        assert l.get("id")


def test_all_npi_artifacts_present_in_dialer():
    artifacts = _npi_artifact_records()
    assert len(artifacts) >= 242
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_ids = {str(l.get("id")) for l in leads}
    missing = set(artifacts.keys()) - db_ids
    assert missing == set(), f"MISSING_FROM_DIALER: {list(missing)[:5]}"


def test_no_extra_npi_beyond_artifacts():
    artifacts = _npi_artifact_records()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    db_npi = {str(l.get("id")) for l in leads if str(l.get("id", "")).startswith("NPI-")}
    extra = db_npi - set(artifacts.keys())
    assert extra == set(), f"EXTRA_NPI_BEYOND_ARTIFACTS: {list(extra)[:5]}"


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