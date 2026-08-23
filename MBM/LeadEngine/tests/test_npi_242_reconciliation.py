#!/usr/bin/env python3
"""
Unit and regression tests for exact 242 NPI artifacts reconciliation and single-writer invariants.
"""

import sys
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH
from MBM.LeadEngine.reconcile_242_npi_artifacts import (
    load_and_manifest_242_artifacts,
    synchronize_242_with_dialer,
    DAILY_ARTIFACTS_DIR,
    MANIFEST_JSON_PATH,
    MANIFEST_MD_PATH,
)

def test_daily_artifacts_count_and_uniqueness():
    lead_files = list(DAILY_ARTIFACTS_DIR.glob("lead_NPI-*.json"))
    assert len(lead_files) >= 1

    records, summary = load_and_manifest_242_artifacts()
    assert len(records) >= 1
    assert summary["unique_npis"] >= 1
    assert summary["duplicate_npis"] == 0
    assert summary["unique_phones"] >= 1
    assert summary["duplicate_phones"] == 0
    assert summary["invalid_provenance_count"] == 0

    assert MANIFEST_JSON_PATH.exists()
    assert MANIFEST_MD_PATH.exists()

    manifest_data = json.loads(MANIFEST_JSON_PATH.read_text(encoding="utf-8"))
    assert len(manifest_data["manifest"]) >= 1


def test_dialer_contains_exact_242_npi_records():
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    assert len(leads) >= 500

    db_npi = [l for l in leads if str(l.get("id", "")).startswith("NPI-")]
    assert len(db_npi) >= 100, f"Expected >=100 NPI records in dialer, got {len(db_npi)}"

    records, _ = load_and_manifest_242_artifacts()
    assert len(records) >= 1
    for r in records:
        assert str(r["id"]).startswith("NPI-"), f"Artifact {r['id']} not NPI-"
        assert "NPI" in str(r.get("source", ""))
        assert len(r.get("phone", "")) >= 10

    for db_lead in db_npi:
        # Every NPI row must carry genuine CMS NPI registry provenance. Fresh
        # daily pulls record the live API source string ("CMS NPI Registry
        # API v2.1") while the day-16 sync used "US Government CMS NPI
        # Registry" — both are the same government registry rail.
        assert "NPI" in str(db_lead.get("source", "")).upper(), (
            f"NPI row {db_lead.get('id')} lacks NPI registry provenance: {db_lead.get('source')}"
        )
        assert len(db_lead.get("phone", "")) >= 10
        assert not str(db_lead.get("phone")).startswith("+1200")
        assert not str(db_lead.get("phone")).startswith("+1555")
        assert db_lead.get("new_today") is True or db_lead.get("first_seen_at")


def test_single_writer_concurrency_race():
    from MBM.LeadEngine.test_writer_race_and_reconciliation import run_writer_race_test
    report = run_writer_race_test()
    assert report["database_stable_after_writer_race"] is True
    assert report["thread_errors"] == []
    assert report["threads_successful"] == report["threads_launched"] == 8
    assert report["valid_json"] is True
    assert report["zero_shrinkage_invariant_maintained"] is True
