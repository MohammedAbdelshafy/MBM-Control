"""
MBM REAL ESTATE SELLER BATCH RUNNER & OUTBOUND OPERATOR COPILOT
=============================================================================
Frictionless CLI copilot and dispatch engine for Real Estate Seller outbound calls.

Commands:
  1. `python MBM/LeadEngine/seller_batch_runner.py --next`
     Surfaces the single highest-priority, verified, callable seller target with
     1-click WhatsApp link, direct script, and instant disposition commands.

  2. `python MBM/LeadEngine/seller_batch_runner.py --record --lead-id <ID> --disposition <DISP> [--notes <TXT>]`
     Atomically records the disposition, updates state, reprioritizes the queue,
     refreshes the scoreboard, and immediately displays the next best target.

  3. `python MBM/LeadEngine/seller_batch_runner.py --batch-size 10`
     Generates the full Batch 1 dispatch package with compact cards.

Valid Dispositions:
  - `CONTACTED`             (Live conversation with owner)
  - `CALLBACK_REQUESTED`    (Owner asked to call back at specific time)
  - `VOICEMAIL`             (Left property acquisition voicemail)
  - `NO_ANSWER`             (Ranged out / no answer)
  - `QUALIFIED`             (Confirmed seller motivation & property condition)
  - `INTERESTED`            (Requested all-cash preliminary offer)
  - `NOT_INTERESTED`        (Not selling, move down)
  - `DNC`                   (Do not call - immediate suppression)
  - `INVALID`               (Bad number / wrong person)
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
from MBM.LeadEngine.dialer_priority_engine import (
    refresh_dialer_priority_queue,
    is_lead_suppressed,
    is_real_estate_seller,
    has_verified_owner_and_phone,
    _digits,
)
from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard

DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
BATCH_1_DOC_PATH = ROOT_DIR / "MBM" / "Artifacts" / "SELLER_BATCH_1_DISPATCH.md"
SALES_LEDGER_PATH = ROOT_DIR / "MBM" / "Whop" / "ai-consultancy-agency" / "sales_ledger_day1.json"


def get_callable_sellers(db_path: Path = DIALER_DB_PATH) -> List[Dict[str, Any]]:
    """
    Returns only verified, callable, non-suppressed real estate seller leads,
    sorted by queue_rank ascending (highest priority first).
    """
    writer = DialerSingleWriter(db_path=db_path)
    leads = writer.read_leads()

    valid_sellers = []
    for l in leads:
        if is_lead_suppressed(l):
            continue
        if not is_real_estate_seller(l):
            continue
        if not has_verified_owner_and_phone(l):
            continue
        if l.get("callable") is False or l.get("is_callable") is False:
            continue
        valid_sellers.append(l)

    # Sort strictly by queue_rank ascending, then priority_score descending
    valid_sellers.sort(key=lambda x: (
        x.get("queue_rank") if isinstance(x.get("queue_rank"), int) else 999999,
        -float(x.get("priority_score") or 0.0)
    ))
    return valid_sellers


def generate_seller_script(lead: Dict[str, Any]) -> str:
    owner = lead.get("contact") or lead.get("owner_name") or lead.get("authorized_official_name") or "there"
    first_name = owner.split()[0] if owner else "there"
    prop = lead.get("address") or lead.get("property_address") or lead.get("company") or "the property"

    return (
        f"1. OPENING: Hi {first_name}, my name is Mohammed. I'm reaching out regarding {prop} in Texas. Are you still the owner of this property?\n"
        f"2. PURPOSE: We are actively acquiring residential and commercial assets in your area for direct portfolio investment. If you received a fair, all-cash, as-is offer with zero closing costs, would you consider selling?\n"
        f"3. DISCOVERY: What is the current occupancy and condition of the property? What timeline would work best for you?\n"
        f"4. NEXT STEP: Let's do a quick 10-minute preliminary walkthrough or cash offer review. Are you available tomorrow at 10 AM or 2 PM?\n"
        f"5. POLITE EXIT: Thank you {first_name}, appreciate your time!"
    )


def format_next_target_cli(lead: Dict[str, Any], position: int = 1, total: int = 155) -> str:
    """Formats a single high-priority seller into a compact, actionable operator card."""
    lead_id = lead.get("id", "UNKNOWN")
    rank = lead.get("queue_rank", position)
    owner = lead.get("contact") or lead.get("owner_name") or lead.get("authorized_official_name") or "Verified Owner"
    first_name = owner.split()[0] if owner else "there"
    phone = lead.get("phone", "")
    clean_phone = _digits(phone)
    prop = lead.get("address") or lead.get("property_address") or lead.get("company") or "Texas Property"
    segment = lead.get("segment") or lead.get("distress_reason") or "Motivated Seller"
    score = lead.get("priority_score", 0.0)
    raw_reason = lead.get("priority_reason", "VERIFIED MOTIVATED SELLER")
    reason = str(raw_reason).encode("ascii", errors="ignore").decode("ascii").strip()


    msg_text = (
        f"Hi {first_name} — reaching out regarding {prop} in TX. "
        f"We are actively acquiring properties in your area for direct portfolio investment. "
        f"If you received a fair, all-cash, as-is offer with zero closing costs, would you consider an offer? "
        f"Do you have 2 minutes to discuss?"
    )
    encoded_msg = urllib.parse.quote(msg_text)
    wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

    lines = [
        "================================================================================",
        f"[*] NEXT HIGHEST-PRIORITY SELLER: #{rank} of {total} (Score: {score})",
        "================================================================================",
        f"  PROPERTY:  {prop}",
        f"  OWNER:     {owner}",
        f"  PHONE:     {phone}",
        f"  SIGNAL:    {segment} ({reason})",
        f"  LEAD ID:   {lead_id}",
        "--------------------------------------------------------------------------------",
        f"  1-CLICK WHATSAPP: {wa_link}",
        f"  DIRECT CALL:      tel:{phone}",
        "--------------------------------------------------------------------------------",
        "SCRIPT:",
        f"  1. 'Hi {first_name}, calling regarding {prop}. Are you still the owner?'",
        "  2. 'We buy properties as-is for cash. Would you consider an offer?'",
        "  3. 'What condition is it in, and what timeline works for you?'",
        "  4. 'Let's schedule a 10-minute offer review tomorrow at 10 AM or 2 PM.'",
        "--------------------------------------------------------------------------------",
        "RECORD DISPOSITION (Copy & Run):",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition CONTACTED",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition CALLBACK_REQUESTED",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition VOICEMAIL",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition NO_ANSWER",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition QUALIFIED",
        f"  python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition DNC",
        "================================================================================",
    ]
    return "\n".join(lines)



def get_next_seller() -> Optional[Dict[str, Any]]:
    """Returns the top callable seller lead."""
    sellers = get_callable_sellers()
    return sellers[0] if sellers else None


def generate_batch_package(batch_size: int = 10) -> Dict[str, Any]:
    """Generates the compact markdown batch dispatch sheet."""
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
        "## OPERATOR WORKFLOW",
        "1. Surface the next lead: `python MBM/LeadEngine/seller_batch_runner.py --next`",
        "2. Click the 1-Click WhatsApp Link or dial directly.",
        "3. Record disposition: `python MBM/LeadEngine/seller_batch_runner.py --record --lead-id <ID> --disposition <DISP>`",
        "",
        "---",
        ""
    ]

    for idx, lead in enumerate(batch, start=1):
        lead_id = lead.get("id")
        rank = lead.get("queue_rank", idx)
        owner = lead.get("contact") or lead.get("owner_name") or lead.get("authorized_official_name") or "Owner"
        phone = lead.get("phone")
        clean_phone = _digits(phone)
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
            f"- **Direct Call:** `tel:{phone}`",
            f"- **Record Disposition:** `python MBM/LeadEngine/seller_batch_runner.py --record --lead-id {lead_id} --disposition CONTACTED`",
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
    Records a real operator disposition, updates sales ledger, reprioritizes queue,
    and exports updated scoreboard.
    """
    valid_dispositions = {
        "NO_ANSWER", "VOICEMAIL", "CONTACTED", "CALLBACK_REQUESTED",
        "INTERESTED", "QUALIFIED", "NOT_INTERESTED", "DNC", "INVALID"
    }
    disp_upper = disposition.upper()
    if disp_upper not in valid_dispositions:
        raise ValueError(f"Invalid disposition '{disposition}'. Must be one of: {sorted(valid_dispositions)}")

    # 1. Update lead in canonical database
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    leads = writer.read_leads()
    target_lead = None

    for l in leads:
        if str(l.get("id")) == str(lead_id):
            target_lead = l
            l["last_contact_date"] = datetime.now(timezone.utc).isoformat()
            l["status"] = disp_upper

            if disp_upper == "DNC":
                l["identity_state"] = "DO_NOT_CALL"
                l["is_suppressed"] = True
                l["is_callable"] = False
                l["callable"] = False
            elif disp_upper in {"NOT_INTERESTED", "INVALID"}:
                l["identity_state"] = "NOT_INTERESTED" if disp_upper == "NOT_INTERESTED" else "WRONG_PERSON"
                l["is_suppressed"] = True
                l["is_callable"] = False
                l["callable"] = False
            elif disp_upper in {"CALLBACK_REQUESTED", "QUALIFIED", "CONTACTED", "INTERESTED"}:
                l["crm_stage"] = disp_upper
                l["identity_state"] = "OWNER_CONFIRMED"
            break

    if target_lead is None:
        raise ValueError(f"Lead ID '{lead_id}' not found in canonical dialer database.")

    # Commit update under single-writer lock
    writer.commit_update(leads, author="OPERATOR", reason=f"seller_disposition_{disp_upper}")

    # 2. Record to sales ledger
    ledger = GtmSalesLedger()
    event = ledger.record_transition(
        prospect_id=lead_id,
        agent="OPERATOR_HUMAN",
        channel=channel,
        previous_state="QUEUED",
        new_state=disp_upper,
        action=f"SELLER_{disp_upper}",
        evidence={
            "disposition": disp_upper,
            "notes": notes,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "phone": target_lead.get("phone"),
            "property": target_lead.get("company") or target_lead.get("address"),
        },
        next_action="FOLLOW_UP" if disp_upper in {"CALLBACK_REQUESTED", "VOICEMAIL", "INTERESTED"} else "CLOSE",
        notes=notes,
    )

    # 3. Dynamically reprioritize queue
    refresh_result = refresh_dialer_priority_queue(dry_run=False, author=f"DISPOSITION_{disp_upper}")

    # 4. Update scoreboard
    scoreboard = GtmRevenueScoreboard(ledger=ledger)
    scoreboard.export_reports()

    # 5. Get next seller
    next_seller = get_next_seller()

    return {
        "status": "DISPOSITION_RECORDED",
        "lead_id": lead_id,
        "disposition": disp_upper,
        "event": event,
        "queue_refresh": refresh_result,
        "next_seller": next_seller,
    }


