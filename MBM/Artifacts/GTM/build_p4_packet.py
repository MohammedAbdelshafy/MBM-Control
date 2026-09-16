#!/usr/bin/env python3
"""Build the manual send packet for the P4 top-10 (read-only assembly).

No sending. Emits p4_manual_send_packet.md with exact recipient, subject,
body, recommended window, evidence, follow-up date, and logging instructions.
"""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

GTM_DIR = Path(__file__).resolve().parent
TOP10_PATH = GTM_DIR / "p4_today_top10.csv"
PROSPECTS_PATH = GTM_DIR / "p4_first_25_prospects.csv"
QUEUE_PATH = GTM_DIR / "p4_outreach_queue.json"
OUT_PATH = GTM_DIR / "p4_manual_send_packet.md"

BASE_DATE = date(2026, 9, 17)  # packet assembly date; windows relative to it


def main() -> int:
    with open(TOP10_PATH, encoding="utf-8-sig", newline="") as fh:
        top = list(csv.DictReader(fh))
    with open(PROSPECTS_PATH, encoding="utf-8-sig", newline="") as fh:
        websites = {r["prospect_id"]: r["website"] for r in csv.DictReader(fh)}
    queue = {r["prospect_id"]: r for r in json.loads(
        QUEUE_PATH.read_text(encoding="utf-8"))["queue"]}
    lines = [
        "# P4 Manual Send Packet — TOP 10 (human sends only)",
        "",
        "No authorized automatic sender exists (no SMTP creds in env; gmail "
        "dispatcher DRY-RUN default). Send each APPROVED item by hand from "
        "your own mailbox, then log CONTACTED + timestamp + sender + approval ref.",
        "",
    ]
    for row in top:
        pid = row["prospect_id"]
        draft = queue[pid]
        recipient = row["email"] if row["email"] != "UNKNOWN" else (
            websites[pid] + " contact form (" + websites[pid] + ")")
        fu1 = BASE_DATE + timedelta(days=4)
        fu2 = BASE_DATE + timedelta(days=11)
        lines += [
            f"## {row['rank']}. {row['company']} ({pid})",
            f"TO: {recipient}",
            f"PHONE (alt path, published-not-verified): {row['phone']}",
            f"SUBJECT: {draft['message']['subject'].rstrip()}",
            "BODY:",
            "```",
            draft["message"]["body"],
            "```",
            f"EVIDENCE: {row['evidence']}",
            f"ANGLE: {row['message_angle']}",
            "SEND WINDOW: business hours America/Chicago, Tue-Thu preferred.",
            f"FOLLOW-UP #1: {fu1.isoformat()} (playbook §2, only if no reply/opt-out).",
            f"FOLLOW-UP #2: {fu2.isoformat()} (final; then CLOSED/NO RESPONSE).",
            "LOG AFTER SEND: queue send_status CONTACTED + timestamp + sender + approval ref; metrics contacted += 1.",
            "",
        ]
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"packet: {len(top)} items, sends_executed: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
