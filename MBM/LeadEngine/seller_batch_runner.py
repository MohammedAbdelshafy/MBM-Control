"""
MBM REAL ESTATE SELLER BATCH RUNNER & OUTBOUND DISPOSITION ENGINE
=============================================================================
Controls batching, scripting, live disposition recording, and automatic
reprioritization for verified Real Estate Seller opportunities.

Progression: Batch 1 (Top 10) -> Batch 2 (Top 25) -> Batch 3 (Top 50) -> All 155.

Zero fabrication guarantee:
  - Dispositions recorded only upon real operator events.
  - Preserves 1,222 records under DialerSingleWriter.
  - Updates GtmRevenueScoreboard and DIALER_TOP_PRIORITY_CALLSHEET.md dynamically.
=============================================================================
"""

import os
import sys
import json
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter
from MBM.LeadEngine.dialer_priority_engine import refresh_dialer_priority_queue
from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard

DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
BATCH_1_DOC_PATH = ROOT_DIR / "MBM" / "Artifacts" / "SELLER_BATCH_1_DISPATCH.md"


def get_callable_sellers(db_path: Path = DIALER_DB_PATH) -> List[Dict[str, Any]]:
    writer = DialerSingleWriter(db_path=db_path)
    leads = writer.read_leads()
    sellers = [l for l in leads if l.get("is_real_estate") and l.get("is_callable")]
    sellers.sort(key=lambda x: (x.get("queue_rank") or 999999))
    return sellers


def generate_seller_script(lead: Dict[str, Any]) -> str:
    owner = lead.get("contact") or lead.get("owner_name") or lead.get("authorized_official_name") or "there"
    first_name = owner.split()[0] if owner else "there"
    prop = lead.get("address") or lead.get("property_address") or lead.get("company") or "the property"

    script = (
        f"1. OPENING: Hi {first_name}, my name is Mohammed. I'm reaching out regarding {prop} in Texas. Are you still the owner of this property?\n"
        f"2. PURPOSE: We are actively acquiring residential and commercial assets in your area for direct portfolio investment. If you received a fair, all-cash, as-is offer with zero closing costs, would you consider selling?\n"
        f"3. DISCOVERY: What is the current occupancy and condition of the property? What timeline would work best for you?\n"
        f"4. NEXT STEP: Let's do a quick 10-minute preliminary walkthrough or cash offer review. Are you available tomorrow at 10 AM or 2 PM?\n"
        f"5. POLITE EXIT: Thank you {first_name}, appreciate your time!"
    )
    return script


def generate_batch_package(batch_size: int = 10) -> Dict[str, Any]:
    sellers = get_callable_sellers()
    batch = sellers[:batch_size]

    lines = [
        f"# REAL ESTATE SELLER OUTBOUND — BATCH 1 (TOP {len(batch)} SELLERS)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Total Callable Sellers in Queue:** {len(sellers)}",
        "**Strategy:** Direct property acquisition / Wholesale cash offer ladder.",
        "",
        "---",
        "",
        "## OPERATOR EXECUTION INSTRUCTIONS",
        "1. Click the **WhatsApp 1-Click Link** or dial directly from your mobile/dialer.",
        "2. Follow the real estate property acquisition script.",
        "3. Record the real disposition immediately via:",
        "   ```bash",
        "   python MBM/LeadEngine/seller_batch_runner.py --record --lead-id <ID> --disposition <CONTACTED|CALLBACK_REQUESTED|VOICEMAIL|NO_ANSWER|QUALIFIED|DNC>",
        "   ```",
        "",
        "---",
        ""
    ]

    for idx, lead in enumerate(batch, start=1):
        lead_id = lead.get("id")
        rank = lead.get("queue_rank")
        owner = lead.get("contact") or lead.get("owner_name") or lead.get("authorized_official_name") or "Owner"
        phone = lead.get("phone")
        clean_phone = "".join(filter(str.isdigit, str(phone or "")))
        prop = lead.get("address") or lead.get("property_address") or lead.get("company") or "Property"
        segment = lead.get("segment") or lead.get("distress_reason") or "Motivated Seller"
        score = lead.get("priority_score", 0.0)

        first_name = owner.split()[0] if owner else "there"
        msg_text = (
            f"Hi {first_name} — reaching out regarding {prop} in TX. "
            f"We are actively acquiring properties in your area for direct portfolio investment. "
            f"If you received a fair, all-cash, as-is offer with zero closing costs, would you consider an offer? "
            f"Do you have 2 minutes to discuss?"
        )
        encoded_msg = urllib.parse.quote(msg_text)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

        lines.extend([
            f"### #{idx} (Queue #{rank}) | {prop}",
            f"- **Lead ID:** `{lead_id}`",
            f"- **Owner Name:** {owner}",
            f"- **Verified Phone:** `{phone}`",
            f"- **Priority Score:** `{score}` ({lead.get('priority_reason')})",
            f"- **Signal / Strategy:** {segment}",
            f"- **1-Click WhatsApp Opener:** [Open WhatsApp Chat]({wa_link})",
            "",
            "**Real Estate Call Script:**",
            f"```text\n{generate_seller_script(lead)}\n```",
            "",
            "---",
            ""
        ])

    BATCH_1_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_1_DOC_PATH.write_text("\n".join(lines), encoding="utf-8")

    return {
        "status": "BATCH_PREPARED",
        "batch_size": len(batch),
        "total_sellers": len(sellers),
        "batch": batch,
        "doc_path": str(BATCH_1_DOC_PATH)
    }


