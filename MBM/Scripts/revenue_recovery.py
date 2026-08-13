#!/usr/bin/env python3
"""
Revenue Recovery Pass — Purge Fabricated Rows From the LIVE Queues
===================================================================
The revenue gate ("Have we made any money?") was fed by `cold_calling_queue.json`
and `enriched_global_leads.json`, which contained fabricated rows (fake phones,
placeholder domains, invented personas). That inflated outreach_volume while
yielding zero real conversions — a fake score fed a false picture.

This recovery pass:
  1. Backs up the live feeds (so nothing is lost).
  2. Applies the SAME hygiene verdicts as lead_hygiene.py (phone + DNS + persona).
  3. Writes back ONLY verified real rows (PASS / PHONE_ONLY) into the live
     files the dialer + revenue tracker actually consume.
  4. Reports what changed and re-arms the revenue gate on real data.

Use `--apply` to actually overwrite live feeds. Without it, it only reports.

Usage:
  python MBM/Scripts/revenue_recovery.py               # report only (safe)
  python MBM/Scripts/revenue_recovery.py --apply       # rewrite live queues
  python MBM/Scripts/revenue_recovery.py --no-dns     # skip DNS checks
"""

import os
import sys
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
MBM = BASE.parent
LE = MBM / "LeadEngine"
BACKUPS = MBM / "Artifacts" / "recovery_backups"

# Reuse the hygiene verdict engine from lead_hygiene.py
sys.path.insert(0, str(BASE))
try:
    import lead_hygiene as hg
except Exception as e:
    print(f"[RECOVERY] Cannot import lead_hygiene: {e}")
    hg = None

# Live feeds we rewrite (kept in place; recovery actually switches them for real)
LIVE_FILES = {
    "cold_calling_queue.json": LE / "cold_calling_queue.json",
    "enriched_global_leads.json": LE / "enriched_global_leads.json",
    "global_leads.json": LE / "global_leads.json",
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[REVENUE RECOVERY] {ts} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def backup(path):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUPS / f"{stamp}__{path.name}"
    shutil.copy2(path, dst)
    return dst


def clean_rows(rows, with_dns=True):
    """Run every dict through the hygiene gate; return (passes, flagged)."""
    if hg is None:
        return rows, []
    mx = {}
    passes, dirty = [], []
    for r in rows:
        phone, verdict, reason, _dom = hg.assess_row(r, mx, with_net=with_dns)
        if verdict in ("PASS", "PHONE_ONLY"):
            passes.append(r)
        else:
            r["_flagged"] = reason
            dirty.append(r)
    return passes, dirty


def save_json(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)


def load_rows(path):
    p = Path(path)
    if p.suffix.lower() == ".csv":
        with open(p, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        return data.get("queue", data.get("leads", []))
    return data if isinstance(data, list) else []


def run(apply=False, with_dns=True):
    report = {"run_at": datetime.now(timezone.utc).isoformat(),
              "applied": apply, "feeds": {}}
    for name, path in LIVE_FILES.items():
        if not path.exists():
            report["feeds"][name] = {"status": "missing"}
            continue
        rows = load_rows(path)
        clean, dirty = clean_rows(rows, with_dns=with_dns)
        entry = {
            "status": "ok",
            "before": len(rows),
            "kept": len(clean),
            "purged": len(dirty),
        }
        if apply and len(dirty) > 0:
            bkp = backup(path)
            save_json(path, clean)
            entry["backup"] = str(bkp)
        report["feeds"][name] = entry
        log(f"{name}: {len(rows)} -> kept {len(clean)}, purged {len(dirty)}"
            + (f" (backup {bkp})" if apply and dirty else ""))

    summary = report
    out = MBM / "Artifacts" / "revenue_recovery_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return summary


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Revenue Recovery Pass")
    ap.add_argument("--apply", action="store_true", help="rewrite live queues")
    ap.add_argument("--no-dns", action="store_true", help="skip DNS checks")
    args = ap.parse_args()
    run(apply=args.apply, with_dns=not args.no_dns)


if __name__ == "__main__":
    main()