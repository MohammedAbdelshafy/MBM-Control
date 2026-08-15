"""
Reddit Cold Caller & Appointment Setter Sourcing Engine
========================================================
Mission: Recruit fluent English cold callers willing to make 100 dials/day
for a 10% commission on every closed deal ($500 - $3,500 per close).

Target Subreddits:
- r/forhire
- r/remotejobs
- r/sales
- r/coldcalling
- r/WorkOnline
- r/freelance_forhire
- r/hiring

Generates:
1. Formatted Reddit Markdown Submissions for all targeted subreddits
2. Direct Message (DM) Outreach Scripts for active [For Hire] setters
3. 60-Second English Voice Audition Screening Framework
4. Interactive Recruitment & Applicant Tracking Dashboard (HTML)
"""

import os
import sys
import json
import csv
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
OUTPUTS_DIR = BASE_DIR / "outreach_packs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

RECRUITMENT_MD = OUTPUTS_DIR / "REDDIT_CALLER_RECRUITMENT_PACK.md"
RECRUITMENT_JSON = OUTPUTS_DIR / "reddit_recruitment_posts.json"
APPLICANT_DASHBOARD = BASE_DIR / "caller_recruitment_dashboard.html"


# ── Reddit Job Submissions ───────────────────────────────────────────────────

REDDIT_POSTS = [
    {
        "subreddit": "r/forhire",
        "title": "[Hiring] High-Ticket B2B & Real Estate Cold Callers (100 Dials/Day) — 10% Commission Per Close ($500 - $3,500/deal), Pre-Verified Leads & Full AI Dialer Provided",
        "flair": "Hiring",
        "compensation": "10% Commission per closed deal ($500 to $3,500+ / close). Average expected: $2,000 - $6,000+/mo for high-volume callers.",
        "content": """### [Hiring] High-Ticket Cold Callers / Appointment Setters (100 Dials/Day)

**Agency**: MBM Capital & ConTech AI  
**Role**: Remote Outbound Sales Representative / Appointment Setter  
**Compensation**: **10% Commission on every closed deal** ($500 to $3,500+ per deal depending on contract size). Fast payouts via Neteller, Bank Wire, PayPal, or Crypto.  
**Hours / Volume**: Flexible / Remote — Minimum **100 calls/day**.

---

#### 🚀 What We Do & What You Will Be Calling:
We operate two high-converting acquisition tracks:
1. **Real Estate Off-Market Deals**: Calling motivated property owners and cash buyers with 7-day cash purchase contracts (Avg commission: $1,000 - $3,500 per closed deal).
2. **ConTech AI Consultancy**: Reaching out to civil engineering & structural contracting executives for AI Takeoff & Estimation audits (Avg retainer: $4,500 - $18,500 $\rightarrow$ **$450 - $1,850 commission per client**).

---

#### ✨ What We Provide to Make You Win:
* 📞 **Custom High-Speed Web & Mobile Dialer**: Pre-loaded with 100% skip-traced, verified decision-maker cell numbers (Zero fake numbers, zero 555s).
* 📜 **Battle-Tested Word-for-Word Scripts**: Proven 4-beat pattern-interrupt scripts and live objection cheat sheets.
* 🤖 **Realtime AI Objection Copilot**: Built into the screen to give you instant comeback answers while on live calls.

---

#### 🎯 Requirements:
* **Fluent English Language Skills** (Clear, confident, professional communication).
* **Work Ethic**: Disciplined to hit 100 dials per day.
* **Quiet Calling Environment** with a good headset and stable internet.

---

#### 🎙️ How to Apply (Fast-Track 60-Second Voice Audition):
To ensure great English fluency and tone, please DM me or message our Telegram `@Kyle500_bot` with:
1. Your Name & Location.
2. A 30-to-60 second voice note (or Loom/Vocaroo link) reading this sample opener:
> *"Hi John, my name is [Your Name] from MBM Capital. I know I’m catching you out of the blue, but I’m calling specifically about your property on Main Street. We’re active private buyers looking to purchase 2 more properties in the area this month—we buy 100% as-is for cash, pay all closing costs, and close in 7 days. If the price and terms make sense, would you consider a cash offer today?"*

Positions open immediately. We onboard and provide dialer access on the same day!"""
    },
    {
        "subreddit": "r/remotejobs",
        "title": "[Remote Work] Commission-Only Cold Callers Wanted (100 Dials/Day) — Earn 10% on $5k-$25k B2B & Real Estate Deals ($500-$2,500/close)",
        "flair": "Job Opportunity",
        "compensation": "10% Uncapped Commission ($500 - $2,500+ per closed client)",
        "content": """Looking for hungry, self-driven cold callers who want high commission upside.

**The Offer:**
- 10% commission on every closed deal ($500 - $2,500+ per deal).
- We provide the complete leads database (100% verified owner numbers), scripts, and browser dialer.
- 100 dials per day expectation.
- High-intent niches: Real estate off-market sellers & ConTech engineering consultancy.

**Who this is for:**
- Fluent English speakers who love outbound prospecting.
- Callers who want to work remotely on their own schedule.

**How to Apply:** Send a short voice recording (Vocaroo / Loom / Telegram) introducing yourself and why you're a fit for cold calling."""
    },
    {
        "subreddit": "r/sales",
        "title": "Hiring 100-dial/day Commission Closers & Setters — 10% spread on high-ticket B2B & wholesale contracts",
        "flair": "Career / Hiring",
        "compensation": "10% Gross Commission per close",
        "content": """We are scaling our outbound deal desk and bringing on 3 performance-based cold callers.

**Deals you are booking/closing:**
- $4,500 to $18,500 ConTech AI estimation consulting retainers.
- $10,000 to $35,000 real estate wholesale assignment contracts.

**Your cut:** 10% flat ($450 to $3,500 per closed deal).

Full custom dialer, verified direct cell numbers, and objection copilot provided. DM with your experience or a 30-sec voice sample."""
    }
]


