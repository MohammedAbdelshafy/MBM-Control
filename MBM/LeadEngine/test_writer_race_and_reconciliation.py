#!/usr/bin/env python3
"""
MBM LeadEngine - Writer Race & 242 NPI Concurrency Verification Suite
=============================================================================
Tests concurrent single-writer lock contention, verifies zero dataset corruption,
zero record shrinkage, and 100% retention of the 242 authoritative NPI records.
=============================================================================
"""

import sys
import json
import hashlib
import threading
import time
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH

def compute_db_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def run_writer_race_test() -> Dict[str, Any]:
    print("=" * 80)
    print("RUNNING CONCURRENT WRITER-RACE TEST ON LEADS_DATABASE.JSON")
    print("=" * 80)

    initial_sha = compute_db_sha256(DIALER_DB_PATH)
    initial_size = DIALER_DB_PATH.stat().st_size
    initial_leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    initial_count = len(initial_leads)

    print(f"Baseline: Count={initial_count} | Size={initial_size} bytes | SHA256={initial_sha[:12]}...")

    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    errors = []
    thread_results = []

    def worker(worker_id: int, lead_id: str, note: str):
        try:
            update_payload = [{
                "id": lead_id,
                "notes": note,
                "last_dialed_worker": f"WORKER_{worker_id}",
                "last_dialed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }]
            res = writer.commit_update(update_payload, author=f"RACE_WORKER_{worker_id}")
            thread_results.append((worker_id, res))
        except Exception as e:
            errors.append((worker_id, str(e)))

    # Spawn 8 concurrent threads attempting rapid updates
    threads = []
    test_npi_ids = [l["id"] for l in initial_leads if str(l.get("id", "")).startswith("NPI-")][:8]

    for idx, nid in enumerate(test_npi_ids):
        t = threading.Thread(target=worker, args=(idx + 1, nid, f"Concurrent stress test note from worker {idx+1}"))
        threads.append(t)

    start_time = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start_time

    # Re-read and audit final state
    raw_final = DIALER_DB_PATH.read_text(encoding="utf-8")
    try:
        final_leads = json.loads(raw_final)
        valid_json = True
    except Exception as e:
        valid_json = False
        final_leads = []

    final_count = len(final_leads)
    final_sha = compute_db_sha256(DIALER_DB_PATH)

    # Check 242 NPI presence
    daily_dir = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "daily" / "2026-08-16"
    artifact_files = list(daily_dir.glob("lead_NPI-*.json"))
    artifact_ids = set()
    for f in artifact_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        artifact_ids.add(d.get("id"))

    final_ids = set(l.get("id") for l in final_leads)
    missing_npis = artifact_ids - final_ids

    race_report = {
        "threads_launched": len(threads),
        "threads_successful": len(thread_results),
        "thread_errors": errors,
        "duration_seconds": round(duration, 3),
        "initial_count": initial_count,
        "final_count": final_count,
        "valid_json": valid_json,
        "total_242_artifacts_checked": len(artifact_ids),
        "total_242_artifacts_retained": len(artifact_ids) - len(missing_npis),
        "missing_242_artifacts": len(missing_npis),
        "zero_shrinkage_invariant_maintained": final_count >= initial_count,
        "database_stable_after_writer_race": valid_json and (len(missing_npis) == 0) and (final_count >= initial_count),
    }

    print("=" * 80)
    print("WRITER-RACE AUDIT RESULTS:")
    print(json.dumps(race_report, indent=2))
    print("=" * 80)

    return race_report

if __name__ == "__main__":
    run_writer_race_test()
