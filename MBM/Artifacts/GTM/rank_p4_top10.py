#!/usr/bin/env python3
"""Rank P4 prospects into the daily top-10 (deterministic, evidence-backed).

Rule (uses CSV fields only, no invented data):
  rank_score = ICP_fit * 0.5 + confidence * 0.3 + contact_bonus
  contact_bonus = 0.2 if an observed phone or email exists, else 0.0
Ties break by prospect_id. Review status is always PENDING_REVIEW
(no bulk approval, ever).

Usage: python MBM/Artifacts/GTM/rank_p4_top10.py
"""
from __future__ import annotations

import csv
from pathlib import Path

GTM_DIR = Path(__file__).resolve().parent
CSV_PATH = GTM_DIR / "p4_first_25_prospects.csv"
OUT_PATH = GTM_DIR / "p4_today_top10.csv"

ANGLES = {
    "P4-011": "qualify rows before they reach client calendars",
    "P4-013": "every follow-up attempt lands on a real record",
    "P4-004": "clean VIP intake before deal matching",
    "P4-010": "hand sales only verified contacts",
    "P4-015": "standardize list quality as teams scale",
    "P4-018": "route only real local records to closers",
    "P4-019": "keep high-volume inbound lists callable",
    "P4-020": "filter quote lists to callable owners",
    "P4-021": "dedupe households across metros",
    "P4-022": "feed crews only callable appointments",
}


def main() -> int:
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    scored = []
    for row in rows:
        bonus = 0.2 if (row["phone"] != "UNKNOWN" or row["email"] != "UNKNOWN") else 0.0
        score = round(float(row["ICP_fit"]) * 0.5 + float(row["confidence"]) * 0.3 + bonus, 4)
        scored.append((score, row["prospect_id"], row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    top10 = scored[:10]
    cols = ["rank", "prospect_id", "company", "contact", "role", "email", "phone", "evidence",
            "pain_signal", "ICP_fit", "offer_match", "confidence",
            "message_angle", "review_status"]
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for rank, (_, pid, row) in enumerate(top10, start=1):
            writer.writerow({
                "rank": rank, "prospect_id": pid, "company": row["company"],
                "contact": row["contact_name"], "role": row["role"],
                "email": row["email"], "phone": row["phone"],
                "evidence": row["evidence"], "pain_signal": row["pain_signal"],
                "ICP_fit": row["ICP_fit"], "offer_match": row["offer_match"],
                "confidence": row["confidence"],
                "message_angle": ANGLES.get(pid, row["pain_signal"][:60]),
                "review_status": "PENDING_REVIEW",
            })
    print("top10: " + ",".join(pid for _, pid, _ in top10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
