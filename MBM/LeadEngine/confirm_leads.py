#!/usr/bin/env python3
"""
MBM Lead Confirmer
Calls pipeline leads to confirm if they're still interested in selling/buying.
Uses Retell AI outbound calling.

Usage: python confirm_leads.py --leads pipeline.csv --phone 4695551234
"""

import csv
import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE = ROOT / "MBM" / "Pipeline" / "pipeline.csv"
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SELLER_CONFIRM_PROMPT = """You are calling from MBM Property Solutions to confirm if the homeowner is still interested in selling their property.

Your goal: Confirm selling intent and gather key details.

Opening: "Hi, this is Sarah from MBM Property Solutions. I'm reaching out regarding your property. Are you still interested in selling?"

If YES:
- "Great! Can I ask a few quick questions?"
- "What's the address of the property?"
- "What's your timeline for selling?"
- "What's your asking price, or are you flexible?"
- "Would you consider a cash offer?"
- "We can close in as little as 72 hours. Would you like to schedule a walkthrough?"

If NO:
- "No problem. Have you already sold, or are you not looking to sell right now?"
- If sold: "Congratulations! If you need help buying another property, we're here."
- If not selling: "Understood. If your plans change, feel free to call us back."

If BUSY:
- "I understand. When would be a better time for a quick 2-minute call?"

If OBJECTIONS:
- "I completely understand your concern. Many of our clients felt the same way initially."
- "We handle all the paperwork and there are zero fees to you."
- "Our cash offers are competitive and we close on your timeline."

Closing: "Thanks for your time. I'll follow up with an email. Have a great day!"

IMPORTANT: Be natural, empathetic, and professional. Don't be pushy. Log the outcome. """

BUYER_CONFIRM_PROMPT = """You are calling from MBM Property Solutions to confirm if the potential buyer is still interested in purchasing.

Your goal: Confirm buying intent and qualify the buyer.

Opening: "Hi, this is James from MBM Property Solutions. I'm reaching out about your property search. Are you still looking to buy?"

If YES:
- "Excellent! What's your budget range?"
- "What area are you looking in?"
- "Are you pre-approved for financing?"
- "What's your timeline for moving?"
- "We have great options in DFW. Want me to send you some listings?"

If NO:
- "Got it. Have you already found a property, or are you holding off?"
- If found: "Congratulations! If you need help selling your previous property, we can assist."
- If holding off: "No problem. I'll check back in a few weeks."

Closing: "I'll send over some options that match your criteria. Looking forward to helping you find the perfect property!"

IMPORTANT: Be natural and professional. Log the outcome."""


def load_leads():
    leads = []
    if not PIPELINE.exists():
        print(f"[!] Pipeline file not found: {PIPELINE}")
        return leads

    with open(PIPELINE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phone = row.get("phone", "").strip()
            if phone and phone != "phone":
                leads.append({
                    "company": row.get("company", "Unknown"),
                    "email": row.get("email", ""),
                    "phone": phone,
                    "solution": row.get("solution", ""),
                    "deal_value": row.get("deal_value", ""),
                    "stage": row.get("stage", ""),
                    "notes": row.get("notes", "")
                })
    return leads


def call_lead_retell(lead, my_number, api_key):
    """Place outbound call via Retell AI"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Choose prompt based on whether they're a seller or buyer lead
    is_buyer = "buy" in lead.get("solution", "").lower() or "buyer" in lead.get("notes", "").lower()
    prompt = BUYER_CONFIRM_PROMPT if is_buyer else SELLER_CONFIRM_PROMPT

    payload = {
        "phone_number": {
            "from": my_number,
            "to": lead["phone"].replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
        },
        "retell_llm_dynamic_variables": {
            "company_name": lead["company"],
            "solution": lead["solution"],
            "deal_value": lead.get("deal_value", "")
        }
    }

    try:
        r = requests.post("https://api.retellai.com/create-phone-call", headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            call_id = data.get("call_id", "unknown")
            return {"status": "initiated", "call_id": call_id}
        else:
            return {"status": "failed", "error": r.text[:200]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Confirm leads via voice calls")
    parser.add_argument("--phone", "-p", help="Your outbound caller ID number (E.164 format)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be called without actually calling")
    args = parser.parse_args()

    api_key = os.getenv("RETELL_API_KEY")
    if not api_key and not args.dry_run:
        print("[!] RETELL_API_KEY not set. Run with --dry-run to preview, or add key to .env")
        print("    Sign up at https://retellai.com → Dashboard → API Keys")
        return

    leads = load_leads()
    if not leads:
        print("[!] No leads found in pipeline.csv")
        return

    print(f"\n{'='*60}")
    print(f"  MBM LEAD CONFIRMER")
    print(f"  {len(leads)} leads to confirm")
    print(f"  Script: 'Are you still interested in selling or buying?'")
    print(f"{'='*60}\n")

    results = []
    for i, lead in enumerate(leads, 1):
        phone = lead["phone"]
        company = lead["company"]
        stage = lead["stage"]
        notes = lead.get("notes", "")

        print(f"[{i}/{len(leads)}] {company}")
        print(f"  Phone: {phone}")
        print(f"  Stage: {stage}")
        print(f"  Solution: {lead['solution']}")
        if notes:
            print(f"  Notes: {notes}")
        print()

        if args.dry_run:
            print(f"  -> Would call {phone} with seller/buyer qualifier script")
            results.append({"company": company, "phone": phone, "status": "dry_run"})
        else:
            if not args.phone:
                print("  [!] --phone required for live calls. Use --dry-run to preview.")
                continue

            outcome = call_lead_retell(lead, args.phone, api_key)
            results.append({"company": company, "phone": phone, **outcome})
            print(f"  → Call {outcome['status']}: {outcome.get('call_id', outcome.get('error', ''))}")
            time.sleep(2)  # Rate limit

        print()

    # Save results
    output_file = LOGS_DIR / f"lead_confirm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"{'='*60}")
    print(f"  Results saved to {output_file.name}")
    total = len(results)
    called = sum(1 for r in results if r["status"] == "initiated")
    dry = sum(1 for r in results if r["status"] == "dry_run")
    failed = sum(1 for r in results if r["status"] in ("failed", "error"))
    print(f"  Total: {total} | Called: {called} | Dry Run: {dry} | Failed: {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
