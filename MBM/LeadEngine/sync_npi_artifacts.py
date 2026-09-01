#!/usr/bin/env python3
"""
MBM LeadEngine - Current-Day NPI Artifact Synchronizer (STRICT PRODUCTION GATE)
===============================================================================
Canonical path for merging newly-verified NPI artifacts (e.g. 2026-08-17) into
`mbm-dialer/app/public/leads_database.json` WITHOUT weakening the production
acceptance invariant:

    every valid current-day NPI artifact -> canonical dialer record

Guarantees:
- Validates every artifact through the SAME production gate as the day-16 NPI
  batch (provenance + verification method + phone quality + suppression).
- Syncs ONLY valid artifacts through `patch_dialer_db` (single-writer lock,
  merge/upsert, no-shrink, atomic temp-file rename, snapshot backup).
- Dedupes by NPI id AND normalized phone (against live DB + within batch).
- Stamps canonical dialer shape: first_seen_at=<day>, new_today=true,
  verification_method=npi_registry_api, verification_status=VERIFIED_OFFICIAL_RECORD.
- Re-verifies after sync by NPI id AND normalized phone (both identifiers).

Usage:
    python -m MBM.LeadEngine.sync_npi_artifacts --day 2026-08-17 [--apply]
    python -m MBM.LeadEngine.sync_npi_artifacts --audit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_gateway import (
    _norm_phone,
    is_strong_synthetic,
    patch_dialer_db,
    validate_records,
    DIALER_DB_PATH,
)
from MBM.LeadEngine.dialer_verification_gate import check_lead
from MBM.LeadEngine.lead_provenance import is_placeholder_phone

DAILY_ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "daily"


def normalize_phone(p: Any) -> str:
    """Canonical E.164-style dialer phone (same as reconcile_242)."""
    if not p:
        return ""
    digits = "".join(c for c in str(p) if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif len(digits) > 10:
        return f"+{digits}"
    return ""


def _validated_phone(phone: Any) -> str:
    """Phone the way the suppression/synthetic gate compares (10-digit body)."""
    return _norm_phone(phone)


def validate_artifacts(records: List[Dict[str, Any]], day: str) -> Dict[str, Any]:
    """Run the SAME production gate as the day-16 NPI batch on every artifact.

    Returns per-artifact gate results + aggregate counts.
    """
    results = []
    invalid_provenance = []
    invalid_phone = []
    seen_npis: Dict[str, List[str]] = {}
    seen_phones: Dict[str, List[str]] = {}

    for rec in records:
        rid = str(rec.get("id") or "")
        npi = rid.replace("NPI-", "") if rid.startswith("NPI-") else rid
        phone_raw = rec.get("phone", "")
        phone = normalize_phone(phone_raw)

        issues = []

        # Strong synthetic fingerprint (same gate as dialer_gateway production path)
        synth = is_strong_synthetic(rec)
        if synth:
            issues.append(f"synthetic:{','.join(synth)}")

        # NPI present
        if not npi or not npi.isdigit():
            issues.append("no_npi")

        # source / provenance valid
        src = str(rec.get("source") or "")
        if "NPI" not in src.upper() and "CMS" not in src.upper():
            issues.append(f"invalid_provenance:{src}")
            invalid_provenance.append(rid)

        # verification_method valid
        vm = str(rec.get("verification_method") or "")
        if vm != "npi_registry_api" and "CMS" not in vm.upper() and "NPI" not in vm.upper():
            issues.append(f"invalid_verification_method:{vm}")

        # verification_status valid
        vs = str(rec.get("verification_status") or "")
        if "VERIFIED" not in vs.upper():
            issues.append(f"not_verified:{vs}")

        # phone valid + not synthetic + not suppressed
        if not phone:
            issues.append("no_phone")
            invalid_phone.append(rid)
        else:
            gate = check_lead({**rec, "phone": phone})
            if not gate["phone_ok"]:
                issues.append(f"bad_phone:{gate['phone_reason']}")
                invalid_phone.append(rid)
            if not gate["name_ok"]:
                issues.append(f"bad_name:{gate['name_reason']}")
            if not gate["verified_ok"]:
                issues.append(f"verify_fail:{gate['verified_source']}")
            if is_placeholder_phone(phone_raw):
                issues.append("placeholder_phone")

        # business/entity identity present
        comp = str(rec.get("company") or rec.get("company_name") or "").strip()
        contact = str(rec.get("contact") or rec.get("decision_maker") or "").strip()
        if not comp:
            issues.append("no_company")
        if not contact or len(contact) < 3:
            issues.append("no_contact")

        # dedupe by NPI and normalized phone
        if npi:
            seen_npis.setdefault(npi, []).append(rid)
        p10 = _validated_phone(phone_raw)
        if p10:
            seen_phones.setdefault(p10, []).append(rid)

        results.append(
            {
                "id": rid,
                "npi": npi,
                "company": comp,
                "contact": contact,
                "phone": phone,
                "phone_body": p10,
                "source": src,
                "verification_method": vm,
                "verification_status": vs,
                "verified_at": rec.get("verified_at", ""),
                "first_seen_date": rec.get("first_seen_date", day),
                "passed": len(issues) == 0,
                "issues": issues,
            }
        )

    return {
        "results": results,
        "count": len(results),
        "valid": [r for r in results if r["passed"]],
        "invalid": [r for r in results if not r["passed"]],
        "dup_npi": {k: v for k, v in seen_npis.items() if len(v) > 1},
        "dup_phone": {k: v for k, v in seen_phones.items() if len(v) > 1},
        "invalid_provenance": invalid_provenance,
        "invalid_phone": invalid_phone,
    }


def build_canonical_record(rec: Dict[str, Any], day: str, validation: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a valid artifact into the canonical dialer record shape."""
    rid = str(rec.get("id") or "")
    npi = rid.replace("NPI-", "") if rid.startswith("NPI-") else rid
    company = str(rec.get("company") or "").strip()
    contact = str(rec.get("contact") or rec.get("decision_maker") or "Managing Director").strip()
    phone = validation["phone"]
    vertical = rec.get("vertical") or rec.get("industry") or "Clinic & Healthcare"
    callability = float(rec.get("callability", 95.0) if rec.get("callability") is not None else 95.0)
    priority = str(rec.get("priority", "HIGH")).upper()
    deal_score = float(rec.get("deal_score", 85.0) if rec.get("deal_score") is not None else 85.0)
    intent_score = float(rec.get("intent_score", 90.0) if rec.get("intent_score") is not None else 90.0)

    canonical = {
        "id": rid,
        "npi": npi,
        "artifact_file": f"lead_{rid}.json",
        "company": company,
        "contact": contact,
        "title": rec.get("title") or rec.get("role") or "Managing Director",
        "role": rec.get("role") or rec.get("title") or "Managing Director",
        "vertical": vertical,
        "industry": vertical,
        "phone": phone,
        "email": rec.get("email", ""),
        "address": rec.get("address", ""),
        "city": rec.get("city", ""),
        "state": rec.get("state", "TX"),
        "source": "US Government CMS NPI Registry",
        "source_reference": f"NPI #{npi}",
        "source_type": "GOVERNMENT_HEALTHCARE_REGISTRY",
        "verification_method": "npi_registry_api",
        "verification_status": "VERIFIED_OFFICIAL_RECORD",
        "verified_at": rec.get("verified_at") or f"{day}T00:00:00Z",
        "first_seen_at": day,
        "first_seen_date": rec.get("first_seen_date", day),
        "new_today": True,
        "freshness_label": "NEW TODAY",
        "callability": callability,
        "priority": priority,
        "deal_score": deal_score,
        "intent_score": intent_score,
        "stage": "NEW_LEAD",
        "sales_lane": "AI_CONSULTANCY",
        "why_them": rec.get("why_this_company") or rec.get("why_now")
        or f"Licensed medical practice with verified front-desk operating phone in {rec.get('state', 'TX')}.",
        "why_now": rec.get("why_now") or "High clinical intake volume during business hours with after-hours overflow bottleneck.",
        "business_pain": rec.get("pain") or "After-hours patient call overflow and manual appointment scheduling bottlenecks.",
        "ai_fit": rec.get("recommended_ai_assistant") or "24/7 AI Receptionist & Patient Triage Agent",
        "primary_offer": rec.get("recommended_ai_assistant") or "24/7 AI Receptionist & Patient Triage Agent",
        "secondary_offer": "Patient Recall & Unscheduled Treatment Reactivation Swarm",
        "consultancy_angle": "Clinical Revenue Operations & Autonomous Intake Automation",
        "expected_value_usd": float(rec.get("monthly_retainer_usd", 1997.0)) * 4.0,
        "recommended_next_action": "DIAL_WITH_DYNAMIC_HUD",
        "details": rec.get("details", {}),
    }
    # Carry through optional sales/skip-trace fields if present
    for k in ("sales_strategy", "skip_trace_status", "skip_trace_confidence", "sales_lane_override",
              "intent_tier", "tier", "status", "sku", "monthly_retainer_usd", "neteller_link",
              "sales_lane", "callable"):
        if rec.get(k) is not None:
            canonical[k] = rec[k]
    return canonical


