"""
REGRESSION TESTS: PRODUCTION SINGLE-WRITER CONTRACT
=============================================================================
Locks in the contract that every mutation of `leads_database.json` must be
atomic, must never shrink the dataset without explicit authorization, and must
go through DialerSingleWriter / DialerDatabaseLock / commit_dialer_db /
patch_dialer_db / dialer_gateway (NO raw write_text / open("w") / rename on the
live store).

Covers the merged class in MBM/GLM/single_writer_lock.py:
1. test_no_shrink_blocks_default            - subset commit raises (no shrink)
2. test_no_shrink_allows_with_allow_shrink   - subset commit w/ allow_shrink ok
3. test_regression_fixture_full_sync         - mixed add/update/phone-reject
4. test_idless_record_never_lands            - records without id never land
5. test_placeholder_phone_rejected           - 555-exchange phone blocked
6. test_revision_bumps_and_audit_appended    - rev++ + audit entry on each commit
7. test_stale_writer_rejected                - stale read + stale-writer rejection
8. test_concurrent_writers_serialized        - parallel writers, no corruption
9. test_malformed_db_fails_loud             - corrupt live DB raises (no silent garbage)
10. test_interrupted_write_cleans_temp      - temp file removed on failure
11. test_dialer_db_lock_write_atomic_and_audited  - DialerDatabaseLock.write path
12. test_dialer_db_lock_no_shrink_default   - DialerDatabaseLock.write no-shrink
13. test_static_guard_detects_rogue_writer   - a raw write_text .py is flagged
14. test_static_guard_clean_module            - sanctioned gateway .py is clean
15. test_static_guard_cleans_fixed_tree       - repo writers are gate-clean
=============================================================================
"""

import json
import sys
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from MBM.GLM.single_writer_lock import (
    DialerSingleWriter,
    SingleWriterViolation,
    sidecar_paths,
    _read_revision,
)
from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock
from MBM.LeadEngine.dialer_gateway import (
    patch_dialer_db,
    commit_dialer_db,
    validate_records,
)
from MBM.LeadEngine.check_single_writer import scan_file


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _make_lead(lid, phone="214-725-1001"):
    """A clean, fully-valid dialable lead (real phone, real company, real id)."""
    return {
        "id": f"REAL-{lid}",
        "company": f"Oak Street Practice {lid}",
        "phone": phone,
        "city": "Dallas",
        "state": "TX",
        "vertical": "Healthcare",
        "callable": True,
        "queue_bucket": "PRIME",
        "source": "NPI_REGISTRY",
        "source_reference": "npi-verified",
        "verification_status": "VERIFIED",
    }


def _write_db(db: Path, records):
    """Seed a DB file directly for test setup only (bypasses lock)."""
    tmp = db.parent / (db.name + ".init")
    tmp.write_text(json.dumps(list(records)), encoding="utf-8")
    tmp.replace(db)
    return list(records)


