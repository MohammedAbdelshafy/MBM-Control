#!/usr/bin/env python3
"""One-shot recovery backfill: give EVERY canonical lead its segment/script.

Law: scripts never make a lead callable; they only guarantee that IF a lead
is ever gated callable, its segment-correct script is already on file.
All writes go through DialerSingleWriter (revision + audit + no-shrink).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH
from MBM.LeadEngine.dialer_script_engine import DialerScriptEngine, enrich_leads_with_playbooks


def main() -> int:
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    leads = writer.read_leads()
    missing = [
        l for l in leads
        if not l.get("script_id") or not l.get("Call_Script")
        or not l.get("segment") or not l.get("sales_strategy")
    ]
    print(f"[SCAN] total={len(leads)} missing_script_fields={len(missing)}")
    if not missing:
        print("[OK] nothing to backfill")
        return 0

    fixed = enrich_leads_with_playbooks(missing)
    for src, dst in zip(missing, fixed):
        assert dst.get("script_id") and dst.get("Call_Script") and dst.get("segment"), dst.get("id")

    res = writer.commit_update(
        fixed,
        author="SCRIPT_BACKFILL_RECOVERY",
        allow_upsert=True,
        reason="crash_recovery_script_coverage_100pct",
    )
    print(f"[WRITE] {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
