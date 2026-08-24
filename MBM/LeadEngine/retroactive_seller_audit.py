"""retroactive_seller_audit -- section-11 classification + section-2 audit export.

Classifies every DISTRESSED_SELLER record into the mandated taxonomy and
demotes any CALL_READY seller lacking provable owner<->phone identity
evidence through the canonical single writer. Also exports the full
callable-population audit with the mandated field list.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from MBM.GLM.single_writer_lock import DialerSingleWriter  # noqa: E402
from MBM.LeadEngine.contact_verification_pipeline import (  # noqa: E402
    QuarantineLedger,
    SyntheticPhoneDetector,
    script_integrity_check,
    seller_quality_gate,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TAXONOMY = ("VERIFIED_CONTACT", "UNVERIFIED", "WRONG_PARTY", "BAD_PHONE",
            "DNC", "NO_CONTACT", "NEEDS_REVIEW")


def classify_seller(lead: dict) -> str:
    if str(lead.get("suppression_reason") or "").strip():
        return "DNC"
    verdict = SyntheticPhoneDetector.classify(str(lead.get("id")), lead.get("phone"))
    if verdict in ("SYNTHETIC", "MALFORMED"):
        return "BAD_PHONE"
    if not lead.get("phone"):
        return "NO_CONTACT"
    admitted, state = seller_quality_gate(lead)
    if admitted:
        return "VERIFIED_CONTACT"
    if state in ("SYNTHETIC", "MALFORMED"):
        return "BAD_PHONE"
    if state == "CATEGORY_MISMATCH":
        return "WRONG_PARTY"
    return "NEEDS_REVIEW"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    writer = DialerSingleWriter()
    leads = writer.read_leads()
    sellers = [l for l in leads if l.get("segment") == "DISTRESSED_SELLER"]

    day_dir = REPO / "MBM" / "Artifacts" / "GTM" / "daily" / _iso_now()[:10]
    day_dir.mkdir(parents=True, exist_ok=True)
    ledger = QuarantineLedger(day_dir / "phone_quarantine.jsonl")

    classification: dict[str, list[str]] = {t: [] for t in TAXONOMY}
    demotions: list[dict] = []
    for s in sellers:
        cls = classify_seller(s)
        classification[cls].append(str(s.get("id")))
        if cls != "VERIFIED_CONTACT" and s.get("callable") in (True, "True"):
            s["callable"] = False
            s["is_callable"] = False
            s["queue_bucket"] = "NEEDS_REVIEW_IDENTITY_EVIDENCE"
            s["next_action"] = "OBTAIN_OWNER_PHONE_IDENTITY_EVIDENCE"
            s["quality_remediation"] = {
                "ts": _iso_now(), "reason_code": "NO_OWNER_PHONE_IDENTITY_EVIDENCE",
                "actor": "OX-P0-V2", "previous_callable": True,
            }
            ledger.add(
                lead_id=str(s.get("id")), company=str(s.get("company"))[:80],
                phone=str(s.get("phone")), phone_status="NEEDS_RECHECK",
                reason_code="NO_OWNER_PHONE_IDENTITY_EVIDENCE",
                detail=f"classification={cls}", previous_callable=True,
            )
            demotions.append(s)

    callable_all = [l for l in leads if l.get("callable") in (True, "True")]

    def capture(l: dict) -> dict:
        d = l.get("details") or {}
        return {
            "lead_id": l.get("id"),
            "property_address": (d.get("property_address") or l.get("address")
                                 or l.get("city") or "")[:120],
            "owner_name": d.get("Owner_Name") or l.get("contact"),
            "mailing_address": (d.get("mailing_address") or "")[:120],
            "phone": l.get("phone"),
            "phone_source": l.get("phone_source") or l.get("skip_trace_source"),
            "phone_source_timestamp": l.get("discovered_at"),
            "phone_verified_at": l.get("phone_verified_at") or l.get("last_verified_at"),
            "phone_type": d.get("line_type", "unknown"),
            "phone_status": l.get("phone_status", "VERIFIED" if l.get("phone_verified") else "UNVERIFIED"),
            "owner_verified": l.get("owner_status"),
            "contact_identity_verified": bool(d.get("owner_phone_evidence")),
            "property_owner_match": l.get("verification_method"),
            "dnc_status": bool(l.get("suppression_reason")),
            "suppression_status": l.get("suppression_reason") or "CLEAR",
            "litigator_status": d.get("litigator_status", "UNKNOWN"),
            "verification_provider": l.get("skip_trace_source") or l.get("source"),
            "verification_confidence": l.get("skip_trace_confidence"),
            "last_verified_at": l.get("last_verified_at"),
        }

    script_bad = []
    for l in callable_all:
        ok, reason = script_integrity_check(l)
        if not ok:
            script_bad.append({"lead_id": l.get("id"), "reason": reason})

    audit = {
        "generated_at": _iso_now(),
        "seller_classification": {k: len(v) for k, v in classification.items()},
        "seller_ids_by_class": classification,
        "demoted_now": [l.get("id") for l in demotions],
        "callable_total": len(callable_all),
        "script_integrity_failures": script_bad,
        "callable_audit": [capture(l) for l in callable_all[:2000]],
    }
    out = day_dir / "contact_verification_audit.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "sellers": len(sellers),
        "classification": {k: len(v) for k, v in classification.items()},
        "demotions_applied_pending_write": len(demotions),
        "callable_total": len(callable_all),
        "script_failures_among_callable": len(script_bad),
    }, indent=2))

    if args.apply and demotions:
        r = writer.commit_update(
            demotions, author="OX-P0-V2", allow_upsert=True,
            reason="Retroactive seller identity-evidence gate: no proven owner<->phone link",
        )
        print(json.dumps({"writer_ok": r.get("ok"), "revision": writer.read_revision()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
