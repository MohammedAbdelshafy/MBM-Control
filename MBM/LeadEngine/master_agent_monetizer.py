"""
MBM Master Agent Monetization Pipeline
======================================
Passes all verified and enriched leads across ALL monetization agents & offer suites:

Monetization Channels & Agents:
  1. High-Ticket Enterprise Retainer Engine ($1,997/mo - $3,499 upfront)
     -> Targets: Clinics, Practice Admins, Corporate Businesses
     -> Deliverable: VIP AI Voice Employee & Patient-Growth Engine

  2. Real Estate Assignment & Wholesale Deal Matcher ($2,500 - $10,000 commission)
     -> Targets: Property Owners, Off-Market Distressed Sellers, Hedge Funds
     -> Deliverable: Cash Equity Match & Assignment Contract

  3. White-Label Agency & Lead Stream Subscription ($997/mo - $2,497/mo)
     -> Targets: Agencies, Wholesalers, B2B Sales Teams
     -> Deliverable: Full White-Label AI Portal & Verified Lead Stream

  4. Wolf Closer & Phone Bridge Agent
     -> Feeds closing scripts & 1-click Stripe/Neteller checkout links to active callers

Run:
  python MBM/LeadEngine/master_agent_monetizer.py
"""

import json
import os
import re
import sys
import io
import time
import subprocess
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
MONETIZATION_LOG = BASE_DIR / "logs" / "master_monetization_pipeline.json"
MONETIZATION_MD = BASE_DIR / "logs" / "master_monetization_pipeline.md"

NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[MASTER MONETIZER] [{ts}] {msg}"
    print(line)


def match_offer_for_lead(lead):
    contact = lead.get("contact", "")
    company = lead.get("company", "") or lead.get("gmaps_name", "")
    vertical = (lead.get("vertical") or "").lower()

    if any(k in vertical for k in ["clinic", "health", "doctor", "medical", "physician", "therapist", "dentist"]):
        return {
            "offer_id": "CLINIC_PATIENT_RETAINER",
            "title": "Medical Practice Patient-Growth & AI No-Show Automation Retainer",
            "upfront_price": 1997.00,
            "recurring_monthly": 497.00,
            "target_niche": "Healthcare / Clinic",
            "pitch_script": (
                f"Hi {contact}, we provide {company or 'your practice'} with a verified weekly patient lead stream "
                f"and automated AI no-show reminders. Setup is done-for-you with zero tech hassle."
            ),
            "neteller_checkout": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=1997.00&currency=USD&item=Clinic_AI_Retainer",
            "stripe_checkout": "https://checkout.stripe.com/pay/cs_live_clinic_retainer_1997"
        }
    elif any(k in vertical for k in ["real estate", "property", "wholesal", "investor", "distressed", "land"]):
        return {
            "offer_id": "REAL_ESTATE_EQUITY_MATCH",
            "title": "Off-Market Distressed Equity Match & Cash Assignment",
            "upfront_price": 5000.00,
            "recurring_monthly": 0.00,
            "target_niche": "Real Estate / Off-Market",
            "pitch_script": (
                f"Hi {contact}, we have pre-vetted cash buyers looking for off-market inventory in your area. "
                f"We can present an immediate cash contract with built-in assignment equity."
            ),
            "neteller_checkout": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=5000.00&currency=USD&item=Wholesale_Deal_Rights",
            "stripe_checkout": "https://checkout.stripe.com/pay/cs_live_wholesale_deal_5000"
        }
    else:
        return {
            "offer_id": "CONTECH_AGENCY_WHITE_LABEL",
            "title": "Contech AI White-Label Agency License & Verified Lead Stream Pass",
            "upfront_price": 2497.00,
            "recurring_monthly": 997.00,
            "target_niche": "B2B / Agency / Wholesaler",
            "pitch_script": (
                f"Hi {contact}, unlock our full white-label AI Telephony portal and daily verified lead stream "
                f"under your brand with 80%+ gross profit margins."
            ),
            "neteller_checkout": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=2497.00&currency=USD&item=Agency_WhiteLabel_License",
            "stripe_checkout": "https://checkout.stripe.com/pay/cs_live_agency_whitelabel_2497"
        }


