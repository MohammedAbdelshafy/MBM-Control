#!/usr/bin/env python3
"""One-shot recovery enforcement: demote any NPI row that is flagged callable
while failing the canonical verification gate (identity-first law)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH
from MBM.LeadEngine.dialer_verification_gate import check_lead


def main() -> int:
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    leads = writer.read_leads()
    demotions = []
    for l in leads:
        if not str(l.get("id", "")).startswith("NPI-"):
            continue
        if not l.get("callable"):
            continue
        r = check_lead(l)
        if not r["passed"]:
            l["callable"] = False
            l["queue_bucket"] = "VERIFICATION_REQUIRED"
            l["status"] = "VERIFICATION_REQUIRED"
            l["blocked_reason"] = "GATE_FAIL:" + ",".join(r["rejection_reasons"])
            demotions.append(l)
    print(f"[SCAN] callable NPI rows failing gate: {len(demotions)}")
    for l in demotions:
        print("  -", l.get("id"), l.get("blocked_reason"))
    if not demotions:
        return 0
    res = writer.commit_update(
        demotions,
        author="GATE_ENFORCEMENT_RECOVERY",
        allow_upsert=True,
        reason="crash_recovery_demote_callable_gate_failures",
    )
    print(f"[WRITE] {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
