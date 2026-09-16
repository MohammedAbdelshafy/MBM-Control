#!/usr/bin/env python3
"""Generate P4 first-contact drafts (DRAFT_ONLY, never sends).

Reads MBM/Artifacts/GTM/p4_first_25_prospects.csv, builds one draft per
QUALIFIED row via MBM.LeadEngine.gtm.guarded_actions.draft_outreach
(banned-claim fail-closed), and writes p4_outreach_queue.json with
send_status=DRAFT_ONLY and approval_required=true.

Usage: python MBM/Artifacts/GTM/generate_p4_outreach.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.gtm.guarded_actions import draft_outreach  # noqa: E402

GTM_DIR = Path(__file__).resolve().parent
CSV_PATH = GTM_DIR / "p4_first_25_prospects.csv"
OUT_PATH = GTM_DIR / "p4_outreach_queue.json"

PROOF = ("P4 demo: an 11-row sample classified into CALLABLE / NOT CALLABLE / "
         "DUPLICATE / SUPPRESSED with per-row reason codes")


def main() -> int:
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("qualification_status") or "").strip() == "QUALIFIED"]
    queue = []
    for row in rows:
        observation = f"saw your {row['website']} operation ({row['evidence'][:140]}…)"
        pain = f"hypothesis: {row['pain_signal']}"
        try:
            draft = draft_outreach(
                prospect={"company": row["company"],
                          "contact_name": row["contact_name"]
                          if row["contact_name"] != "UNKNOWN" else "there"},
                problem=f"{observation} {pain}",
                proof=PROOF,
                evidence_ids=[f"prospect:{row['prospect_id']}", "p4-demo:11-row"],
            )
            queue.append({
                "prospect_id": row["prospect_id"],
                "channel": "EMAIL",
                "message": {"subject": draft.subject, "body": draft.body},
                "evidence_used": draft.evidence_ids,
                "confidence": float(row["confidence"]),
                "approval_required": True,
                "send_status": "DRAFT_ONLY",
            })
        except ValueError as exc:
            queue.append({
                "prospect_id": row["prospect_id"],
                "channel": "EMAIL",
                "message": None,
                "evidence_used": [],
                "confidence": float(row["confidence"]),
                "approval_required": True,
                "send_status": f"BLOCKED:{exc}",
            })
    payload = {"generated_by": "generate_p4_outreach.py (draft_outreach, banned-claim fail-closed)",
               "draft_count": len(queue),
               "sends_executed": 0,
               "queue": queue}
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"drafts": len(queue),
                      "blocked": sum(1 for q in queue if q["send_status"] != "DRAFT_ONLY"),
                      "sends": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
