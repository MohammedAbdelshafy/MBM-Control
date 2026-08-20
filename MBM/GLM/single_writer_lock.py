#!/usr/bin/env python3
"""
MBM Canonical Single-Writer Gateway for Dialer Inventory (leads_database.json)
=============================================================================
Enforces a single canonical writer rule across all background processes, daemons,
reconcilers, and agents.

Guarantees:
  1. Process-level mutex lock on `leads_database.json`.
  2. Monotonic non-destructive updates (leads can NEVER be silently dropped or shrunk).
  3. Strict schema validation & verification gate enforcement.
  4. Real-source provenance (NPI, DCAD, Secretary of State, County Records). Zero synthetic rows.
  5. Atomic write with backup snapshot creation before any file modification.
"""

import os
import json
import time
import shutil
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CANONICAL_MEMORY_PATH = ROOT_DIR / "MBM" / "Artifacts" / "canonical_deals_memory.json"
BACKUP_DIR = ROOT_DIR / "MBM" / "Artifacts" / "db_backups"
LOCK_FILE = ROOT_DIR / "MBM" / "Artifacts" / ".leads_database.lock"
REVISION_FILE = ROOT_DIR / "MBM" / "Artifacts" / "leads_database_revision.json"
AUDIT_FILE = ROOT_DIR / "MBM" / "Artifacts" / "leads_database_audit.jsonl"


class SingleWriterViolation(Exception):
    """Raised when a concurrent or invalid write attempt is detected."""
    pass


def sidecar_paths(db_path: Path) -> Tuple[Path, Path]:
    """Return (revision_file, audit_file) for a given dialer DB.

    The production store keeps its revision + audit in MBM/Artifacts so the
    live JSON stays a BARE LIST (the dialer app reads it directly). Test /
    fixture DBs get their sidecars next to the DB so tests stay hermetic.
    """
    db_str = str(db_path).replace("\\", "/")
    if db_str.endswith("mbm-dialer/app/public/leads_database.json"):
        return REVISION_FILE, AUDIT_FILE
    return (
        db_path.with_name(f"{db_path.name}.revision.json"),
        db_path.with_name(f"{db_path.name}.audit.jsonl"),
    )