def main():
    parser = argparse.ArgumentParser(description="MBM Real Estate Seller Batch Runner")
    parser.add_argument("--next", action="store_true", help="Display the next highest-priority seller lead")
    parser.add_argument("--batch-size", type=int, default=10, help="Generate batch package (default: 10)")
    parser.add_argument("--record", action="store_true", help="Record a disposition")
    parser.add_argument("--lead-id", type=str, help="Lead ID to record disposition for")
    parser.add_argument("--disposition", type=str, help="Disposition (CONTACTED, CALLBACK_REQUESTED, VOICEMAIL, NO_ANSWER, QUALIFIED, DNC, etc.)")
    parser.add_argument("--notes", type=str, default="", help="Optional disposition notes")
    args = parser.parse_args()

    if args.next:
        next_lead = get_next_seller()
        if not next_lead:
            print("[INFO] No callable real estate seller leads remaining in queue.")
            return
        sellers = get_callable_sellers()
        print(format_next_target_cli(next_lead, position=1, total=len(sellers)))
        return

    if args.record:
        if not args.lead_id or not args.disposition:
            print("[ERROR] --lead-id and --disposition are required when recording.")
            sys.exit(1)
        res = record_disposition(args.lead_id, args.disposition, notes=args.notes)
        print(f"\n[OK] Disposition '{args.disposition.upper()}' recorded for {args.lead_id}.")
        print("[OK] Priority queue reprioritized & GTM scoreboard updated.")

        if res.get("next_seller"):
            sellers = get_callable_sellers()
            print("\n" + format_next_target_cli(res["next_seller"], position=1, total=len(sellers)))
        else:
            print("\n[INFO] All real estate seller leads in this batch processed.")
        return

    res = generate_batch_package(batch_size=args.batch_size)
    print(f"[OK] Batch 1 ({res['batch_size']} real estate sellers) generated -> {res['doc_path']}")


if __name__ == "__main__":
    main()
