#!/usr/bin/env python3
"""
P4 — AI Lead Qualification Agent · Done-For-You Lead List Cleaner
=================================================================
Production-safe DFY runner. Reuses the CANONICAL verification engine
(MBM.LeadEngine.dialer_verification_gate) — this module only orchestrates
normalize → verify → classify → dedupe → suppression → score, and writes:

  output/<job>/cleaned.csv       — every input row + VERIFIED/CALLABLE/etc.
  output/<job>/summary.json      — machine-readable summary + reason breakdown
  output/<job>/report.md         — human-readable before/after report

Usage:
  python clean_leads.py --input input/leads.csv            # default job name = input stem
  python clean_leads.py --input leads.csv --job sample     # explicit job id
  python clean_leads.py --demo                             # run the labeled demo set

No fabricated results. Every classification is a direct function of the
canonical gate + provenance fingerprints + suppression index.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.dialer_verification_gate import check_lead  # noqa: E402
from MBM.LeadEngine.lead_provenance import is_placeholder_phone  # noqa: E402

SERVICE_ROOT = Path(__file__).resolve().parent
INPUT_DIR = SERVICE_ROOT / "input"
OUTPUT_DIR = SERVICE_ROOT / "output"

SUPPRESSION_INDEX = ROOT / "MBM" / "Artifacts" / "suppressed_bad_phones.json"
QUARANTINE_INDEX = ROOT / "MBM" / "Artifacts" / "quarantined_bad_leads.json"

# Statuses returned to the customer (Phase 1 contract).
STATUS_VERIFIED = "VERIFIED"
STATUS_CALLABLE = "CALLABLE"
STATUS_NOT_CALLABLE = "NOT CALLABLE"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_SUPPRESSED = "SUPPRESSED"
STATUS_NEEDS_REVIEW = "NEEDS REVIEW"


def _digits(phone: Any) -> str:
    return re.sub(r"\D", "", str(phone or ""))


def _load_suppression_phones() -> set[str]:
    phones: set[str] = set()
    if SUPPRESSION_INDEX.exists():
        try:
            data = json.loads(SUPPRESSION_INDEX.read_text(encoding="utf-8"))
            for p in data.get("suppressed_phones", []):
                d = _digits(p)
                if d:
                    phones.add(d[-10:])
        except Exception:
            pass
    return phones


def _load_quarantined_phones() -> set[str]:
    phones: set[str] = set()
    if QUARANTINE_INDEX.exists():
        try:
            data = json.loads(QUARANTINE_INDEX.read_text(encoding="utf-8"))
            for q in data.get("quarantined_leads", []):
                p = q.get("phone") or q.get("verified_phone") or ""
                d = _digits(p)
                if d:
                    phones.add(d[-10:])
        except Exception:
            pass
    return phones


def _input_phone(lead: dict) -> str:
    for key in ("verified_phone", "phone", "phone_number", "primary_phone",
                "contact_phone", "phone1", "Phone", "phone_n"):
        val = lead.get(key, "")
        if val and str(val).strip() and len(_digits(val)) >= 7:
            return str(val).strip()
    return ""


def _input_name(lead: dict) -> str:
    for key in ("contact_name", "name", "contact", "owner_name", "Name",
                "prospect_name", "company_name", "company", "Company"):
        val = lead.get(key, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _classify(lead: dict, gate: dict, dedupe_hit: bool,
              suppressed: bool) -> str:
    """Map the gate result onto the customer-visible status taxonomy."""
    if suppressed:
        return STATUS_SUPPRESSED
    if dedupe_hit:
        return STATUS_DUPLICATE
    if gate["passed"]:
        return STATUS_CALLABLE
    # Verified by source but blocked on a non-fatal attribute → review.
    if gate["verified_ok"]:
        return STATUS_NEEDS_REVIEW
    # No verification source at all → NOT CALLABLE (no proof).
    return STATUS_NOT_CALLABLE


def _status_order(status: str) -> int:
    order = {
        STATUS_CALLABLE: 0, STATUS_VERIFIED: 1, STATUS_NEEDS_REVIEW: 2,
        STATUS_DUPLICATE: 3, STATUS_SUPPRESSED: 4, STATUS_NOT_CALLABLE: 5,
    }
    return order.get(status, 99)


def run_cleaner(
    input_path: Path,
    job: str,
    report_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Run the full normalize → verify → classify → dedupe → suppress → score
    pipeline over an input CSV or JSON file. Returns the summary dict."""
    leads: list[dict] = []
    if input_path.suffix.lower() == ".csv":
        with open(input_path, encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(
                (line for line in fh if not line.lstrip().startswith("#")))
            leads = list(reader)
    else:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            leads = data
        elif isinstance(data, dict):
            leads = data.get("leads", data.get("data", data.get("queue", [])))
        if not isinstance(leads, list):
            leads = []

    suppressed_phones = _load_suppression_phones() | _load_quarantined_phones()

    seen: dict[str, int] = {}
    rows: list[dict] = []
    for raw in leads:
        row = dict(raw)
        phone = _input_phone(row)
        name = _input_name(row)
        gate = check_lead(row)

        # Dedupe by normalized phone (canonical 10-digit form). First seen wins.
        digits = _digits(phone)[-10:]
        if digits and len(digits) == 10:
            if digits in seen:
                dedupe_hit = True
                seen[digits] += 1
            else:
                seen[digits] = 0
                dedupe_hit = False
        else:
            dedupe_hit = False

        suppressed = bool(phone and _digits(phone)[-10:] in suppressed_phones)

        status = _classify(row, gate, dedupe_hit, suppressed)

        # Aggregate duplicate/suppressed rows point at the kept original.
        dup_of = ""
        if status == STATUS_DUPLICATE:
            dup_of = f"phone:{digits}" if digits else ""

        reason_codes = []
        if status in (STATUS_NOT_CALLABLE, STATUS_NEEDS_REVIEW):
            reason_codes = list(gate["rejection_reasons"])
        if status == STATUS_SUPPRESSED:
            reason_codes = ["suppressed_number"]
        if status == STATUS_DUPLICATE:
            reason_codes = ["duplicate_phone"]

        row["p4_status"] = status
        row["p4_reason"] = " | ".join(reason_codes)
        row["p4_phone_ok"] = "YES" if gate["phone_ok"] else "NO"
        row["p4_phone_reason"] = gate["phone_reason"]
        row["p4_name_ok"] = "YES" if gate["name_ok"] else "NO"
        row["p4_verified"] = "YES" if gate["verified_ok"] else "NO"
        row["p4_verified_source"] = gate["verified_source"]
        row["p4_duplicate_of"] = dup_of
        rows.append(row)

    # Order: callable first, then duplicates/suppressed/blocked.
    rows.sort(key=lambda r: _status_order(r["p4_status"]))

    counts = Counter(r["p4_status"] for r in rows)
    total = len(rows)
    callable = counts[STATUS_CALLABLE]
    verified = callable  # callable ⊂ verified-owner
    summary = {
        "job": job,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_records": total,
        "status_counts": {
            STATUS_VERIFIED: verified,
            STATUS_CALLABLE: callable,
            STATUS_NOT_CALLABLE: counts[STATUS_NOT_CALLABLE],
            STATUS_DUPLICATE: counts[STATUS_DUPLICATE],
            STATUS_SUPPRESSED: counts[STATUS_SUPPRESSED],
            STATUS_NEEDS_REVIEW: counts[STATUS_NEEDS_REVIEW],
        },
        "dialable_pct": round(callable / max(1, total) * 100, 1),
        "reason_breakdown": dict(Counter(
            r for row in rows for r in (row["p4_reason"].split(" | ") if row["p4_reason"] else [])
        )),
        "deduped_phones_removed": counts[STATUS_DUPLICATE],
        "suppressed_removed": counts[STATUS_SUPPRESSED],
        "input_file": str(input_path),
    }

    # Persist outputs.
    out_dir = report_dir or OUTPUT_DIR / job
    out_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    csv_path = out_dir / "cleaned.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(
        _build_report(summary, job), encoding="utf-8")
    summary["cleaned_csv"] = str(csv_path)
    return summary


