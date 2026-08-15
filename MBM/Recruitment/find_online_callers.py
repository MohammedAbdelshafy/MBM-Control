"""
Live Online Experienced Cold Caller Sourcing & Direct Outreach Engine
=====================================================================
Finds currently online, experienced cold callers with verified track records
across Reddit, Upwork, OnlineJobs, and Sales Communities.
"""

import os
import sys
import json
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

# Curated Live Platforms & Communities for Immediate Sourcing
ONLINE_SOURCES = [
    {
        "platform": "Reddit r/forhire (Live [For Hire] Cold Callers)",
        "type": "Community / Freelance",
        "search_url": "https://www.reddit.com/r/forhire/search/?q=%22%5BFor+Hire%5D%22+%22cold+call%22+OR+%22appointment+setter%22&sort=new&restrict_sr=1",
        "description": "Active sales reps posting availability today. Filter by 'New' to message callers who posted in the last 24 hours.",
        "badge": "Online Candidates"
    },
    {
        "platform": "Reddit r/CommissionSales (Performance Reps)",
        "type": "Commission Only Reps",
        "search_url": "https://www.reddit.com/r/CommissionSales/search/?q=caller+OR+setter&sort=new&restrict_sr=1",
        "description": "Dedicated commission-only SDRs and closers looking for 10% commission high-ticket offers.",
        "badge": "100% Commission Ready"
    },
    {
        "platform": "Upwork (Filtered: Online Now + Fluent English + >90% JSS)",
        "type": "Vetted Freelance Market",
        "search_url": "https://www.upwork.com/nx/search/talent/?q=real%20estate%20cold%20caller&category_uid=531770282580668420&profile_type=individual&rate=0-15&success_rate=90&english_level=4,5",
        "description": "Experienced Real Estate & B2B Cold Callers with proven billable hours and 5-star call ratings.",
        "badge": "Top Rated / Vetted"
    },
    {
        "platform": "OnlineJobs.ph (Dedicated US-Shift Real Estate Callers)",
        "type": "Direct Hire Callers",
        "search_url": "https://www.onlinejobs.ph/jobseekers/jobsearch?job_title=cold+caller&skill=cold+calling",
        "description": "Specialized real estate cold callers with neutral American English accents trained on Mojo/PropStream.",
        "badge": "High Volume (100+ dials/day)"
    }
]

# Direct Outreach Script to Candidates with Proven Work
EXPERIENCED_CALLER_OUTREACH = {
    "subject": "100-Dial/Day High-Ticket Cold Calling (10% Commission / $500–$3,500 per deal)",
    "body": """Hey [Name],

I saw your profile and background in cold calling and outbound appointment setting.

We run an active deal desk specializing in:
1. Off-Market Real Estate Acquisitions (7-day cash purchase contracts)
2. ConTech AI Consulting ($4,500 - $18,500 B2B engineering retainers)

We are looking for an experienced, native/fluent English caller to run 100 dials/day.

What We Provide:
• 100% Skip-Traced Direct Cell Numbers (Zero 555s, zero bad data)
• Custom Web & Mobile Browser Dialer with built-in Groq AI objection helper
• 10% Commission on every closed deal ($500 to $3,500+ payout per close)
• Fast weekly payouts via Neteller, Bank Wire, PayPal, or Crypto

If you're interested and ready to start dialing this week, send a quick 30-sec voice sample or let me know a good time to connect!"""
}


