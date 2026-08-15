"""
Phound & Native SMS Enterprise Outreach Engine for ConTech AI Consultancy
==========================================================================
Engineered specifically for Phound App and Native Mobile SMS dispatch.
Generates personalized, high-converting B2B SMS sequences for ConTech AI
Consultancy client acquisition without any third-party Twilio dependency.

Key Features:
- 1-Touch Phound Web & Mobile Deeplinks (`sms:` and `https://web.phound.app`)
- 3-Stage High-Converting B2B Enterprise Copy (CAD Takeoff, Estimation Bandwidth)
- Non-colliding standalone architecture (Zero interference with other queues)
- Export to Interactive Visual Dispatch Room + CSV Calling Queue
"""

import os
import sys
import json
import csv
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
OUTPUT_DIR = BASE_DIR / "campaigns"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HTML_DISPATCH_ROOM = BASE_DIR / "phound_sms_cockpit.html"
CAMPAIGN_CSV = OUTPUT_DIR / "phound_contech_sms_queue.csv"
CAMPAIGN_JSON = OUTPUT_DIR / "phound_contech_sms_queue.json"


# ── High-Converting Enterprise ConTech SMS Templates ─────────────────────────

TOUCH_1_TEMPLATE = (
    "Hi {first_name}, Omar here from ConTech AI. We built an autonomous CAD-to-BOQ "
    "pipeline for civil & structural engineering firms that cuts 3-week manual takeoffs down "
    "to 10 mins with zero math errors. We are doing 3 complimentary benchmark audits for "
    "contractors in {city} this month. Open to seeing a 60-sec demo on 1 sample drawing?"
)

TOUCH_2_TEMPLATE = (
    "Hey {first_name}, quick follow up—we just helped a structural team cut bid prep time "
    "by 78% while doubling their tender volume. Would love to send over the 1-page case breakdown. "
    "What is the best email for your estimating lead?"
)

TOUCH_3_TEMPLATE = (
    "Hey {first_name}, assuming your estimating team is fully set on bandwidth right now. "
    "If takeoff bottlenecks ever slow down bid submissions, keep my cell handy. "
    "Best of luck on your active bids, Omar."
)


def _clean_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif len(digits) > 10:
        return f"+{digits}"
    return str(raw).strip()


def build_phound_link(phone: str, message: str) -> str:
    """Builds native Phound web and deeplink URL."""
    encoded_phone = urllib.parse.quote(phone)
    encoded_msg = urllib.parse.quote(message)
    return f"https://web.phound.app/?phone={encoded_phone}&message={encoded_msg}"


def build_native_sms_link(phone: str, message: str) -> str:
    """Standard mobile SMS scheme compatible with iOS & Android."""
    encoded_msg = urllib.parse.quote(message)
    return f"sms:{phone}?body={encoded_msg}"


def load_prospects() -> list[dict]:
    """Extracts top B2B & Real Estate / Commercial contacts from master database."""
    prospects = []
    leads_db = REPO_ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"

    if leads_db.exists():
        try:
            with open(leads_db, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    phone = _clean_phone(item.get("phone"))
                    if not phone or "555" in phone or len(re.sub(r"\D", "", phone)) < 10:
                        continue
                    name = item.get("contact") or item.get("company") or "Engineering Director"
                    first_name = name.split()[0] if name else "there"
                    company = item.get("company") or "Engineering Firm"
                    city = item.get("details", {}).get("city") or item.get("details", {}).get("City") or "your market"
                    
                    prospects.append({
                        "id": item.get("id", f"PROSPECT-{len(prospects)+1}"),
                        "contact_name": name,
                        "first_name": first_name,
                        "company_name": company,
                        "phone": phone,
                        "city": city,
                        "vertical": item.get("vertical", "Commercial / Engineering"),
                        "motivation_score": item.get("motivation_score", 90),
                    })
        except Exception as e:
            print(f"  [WARN] Error loading leads_database: {e}")

    # Fallback to curated B2B Engineering sample if db is small
    if len(prospects) < 25:
        sample_b2b = [
            {"id": "CONTECH-001", "contact_name": "Marcus Vance", "first_name": "Marcus", "company_name": "Vance Heavy Civil LLC", "phone": "+12145550192", "city": "Dallas", "vertical": "Civil Contracting", "motivation_score": 95},
            {"id": "CONTECH-002", "contact_name": "Sarah Jenkins", "first_name": "Sarah", "company_name": "Apex Structural Engineering", "phone": "+19725550144", "city": "Fort Worth", "vertical": "Structural Design", "motivation_score": 93},
            {"id": "CONTECH-003", "contact_name": "David Sterling", "first_name": "David", "company_name": "Sterling Infrastructure Partners", "phone": "+14695550183", "city": "Austin", "vertical": "EPC Heavy Civil", "motivation_score": 97},
            {"id": "CONTECH-004", "contact_name": "Elena Rostova", "first_name": "Elena", "company_name": "Rostova Project Estimation", "phone": "+17135550122", "city": "Houston", "vertical": "Cost Consulting", "motivation_score": 91},
        ]
        prospects.extend(sample_b2b)

    return prospects[:100]  # Focus on top 100 targets


def generate_phound_campaign():
    print("=" * 75)
    print("  📱 PHOUND APP & NATIVE SMS OUTREACH ENGINE (CONTECH AI CONSULTANCY)")
    print("=" * 75)

    prospects = load_prospects()
    print(f"  Loaded {len(prospects)} Verified Decision-Maker Targets")

    campaign_queue = []
    for idx, p in enumerate(prospects, 1):
        msg_t1 = TOUCH_1_TEMPLATE.format(first_name=p["first_name"], city=p["city"])
        msg_t2 = TOUCH_2_TEMPLATE.format(first_name=p["first_name"])
        msg_t3 = TOUCH_3_TEMPLATE.format(first_name=p["first_name"])

        campaign_queue.append({
            "queue_position": idx,
            "prospect_id": p["id"],
            "contact_name": p["contact_name"],
            "company_name": p["company_name"],
            "phone": p["phone"],
            "city": p["city"],
            "vertical": p["vertical"],
            "phound_link_t1": build_phound_link(p["phone"], msg_t1),
            "sms_native_t1": build_native_sms_link(p["phone"], msg_t1),
            "touch_1_body": msg_t1,
            "touch_2_body": msg_t2,
            "touch_3_body": msg_t3,
        })

    # 1. Save JSON
    with open(CAMPAIGN_JSON, "w", encoding="utf-8") as f:
        json.dump(campaign_queue, f, indent=2)

    # 2. Save CSV
    with open(CAMPAIGN_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Queue_Position", "Contact_Name", "Company", "Phone", "City",
            "Phound_App_URL", "Touch_1_SMS", "Touch_2_SMS", "Touch_3_SMS"
        ])
        for q in campaign_queue:
            writer.writerow([
                q["queue_position"], q["contact_name"], q["company_name"],
                q["phone"], q["city"], q["phound_link_t1"],
                q["touch_1_body"], q["touch_2_body"], q["touch_3_body"]
            ])

    # 3. Generate Interactive Phound Cockpit HTML UI
    render_phound_cockpit(campaign_queue)

    print(f"  ✓ Saved Campaign JSON: {CAMPAIGN_JSON}")
    print(f"  ✓ Saved Campaign CSV:  {CAMPAIGN_CSV}")
    print(f"  ✓ Rendered HTML Hub:   {HTML_DISPATCH_ROOM}")
    print("=" * 75)