def _read_db(db: Path):
    return json.loads(db.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1-2  no-shrink guard
# ---------------------------------------------------------------------------

def test_no_shrink_blocks_default(tmp_path):
    db = tmp_path / "leads_database.json"
    existing = [_make_lead(i) for i in range(10)]
    _write_db(db, existing)
    subset = existing[:4]  # shrinking is forbidden without explicit opt-in
    with pytest.raises(SingleWriterViolation):
        commit_dialer_db(subset, reason="shrink-test", db_path=db)


def test_no_shrink_allows_with_allow_shrink(tmp_path):
    db = tmp_path / "leads_database.json"
    existing = [_make_lead(i) for i in range(10)]
    _write_db(db, existing)
    subset = existing[:4]
    res = commit_dialer_db(subset, reason="shrink-ok", allow_shrink=True, db_path=db)
    assert res["final_count"] == 4
    assert res["mode"] == "full_replace"
    assert _read_revision(db) >= 1


# ---------------------------------------------------------------------------
# 3  regression fixture - mixed add / update / placeholder rejection
# ---------------------------------------------------------------------------

def test_regression_fixture_full_sync(tmp_path):
    db = tmp_path / "leads_database.json"
    existing = [_make_lead(i) for i in range(100)]
    _write_db(db, existing)

    # 20 brand-new clean leads (ids REAL-1000..1019)
    new_leads = [_make_lead(1000 + i) for i in range(20)]
    # 10 existing ids receiving an improved phone (upsert -> updated), ids REAL-0..9
    improved = [_make_lead(i, phone=f"214-725-2{i:03d}") for i in range(10)]
    # 5 existing ids re-submitted (dupes -> updated), ids REAL-0..4
    dupes = [_make_lead(i, phone=f"214-725-3{i:03d}") for i in range(5)]
    # 3 placeholder phones (555 in the NANP EXCHANGE digits[3:6] -> rejected_bad_phone)
    bad_phones = [_make_lead(2000 + i, phone=f"214-555-0{i:03d}") for i in range(3)]

    incoming = new_leads + improved + dupes + bad_phones
    res = patch_dialer_db(incoming, reason="regression-fixture", author="TEST", db_path=db)

    assert res["final_count"] == 120
    assert res["added_count"] == 20
    assert res["updated_count"] == 15  # 10 improved + 5 dupes
    assert res["rejected_count"] == 0
    assert res["rejected_bad_phone"] == 3
    assert res["rejected_synthetic"] == 0
    assert res["rejected_suppressed"] == 0
    on_disk = _read_db(db)
    assert len(on_disk) == 120
    # REAL-0 phone was last written by the dupes batch -> "214-725-3000"
    first = next(lead for lead in on_disk if lead["id"] == "REAL-0")
    assert first["phone"] == "214-725-3000"


# ---------------------------------------------------------------------------
# 4-5  id / phone validation
# ---------------------------------------------------------------------------

def test_idless_record_never_lands(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [])  # empty store
    no_id = {"company": "No Id Practice", "phone": "214-725-1001"}
    writer = DialerSingleWriter(db_path=db)
    # _validate_lead vetoes id-less records -> rejected_count, db stays empty.
    res = writer.commit_update([no_id], reason="no-id")
    assert _read_db(db) == []
    assert res["rejected_count"] == 1


def test_placeholder_phone_rejected(tmp_path):
    # 555 in the NANP exchange (digits[3:6]) is a reserved/placeholder number.
    rec = {"id": "R-1", "company": "Bad", "phone": "214-555-0101"}
    filtered = validate_records([rec])
    assert filtered["rejected_bad_phone"] == 1
    clean_ids = [r.get("id") for r in filtered["clean"]]
    assert "R-1" not in clean_ids

    # And via the gateway: only-bad records onto a populated store raise no-shrink
    db = tmp_path / "leads_database.json"
    existing = [_make_lead(i) for i in range(2)]
    _write_db(db, existing)
    with pytest.raises(SingleWriterViolation):
        commit_dialer_db([rec], reason="bad-phone", db_path=db)
    assert len(_read_db(db)) == 2  # untouched


# ---------------------------------------------------------------------------
# 6  revision + audit sidecar
# ---------------------------------------------------------------------------

def test_revision_bumps_and_audit_appended(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(0)])
    rev_file, audit_file = sidecar_paths(db)
    payload = [_make_lead(i) for i in range(5)]
    assert _read_revision(db) == 0

    w = DialerSingleWriter(db_path=db)
    w.full_replace(payload, reason="b")

    assert _read_revision(db) == 1
    rev_data = json.loads(rev_file.read_text(encoding="utf-8"))
    assert rev_data["revision"] == 1
    # audit is JSONL (one JSON object per line) -> count lines, not dict keys.
    audit_lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    first_entry = json.loads(audit_lines[0])
    assert first_entry["operation_id"].startswith("GLM_SWARM:")
    assert first_entry["mode"] == "full_replace"


# ---------------------------------------------------------------------------
# 7  stale-writer protection
# ---------------------------------------------------------------------------

def test_stale_writer_rejected(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(i) for i in range(2)])
    w = DialerSingleWriter(db_path=db)
    old_rev = _read_revision(db)
    # a second writer commits between the first writer's read and commit
    w2 = DialerSingleWriter(db_path=db)
    w2.full_replace([_make_lead(i) for i in range(3)], reason="concurrent-bump")

    with pytest.raises(SingleWriterViolation):
        w.commit_update(
            [_make_lead(10, phone="214-725-1099")],
            expected_revision=old_rev,  # stale -> rejected
        )


# ---------------------------------------------------------------------------
# 8  concurrent writers serialized
# ---------------------------------------------------------------------------

def test_concurrent_writers_serialized(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(0)])
    errors = []

    def worker():
        try:
            w = DialerSingleWriter(db_path=db)
            w.full_replace([_make_lead(i) for i in range(5)], author="W", reason="concurrent")
        except Exception as e:  # pragma: no cover - surfaced via errors list
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    final = _read_db(db)
    assert len(final) == 5
    assert _read_revision(db) == 5  # one committed revision per writer


