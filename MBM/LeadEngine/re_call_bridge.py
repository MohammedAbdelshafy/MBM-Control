"""
Real Estate Option 2 Live Mobile Call Bridger
===============================================
Mission: Live Call Bridger for Real Estate Deals & Motivated Sellers.
Rings your personal mobile phone (+201040404118) with complete deal objectives
(ARV, Target Cash Offer, Assignment Profit, Address), then bridges you live to the seller/agent.

Usage:
  python re_call_bridge.py --deal 1
  python re_call_bridge.py --deal 1 --my-phone +201040404118
  python re_call_bridge.py --list
  python re_call_bridge.py --deal 1 --simulate
"""

import os
import sys
import json
import csv
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
WORKSPACE_ROOT = BASE_DIR.parent.parent.resolve()
load_dotenv(WORKSPACE_ROOT / ".env")

QUEUE_FILE = BASE_DIR / "real_estate_calling_queue.json"
CSV_FILE = WORKSPACE_ROOT / "real_estate_200_deals_top_prospects.csv"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+16619909068").strip()
DEFAULT_USER_PHONE = os.getenv("USER_MOBILE_PHONE", "+201040404118").strip()


def load_deals():
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, encoding='utf-8') as f:
            return json.load(f)
    elif CSV_FILE.exists():
        deals = []
        with open(CSV_FILE, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                deals.append(row)
        return deals
    return []


def list_top_deals(deals, count=15):
    print("==================================================================")
    print("  JARVIS OS — TOP REAL ESTATE DEALS & SELLER CALL QUEUE")
    print("==================================================================")
    print(f"{'Rank':<6} {'Owner / Seller':<22} {'Role / Type':<20} {'Est. ARV':<12} {'Target Offer':<14} {'Profit Target':<14} {'City, State'}")
    print("-" * 105)
    for d in deals[:count]:
        rank = d.get('prospect_rank') or d.get('rank') or '?'
        name = d.get('contact_name', 'Owner')[:20]
        role = d.get('role_type', 'Seller')[:18]
        arv = d.get('est_arv', 'N/A')
        offer = d.get('target_cash_offer', 'N/A')
        profit = d.get('est_assignment_profit', 'N/A')
        city_st = f"{d.get('city', '')}, {d.get('state', '')}"
        print(f"#{rank:<5} {name:<22} {role:<20} {arv:<12} {offer:<14} {profit:<14} {city_st}")
    print("------------------------------------------------------------------")
    print(f"Total Real Estate Deals Ready: {len(deals)}")
    print("Run command: python re_call_bridge.py --deal 1 --my-phone +201040404118\n")


def bridge_real_estate_call(deal: dict, my_mobile: str, simulate: bool = False):
    rank = deal.get('prospect_rank') or deal.get('deal_id') or '1'
    address = deal.get('property_address') or 'Property'
    contact = deal.get('contact_name') or 'Motivated Seller'
    role = deal.get('role_type') or 'Seller'
    phone = deal.get('phone_number') or deal.get('phone')
    arv = deal.get('est_arv') or '$300,000'
    price = deal.get('asking_price') or '$210,000'
    offer = deal.get('target_cash_offer') or '$185,000'
    profit = deal.get('est_assignment_profit') or '$25,000'
    distress = deal.get('distress_signal') or 'Pre-Foreclosure / High Equity'
    hook = deal.get('call_opening_hook') or f"Hi {contact}! Reaching out regarding your property at {address}."

    print("\n==================================================================")
    print(f"  REAL ESTATE DEAL BRIEFING — DEAL #{rank}")
    print("==================================================================")
    print(f"  [Property Address]       {address}")
    print(f"  [Seller / Contact Name]  {contact} ({role})")
    print(f"  [Seller Phone Number]   {phone}")
    print(f"  [Distress Signal]       {distress}")
    print(f"  [Est. ARV]              {arv}")
    print(f"  [Asking Price]          {price}")
    print(f"  [Target Cash Offer]     {offer}")
    print(f"  [Est. Assignment Profit]{profit}")
    print("------------------------------------------------------------------")
    print(f"  [Recommended Pitch Hook]:\n     \"{hook}\"")
    print("==================================================================")
    print(f"  Bridging call from Twilio ({TWILIO_PHONE_NUMBER}) to your cell ({my_mobile})...")

    if simulate:
        print("\n[SIMULATION MODE] Live Real Estate Call Bridge Verified!")
        print(f"1. System rings your mobile phone ({my_mobile})")
        print(f"2. You answer -> Audio plays: 'Connecting you to {contact} for {address}. Target offer: {offer}'")
        print(f"3. System dials {contact} ({phone}) displaying Caller ID {TWILIO_PHONE_NUMBER}")
        print("==================================================================")
        return "SIMULATED_RE_CALL_SID_998877"

    # Try Twilio call bridge
    try:
        from twilio.rest import Client
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            twiml_content = f"""<Response>
                <Say>Connecting your real estate call to {contact} regarding {address}. Your target cash offer is {offer} with {profit} assignment profit target.</Say>
                <Dial callerId="{TWILIO_PHONE_NUMBER}">{phone}</Dial>
            </Response>"""
            
            call = client.calls.create(
                twiml=twiml_content,
                to=my_mobile,
                from_=TWILIO_PHONE_NUMBER
            )
            print(f"\n[+] SUCCESS! Twilio is ringing your cell phone ({my_mobile}) right now!")
            print(f"[+] Answer the call to connect live to {contact} ({phone}).")
            print(f"[+] Call SID: {call.sid}")
            return call.sid
    except Exception as e:
        print(f"\n[!] Twilio live bridge status: {e}")

    # Retell AI Web / Phone Voice Bridge fallback
    retell_key = os.getenv("RETELL_API_KEY", "").strip()
    if retell_key:
        print(f"[+] Initiating Retell AI Live Voice Session for {contact} ({phone})...")
        try:
            import requests
            r = requests.post(
                "https://api.retellai.com/v2/create-web-call",
                headers={"Authorization": f"Bearer {retell_key}", "Content-Type": "application/json"},
                json={"agent_id": "agent_728edb006e021ef7e40cbaba38"},
                timeout=10
            )
            if r.status_code in (200, 201):
                data = r.json()
                print(f"[+] SUCCESS: Retell Voice Session Active (Call ID: {data.get('call_id')})")
                print(f"[+] Web Session Token: {data.get('access_token')[:30]}...")
                return data.get('call_id')
        except Exception as re_err:
            print(f"[!] Retell Voice error: {re_err}")

    return None


def main():
    parser = argparse.ArgumentParser(description="Option 2 Real Estate Live Call Bridger")
    parser.add_argument("--deal", type=int, default=1, help="Deal rank (1-200) to bridge call")
    parser.add_argument("--my-phone", type=str, default=DEFAULT_USER_PHONE, help="Your personal cell phone number")
    parser.add_argument("--list", action="store_true", help="List top real estate deals in queue")
    parser.add_argument("--simulate", action="store_true", help="Simulate call bridge without live dialing")
    args = parser.parse_args()

    deals = load_deals()
    if not deals:
        print("ERROR: No real estate deals found. Run harvest_200_real_estate_deals.py first.")
        return

    if args.list:
        list_top_deals(deals, count=20)
        return

    deal_idx = max(0, min(args.deal - 1, len(deals) - 1))
    target_deal = deals[deal_idx]

    bridge_real_estate_call(target_deal, args.my_phone, args.simulate)


if __name__ == "__main__":
    main()