def update_dashboard_with_live_sources():
    dashboard_file = BASE_DIR / "caller_recruitment_dashboard.html"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MBM CAPITAL // SOURCING LIVE EXPERIENCED COLD CALLERS</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #030712;
            --panel: #0b1329;
            --panel-hover: #14203d;
            --border: #1e293b;
            --cyan: #06b6d4;
            --emerald: #10b981;
            --gold: #f59e0b;
            --orange: #ff4500;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: #f8fafc;
            font-family: 'Inter', sans-serif;
            padding: 32px 24px;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .brand-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #ffffff, var(--cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }}
        @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .card-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .source-item {{
            background: #070e1e;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 14px;
            transition: all 0.2s;
        }}
        .source-item:hover {{
            background: var(--panel-hover);
            border-color: var(--cyan);
        }}
        .source-title {{
            font-size: 16px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .source-desc {{
            font-size: 13px;
            color: #94a3b8;
            margin: 8px 0 14px;
            line-height: 1.4;
        }}
        .badge {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .badge-green {{ background: rgba(16, 185, 129, 0.15); color: var(--emerald); border: 1px solid var(--emerald); }}
        .badge-cyan {{ background: rgba(6, 182, 212, 0.15); color: var(--cyan); border: 1px solid var(--cyan); }}
        .btn {{
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: white;
            padding: 9px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
            text-decoration: none;
            display: inline-block;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .post-box {{
            background: #020617;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #cbd5e1;
            white-space: pre-wrap;
            margin-bottom: 12px;
            max-height: 220px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div style="font-family: 'JetBrains Mono'; font-size: 11px; color: var(--cyan); letter-spacing: 1px; text-transform: uppercase;">
                    ◆ LIVE COLD CALLER SOURCING PIPELINE
                </div>
                <h1 class="brand-title">Hire Experienced 100-Dial/Day Callers</h1>
                <p style="color: #94a3b8; font-size: 13px; margin-top: 4px;">
                    Active Talent Channels • Fluent English Fluency • 10% Commission Per Closed Deal
                </p>
            </div>
            <div>
                <a href="http://localhost:8080" class="btn" style="background: rgba(255,255,255,0.08); border: 1px solid var(--border);">← Back to Hub</a>
            </div>
        </div>

        <div class="grid">
            <div>
                <div class="card">
                    <div class="card-title">
                        <span>🔥 Direct Channels with Callers Currently Online</span>
                    </div>

                    {"".join([f'''
                    <div class="source-item">
                        <div class="source-title">
                            <span>{s['platform']}</span>
                            <span class="badge badge-green">{s['badge']}</span>
                        </div>
                        <div class="source-desc">{s['description']}</div>
                        <a href="{s['search_url']}" target="_blank" class="btn">
                            🚀 View Active Callers on {s['platform'].split()[0]} →
                        </a>
                    </div>
                    ''' for s in ONLINE_SOURCES])}
                </div>

                <div class="card">
                    <div class="card-title">
                        <span>💬 Direct Outreach Message (Copy & Send to Experienced Candidates)</span>
                    </div>
                    <div class="post-box" id="msgText">{EXPERIENCED_CALLER_OUTREACH['body']}</div>
                    <button class="btn" style="background: var(--emerald);" onclick="navigator.clipboard.writeText(document.getElementById('msgText').innerText); alert('Copied Outreach Template!');">
                        📋 Copy Direct Message Template
                    </button>
                </div>
            </div>

            <div>
                <div class="card">
                    <div class="card-title">🎯 The 10% Commission Math</div>
                    <ul style="list-style: none; font-size: 13px; line-height: 2.1; color: #cbd5e1;">
                        <li>📞 <strong>Daily Dials</strong>: 100 Calls / Day</li>
                        <li>💰 <strong>ConTech AI Retainer ($8.5k)</strong>: <span style="color: var(--emerald); font-weight: 700;">$850 Payout</span></li>
                        <li>🏠 <strong>Real Estate Deal ($15k fee)</strong>: <span style="color: var(--emerald); font-weight: 700;">$1,500 Payout</span></li>
                        <li>💎 <strong>Commercial Contract ($30k fee)</strong>: <span style="color: var(--emerald); font-weight: 700;">$3,000 Payout</span></li>
                    </ul>
                </div>

                <div class="card">
                    <div class="card-title">🎙️ Instant English Verification</div>
                    <p style="font-size: 12px; color: #94a3b8; line-height: 1.6; margin-bottom: 12px;">
                        Have candidates send a 30-sec recording via <a href="https://vocaroo.com" target="_blank" style="color: var(--cyan);">Vocaroo</a> reading:
                    </p>
                    <div style="background: rgba(0,0,0,0.4); padding: 10px; border-radius: 6px; font-size: 11px; color: #e2e8f0; font-style: italic;">
                        "Hi John, Omar here from MBM Capital. We're active cash buyers looking to acquire 2 properties this month as-is with 7-day close. Would you be open to a cash offer today?"
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    with open(dashboard_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ Updated {dashboard_file}")


if __name__ == "__main__":
    update_dashboard_with_live_sources()