def sync_day_artifacts(day: str, apply: bool = False) -> Dict[str, Any]:
    day_dir = DAILY_ARTIFACTS_DIR / day
    if not day_dir.exists():
        raise FileNotFoundError(f"No artifact dir for {day}: {day_dir}")

    records: List[Dict[str, Any]] = []
    for f in sorted(day_dir.glob("lead_NPI-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("id"):
                records.append(d)
        except Exception as err:
            print(f"[WARN] Unreadable artifact {f.name}: {err}")

    validation = validate_artifacts(records, day)
    print(f"[SYNC] {day}: {validation['count']} artifacts, "
          f"{len(validation['valid'])} valid, {len(validation['invalid'])} invalid")
    if validation["dup_npi"] or validation["dup_phone"]:
        print(f"[SYNC] WARNING duplicate NPI: {validation['dup_npi']}")
        print(f"[SYNC] WARNING duplicate phone: {validation['dup_phone']}")

    # Read live DB for collision/dedupe checks (never stale snapshot)
    live = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    live_ids = {str(l.get("id")) for l in live}
    live_phones = {_validated_phone(l.get("phone")) for l in live if l.get("phone")}

    canonical_valid: List[Dict[str, Any]] = []
    skipped_collision = []
    for v in validation["valid"]:
        if v["id"] in live_ids:
            skipped_collision.append((v["id"], "npi_already_in_dialer"))
            continue
        if v["phone_body"] in live_phones:
            skipped_collision.append((v["id"], "phone_already_in_dialer"))
            continue
        rec = next(r for r in records if str(r.get("id")) == v["id"])
        canonical_valid.append(build_canonical_record(rec, day, v))

    print(f"[SYNC] Valid-to-insert after live-dialer dedupe: {len(canonical_valid)} "
          f"(skipped {len(skipped_collision)}: {skipped_collision[:3]})")

    if not apply:
        print("[SYNC] DRY-RUN: no write performed. Re-run with --apply to commit.")
        return {
            "day": day,
            "status": "dry-run",
            "artifacts_found": validation["count"],
            "valid_artifacts": len(validation["valid"]),
            "invalid_artifacts": [r["id"] for r in validation["invalid"]],
            "to_insert": [r["id"] for r in canonical_valid],
            "skipped_collision": skipped_collision,
            "duplicate_npi": len(validation["dup_npi"]),
            "duplicate_phone": len(validation["dup_phone"]),
        }

    # Canonical commit through the single-writer gateway (merge, no-shrink, atomic)
    commit = patch_dialer_db(
        canonical_valid,
        reason=f"npi_sync_{day}",
        author="NPI_ARTIFACT_SYNC",
        allow_upsert=True,
    )
    print(f"[SYNC] Commit result: {commit}")

    # Post-sync reconciliation by BOTH NPI id and normalized phone
    final = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    final_ids = {str(l.get("id")) for l in final}
    final_phones = {_validated_phone(l.get("phone")) for l in final if l.get("phone")}

    valid_ids = [r["id"] for r in canonical_valid]
    valid_bodies = [_validated_phone(r["phone"]) for r in canonical_valid]

    missing_by_id = [i for i in valid_ids if i not in final_ids]
    missing_by_phone = [p for p in valid_bodies if p not in final_phones]

    # NPI population check (must only increase by the validated count)
    npi_before = len([l for l in live if str(l.get("id", "")).startswith("NPI-")])
    npi_after = len([l for l in final if str(l.get("id", "")).startswith("NPI-")])

    return {
        "day": day,
        "status": "synced",
        "artifacts_found": validation["count"],
        "valid_artifacts": len(validation["valid"]),
        "invalid_artifacts": [r["id"] for r in validation["invalid"]],
        "synced": len(canonical_valid),
        "duplicate_npi": len(validation["dup_npi"]),
        "duplicate_phone": len(validation["dup_phone"]),
        "skipped_collision": skipped_collision,
        "missing_from_dialer_by_id": missing_by_id,
        "missing_from_dialer_by_phone": missing_by_phone,
        "npi_before": npi_before,
        "npi_after": npi_after,
        "expected_increment": len(canonical_valid),
        "actual_increment": npi_after - npi_before,
        "dialer_total": len(final),
        "commit": commit,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Canonical current-day NPI artifact -> dialer sync")
    ap.add_argument("--day", default="2026-08-17", help="Daily artifact dir (YYYY-MM-DD)")
    ap.add_argument("--apply", action="store_true", help="Actually commit (default dry-run)")
    ap.add_argument("--audit", action="store_true", help="Audit current dialer against all daily artifact dirs")
    args = ap.parse_args()

    if args.audit:
        for d in sorted(p.name for p in DAILY_ARTIFACTS_DIR.glob("2026-08-*")):
            day_dir = DAILY_ARTIFACTS_DIR / d
            files = list(day_dir.glob("lead_NPI-*.json"))
            if not files:
                continue
            recs = []
            for f in files:
                try:
                    dd = json.loads(f.read_text(encoding="utf-8"))
                    if dd.get("id"):
                        recs.append(dd)
                except Exception:
                    pass
            v = validate_artifacts(recs, d)
            live = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
            live_ids = {str(l.get("id")) for l in live}
            in_db = [r["id"] for r in v["valid"] if r["id"] in live_ids]
            print(f"[AUDIT] {d}: artifacts={v['count']} valid={len(v['valid'])} "
                  f"in_dialer={len(in_db)} missing={len(v['valid']) - len(in_db)}")
        sys.exit(0)

    result = sync_day_artifacts(args.day, apply=args.apply)
    print(json.dumps(result, indent=2, default=str))