# ── Direct Message (DM) Outreach Scripts for Active Job Seekers ──────────────

DIRECT_DM_SCRIPTS = [
    {
        "angle": "For active [For Hire] Sales Reps on r/forhire",
        "subject": "100-Dial/Day Cold Calling Role — 10% Commission ($500-$2,500/close)",
        "body": """Hey [Username], saw your [For Hire] post regarding outbound sales / appointment setting.

We're currently bringing on hungry cold callers for our Real Estate and ConTech AI Consultancy deal desk. 

Quick breakdown:
• 10% commission on every closed deal ($500 - $3,500 per close).
• We provide our custom Web & Mobile Dialer with 100% verified direct owner cell numbers (zero bad numbers).
• Full proven scripts + live AI objection copilot on screen.
• Volume: 100 dials/day.

If you have great English fluency and want high uncapped commission upside, shoot me a 30-second audio note introducing yourself and we can get you onboarded onto the dialer today!"""
    },
    {
        "angle": "Follow-Up / Fast Audition Request",
        "subject": "Audition script for MBM Caller Role",
        "body": """Awesome to connect! To fast-track your onboarding, record a quick 30-sec clip on https://vocaroo.com (or Telegram) reading this sample hook:

"Hi John, Omar here from MBM Capital. We're active cash buyers looking to purchase 2 more properties in the area this month—we buy 100% as-is, cover all closing costs, and close in 7 days with zero realtor fees. Would you be open to a direct cash offer today?"

Once I hear your tone, I'll send over your live dialer login credentials."""
    }
]


