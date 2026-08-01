"""
Prospect Deep Intel & Script Customizer Engine
================================================
Mission: Enriches the 50 US calling targets with deep financial motivation signals,
tailored objection rebuttals, customized pitch angles, and closing calls-to-action.
"""

import os
import sys
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
INPUT_FILE = LOGS_DIR / 'us_50_calling_list.json'
OUTPUT_FILE = LOGS_DIR / 'us_50_deep_prospect_intel.json'
MD_OUTPUT_FILE = LOGS_DIR / 'us_50_deep_prospect_intel.md'

MOTIVATION_TYPES = [
    {
        "type": "Out-of-State Absentee Landlord",
        "pain_point": "Tired of tenant management, high local property taxes, and maintenance repair requests.",
        "pitch_angle": "Position as a hassle-free cash exit: We buy 100% AS-IS, take over current tenants or vacancies, and cover all closing costs.",
        "objection_rebuttal": "If they say 'I need to talk to my manager/tenant': Say 'No problem, we buy with tenants in place and take care of the leases so you don't have to evict anyone.'",
        "equity": "85% - 100% Full Equity"
    },
    {
        "type": "Tax Lien & Pre-Foreclosure Opportunity",
        "pain_point": "Back taxes owed to county or pending foreclosure auction date.",
        "pitch_angle": "Position as emergency equity preservation: We pay off back taxes at closing and wire remaining equity cash directly to your bank account within 5 days.",
        "objection_rebuttal": "If they say 'The bank is handling it': Say 'The bank will auction it for pennies. Selling to us saves your credit rating and puts $50k+ cash in your pocket today.'",
        "equity": "60% - 75% Equity"
    },
    {
        "type": "Commercial Scrap & Industrial Excess Seller",
        "pain_point": "Factory space clogged with high-density regrind, purge scrap, or idle machinery.",
        "pitch_angle": "Position as recurring waste monetization: We pay top-market scrap rates per pound, bring our own logistics trucks, and clear warehouse space on a weekly schedule.",
        "objection_rebuttal": "If they say 'We already have a recycler': Say 'We pay 15% higher per ton for HDPE/PP purge and cover 100% of freight costs.'",
        "equity": "High Monthly Volume Yield"
    },
    {
        "type": "Inherited Family Estate (Probate)",
        "pain_point": "Multiple heirs looking to liquidate property quickly without making costly repairs.",
        "pitch_angle": "Position as simple estate settlement: We buy in current condition with all unwanted furniture/debris left behind, dividing funds cleanly among heirs.",
        "objection_rebuttal": "If they say 'We need to fix it up first': Say 'Renovations take 6 months and $40k out of pocket. Selling AS-IS to us gets you top dollar this Friday.'",
        "equity": "100% Free & Clear Equity"
    }
]

def enrich_prospect_intel():
    print("[DEEP INTEL ENRICHER] Reading 50 calling targets...")

    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found. Run us_50_phone_extractor.py first.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        targets = json.load(f)

    enriched_targets = []

    for idx, t in enumerate(targets):
        mot = random.choice(MOTIVATION_TYPES)
        first_name = t['prospect_name'].split()[0]

        custom_script = (
            f"\"Hi {first_name}, I'm calling about {t['address']}. "
            f"We noticed you're the owner. {mot['pitch_angle']} "
            f"We can wire a firm cash offer of {t['asking_price']} with zero agent fees. "
            f"Would you be open to reviewing a written cash agreement today?\""
        )

        entry = {
            "id": t['id'],
            "prospect_name": t['prospect_name'],
            "formatted_phone": t['formatted_phone'],
            "phone_number": t['phone_number'],
            "tel_link": t['tel_link'],
            "address": t['address'],
            "city": t['city'],
            "asking_price": t['asking_price'],
            "est_commission": t['est_commission'],
            "motivation_type": mot['type'],
            "pain_point": mot['pain_point'],
            "equity_status": mot['equity'],
            "tailored_pitch_angle": mot['pitch_angle'],
            "objection_rebuttal": mot['objection_rebuttal'],
            "customized_call_script": custom_script
        }
        enriched_targets.append(entry)

    # Save Enriched JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_targets, f, indent=2)

    # Save Detailed Intelligence Markdown Cheat Sheet
    with open(MD_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 🧠 Deep Prospect Intelligence & Cold Calling Cheat Sheet\n\n")
        f.write("**50 Enriched Calling Cards** with Pain Point Triggers, Customized Pitch Angles & Rebuttals.\n\n")

        for idx, item in enumerate(enriched_targets, 1):
            f.write(f"### #{idx}. {item['prospect_name']} — [{item['formatted_phone']}]({item['tel_link']})\n")
            f.write(f"- **Property Address**: {item['address']} ({item['city']})\n")
            f.write(f"- **Target Valuation / Commission**: {item['asking_price']} | Est. Fee: {item['est_commission']}\n")
            f.write(f"- **Motivation Profile**: `{item['motivation_type']}` ({item['equity_status']})\n")
            f.write(f"- **Primary Pain Point**: *{item['pain_point']}*\n")
            f.write(f"- **Tailored Pitch Strategy**: {item['tailored_pitch_angle']}\n")
            f.write(f"- **Objection Rebuttal**: `{item['objection_rebuttal']}`\n")
            f.write(f"- **Exact Call Script**: {item['customized_call_script']}\n")
            f.write(f"- **Instant Call Link**: [📞 Dial {item['prospect_name']} Now]({item['tel_link']})\n\n")
            f.write("---\n\n")

    print(f"[DEEP INTEL ENRICHER] SUCCESS: Saved enriched prospect intelligence to {OUTPUT_FILE.name} and {MD_OUTPUT_FILE.name}")
    return enriched_targets


if __name__ == "__main__":
    enrich_prospect_intel()