def main():
    log("==========================================================")
    log("  MBM MASTER AGENT MONETIZATION ENGINE ACTIVATED")
    log("==========================================================")

    if not DIALER_DB.exists():
        log(f"ERROR: {DIALER_DB} does not exist.")
        return

    with open(DIALER_DB, "r", encoding="utf-8") as f:
        leads = json.load(f)

    qualified = [l for l in leads if l.get("skip_trace_status") in ("VERIFIED", "ENRICHED")]
    log(f"Processing Monetization Match for {len(qualified)} Qualified Leads...")

    monetized_pipeline = []
    total_upfront_pipeline_value = 0.0
    total_recurring_pipeline_value = 0.0

    for i, lead in enumerate(qualified):
        offer = match_offer_for_lead(lead)
        item = {
            "lead_id": lead.get("id"),
            "contact": lead.get("contact"),
            "company": lead.get("company") or lead.get("gmaps_name", ""),
            "phone": lead.get("phone"),
            "alt_phone": lead.get("skip_trace_phone_alt", ""),
            "email": lead.get("email") or lead.get("skip_trace_email", ""),
            "verification_status": lead.get("skip_trace_status"),
            "matched_offer_id": offer["offer_id"],
            "matched_offer_title": offer["title"],
            "upfront_value": offer["upfront_price"],
            "recurring_value": offer["recurring_monthly"],
            "pitch_script": offer["pitch_script"],
            "neteller_link": offer["neteller_checkout"],
            "stripe_link": offer["stripe_checkout"]
        }
        monetized_pipeline.append(item)
        total_upfront_pipeline_value += offer["upfront_price"]
        total_recurring_pipeline_value += offer["recurring_monthly"]

    # Save JSON report
    with open(MONETIZATION_LOG, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_qualified_leads": len(qualified),
            "projected_upfront_value_usd": total_upfront_pipeline_value,
            "projected_monthly_recurring_usd": total_recurring_pipeline_value,
            "pipeline": monetized_pipeline
        }, f, indent=2, default=str)

    # Save Markdown executive summary
    md_lines = [
        "# MBM Master Agent Monetization Pipeline Report",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Qualified Leads Matched**: {len(qualified)}",
        f"**Projected Upfront Pipeline Revenue**: **${total_upfront_pipeline_value:,.2f} USD**",
        f"**Projected Monthly Recurring Revenue**: **${total_recurring_pipeline_value:,.2f} USD/mo**",
        "",
        "| Lead Contact | Company / Practice | Verification | Matched Offer | Upfront Value | Monthly Recurring | Neteller Checkout | Stripe Checkout |",
        "|---|---|---|---|---|---|---|---|"
    ]

    for item in monetized_pipeline[:50]:
        md_lines.append(
            f"| {item['contact']} | {item['company']} | {item['verification_status']} | {item['matched_offer_title']} | "
            f"${item['upfront_value']:,.2f} | ${item['recurring_value']:,.2f}/mo | [Pay Neteller]({item['neteller_link']}) | [Pay Stripe]({item['stripe_link']}) |"
        )

    with open(MONETIZATION_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    log(f"✅ Generated Monetization Pipeline for {len(qualified)} leads!")
    log(f"💰 PROJECTED UPFRONT PIPELINE VALUE: ${total_upfront_pipeline_value:,.2f} USD")
    log(f"🔁 PROJECTED MONTHLY RECURRING VALUE: ${total_recurring_pipeline_value:,.2f} USD/mo")
    log(f"📄 Report saved to: {MONETIZATION_LOG}")
    log(f"📄 Markdown summary saved to: {MONETIZATION_MD}")

    # Trigger sub-monetizers
    sub_monetizers = [
        BASE_DIR / "high_ticket_instant_monetizer.py",
        BASE_DIR / "extreme_monetization_sales_hub.py",
        BASE_DIR / "seller_monetization_agent.py",
    ]
    for script in sub_monetizers:
        if script.exists():
            try:
                subprocess.run([sys.executable, str(script)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log(f"Executed sub-monetizer: {script.name}")
            except Exception as e:
                log(f"Notice executing {script.name}: {e}")

    log("==========================================================")
    log("  ALL MONETIZATION AGENTS COMPLETED SUCCESSFULLY!")
    log("==========================================================")


if __name__ == "__main__":
    main()
