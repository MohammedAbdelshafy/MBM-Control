"""
REGRESSION TESTS: DIALER SINGLE-WRITER LOCK
=============================================================================
Guards the production leads_database.json against concurrent writers:
1. test_single_writer_lock_acquire_release - exclusive O_EXCL lock lifecycle
2. test_single_writer_lock_excludes_second  - concurrent writer is blocked
3. test_single_writer_lock_read_modify_write - atomic read/write via lock
4. test_stale_lock_break - stale lock (old PID) is broken safely
=============================================================================
"""

import os
import sys
import time
import json
import threading
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock


def _lock_on(db_path: Path):
    return DialerDatabaseLock(db_path=db_path)


def test_single_writer_lock_acquire_release(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text("[]", encoding="utf-8")
    lock = _lock_on(db)
    assert lock.acquire() is True
    assert lock.is_held() is True
    lock.release()
    assert lock.is_held() is False


def test_single_writer_lock_excludes_second(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text("[]", encoding="utf-8")
    lock1 = _lock_on(db)
    lock2 = _lock_on(db)
    assert lock1.acquire() is True
    assert lock2.acquire(timeout=0.2) is False  # second writer blocked
    lock1.release()
    assert lock2.acquire() is True
    lock2.release()


def test_single_writer_lock_read_modify_write(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text('[]', encoding="utf-8")
    with _lock_on(db) as lock:
        rows = lock.read()
        rows.append({"id": "NPI-1", "phone": "+17873068356"})
        total = lock.write(rows)
    assert total == 1
    # Data persisted and readable under a fresh lock.
    with _lock_on(db) as lock:
        assert len(lock.read()) == 1


def test_stale_lock_break(tmp_path):
    db = tmp_path / "leads_database.json"
    db.write_text('[]', encoding="utf-8")
    lock = _lock_on(db)
    assert lock.acquire() is True
    lock_file = lock.lock_path
    lock.release()
    # Simulate a crashed/abandoned writer: a stale lock file with an old timestamp.
    lock_file.write_text(
        json.dumps({"pid": 999999, "run_id": "stale", "acquired_at": time.time() - 3600, "db": str(db)}),
        encoding="utf-8",
    )
    # A new writer must be able to break the stale lock.
    lock2 = _lock_on(db)
    assert lock2.acquire() is True
    lock2.release()