def generate_recruitment_package():
    print("=" * 75)
    print("  🚀 REDDIT COLD CALLER SOURCING & OUTREACH SUITE")
    print("=" * 75)

    # 1. Save JSON
    with open(RECRUITMENT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_subreddits": ["r/forhire", "r/remotejobs", "r/sales", "r/coldcalling", "r/WorkOnline"],
            "reddit_posts": REDDIT_POSTS,
            "direct_dm_scripts": DIRECT_DM_SCRIPTS
        }, f, indent=2)

    # 2. Save Markdown Playbook
    with open(RECRUITMENT_MD, "w", encoding="utf-8") as f:
        f.write("# 🎙️ Reddit Cold Caller Recruitment & Commission Outreach Playbook\n\n")
        f.write(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write("## 🎯 Target Compensation & Deal Structure\n")
        f.write("- **Volume Requirement**: 100 Dials / Day\n")
        f.write("- **Commission Structure**: **10% Gross Payout per Closed Deal**\n")
        f.write("  - ConTech AI Retainers ($4,500 – $18,500) $\\rightarrow$ **$450 – $1,850 Payout**\n")
        f.write("  - Real Estate Wholesale Contracts ($10,000 – $35,000) $\\rightarrow$ **$1,000 – $3,500 Payout**\n")
        f.write("- **Tools Provided**: Pre-loaded MBM Dialer, Verified Leads, AI Objection Copilot\n\n")
        f.write("---\n\n")

        f.write("## 📋 Ready-to-Post Reddit Submissions\n\n")
        for p in REDDIT_POSTS:
            f.write(f"### Subreddit: `{p['subreddit']}`\n")
            f.write(f"**Title**: `{p['title']}`\n\n")
            f.write(f"```markdown\n{p['content']}\n```\n\n---\n\n")

        f.write("## 💬 Direct DM Scripts for [For Hire] Sales Candidates\n\n")
        for dm in DIRECT_DM_SCRIPTS:
            f.write(f"### Angle: {dm['angle']}\n")
            f.write(f"**Subject**: `{dm['subject']}`\n\n")
            f.write(f"```text\n{dm['body']}\n```\n\n---\n\n")

    # 3. Generate Recruitment Dashboard HTML
    render_recruitment_dashboard()

    print(f"  ✓ Saved Recruitment JSON: {RECRUITMENT_JSON}")
    print(f"  ✓ Saved Recruitment MD:   {RECRUITMENT_MD}")
    print(f"  ✓ Rendered Applicant Hub: {APPLICANT_DASHBOARD}")
    print("=" * 75)


def render_recruitment_dashboard():
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MBM CAPITAL // COLD CALLER RECRUITMENT COMMAND CENTER</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #030712;
            --panel: #0b1329;
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
            background: linear-gradient(135deg, #ffffff, var(--orange));
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
            gap: 8px;
        }}
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
            max-height: 250px;
            overflow-y: auto;
        }}
        .btn {{
            background: var(--orange);
            color: white;
            padding: 10px 18px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .badge-reddit {{
            background: rgba(255, 69, 0, 0.15);
            border: 1px solid var(--orange);
            color: var(--orange);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        .applicant-row {{
            background: #070e1e;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .accent-pill {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--emerald);
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div style="font-family: 'JetBrains Mono'; font-size: 11px; color: var(--orange); letter-spacing: 1px; text-transform: uppercase;">
                    ◆ REDDIT OUTREACH & HIRING ENGINE
                </div>
                <h1 class="brand-title">Cold Caller Sourcing Command Center</h1>
                <p style="color: #94a3b8; font-size: 13px; margin-top: 4px;">
                    100 Dials/Day Commission Closers • 10% Spread on All Closed Deals • English Fluency Screening
                </p>
            </div>
            <div>
                <a href="https://www.reddit.com/r/forhire/submit" target="_blank" class="btn">Post to r/forhire</a>
                <a href="https://www.reddit.com/r/remotejobs/submit" target="_blank" class="btn" style="background: #2563eb;">Post to r/remotejobs</a>
            </div>
        </div>

        <div class="grid">
            <div>
                <div class="card">
                    <div class="card-title">
                        <span>📝 Live Recruitment Post Template (Ready to Copy)</span>
                        <span class="badge-reddit">r/forhire</span>
                    </div>
                    <div class="post-box" id="postText">{REDDIT_POSTS[0]['content']}</div>
                    <button class="btn" onclick="navigator.clipboard.writeText(document.getElementById('postText').innerText); alert('Copied Reddit Post to clipboard!');">
                        📋 Copy Reddit Submission Text
                    </button>
                </div>

                <div class="card">
                    <div class="card-title">
                        <span>💬 Direct DM Script for [For Hire] Cold Callers</span>
                    </div>
                    <div class="post-box" id="dmText">{DIRECT_DM_SCRIPTS[0]['body']}</div>
                    <button class="btn" style="background: #0284c7;" onclick="navigator.clipboard.writeText(document.getElementById('dmText').innerText); alert('Copied DM Template to clipboard!');">
                        📋 Copy DM Template
                    </button>
                </div>
            </div>

            <div>
                <div class="card">
                    <div class="card-title">🎯 Compensation & Quotas</div>
                    <ul style="list-style: none; font-size: 13px; line-height: 2; color: #cbd5e1;">
                        <li>📞 <strong>Daily Dials</strong>: 100 Calls / Day</li>
                        <li>💰 <strong>Commission</strong>: 10% per close</li>
                        <li>💵 <strong>Avg Deal Payout</strong>: $500 – $3,500+</li>
                        <li>⚡ <strong>Leads Supplied</strong>: 712 verified numbers</li>
                        <li>🤖 <strong>AI Copilot</strong>: Groq Llama 3.3 70B</li>
                        <li>💳 <strong>Payout Rail</strong>: Neteller / Wire / Crypto</li>
                    </ul>
                </div>

                <div class="card">
                    <div class="card-title">🎙️ 3-Step Screening Gate</div>
                    <ol style="font-size: 12px; line-height: 1.8; color: #cbd5e1; padding-left: 18px;">
                        <li><strong>Voice Note Audition</strong>: 30-sec Vocaroo / Loom reading pattern-interrupt script.</li>
                        <li><strong>English Tone Check</strong>: Natural cadence, confident tone, clear pronunciation.</li>
                        <li><strong>Dialer Sandbox</strong>: Grant credentials to <code>http://localhost:8080/dialer</code>.</li>
                    </ol>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    with open(APPLICANT_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    generate_recruitment_package()