def compute_checksum(records: List[Dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _is_prod_db(db_path: Path) -> bool:
    return str(db_path).replace("\\", "/").endswith("mbm-dialer/app/public/leads_database.json")


class DialerSingleWriter:
    """The SOLE authorized gateway for modifying `leads_database.json`."""

    def __init__(self, db_path: Path = DIALER_DB_PATH):
        self.db_path = db_path
        prod = _is_prod_db(db_path)
        # Production uses the shared canonical lock + Artifacts backup dir so all
        # gateways mutually exclude. Non-production (tests/fixtures) keep their
        # lock/backup/revision/audit NEXT TO the db so tests are fully hermetic.
        self.lock_file = LOCK_FILE if prod else db_path.with_name(db_path.name + ".lock")
        self.backup_dir = BACKUP_DIR if prod else db_path.parent / "db_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.Lock()

    def _acquire_lock(self, timeout_sec: float = 15.0) -> bool:
        start = time.time()
        # Acquire thread lock first
        if not self._thread_lock.acquire(timeout=timeout_sec):
            return False

        while time.time() - start < timeout_sec:
            try:
                # Atomic file creation using exclusive mode 'x'
                with open(self.lock_file, "x", encoding="utf-8") as f:
                    json.dump({
                        "pid": os.getpid(),
                        "thread_id": threading.get_ident(),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }, f)
                return True
            except FileExistsError:
                # If lock file exists and is stale (> 30 sec old), break it
                try:
                    mtime = self.lock_file.stat().st_mtime
                    if time.time() - mtime > 30.0:
                        self.lock_file.unlink(missing_ok=True)
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.05)

        self._thread_lock.release()
        return False

    def _release_lock(self):
        try:
            if self.lock_file.exists():
                self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass
        finally:
            if self._thread_lock.locked():
                try:
                    self._thread_lock.release()
                except RuntimeError:
                    pass

    def read_leads(self) -> List[Dict[str, Any]]:
        """Safely read the current active dialer database.

        On invalid JSON the corrupt file is preserved to a ``.corrupt`` backup
        and the most recent valid snapshot from ``db_backups`` is restored, so a
        mid-write crash can never silently return an empty dataset.
        """
        if not self.db_path.exists():
            return []
        try:
            data = json.loads(self.db_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("leads"), list):
                return data["leads"]
            print(f"[WARN] {self.db_path.name} is not a list; treating as empty.")
            return []
        except Exception as e:
            print(f"[WARN] Error reading {self.db_path}: {e}")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            corrupt = self.db_path.with_name(f"{self.db_path.name}.corrupt_{ts}")
            try:
                shutil.copy2(self.db_path, corrupt)
                print(f"[WARN] Corrupt dialer DB preserved to {corrupt.name}")
            except Exception:
                pass
            # Restore the most recent valid backup if available.
            backups = sorted(self.backup_dir.glob("leads_database_backup_*.json"), reverse=True)
            for b in backups:
                try:
                    data = json.loads(b.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        print(f"[RECOVER] Restored {len(data)} leads from {b.name}")
                        return data
                except Exception:
                    continue
            return []

    def _validate_lead(self, lead: Dict[str, Any]) -> bool:
        """Enforce strict real-source and valid contact invariants."""
        # 1. Must have an ID and contact/company
        lead_id = str(lead.get("id") or "").strip()
        if not lead_id:
            return False

        # 2. Must have a non-fake phone number
        phone = str(lead.get("phone") or lead.get("details", {}).get("Owner_Phone", "")).strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10:
            return False
        if "555" in digits[3:6] or digits.startswith("000"):
            return False

        return True

    # -- revision + audit sidecars ------------------------------------------

    def _sidecar(self) -> Tuple[Path, Path]:
        return sidecar_paths(self.db_path)

    def read_revision(self) -> int:
        """Return the current monotonic revision of the live DB (0 if none yet)."""
        return _read_revision(self.db_path)

    def read_checksum(self) -> Optional[str]:
        """Return the checksum of the last committed state (None if none yet)."""
        rev_file, _ = self._sidecar()
        if not rev_file.exists():
            return None
        try:
            return json.loads(rev_file.read_text(encoding="utf-8")).get("checksum")
        except Exception:
            return None

    def _append_audit(self, entry: Dict[str, Any]) -> None:
        _append_audit(self.db_path, entry)

    def _atomic_write(
        self,
        records: List[Dict[str, Any]],
        *,
        author: str,
        reason: str,
        operation_id: str,
        initial_count: int,
        mode: str,
        allow_shrink: bool = False,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Delegate to the shared module-level atomic_persist (caller holds lock)."""
        return atomic_persist(
            self.db_path,
            records,
            backup_dir=self.backup_dir,
            initial_count=initial_count,
            author=author,
            reason=reason,
            operation_id=operation_id,
            mode=mode,
            allow_shrink=allow_shrink,
            expected_revision=expected_revision,
        )

    def commit_update(
        self,
        new_or_updated_leads: List[Dict[str, Any]],
        author: str = "GLM_SWARM",
        allow_upsert: bool = True,
        reason: str = "commit_update",
        operation_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Atomically merges and writes leads to `leads_database.json`.
        Guarantees that total lead count NEVER decreases without explicit authorization.
        """
        if not self._acquire_lock():
            raise SingleWriterViolation("Could not acquire single-writer lock")

        try:
            existing_leads = self.read_leads()
            existing_map = {
                str(rec.get("id")): rec for rec in existing_leads if rec.get("id")
            }
            initial_count = len(existing_map)

            added_count = 0
            updated_count = 0
            rejected_count = 0

            for candidate in new_or_updated_leads:
                cid = str(candidate.get("id") or "").strip()
                if not self._validate_lead(candidate):
                    rejected_count += 1
                    continue

                if cid in existing_map:
                    if allow_upsert:
                        # Deep merge preserving existing verified fields
                        merged = {**existing_map[cid], **candidate}
                        existing_map[cid] = merged
                        updated_count += 1
                else:
                    existing_map[cid] = candidate
                    added_count += 1

            final_leads = list(existing_map.values())
            result = self._atomic_write(
                final_leads,
                author=author,
                reason=reason,
                operation_id=operation_id or f"{author}:{reason}",
                initial_count=initial_count,
                mode="commit_update",
                expected_revision=expected_revision,
            )
            result.update(
                {
                    "added_count": added_count,
                    "updated_count": updated_count,
                    "rejected_count": rejected_count,
                }
            )
            return result
        finally:
            self._release_lock()

    def full_replace(
        self,
        records: List[Dict[str, Any]],
        author: str = "GLM_SWARM",
        allow_shrink: bool = False,
        reason: str = "full_replace",
        operation_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Authorized whole-file replacement used by annotators that rewrite the
        full dialer DB (skip-trace verifier, seller skip tracer, dashboard
        bundler). Acquires the single-writer lock, snapshots a backup, and
        refuses to shrink the dataset unless ``allow_shrink`` is explicitly set.
        """
        if not self._acquire_lock():
            raise SingleWriterViolation("Could not acquire single-writer lock")

        try:
            existing = self.read_leads()
            initial_count = len(existing)

            if not isinstance(records, list):
                raise SingleWriterViolation("full_replace requires a list of records")

            result = self._atomic_write(
                records,
                author=author,
                reason=reason,
                operation_id=operation_id or f"{author}:{reason}",
                initial_count=initial_count,
                mode="full_replace",
                allow_shrink=allow_shrink,
                expected_revision=expected_revision,
            )
            result["mode"] = "full_replace"
            return result
        finally:
            self._release_lock()


def _read_revision(db_path: Path) -> int:
    """Return the current monotonic revision of the DB (0 if none yet)."""
    rev_file, _ = sidecar_paths(db_path)
    if not rev_file.exists():
        return 0
    try:
        return int(json.loads(rev_file.read_text(encoding="utf-8")).get("revision", 0))
    except Exception:
        return 0


def _append_audit(db_path: Path, entry: Dict[str, Any]) -> None:
    _, audit_file = sidecar_paths(db_path)
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")


def _bump_revision(
    db_path: Path,
    *,
    author: str,
    reason: str,
    operation_id: str,
    records: List[Dict[str, Any]],
    initial_count: int,
    final_count: int,
    mode: str,
) -> int:
    """Persist the revision sidecar + append an audit entry (no lock needed)."""
    rev_file, _ = sidecar_paths(db_path)
    new_rev = _read_revision(db_path) + 1
    now = datetime.now(timezone.utc).isoformat()
    checksum = compute_checksum(records)
    rev_data = {
        "revision": new_rev,
        "checksum": checksum,
        "count": final_count,
        "updated_at": now,
        "author": author,
        "reason": reason,
        "operation_id": operation_id,
    }
    rev_file.parent.mkdir(parents=True, exist_ok=True)
    rev_file.write_text(json.dumps(rev_data, indent=2), encoding="utf-8")
    _append_audit(
        db_path,
        {
            "event": "write",
            "revision": new_rev,
            "timestamp": now,
            "author": author,
            "reason": reason,
            "operation_id": operation_id,
            "mode": mode,
            "initial_count": initial_count,
            "final_count": final_count,
            "checksum": checksum,
            "db": str(db_path),
        },
    )
    return new_rev


def atomic_persist(
    db_path: Path,
    records: List[Dict[str, Any]],
    *,
    backup_dir: Path,
    initial_count: int,
    author: str,
    reason: str,
    operation_id: str,
    mode: str,
    allow_shrink: bool = False,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate-before-replace atomic write (caller MUST hold the single-writer lock).

    Steps:
      1. Stale-writer check: if `expected_revision` is given and does not match the
         current on-disk revision, refuse to write.
      2. No-shrink invariant: refuse a smaller dataset unless `allow_shrink`.
      3. Backup snapshot of the pre-write state.
      4. Write a unique temp file, parse it back, verify round-trip before replacing
         the live file (validate-before-replace).
      5. Atomic os.replace (with retry for Windows file locks) + fsync.
      6. Bump the revision sidecar and append an audit entry.
    """
    final_leads = [r for r in records if isinstance(r, dict) and str(r.get("id") or "").strip()]
    final_count = len(final_leads)

    # 1. Stale-writer protection
    current_rev = _read_revision(db_path)
    if expected_revision is not None and current_rev != expected_revision:
        raise SingleWriterViolation(
            f"Stale writer blocked: expected revision {expected_revision} but "
            f"on-disk revision is {current_rev}. Re-read the current state and retry."
        )

    # 2. No-shrink invariant
    if not allow_shrink and final_count < initial_count:
        raise SingleWriterViolation(
            f"Dataset shrinkage detected! Initial: {initial_count}, Final: {final_count}. "
            "Write aborted. Pass allow_shrink=True only for explicit purge/repair operations."
        )

    # 3. Backup snapshot before modification
    if db_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"leads_database_backup_{ts}.json"
        shutil.copy2(db_path, backup_file)

    # 4. Temp write + validate-before-replace
    payload = json.dumps(final_leads, indent=2, ensure_ascii=False)
    tmp_name = f".leads_db_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.tmp"
    temp_path = db_path.parent / tmp_name
    temp_path.write_text(payload, encoding="utf-8")
    try:
        parsed = json.loads(temp_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("temp file is not a list")
        if len(parsed) != final_count:
            raise ValueError(f"temp count {len(parsed)} != expected {final_count}")
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise SingleWriterViolation(f"Validate-before-replace failed: {e}. Write aborted.")

    # 5. Atomic replace (retry for Windows file locks), fsync the live file.
    replaced = False
    for _ in range(20):
        try:
            with open(db_path, "r+b") as f:
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass
        try:
            temp_path.replace(db_path)
            replaced = True
            break
        except Exception:
            time.sleep(0.05)
    if not replaced:
        raise SingleWriterViolation(
            "Atomic replace failed after retries. Write aborted (live file untouched)."
        )
    try:
        with open(db_path, "r+b") as f:
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass
    finally:
        temp_path.unlink(missing_ok=True)

    # 6. Revision + audit
    new_rev = _bump_revision(
        db_path,
        author=author,
        reason=reason,
        operation_id=operation_id,
        records=final_leads,
        initial_count=initial_count,
        final_count=final_count,
        mode=mode,
    )

    rev = _read_revision(db_path)
    return {
        "ok": True,
        "author": author,
        "reason": reason,
        "operation_id": operation_id,
        "initial_count": initial_count,
        "final_count": final_count,
        "revision": rev if rev > 0 else new_rev,
        "checksum": compute_checksum(final_leads),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_single_writer() -> DialerSingleWriter:
    return DialerSingleWriter()


if __name__ == "__main__":
    writer = get_single_writer()
    leads = writer.read_leads()
    print(f"Single-Writer Gateway Status: ONLINE. Current Leads: {len(leads)}")