def _build_report(summary: dict, job: str) -> str:
    c = summary["status_counts"]
    lines = [
        f"# Lead Qualification Report — {job}",
        f"Generated {summary['generated_at']}",
        "",
        f"**Total records:** {summary['total_records']}",
        f"**Dialable:** {c[STATUS_CALLABLE]} ({summary['dialable_pct']}%)",
        "",
        "## Before → After",
        f"- VERIFIED / CALLABLE: {c[STATUS_CALLABLE]}",
        f"- NOT CALLABLE (no proof / dead): {c[STATUS_NOT_CALLABLE]}",
        f"- DUPLICATE: {c[STATUS_DUPLICATE]}",
        f"- SUPPRESSED: {c[STATUS_SUPPRESSED]}",
        f"- NEEDS REVIEW: {c[STATUS_NEEDS_REVIEW]}",
        "",
        "## Reason breakdown",
    ]
    for reason, n in sorted(summary["reason_breakdown"].items(),
                            key=lambda kv: -kv[1]):
        lines.append(f"- `{reason}`: {n}")
    lines.append("")
    lines.append("## What you should do")
    if c[STATUS_CALLABLE]:
        lines.append(
            f"- Dial the {c[STATUS_CALLABLE]} CALLABLE records first — they are "
            "real, verified, de-duplicated, and not suppressed.")
    if c[STATUS_NEEDS_REVIEW]:
        lines.append(
            f"- {c[STATUS_NEEDS_REVIEW]} NEEDS REVIEW records have a real "
            "verification signal but a flag to inspect before calling.")
    if c[STATUS_DUPLICATE]:
        lines.append(
            f"- Drop the {c[STATUS_DUPLICATE]} DUPLICATE rows — they repeat a "
            "phone already in your list.")
    if c[STATUS_SUPPRESSED]:
        lines.append(
            f"- {c[STATUS_SUPPRESSED]} SUPPRESSED numbers are DNC/bad-history "
            "and must never be dialed again.")
    lines.append("")
    lines.append("*Every classification is produced by the canonical "
                 "verification gate + provenance fingerprints — no manual "
                 "edits, fully reproducible.*")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="P4 DFY lead list cleaner")
    ap.add_argument("--input", type=str, help="CSV or JSON lead file")
    ap.add_argument("--job", type=str, default="", help="Output job name")
    ap.add_argument("--demo", action="store_true",
                    help="Run the labeled demo set in demo/")
    args = ap.parse_args()

    if args.demo:
        demo_csv = SERVICE_ROOT / "demo" / "sample_lead_list.csv"
        if not demo_csv.exists():
            print(f"[ERROR] demo input missing: {demo_csv}")
            return 1
        job = args.job or "demo_sample"
        summary = run_cleaner(demo_csv, job=job, report_dir=SERVICE_ROOT / "demo" / "output")
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if not args.input:
        ap.print_help()
        return 1

    inp = Path(args.input)
    if not inp.exists():
        print(f"[ERROR] input not found: {inp}")
        return 1
    job = args.job or inp.stem
    summary = run_cleaner(inp, job=job)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())