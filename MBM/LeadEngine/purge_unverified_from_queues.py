#!/usr/bin/env python3
"""
Purge Unverified Leads From All Dialer Queues
===============================================
One-time cleanup script that removes fake/unverified entries from ALL queue files.

SAFE BY DEFAULT: --dry-run is the default. Nothing is written until --apply.
Backups are ALWAYS created before any write (*.bak).

Targets:
  - us_re_dialer_queue.json       (37 fake 555 numbers)
  - real_estate_calling_queue.json (1 fake 555 number)
  - cold_calling_queue.json        (NPI-sourced, mostly clean)
  - mbm-dialer/leads_database.json (6,399 unverified of 7,240)

Usage:
  python MBM/LeadEngine/purge_unverified_from_queues.py              # dry-run (default)
  python MBM/LeadEngine/purge_unverified_from_queues.py --apply      # actually purge + backup
  python MBM/LeadEngine/purge_unverified_from_queues.py --file X.json --apply
"""

import json
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dialer_verification_gate import check_lead, filter_for_dialer  # noqa: E402

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

QUEUE_FILES = {
    "us_re_dialer_queue.json": BASE / "us_re_dialer_queue.json",
    "real_estate_calling_queue.json": BASE / "real_estate_calling_queue.json",
    "cold_calling_queue.json": BASE / "cold_calling_queue.json",
    "leads_database.json": Path(
        r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json"
    ),
}


def load_queue(path: Path) -> tuple[list[dict], str]:
    """Load a queue file, return (leads_list, format_type)."""
    if not path.exists():
        return [], "missing"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data, "list"
    for key in ("queue", "leads", "data"):
        if key in data and isinstance(data[key], list):
            return data[key], f"dict:{key}"
    return [], "unknown"


def save_queue(path: Path, leads: list[dict], fmt: str):
    """Save a queue file in its original format."""
    if fmt == "list":
        payload = leads
    elif fmt.startswith("dict:"):
        key = fmt.split(":", 1)[1]
        with open(path, "r", encoding="utf-8") as f:
            original = json.load(f)
        original[key] = leads
        payload = original
    else:
        payload = leads

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def purge_queue(path: Path, label: str, apply: bool = False) -> dict:
    """Purge unverified leads from one queue file. Returns stats."""
    leads, fmt = load_queue(path)
    if not leads:
        print(f"\n  [{label}] EMPTY or NOT FOUND — skipping")
        return {"file": label, "total": 0, "kept": 0, "purged": 0, "status": "skipped"}

    kept = []
    quarantined = []
    for lead in leads:
        result = check_lead(lead)
        if result["passed"]:
            kept.append(lead)
        else:
            lead["_purge_reasons"] = result["rejection_reasons"]
            quarantined.append(lead)

    stats = {
        "file": label,
        "path": str(path),
        "total": len(leads),
        "kept": len(kept),
        "purged": len(quarantined),
        "purge_rate": f"{len(quarantined)/max(1,len(leads))*100:.1f}%",
    }

    print(f"\n  [{label}]")
    print(f"    Total:     {stats['total']}")
    print(f"    Kept:      {stats['kept']} ✓")
    print(f"    Purged:    {stats['purged']} ✗ ({stats['purge_rate']})")

    if quarantined:
        # Show sample of purged
        print(f"    Sample purged:")
        for q in quarantined[:5]:
            name = (q.get("contact_name") or q.get("name") or q.get("contact") or "?")
            phone = (q.get("phone") or q.get("phone_number") or "?")
            reasons = ", ".join(q.get("_purge_reasons", []))
            print(f"      ✗ {name} | {phone} | {reasons}")
        if len(quarantined) > 5:
            print(f"      ... and {len(quarantined) - 5} more")

    if apply and path.exists():
        # Backup
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
        print(f"    Backup:    {bak.name}")

        # Write clean data
        save_queue(path, kept, fmt)
        print(f"    WRITTEN:   {len(kept)} leads saved to {path.name}")
        stats["status"] = "applied"

        # Save quarantined leads
        q_path = LOGS / f"quarantined_{label}"
        with open(q_path, "w", encoding="utf-8") as f:
            json.dump(quarantined, f, indent=2, default=str)
        print(f"    Quarantine: {q_path.name}")
        stats["quarantine_file"] = str(q_path)
    else:
        stats["status"] = "dry_run"

    return stats


def main():
    ap = argparse.ArgumentParser(description="Purge unverified leads from dialer queues")
    ap.add_argument("--apply", action="store_true",
                    help="Actually purge (default is dry-run)")
    ap.add_argument("--file", type=str,
                    help="Purge a single file instead of all queues")
    args = ap.parse_args()

    mode = "APPLY (will write!)" if args.apply else "DRY RUN (no changes)"

    print("=" * 60)
    print("  DIALER QUEUE PURGE — VERIFIED OWNERS ONLY")
    print(f"  Mode: {mode}")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    if args.file:
        p = Path(args.file)
        stats = [purge_queue(p, p.name, apply=args.apply)]
    else:
        stats = []
        for label, path in QUEUE_FILES.items():
            stats.append(purge_queue(path, label, apply=args.apply))

    # Summary
    total_all = sum(s["total"] for s in stats)
    kept_all = sum(s["kept"] for s in stats)
    purged_all = sum(s["purged"] for s in stats)

    print(f"\n{'='*60}")
    print(f"  PURGE SUMMARY")
    print(f"{'='*60}")
    print(f"  Total across all queues: {total_all}")
    print(f"  Kept (verified):         {kept_all}")
    print(f"  Purged (unverified):     {purged_all}")
    if total_all:
        print(f"  Overall purge rate:      {purged_all/total_all*100:.1f}%")
    print(f"{'='*60}")

    if not args.apply:
        print(f"\n  This was a DRY RUN. To actually purge, run with --apply")
        print(f"  Backups will be created automatically.")

    # Save report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "stats": stats,
        "total": total_all,
        "kept": kept_all,
        "purged": purged_all,
    }
    report_path = LOGS / "purge_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    main()
