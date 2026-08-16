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
    assert len(lead_files) == 242

    records, summary = load_and_manifest_242_artifacts()
    assert len(records) == 242
    assert summary["unique_npis"] == 242
    assert summary["duplicate_npis"] == 0
    assert summary["unique_phones"] == 242
    assert summary["duplicate_phones"] == 0
    assert summary["invalid_provenance_count"] == 0

    assert MANIFEST_JSON_PATH.exists()
    assert MANIFEST_MD_PATH.exists()

    manifest_data = json.loads(MANIFEST_JSON_PATH.read_text(encoding="utf-8"))
    assert len(manifest_data["manifest"]) == 242


def test_dialer_contains_exact_242_npi_records():
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    assert len(leads) >= 1086

    db_map = {l.get("id"): l for l in leads}

    records, _ = load_and_manifest_242_artifacts()
    for r in records:
        rid = r["id"]
        assert rid in db_map, f"Missing NPI record {rid} in dialer database"
        db_lead = db_map[rid]
        assert db_lead.get("source") == "US Government CMS NPI Registry"
        assert len(db_lead.get("phone", "")) >= 10
        assert not str(db_lead.get("phone")).startswith("+1200")
        assert not str(db_lead.get("phone")).startswith("+1555")
        assert db_lead.get("new_today") is True or db_lead.get("first_seen_at") == "2026-08-16"


def test_single_writer_concurrency_race():
    from MBM.LeadEngine.test_writer_race_and_reconciliation import run_writer_race_test
    report = run_writer_race_test()
    assert report["database_stable_after_writer_race"] is True
    assert report["missing_242_artifacts"] == 0
    assert report["valid_json"] is True
    assert report["zero_shrinkage_invariant_maintained"] is True
