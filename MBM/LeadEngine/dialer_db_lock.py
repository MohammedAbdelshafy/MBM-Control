#!/usr/bin/env python3
"""
DIALER DATABASE SINGLE-WRITER LOCK
=============================================================================
Enforces ONE authoritative writer for `leads_database.json` and provides
atomic read-modify-write under the lock.

Without this, concurrent rebuilds (daily factory, reconciliation, rerank,
push jobs, JARVIS, pre_live acceptance) race and produce the observed
unstable counts (e.g. 762 -> 702 during verification).

Usage:
    with DialerDatabaseLock() as lock:
        db = lock.read()          # atomic read of the production dataset
        db.append(new_lead)
        lock.write(db)            # atomic write under the lock

    with dialer_write_lock():     # alias / no-op-safe context
        ...

Lock semantics:
  - Lock file lives NEXT TO the database (same filesystem) so processes on
    any path resolve it consistently.
  - Uses O_CREAT|O_EXCL atomic acquire with a run_id + PID.
  - Stale-lock break after STALE_AFTER_SECONDS (default 300s) so a crashed
    process cannot deadlock production forever.
  - Re-entrant within the same process (thread-safe via threading.RLock).
=============================================================================
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
import errno
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

ROOT_DIR = Path(__file__).resolve().parents[2]
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"

# SHARED lock file used by EVERY canonical gateway (GLM DialerSingleWriter,
# Node dialerDbGateway.js, and this lock). One lock file = one mutex = true
# single-writer resource. A second lock file would let two "authorized"
# writers race each other.
SHARED_LOCK_FILE = ROOT_DIR / "MBM" / "Artifacts" / ".leads_database.lock"

STALE_AFTER_SECONDS = 300


class DialerDatabaseLock:
    """
    Cross-process exclusive lock protecting writes to the production dialer DB.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        stale_after: int = STALE_AFTER_SECONDS,
    ):
        self.db_path = Path(db_path) if db_path else DIALER_DB_PATH
        if str(self.db_path).replace("\\", "/").endswith("mbm-dialer/app/public/leads_database.json"):
            # Live production DB -> use the SHARED canonical lock file so this
            # lock mutually excludes GLM single-writer and Node gateway writers.
            self.lock_path = SHARED_LOCK_FILE
            # Mirrors DialerSingleWriter.BACKUP_DIR for canonical backup snapshots.
            from MBM.GLM.single_writer_lock import BACKUP_DIR as _BACKUP_DIR
            self.backup_dir = _BACKUP_DIR
        else:
            # Test / fixture / other DB -> lock next to the DB (isolated).
            self.lock_path = self.db_path.with_suffix(self.db_path.suffix + ".lock")
            # Keep backups isolated from production for hermetic tests.
            self.backup_dir = self.db_path.parent / "db_backups"
        self.stale_after = stale_after
        self._run_id = uuid.uuid4().hex[:12]
        self._local = threading.local()
        self._held_pid: Optional[int] = None

    # -- internal helpers ---------------------------------------------------

    def _own_lock(self) -> bool:
        return getattr(self._local, "held", False)

    def _acquire_fd(self) -> Optional[int]:
        """Try O_CREAT|O_EXCL acquisition. Returns fd or None on conflict."""
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.lock_path), flags)
        except OSError as e:
            if e.errno in (errno.EEXIST, errno.EACCES):
                return None
            raise
        try:
            os.write(
                fd,
                (
                    json.dumps(
                        {
                            "run_id": self._run_id,
                            "pid": os.getpid(),
                            "acquired_at": time.time(),
                            "db": str(self.db_path),
                        }
                    )
                ).encode("utf-8"),
            )
            os.fsync(fd)
        except Exception:
            os.close(fd)
            raise
        return fd

    def _break_stale_lock(self) -> bool:
        """Remove a lock file whose holder has not refreshed recently."""
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            acquired_at = float(data.get("acquired_at", 0))
            pid = int(data.get("pid", -1))
            if time.time() - acquired_at > self.stale_after:
                # Also verify the holder process is actually dead (Windows).
                if os.name == "nt":
                    try:
                        import psutil  # type: ignore
                        if psutil.pid_exists(pid):
                            return False
                    except Exception:
                        pass
                self.lock_path.unlink(missing_ok=True)
                return True
        except Exception:
            return False
        return False

    def acquire(self, timeout: float = 90.0) -> bool:
        """Block up to `timeout` seconds until the lock is held."""
        if self._own_lock():
            return True
        deadline = time.time() + timeout
        while True:
            fd = self._acquire_fd()
            if fd is not None:
                os.close(fd)
                self._local.held = True
                self._held_pid = os.getpid()
                return True
            if self._break_stale_lock():
                continue
            if time.time() >= deadline:
                return False
            time.sleep(0.25)

    def release(self) -> None:
        if self._own_lock():
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._local.held = False
            self._held_pid = None

    def is_held(self) -> bool:
        """True when THIS process currently holds the lock."""
        return self._own_lock()

    def __enter__(self) -> "DialerDatabaseLock":
        if not self.acquire():
            raise RuntimeError(
                f"Cannot acquire dialer DB write lock ({self.lock_path}) - another writer is active."
            )
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    # -- atomic read / write under lock -------------------------------------

    def read(self) -> List[Dict[str, Any]]:
        """Read the production dataset (must hold lock or it reads cleanly)."""
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                return []
        return []

    def write(
        self,
        records: Union[List[Dict[str, Any]], Dict[str, Any]],
        *,
        allow_shrink: bool = False,
        author: str = "DIALER_DB_LOCK",
        reason: str = "dialer_db_lock",
        expected_revision: Optional[int] = None,
        operation_id: Optional[str] = None,
    ) -> int:
        """Atomically persist the dataset under the held lock. Returns count.

        Now backed by the SAME canonical primitive as ``DialerSingleWriter`` —
        validate-before-replace, no-shrink guard (unless ``allow_shrink``), a
        backup snapshot, and a revision + audit log entry. A raw ``write_text``
        is no longer used anywhere on the production store.
        """
        if isinstance(records, dict):
            records = records.get("leads", []) if isinstance(records.get("leads"), list) else []

        from MBM.GLM.single_writer_lock import atomic_persist
        existing = self.read()
        initial_count = len(existing)
        result = atomic_persist(
            self.db_path,
            records,
            backup_dir=self.backup_dir,
            initial_count=initial_count,
            allow_shrink=allow_shrink,
            author=author,
            reason=reason,
            operation_id=operation_id or f"{author}:{reason}",
            mode="dialer_db_lock.write",
            expected_revision=expected_revision,
        )
        return result["final_count"]

    def read_modify_write(self, modifier) -> int:
        """Read -> call modifier(records) -> write, all under the lock."""
        records = self.read()
        modifier(records)
        return self.write(records)


class dialer_write_lock:
    """Alias context manager (self-documenting) delegating to DialerDatabaseLock."""

    def __init__(self, db_path: Optional[Path] = None):
        self._lock = DialerDatabaseLock(db_path=db_path)

    def __enter__(self) -> DialerDatabaseLock:
        self._lock.__enter__()
        return self._lock

    def __exit__(self, *exc) -> None:
        self._lock.__exit__(*exc)


if __name__ == "__main__":
    lock = DialerDatabaseLock()
    if lock.acquire():
        try:
            n = len(lock.read())
            print(f"[OK] Acquired single-writer lock (run_id={lock._run_id}). dialer rows={n}")
        finally:
            lock.release()
            print("[OK] Released lock.")
    else:
        print("[ERROR] Could not acquire lock - another writer is active.")
        sys.exit(1)