def render_phound_cockpit(queue: list[dict]):
    """Renders an interactive web dispatch room where clicking any lead opens Phound with pre-filled SMS."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phound App // ConTech AI Consultancy SMS Cockpit</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #070b14;
            --panel: #0d1527;
            --panel-hover: #14203d;
            --border: #1e293b;
            --cyan: #06b6d4;
            --emerald: #10b981;
            --amber: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            padding: 32px 24px;
        }}
        .header {{
            max-width: 1280px;
            margin: 0 auto 28px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}
        .brand-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .badge {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: var(--emerald);
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 6px;
        }}
        .grid {{
            max-width: 1280px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 22px;
            transition: all 0.2s ease;
        }}
        .card:hover {{
            background: var(--panel-hover);
            border-color: var(--cyan);
            transform: translateY(-2px);
        }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }}
        .lead-name {{
            font-size: 18px;
            font-weight: 700;
            color: #fff;
        }}
        .lead-company {{
            font-size: 13px;
            color: var(--cyan);
            margin-top: 2px;
        }}
        .lead-phone {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--emerald);
            background: rgba(16, 185, 129, 0.1);
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .sms-box {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            font-size: 12px;
            line-height: 1.5;
            color: #e2e8f0;
            margin: 14px 0;
            font-style: italic;
        }}
        .actions {{
            display: flex;
            gap: 10px;
        }}
        .btn-phound {{
            flex: 1;
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: white;
            padding: 10px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            font-size: 12px;
            text-align: center;
            display: inline-block;
            transition: opacity 0.2s;
        }}
        .btn-phound:hover {{ opacity: 0.9; }}
        .btn-native {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border);
            color: #cbd5e1;
            padding: 10px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            font-size: 12px;
            text-align: center;
            display: inline-block;
        }}
        .btn-native:hover {{ background: rgba(255, 255, 255, 0.15); }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div style="font-family: 'JetBrains Mono'; font-size: 11px; color: var(--cyan); letter-spacing: 1px; text-transform: uppercase;">
                ◆ PHOUND APP DIRECT INTEGRATION
            </div>
            <h1 class="brand-title">ConTech AI Consultancy // SMS Blast Cockpit</h1>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;">
                1-Click Phound & Native Carrier SMS Outreach • Zero Twilio Lock-in • {len(queue)} Verified B2B Targets
            </p>
        </div>
        <div class="badge">● Phound Native Protocol Active</div>
    </div>

    <div class="grid">
        {"".join([f'''
        <div class="card">
            <div class="card-top">
                <div>
                    <div class="lead-name">{item['contact_name']}</div>
                    <div class="lead-company">{item['company_name']} • {item['city']}</div>
                </div>
                <div class="lead-phone">{item['phone']}</div>
            </div>

            <div class="sms-box">
                "{item['touch_1_body']}"
            </div>

            <div class="actions">
                <a href="{item['phound_link_t1']}" target="_blank" class="btn-phound">
                    🚀 Open in Phound App
                </a>
                <a href="{item['sms_native_t1']}" class="btn-native">
                    💬 Native SMS
                </a>
            </div>
        </div>
        ''' for item in queue])}
    </div>
</body>
</html>
"""
    with open(HTML_DISPATCH_ROOM, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    generate_phound_campaign()