def record_disposition(
    lead_id: str,
    disposition: str,
    notes: str = "",
    channel: str = "PHONE",
) -> Dict[str, Any]:
    """
    Records a real operator disposition, updates sales ledger, and triggers dynamic reprioritization.
    """
    valid_dispositions = {
        "NO_ANSWER", "VOICEMAIL", "CONTACTED", "CALLBACK_REQUESTED",
        "INTERESTED", "QUALIFIED", "NOT_INTERESTED", "DNC", "INVALID"
    }
    disp_upper = disposition.upper()
    if disp_upper not in valid_dispositions:
        raise ValueError(f"Invalid disposition {disposition}. Valid: {valid_dispositions}")

    ledger = GtmSalesLedger()
    event = ledger.record_transition(
        prospect_id=lead_id,
        agent="OPERATOR_HUMAN",
        channel=channel,
        previous_state="QUEUED",
        new_state=disp_upper,
        action=f"SELLER_{disp_upper}",
        evidence={"disposition": disp_upper, "notes": notes, "recorded_at": datetime.now(timezone.utc).isoformat()},
        next_action="FOLLOW_UP" if disp_upper in {"CALLBACK_REQUESTED", "VOICEMAIL", "INTERESTED"} else "CLOSE",
        notes=notes,
    )

    # If DNC, mark is_suppressed on lead
    if disp_upper in {"DNC", "INVALID", "NOT_INTERESTED"}:
        writer = DialerSingleWriter()
        leads = writer.read_leads()
        for l in leads:
            if str(l.get("id")) == str(lead_id):
                l["identity_state"] = "DO_NOT_CALL" if disp_upper == "DNC" else "NOT_INTERESTED"
                l["is_suppressed"] = True
                l["is_callable"] = False
        writer.commit_update(leads, author="OPERATOR", reason=f"seller_disposition_{disp_upper}")

    # Dynamically reprioritize queue
    refresh_result = refresh_dialer_priority_queue(dry_run=False, author=f"DISPOSITION_{disp_upper}")

    # Update scoreboard
    scoreboard = GtmRevenueScoreboard(ledger=ledger)
    scoreboard.export_reports()

    return {
        "status": "DISPOSITION_RECORDED",
        "lead_id": lead_id,
        "disposition": disp_upper,
        "event": event,
        "queue_refresh": refresh_result,
    }


def main():
    parser = argparse.ArgumentParser(description="MBM Real Estate Seller Batch Runner")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size (default: 10)")
    parser.add_argument("--record", action="store_true", help="Record a disposition")
    parser.add_argument("--lead-id", type=str, help="Lead ID to record disposition for")
    parser.add_argument("--disposition", type=str, help="Disposition (CONTACTED, CALLBACK_REQUESTED, VOICEMAIL, NO_ANSWER, QUALIFIED, DNC, etc.)")
    parser.add_argument("--notes", type=str, default="", help="Optional disposition notes")
    args = parser.parse_args()

    if args.record:
        if not args.lead_id or not args.disposition:
            print("[ERROR] --lead-id and --disposition are required when recording.")
            sys.exit(1)
        res = record_disposition(args.lead_id, args.disposition, notes=args.notes)
        print(f"[OK] Disposition {args.disposition} recorded for {args.lead_id}.")
        return

    res = generate_batch_package(batch_size=args.batch_size)
    print(f"[OK] Batch 1 ({res['batch_size']} real estate sellers) generated -> {res['doc_path']}")


if __name__ == "__main__":
    main()
