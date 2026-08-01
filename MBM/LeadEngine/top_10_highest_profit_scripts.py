"""
Top 10 Highest Profit Prospects Cold Calling Scripts Generator
===============================================================
Mission: Ranks all calling targets by estimated commission fee and generates
10 custom word-for-word high-ticket cold calling scripts for the highest-profit deals.
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
INPUT_FILE = LOGS_DIR / 'us_50_deep_prospect_intel.json'
OUTPUT_FILE = LOGS_DIR / 'top_10_highest_profit_scripts.md'


def parse_fee(item):
    fee_str = item.get('est_commission', '$0.00').replace('$', '').replace(',', '').replace('.00', '').strip()
    try:
        return float(fee_str)
    except ValueError:
        return 0.0


def generate_top_10_scripts():
    print("[TOP 10 SCRIPT GENERATOR] Ranking prospects by highest commission profit...")

    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Sort descending by estimated commission
    sorted_prospects = sorted(data, key=parse_fee, reverse=True)[:10]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 🏆 Top 10 Highest Profit Prospects — Custom Cold Calling Scripts\n\n")
        f.write("**Ranked by Expected Commission Fee ($25,500 – $35,500)**\n\n")

        for idx, item in enumerate(sorted_prospects, 1):
            first_name = item['prospect_name'].split()[0]

            f.write(f"## #{idx}. {item['prospect_name']} — [{item['formatted_phone']}]({item['tel_link']})\n")
            f.write(f"- **Est. Commission Profit**: `{item['est_commission']}` | Property Target: `{item['asking_price']}`\n")
            f.write(f"- **Address**: {item['address']} ({item['city']})\n")
            f.write(f"- **Motivation Profile**: `{item['motivation_type']}` ({item['equity_status']})\n")
            f.write(f"- **Primary Pain Point**: *{item['pain_point']}*\n\n")

            f.write("### 🎙️ Word-for-Word Phone Script:\n")
            f.write(f"1. **The Hook (First 5 Seconds)**:\n")
            f.write(f"   > *\"Hi {first_name}! My name is Omar. I'm reaching out directly regarding your property over on {item['address']}. Do you have 60 seconds?\"*\n\n")

            f.write(f"2. **The Discovery Question**:\n")
            f.write(f"   > *\"Great! We are active cash buyers deploying capital in {item['city'].split(',')[0]} this week. We noticed the property fits our off-market criteria. Are you currently open to a firm cash offer to sell AS-IS with zero agent commissions?\"*\n\n")

            f.write(f"3. **The Core Pitch ({item['motivation_type']})**:\n")
            f.write(f"   > *\"Here is how we work, {first_name}: {item['tailored_pitch_angle']} We can wire a firm cash offer of {item['asking_price']} with zero agent fees and close in 7 days.\"*\n\n")

            f.write(f"4. **Objection Rebuttal**:\n")
            f.write(f"   > *\"{item['objection_rebuttal']}\"*\n\n")

            f.write(f"5. **The Close (Locking Agreement Today)**:\n")
            f.write(f"   > *\"Let's do this: I'll email over a simple 2-page Cash Agreement for {item['asking_price']} right now. Take a look today. If everything looks good, we can deposit $10,000 earnest money into title this afternoon. What's the best email for you?\"*\n\n")

            f.write(f"📞 **Instant Dial Link**: [Dial {item['prospect_name']} Now ({item['formatted_phone']})]({item['tel_link']})\n\n")
            f.write("---\n\n")

    print(f"[TOP 10 SCRIPT GENERATOR] SUCCESS: Saved top 10 profit scripts to {OUTPUT_FILE.name}")
    return sorted_prospects


if __name__ == "__main__":
    generate_top_10_scripts()