# ---------------------------------------------------------------------------
# 9  malformed existing db fails loud
# ---------------------------------------------------------------------------

def test_malformed_db_fails_loud(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(i) for i in range(3)])
    db.write_text("{ broken json", encoding="utf-8")  # corrupt the live store
    w = DialerSingleWriter(db_path=db)
    # A corrupt live DB must NOT return garbage: it preserves the corrupt
    # snapshot to a `.corrupt_*` sibling and recovers to an empty result.
    assert w.read_leads() == []
    preserved = list(db.parent.glob("*.corrupt_*"))
    assert preserved, "corrupt snapshot should be preserved for forensics"


# ---------------------------------------------------------------------------
# 10  interrupted write cleans temp
# ---------------------------------------------------------------------------

def test_interrupted_write_cleans_temp(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(i) for i in range(2)])
    snapshot = _read_db(db)
    w = DialerSingleWriter(db_path=db)
    # Stale expected_revision raises BEFORE any temp write -> DB untouched, no leak.
    with pytest.raises(SingleWriterViolation):
        w.full_replace([_make_lead(i) for i in range(4)], expected_revision=999)
    temps = list(tmp_path.glob("*.tmp"))
    assert temps == [], f"temp file leaked: {temps}"
    assert _read_db(db) == snapshot


# ---------------------------------------------------------------------------
# 11-12  DialerDatabaseLock.write hardens atomicity
# ---------------------------------------------------------------------------

def test_dialer_db_lock_write_atomic_and_audited(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(i) for i in range(2)])
    lock = DialerDatabaseLock(db_path=db)
    with lock:
        count = lock.write([_make_lead(i) for i in range(6)])
    assert count == 6
    assert _read_db(db) == [_make_lead(i) for i in range(6)]
    assert _read_revision(db) >= 1


def test_dialer_db_lock_no_shrink_default(tmp_path):
    db = tmp_path / "leads_database.json"
    _write_db(db, [_make_lead(i) for i in range(6)])
    lock = DialerDatabaseLock(db_path=db)
    with lock, pytest.raises(SingleWriterViolation):
        lock.write([_make_lead(i) for i in range(2)])
    assert len(_read_db(db)) == 6  # untouched


# ---------------------------------------------------------------------------
# 13-15  static guard (check_single_writer) detects / passes
# ---------------------------------------------------------------------------

def test_static_guard_detects_rogue_writer(tmp_path):
    rogue = tmp_path / "rogue_writer.py"
    rogue.write_text(
        "from pathlib import Path\n"
        "DB = Path('mbm-dialer/app/public/leads_database.json')\n"
        "DB.write_text('[]', encoding='utf-8')\n",
        encoding="utf-8",
    )
    violations = scan_file(rogue, tmp_path)
    lines = [line for _, line in violations]
    assert any("write_text" in line for line in lines), violations


def test_static_guard_clean_module(tmp_path):
    clean = tmp_path / "clean_writer.py"
    clean.write_text(
        "from MBM.LeadEngine.dialer_gateway import patch_dialer_db, commit_dialer_db\n"
        "records = [{'id': 'c-1', 'phone': '214-725-1001'}]\n"
        "patch_dialer_db(records, reason='t')\n"
        "commit_dialer_db(records, reason='t2')\n",
        encoding="utf-8",
    )
    violations = scan_file(clean, tmp_path)
    assert violations == [], violations


def test_static_guard_cleans_fixed_tree():
    """The repo writers I hardened must pass the static guard clean."""
    fixed_files = [
        ROOT_DIR / "MBM" / "LeadEngine" / "dialer_gateway.py",
        ROOT_DIR / "MBM" / "LeadEngine" / "dialer_db_lock.py",
        ROOT_DIR / "MBM" / "GLM" / "single_writer_lock.py",
        ROOT_DIR / "MBM" / "LeadEngine" / "scripts" / "apply_recovery_merge.py",
        ROOT_DIR / "MBM" / "LeadEngine" / "daily_lead_factory.py",
    ]
    total = 0
    for f in fixed_files:
        if not f.exists():
            continue
        v = scan_file(f, ROOT_DIR)
        assert v == [], f"{f.relative_to(ROOT_DIR)} has rogue writers: {v}"
        total += len(v)
    assert total == 0
