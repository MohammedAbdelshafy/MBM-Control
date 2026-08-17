#!/usr/bin/env python3
"""
CANONICAL SINGLE-WRITER GATEWAY for `mbm-dialer/app/public/leads_database.json`
================================================================================

ALL production writers MUST commit through this module (or the equivalent
`DialerSingleWriter` / Node `dialerDbGateway.js`). Direct `open(..., "w")`,
`Path.write_text`, or full-file `json.dump` on the live dialer DB is FORBIDDEN —
it bypasses the lock, races other writers, and re-introduces the observed
count oscillation (762 -> 702 -> 1063).

Every commit guarantees:
  1. Acquire the SHARED single-writer lock (`MBM/Artifacts/.leads_database.lock`).
  2. Read the LATEST on-disk state (never a stale local snapshot).
  3. Validate every incoming record: strong synthetic fingerprint + provenance.
  4. Enforce the permanent suppression index (`suppressed_bad_phones.json`).
  5. Enforce the no-shrink invariant (reject accidental data loss).
  6. Snapshot a timestamped backup before writing.
  7. Atomic temp-file + rename commit.
  8. Release the lock.

Usage:
    from MBM.LeadEngine.dialer_gateway import commit_dialer_db
    result = commit_dialer_db(records, reason="rerank_top_100", allow_shrink=False)

or for patch-only writers:

    from MBM.LeadEngine.dialer_gateway import patch_dialer_db
    result = patch_dialer_db(new_or_updated, reason="owner_identity", author="owner_identity")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
SUPPRESSION_FILE = ARTIFACTS_DIR / "suppressed_bad_phones.json"

sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter, SingleWriterViolation
from MBM.LeadEngine.lead_provenance import (
    is_persona_contact,
    is_placeholder_phone,
    is_sequential_registry_ref,
    is_template_company,
)


def load_suppression_index() -> set:
    """Return the set of permanently suppressed (bad/opt-out) normalized phones."""
    suppressed: set = set()
    if SUPPRESSION_FILE.exists():
        try:
            data = json.loads(SUPPRESSION_FILE.read_text(encoding="utf-8"))
            for p in data.get("suppressed_phones", []):
                suppressed.add(_norm_phone(str(p)))
        except Exception:
            pass
    return suppressed


def _norm_phone(p: str) -> str:
    digits = "".join(ch for ch in str(p or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def is_strong_synthetic(record: Dict[str, Any]) -> List[str]:
    """Return a list of STRONG synthetic signals for a record (empty == clean).

    Only high-confidence markers are used so real NPI/DCAD businesses are never
    misclassified (e.g. generated domains are NOT used — real practices own
    slug-matching domains).
    """
    reasons: List[str] = []
    lead_id = str(record.get("id", "") or "")
    if lead_id.startswith("GEN-NEW") or lead_id.startswith("GEN-FAC"):
        reasons.append("generated_id")
    if is_template_company(str(record.get("company", "") or record.get("company_name", ""))):
        reasons.append("template_company")
    contact = (
        record.get("contact")
        or record.get("decision_maker")
        or record.get("person_name")
        or record.get("owner_name")
        or ""
    )
    if is_persona_contact(str(contact or "")):
        reasons.append("persona_contact")
    ref = str(record.get("source_reference", "") or record.get("source_url", "") or "")
    if is_sequential_registry_ref(ref):
        reasons.append("sequential_registry_ref")
    if record.get("synthetic") or record.get("is_synthetic") or record.get("is_fabricated") or record.get("is_demo"):
        reasons.append("explicit_synthetic")
    return reasons


def validate_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Filter records through strong synthetic + suppression + phone sanity gates."""
    suppressed = load_suppression_index()
    clean: List[Dict[str, Any]] = []
    rejected_synthetic = 0
    rejected_suppressed = 0
    rejected_bad_phone = 0

    for rec in records:
        if not isinstance(rec, dict):
            continue
        reasons = is_strong_synthetic(rec)
        if reasons:
            rejected_synthetic += 1
            continue
        phone = str(rec.get("phone", "") or rec.get("details", {}).get("Owner_Phone", "") or "")
        if is_placeholder_phone(phone):
            rejected_bad_phone += 1
            continue
        if phone and _norm_phone(phone) in suppressed:
            rejected_suppressed += 1
            continue
        if str(rec.get("sms_opted_out")) in ("true", "1", "yes"):
            rejected_suppressed += 1
            continue
        clean.append(rec)

    return {
        "clean": clean,
        "rejected_synthetic": rejected_synthetic,
        "rejected_suppressed": rejected_suppressed,
        "rejected_bad_phone": rejected_bad_phone,
        "suppression_index_size": len(suppressed),
    }


def commit_dialer_db(
    records: List[Dict[str, Any]],
    reason: str = "dialer_gateway",
    allow_shrink: bool = False,
    author: str = "dialer_gateway",
) -> Dict[str, Any]:
    """Authorized whole-file commit of the dialer DB (validated, locked, atomic)."""
    if not isinstance(records, list):
        raise SingleWriterViolation("commit_dialer_db requires a list of records")

    filtered = validate_records(records)
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    result = writer.full_replace(filtered["clean"], author=author, allow_shrink=allow_shrink)

    result.update(
        {
            "reason": reason,
            "rejected_synthetic": filtered["rejected_synthetic"],
            "rejected_suppressed": filtered["rejected_suppressed"],
            "rejected_bad_phone": filtered["rejected_bad_phone"],
            "suppression_index_size": filtered["suppression_index_size"],
        }
    )
    return result


def patch_dialer_db(
    new_or_updated: List[Dict[str, Any]],
    reason: str = "dialer_gateway",
    author: str = "dialer_gateway",
    allow_upsert: bool = True,
) -> Dict[str, Any]:
    """Authorized merge/upsert commit (never shrinks; patches specific leads)."""
    filtered = validate_records(new_or_updated)
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    result = writer.commit_update(filtered["clean"], author=author, allow_upsert=allow_upsert)
    result.update(
        {
            "reason": reason,
            "rejected_synthetic": filtered["rejected_synthetic"],
            "rejected_suppressed": filtered["rejected_suppressed"],
            "rejected_bad_phone": filtered["rejected_bad_phone"],
            "suppression_index_size": filtered["suppression_index_size"],
        }
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Canonical dialer DB gateway (audit + smoke).")
    parser.add_argument("--audit", action="store_true", help="Audit current DB against the gates")
    parser.add_argument("--dry-commit", nargs="?", const="", help="Dry-run a commit (no write)")
    args = parser.parse_args()

    if args.audit:
        data = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("leads", [])
        res = validate_records(rows)
        print(f"dialer rows={len(rows)}")
        print(f"  clean={len(res['clean'])}")
        print(f"  rejected_synthetic={res['rejected_synthetic']}")
        print(f"  rejected_suppressed={res['rejected_suppressed']}")
        print(f"  rejected_bad_phone={res['rejected_bad_phone']}")
        print(f"  suppression_index_size={res['suppression_index_size']}")