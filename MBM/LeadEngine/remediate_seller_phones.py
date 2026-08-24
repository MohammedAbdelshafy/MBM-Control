"""remediate_seller_phones -- P0 execution of the contact-verification rebuild.

Reads the canonical dialer DB, runs the seller quality gate + synthetic-phone
forensics over every lead, then persists state changes THROUGH the canonical
DialerSingleWriter (no direct file writes) and appends audit events.

Actions produced (history preserved; nothing deleted):
  SYNTHETIC_ID_DERIVED   -> callable=false, queue=QUARANTINED_SYNTHETIC
  CATEGORY_MISMATCH      -> callable=false, queue=NEEDS_REVIEW_CATEGORY (NPI-sourced sellers)
  WEAK_SELLER_FIT        -> callable=false, queue=NEEDS_REVIEW_WEAK_FIT (institutional owners)
  PASS                   -> untouched (stays callable, bucket UNCALLED_VERIFIED)

Outputs:
  MBM/Artifacts/GTM/daily/<date>/phone_quarantine.jsonl   (ledger)
  MBM/Artifacts/GTM/daily/<date>/phone_quality_report.json/.md
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
    audit_database,
    seller_quality_gate,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="persist changes via single writer")
    ap.add_argument("--date", default=_iso_now()[:10])
    args = ap.parse_args()

    writer = DialerSingleWriter()
    leads = writer.read_leads()
    before_count = len(leads)

    day_dir = REPO / "MBM" / "Artifacts" / "GTM" / "daily" / args.date
    day_dir.mkdir(parents=True, exist_ok=True)
    ledger = QuarantineLedger(day_dir / "phone_quarantine.jsonl")

    updates: list[dict] = []
    tally: dict[str, int] = {}
    for lead in leads:
        if lead.get("segment") != "DISTRESSED_SELLER":
            continue
        verdict = SyntheticPhoneDetector.classify(str(lead.get("id")), lead.get("phone"))
        admitted, gate_state = seller_quality_gate(lead)
        if admitted and verdict is None:
            continue

        was_callable = lead.get("callable") in (True, "True")
        if verdict == "SYNTHETIC":
            reason_code, status, bucket = (
                "PHONE_SYNTHETIC_ID_DERIVED", "SYNTHETIC_ID_DERIVED", "QUARANTINED_SYNTHETIC")
        elif verdict == "MALFORMED":
            reason_code, status, bucket = ("PHONE_MALFORMED", "MALFORMED", "QUARANTINED_MALFORMED")
        elif gate_state == "CATEGORY_MISMATCH":
            reason_code, status, bucket = (
                "SELLER_SOURCE_CATEGORY_MISMATCH", "CATEGORY_MISMATCH", "NEEDS_REVIEW_CATEGORY")
        else:
            reason_code, status, bucket = (
                "SELLER_GATE_" + gate_state, "OWNER_MISMATCH" if gate_state == "NEEDS_REVIEW"
                else gate_state, "NEEDS_REVIEW_WEAK_FIT")

        lead["callable"] = False
        lead["is_callable"] = False
        lead["phone_status"] = status
        lead["queue_bucket"] = bucket
        lead["next_action"] = "REVERIFY_THROUGH_MULTI_SOURCE_PIPELINE"
        lead["quality_remediation"] = {
            "ts": _iso_now(), "reason_code": reason_code,
            "actor": "OX-P0-REBUILD", "previous_callable": was_callable,
        }
        ledger.add(
            lead_id=str(lead.get("id")), company=str(lead.get("company"))[:80],
            phone=str(lead.get("phone")), phone_status=status,
            reason_code=reason_code,
            detail=f"gate_state={gate_state} src={lead.get('skip_trace_source')}",
            previous_callable=was_callable,
        )
        updates.append(lead)
        tally[reason_code] = tally.get(reason_code, 0) + 1

    report = audit_database(leads, ledger)
    report["remediation"] = {
        "applied": bool(args.apply),
        "leads_changed": len(updates),
        "reason_tally": tally,
        "callable_before": sum(1 for l in leads if l.get("segment") != "DISTRESSED_SELLER" and l.get("callable") in (True, "True"))
        + sum(1 for l in leads if l.get("segment") == "DISTRESSED_SELLER" and l.get("callable") in (True, "True")),
        "note": "callable_after computed post-write",
    }

    (day_dir / "phone_quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# Phone Quality Report — P0 Seller Remediation",
        f"- generated: {report['generated_at']}",
        f"- total_leads: **{report['total_leads']}** · callable_now: **{report['total_callable']}**",
        f"- synthetic phones detected: **{report['synthetic_phone_count']}** · malformed: **{report['malformed_phone_count']}**",
        f"- multi_source_match_rate: **{report['multi_source_match_rate']}**",
        f"- seller_gate: admitted **{report['seller_gate']['admitted']}** / blocked: `{report['seller_gate']['blocked_by_reason']}`",
        f"- remediation applied: **{args.apply}** · leads changed: **{len(updates)}** · reasons: `{tally}`",
    ]
    (day_dir / "phone_quality_report.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "before_count": before_count,
        "seller_updates": len(updates),
        "reason_tally": tally,
        "applied": args.apply,
    }, indent=2))

    if args.apply and updates:
        result = writer.commit_update(
            updates, author="OX-P0-REBUILD", allow_upsert=True,
            reason="P0 seller phone verification remediation (quarantine synthetics, demote mismatches)",
        )
        after = writer.read_leads()
        print(json.dumps({
            "writer_result": {k: result[k] for k in result if k not in ("updated_ids",)},
            "after_count": len(after),
            "no_shrink_ok": len(after) >= before_count,
            "revision": writer.read_revision(),
        }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
