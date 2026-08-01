"""
Top 10 Highest Profit REAL ESTATE Prospects Only Cold Calling Scripts
======================================================================
Mission: Filters calling targets for Real Estate deals ONLY (Probate, Pre-Foreclosure,
Absentee Landlords, Off-Market Distressed) ranked by expected commission fee ($25k+).
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
INPUT_FILE = LOGS_DIR / 'us_50_deep_prospect_intel.json'
OUTPUT_FILE = LOGS_DIR / 'top_10_real_estate_profit_scripts.md'


def parse_fee(item):
    fee_str = item.get('est_commission', '$0.00').replace('$', '').replace(',', '').replace('.00', '').strip()
    try:
        return float(fee_str)
    except ValueError:
        return 0.0


def generate_real_estate_top_10():
    print("[REAL ESTATE SCRIPT GENERATOR] Filtering 100% Real Estate deals ranked by profit...")

    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter for Real Estate motivation types only (exclude industrial scrap)
    re_targets = [
        item for item in data 
        if item.get('motivation_type') in [
            "Inherited Family Estate (Probate)",
            "Tax Lien & Pre-Foreclosure Opportunity",
            "Out-of-State Absentee Landlord"
        ]
    ]

    # Sort descending by estimated commission
    sorted_re = sorted(re_targets, key=parse_fee, reverse=True)[:10]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 🏠 Top 10 Highest Profit REAL ESTATE Prospects — Custom Calling Scripts\n\n")
        f.write("**100% Off-Market Real Estate Deals Ranked by Expected Commission ($25,500 – $35,500)**\n\n")

        for idx, item in enumerate(sorted_re, 1):
            first_name = item['prospect_name'].split()[0]

            f.write(f"## #{idx}. {item['prospect_name']} — [{item['formatted_phone']}]({item['tel_link']})\n")
            f.write(f"- **Est. Commission Profit**: `{item['est_commission']}` | Property Target: `{item['asking_price']}`\n")
            f.write(f"- **Property Address**: {item['address']} ({item['city']})\n")
            f.write(f"- **Real Estate Motivation**: `{item['motivation_type']}` ({item['equity_status']})\n")
            f.write(f"- **Seller Pain Point**: *{item['pain_point']}*\n\n")

            f.write("### 🎙️ Word-for-Word Real Estate Cold Call Script:\n")
            f.write(f"1. **The Hook (First 5 Seconds)**:\n")
            f.write(f"   > *\"Hi {first_name}! My name is Omar. I'm reaching out directly regarding your property over on {item['address']}. Do you have 60 seconds?\"*\n\n")

            f.write(f"2. **The Discovery Question**:\n")
            f.write(f"   > *\"Great! We are active cash buyers deploying private capital in {item['city'].split(',')[0]} this week. Are you currently open to a clean cash offer to sell the property AS-IS with zero agent commissions?\"*\n\n")

            f.write(f"3. **The Core Real Estate Pitch**:\n")
            f.write(f"   > *\"Here is how we work, {first_name}: {item['tailored_pitch_angle']} We cover 100% of closing costs, pay out in cash, and can close in 7 days so you walk away with {item['asking_price']} net.\"*\n\n")

            f.write(f"4. **Objection Rebuttal**:\n")
            f.write(f"   > *\"{item['objection_rebuttal']}\"*\n\n")

            f.write(f"5. **The Close (Locking Written Offer Today)**:\n")
            f.write(f"   > *\"Let's do this: I'll email over a simple 2-page Cash Purchase Agreement for {item['asking_price']} right now. Take a look today. If everything looks good, we can put $10,000 earnest money into title this afternoon. What's the best email for you?\"*\n\n")

            f.write(f"📞 **Instant Dial Link**: [Dial {item['prospect_name']} Now ({item['formatted_phone']})]({item['tel_link']})\n\n")
            f.write("---\n\n")

    print(f"[REAL ESTATE SCRIPT GENERATOR] SUCCESS: Saved 10 real estate scripts to {OUTPUT_FILE.name}")
    return sorted_re


if __name__ == "__main__":
    generate_real_estate_top_10()
