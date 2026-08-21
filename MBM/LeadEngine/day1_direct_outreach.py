"""
DAY-1 DIRECT OUTREACH GENERATOR (ZERO-COST OPERATOR BRIDGE)
=============================================================================
Generates 1-click WhatsApp (`wa.me`) and Gmail Web direct compose links
for the top 10 verified business prospects without requiring Twilio or paid APIs.

Offer: AI Consultancy Sprint Audit ($297.00)
Funnel: https://mbm-dialer-app.vercel.app/sprint/
Whop Checkout: https://whop.com/checkout/plan_e3ibiYXeeAaZV
=============================================================================
"""

import urllib.parse
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SALES_LEDGER_PATH = ROOT_DIR / "MBM" / "Whop" / "ai-consultancy-agency" / "sales_ledger_day1.json"
OUTREACH_DOC_PATH = ROOT_DIR / "MBM" / "Whop" / "ai-consultancy-agency" / "DAY_1_DIRECT_OUTREACH.md"

TARGETS = [
    {
        "id": "PROSPECT-001",
        "company": "Premier Smile Partners Dental Group",
        "contact": "Dr. Sarah Lin",
        "phone": "+19726658140",
        "vertical": "Dental Clinics & Orthodontics",
        "state": "TX",
        "angle": "Stop buying shared dental leads. We install an AI assistant that follows up and books high-value patient consults in 14 days."
    },
    {
        "id": "PROSPECT-002",
        "company": "Pinnacle Acoustical & Drywall Systems Corp",
        "contact": "Douglas Hayes",
        "phone": "+18179483010",
        "vertical": "Commercial Contractors & ConTech",
        "state": "FL",
        "angle": "Automate subcontractor bidding and incoming project estimation follow-ups with a dedicated 14-day AI system."
    },
    {
        "id": "PROSPECT-003",
        "company": "Trident Commercial Flooring & Epoxy Solutions",
        "contact": "Stephen Cooper",
        "phone": "+18179483011",
        "vertical": "Commercial Contractors & ConTech",
        "state": "FL",
        "angle": "Re-activate dormant commercial accounts and capture after-hours quote requests automatically."
    },
    {
        "id": "PROSPECT-004",
        "company": "Metroplex Demolition & Site Clearing LLC",
        "contact": "Donald Weaver",
        "phone": "+19728493012",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "AI system to follow up on municipal and commercial demo RFPs before competitors respond."
    },
    {
        "id": "PROSPECT-005",
        "company": "Red River Steel Erectors & Rigging LLC",
        "contact": "Kenneth Larson",
        "phone": "+19728493010",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Speed-to-lead automation for structural steel fabrication & rigging contracts."
    },
    {
        "id": "PROSPECT-006",
        "company": "Southwest Elevator & Escalator Modernization",
        "contact": "Phillip Hughes",
        "phone": "+12148923415",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Automate routine maintenance contract renewals and emergency dispatch qualification."
    },
    {
        "id": "PROSPECT-007",
        "company": "Prestige Masonry & Architectural Stone LLC",
        "contact": "Victor Morales",
        "phone": "+14698492011",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Done-for-you AI calling system that qualifies luxury architectural and commercial bids."
    },
    {
        "id": "PROSPECT-008",
        "company": "Lonestar Industrial Roofing & Waterproofing LLC",
        "contact": "Mark Henderson",
        "phone": "+12148923413",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Stop losing post-storm commercial leads. AI caller follows up in 60 seconds."
    },
    {
        "id": "PROSPECT-009",
        "company": "Apex Mechanical & Commercial Air Solutions LLC",
        "contact": "David Miller",
        "phone": "+12148923410",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Automate HVAC preventive maintenance agreements and dispatch follow-ups."
    },
    {
        "id": "PROSPECT-010",
        "company": "Houston Piping & Mechanical Contractors Inc",
        "contact": "Raymond Jackson",
        "phone": "+17138492012",
        "vertical": "Commercial Contractors & ConTech",
        "state": "TX",
        "angle": "Industrial piping RFP qualification and vendor relationship outreach engine."
    }
]

FUNNEL_URL = "https://mbm-dialer-app.vercel.app/sprint/"
WHOP_AUDIT_URL = "https://whop.com/checkout/plan_e3ibiYXeeAaZV"


def build_outreach_package():
    outreach_items = []
    lines = [
        "# DAY-1 DIRECT OUTREACH DISPATCH SHEET (FREE OPERATOR CHANNELS)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Funnel URL:** [{FUNNEL_URL}]({FUNNEL_URL})",
        f"**Whop Direct Checkout:** [{WHOP_AUDIT_URL}]({WHOP_AUDIT_URL})",
        "",
        "---",
        "",
        "## INSTRUCTIONS FOR OPERATOR",
        "1. Click the **WhatsApp Direct Link** on mobile/web to send the pre-filled opening pitch instantly.",
        "2. Or click the **Gmail Compose Link** to send from your personal Gmail account.",
        "3. Once the prospect replies, qualify them and send the $297 Whop Audit link.",
        "",
        "---",
        ""
    ]

    for idx, t in enumerate(TARGETS, start=1):
        clean_phone = "".join(filter(str.isdigit, t["phone"]))
        first_name = t["contact"].split()[0] if t["contact"] else "there"

        # WhatsApp Message
        msg_text = (
            f"Hi {t['contact']} — saw {t['company']} is active in {t['state']}. "
            f"We build done-for-you AI systems for {t['vertical']} that follow up, qualify, and book your best jobs in 14 days without hiring a sales team.\n\n"
            f"We just launched our 72-hour AI Sprint Audit ($297): {FUNNEL_URL}\n\n"
            f"Would you like me to send over the 3-point breakdown for {t['company']}?"
        )
        encoded_msg = urllib.parse.quote(msg_text)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

        # Gmail Compose Link
        email_subject = urllib.parse.quote(f"AI growth plan for {t['company']} (14-day Sprint)")
        email_body = urllib.parse.quote(msg_text)
        gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&su={email_subject}&body={email_body}"

        lines.extend([
            f"### #{idx}: {t['company']} — {t['contact']}",
            f"- **Vertical:** {t['vertical']} ({t['state']})",
            f"- **Phone:** `{t['phone']}`",
            f"- **Angle:** {t['angle']}",
            f"- **WhatsApp 1-Click Message:** [Open in WhatsApp]({wa_link})",
            f"- **Gmail 1-Click Compose:** [Open in Gmail]({gmail_link})",
            "",
            "**Message Preview:**",
            f"> {msg_text.replace(chr(10), ' ')}",
            "",
            "---",
            ""
        ])

        outreach_items.append({
            "target": t,
            "wa_link": wa_link,
            "gmail_link": gmail_link,
            "message": msg_text
        })

    OUTREACH_DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    return outreach_items


if __name__ == "__main__":
    items = build_outreach_package()
    print(f"[OK] Generated Day-1 direct outreach for {len(items)} prospects -> {OUTREACH_DOC_PATH}")
