#!/usr/bin/env python3
"""
MBM Dialer — Canonical Queue Rebuild + Audit
============================================
Rebuilds `mbm-dialer/app/public/leads_database.json` from the CURRENT database
plus the preserved suppression/quarantine history. NEVER deletes a lead —
every record is kept and assigned a canonical queue bucket:

  🔥 FRESH_CALL_NOW      top 25 of the ranked main queue
  🟢 FRESH_NEXT          next 75
  🔵 UNCALLED_VERIFIED   remaining uncalled + verified + callable
  🟡 ALREADY_CONTACTED   attempts>0 / disposition / last_touch (history kept)
  🟣 VERIFICATION_REQUIRED  unverified / missing phone / placeholder
  🔴 SUPPRESSED          DNC / BAD_NUMBER / WRONG_NUMBER / WRONG_PERSON / ...
  🟣 QUARANTINED         quarantined records (preserved)

Only the main queue (UNCALLED + VERIFIED + CALLABLE) is dialable; it is
ordered by the SINGLE canonical rule in dialer_queue_engine.py. Run twice —
the second run produces zero duplicates, preserves every disposition/attempt
and the ordering.

Usage:
    python MBM/LeadEngine/rebuild_dialer_queue.py            # rebuild live DB
    python MBM/LeadEngine/rebuild_dialer_queue.py --dry-run  # report only
    python MBM/LeadEngine/rebuild_dialer_queue.py --audit    # audit current DB
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_queue_engine import (
    assign_lead_metadata,
    audit_counts,
    build_global_queue,
    get_callable_state,
    ordered_db_records,
    print_audit,
    rank_main_queue,
)
from MBM.LeadEngine.dialer_gateway import commit_dialer_db

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
QUARANTINE_FILE = ROOT_DIR / "MBM" / "Artifacts" / "quarantined_bad_leads.json"
PARTITION_ARTIFACT = ROOT_DIR / "MBM" / "Artifacts" / "top_100_partition.json"
SUPPRESSION_FILE = ROOT_DIR / "MBM" / "Artifacts" / "suppressed_bad_phones.json"


def _load(path: Path, key: str = "") -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] cannot read {path.name}: {exc}")
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and key and isinstance(data.get(key), list):
        return data[key]
    return []


def load_quarantined_history(quarantine_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Historical bad/quarantined records — preserved, NEVER dialed."""
    target_file = quarantine_file or QUARANTINE_FILE
    rows = _load(target_file, "quarantined_leads")
    for lead in rows:
        lead.setdefault("quarantined", True)
        lead["history_source"] = "quarantined_bad_leads"
    return rows


def load_verification_required_history() -> List[Dict[str, Any]]:
    """Summary rows from the reconcile partition artifact (NEEDS_SKIP_TRACE etc)."""
    if not PARTITION_ARTIFACT.exists():
        return []
    try:
        data = json.loads(PARTITION_ARTIFACT.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for item in data.get("verification_required", []):
        if not isinstance(item, dict):
            continue
        out.append({
            "id": item.get("id") or f"VR-{len(out)}",
            "company": item.get("property_or_company") or item.get("company") or "",
            "contact": item.get("owner") or item.get("name") or item.get("contact") or "",
            "vertical": item.get("vertical") or "UNKNOWN",
            "phone": item.get("phone") or "",
            "verification_status": "VERIFICATION_REQUIRED",
            "source": "reconcile_partition_artifact",
            "blocked_reason": "NEEDS_SKIP_TRACE" if not item.get("phone") else "UNVERIFIED_CONTACT",
            "callable": False,
            "history_source": "top_100_partition",
        })
    return out


def load_suppressed_phone_records() -> List[Dict[str, Any]]:
    """Bare suppressed-phone records for numbers no longer present in the DB
    (kept so the SUPPRESSED section reflects the permanent suppression index)."""
    if not SUPPRESSION_FILE.exists():
        return []
    try:
        data = json.loads(SUPPRESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = []
    for idx, phone in enumerate(data.get("suppressed_phones", [])):
        rows.append({
            "id": f"SUPP-{idx:04d}",
            "company": "SUPPRESSED NUMBER",
            "contact": "—",
            "vertical": "Suppressed",
            "phone": str(phone),
            "callability_status": "SUPPRESSED",
            "suppression_reason": "SUPPRESSED_PHONE_INDEX",
            "suppressed": True,
            "callable": False,
            "source": "suppressed_bad_phones_index",
            "history_source": "suppression_index",
        })
    return rows


def rebuild(dry_run: bool = False, db_path: Path = DIALER_DB, quiet: bool = False) -> Dict[str, Any]:
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    current = json.loads(db_path.read_text(encoding="utf-8"))
    if not isinstance(current, list):
        current = current.get("leads", [])

    combined: List[Dict[str, Any]] = list(current)

    # Preserved history (never deleted, never dialed).
    by_id = {str(l.get("id")): l for l in combined}
    for rec in load_quarantined_history():
        if str(rec.get("id")) not in by_id:
            combined.append(rec)
    for rec in load_verification_required_history():
        if str(rec.get("id")) not in by_id:
            combined.append(rec)
    for rec in load_suppressed_phone_records():
        if str(rec.get("phone")) not in {str(l.get("phone")) for l in combined}:
            combined.append(rec)

    # Canonical state + metadata + buckets on EVERY record.
    for lead in combined:
        state = get_callable_state(lead)
        lead["_callable_state"] = state
        assign_lead_metadata(lead, state)

    buckets = build_global_queue(combined)
    ordered = ordered_db_records(buckets)

    counts = audit_counts(ordered)

    if not quiet:
        print_audit(ordered, "DIALER DATABASE")

    # The DB file is stored in canonical order: main queue first.
    for lead in ordered:
        lead.pop("_callable_state", None)

    result = {
        "status": "dry_run" if dry_run else "success",
        "total_records": len(ordered),
        "counts": counts,
        "buckets": {k: len(v) for k, v in buckets.items()},
        "top25_pass": _top25_pass(ordered),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not dry_run:
        commit = commit_dialer_db(
            ordered,
            reason="rebuild_dialer_queue",
            allow_shrink=False,
            author="REBUILD_DIALER_QUEUE",
            db_path=db_path,
        )
        result["commit"] = {
            "ok": commit.get("ok"),
            "final_count": commit.get("final_count"),
            "rejected_synthetic": commit.get("rejected_synthetic"),
            "rejected_suppressed": commit.get("rejected_suppressed"),
            "rejected_bad_phone": commit.get("rejected_bad_phone"),
        }
        if not quiet:
            print(f"\n  ✓ Committed {len(ordered)} records (ordered) -> {db_path.name}")
    return result


def _top25_pass(ordered: List[Dict[str, Any]]) -> bool:
    ranked = [l for l in ordered if l.get("main_queue")]
    for lead in ranked[:25]:
        state = get_callable_state(lead)
        if state["attempts"] != 0 or state["disposition"] or state["callable"] is not True:
            return False
    return len(ranked) >= 25


def audit(db_path: Path = DIALER_DB) -> None:
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")
    data = json.loads(db_path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("leads", [])
    print_audit(rows, "DIALER DATABASE (current)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild + audit the canonical dialer queue")
    ap.add_argument("--dry-run", action="store_true", help="report only, no write")
    ap.add_argument("--audit", action="store_true", help="audit the current DB")
    args = ap.parse_args()

    if args.audit:
        audit()
        return 0

    result = rebuild(dry_run=args.dry_run)
    if result["top25_pass"]:
        print("TOP25_GATE=PASS")
    else:
        print("TOP25_GATE=FAIL")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())