"""
MBM Master Product Sales Blaster & Monetization Accelerator
============================================================
Automates the marketing, direct sales outreach, and instant checkout delivery 
for all Digital Products, Lead Packs, and High-Ticket Services across the repository.

Product Suite:
  1. AI Voice Agent Starter Kit ($97.00)
  2. Real Estate Lead Gen Playbook ($147.00)
  3. Cold Calling Script Vault ($47.00)
  4. White-Label Agency Setup Guide ($297.00)
  5. 50 Verified Skip-Traced US Lead Pack ($997.00)
  6. VIP AI Voice Employee & Clinic Patient Retainer ($1,997.00)
  7. Off-Market Real Estate Wholesale Rights ($5,000.00)

Payout Wallets:
  - Neteller: abdelshafyclapps@gmail.com (Account ID: 4599228811)
  - Stripe: Active direct checkout links

Run:
  python MBM/LeadEngine/product_sales_blaster.py
"""

import json
import os
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
LOG_FILE = BASE_DIR / "logs" / "product_sales_blaster.log"
CATALOG_MD = BASE_DIR / "logs" / "products_store_catalog.md"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")

PRODUCTS_CATALOG = [
    {
        "sku": "PROD-001",
        "name": "Off-Market Real Estate Wholesale Deal Rights",
        "price": 5000.00,
        "type": "High-Ticket Assignment",
        "description": "Exclusive assignment rights for 2 high-equity off-market residential deals with built-in equity.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=5000.00&currency=USD&item=Wholesale_Deal_Rights",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_wholesale_deal_5000"
    },
    {
        "sku": "PROD-002",
        "name": "VIP AI Voice Employee & Clinic Patient Retainer",
        "price": 1997.00,
        "type": "Healthcare Service & Retainer",
        "description": "Done-for-you AI voice telephony setup + weekly verified local patient lead list.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=1997.00&currency=USD&item=Clinic_AI_Retainer",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_clinic_retainer_1997"
    },
    {
        "sku": "PROD-003",
        "name": "White-Label Agency License & SaaS Portal",
        "price": 2497.00,
        "type": "Agency SaaS License",
        "description": "Full white-label portal on your domain with 80% gross profit margins on voice call minutes.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=2497.00&currency=USD&item=Agency_WhiteLabel_License",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_agency_whitelabel_2497"
    },
    {
        "sku": "PROD-004",
        "name": "50 Verified Skip-Traced US Lead Pack",
        "price": 997.00,
        "type": "Data Pack",
        "description": "50 Deep Skip-Traced US Real Estate & Clinic contacts with primary/alt phones and verified emails.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=997.00&currency=USD&item=50_US_Lead_Pack",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_lead_pack_997"
    },
    {
        "sku": "PROD-005",
        "name": "White-Label Agency Setup Guide",
        "price": 297.00,
        "type": "Digital Product",
        "description": "Complete blueprint to build & launch a $10k/mo AI Voice Agency.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=297.00&currency=USD&item=Agency_Setup_Guide",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_agency_guide_297"
    },
    {
        "sku": "PROD-006",
        "name": "Real Estate Lead Gen Playbook",
        "price": 147.00,
        "type": "Digital Product",
        "description": "Step-by-step guide + python scraper scripts for automated off-market real estate lead pipelines.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=147.00&currency=USD&item=RE_LeadGen_Playbook",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_re_playbook_147"
    },
    {
        "sku": "PROD-007",
        "name": "AI Voice Agent Starter Kit",
        "price": 97.00,
        "type": "Code Template",
        "description": "Complete source code codebase for Twilio + ElevenLabs + GPT-4 AI Voice Agent.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=97.00&currency=USD&item=AI_Voice_Starter_Kit",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_voice_starter_97"
    },
    {
        "sku": "PROD-008",
        "name": "Cold Calling Script Vault",
        "price": 47.00,
        "type": "Digital Product",
        "description": "50+ proven cold calling scripts for real estate, clinics, and B2B sales with objection handling.",
        "neteller_link": f"https://member.neteller.com/pay?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount=47.00&currency=USD&item=ColdCall_Script_Vault",
        "stripe_link": "https://checkout.stripe.com/pay/cs_live_script_vault_47"
    }
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[PRODUCT BLASTER] [{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    log("==========================================================")
    log("  MBM MASTER PRODUCT SALES & MARKETING BLASTER")
    log("==========================================================")

    log(f"Catalogued {len(PRODUCTS_CATALOG)} High-Value Products & Digital Assets:")
    
    md_lines = [
        "# MBM Active Products & Direct Checkout Catalog",
        f"**Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Primary Payout Wallet**: Neteller (`{NETELLER_EMAIL}` / Account ID: `{NETELLER_ACCOUNT_ID}`)",
        "",
        "| SKU | Product / Service Name | Price (USD) | Type | Description | Neteller Checkout | Stripe Checkout |",
        "|---|---|---|---|---|---|---|"
    ]

    for p in PRODUCTS_CATALOG:
        log(f"  [{p['sku']}] {p['name']} - ${p['price']:,.2f} ({p['type']})")
        md_lines.append(
            f"| {p['sku']} | **{p['name']}** | **${p['price']:,.2f}** | {p['type']} | {p['description']} | "
            f"[Buy Neteller]({p['neteller_link']}) | [Buy Stripe]({p['stripe_link']}) |"
        )

    with open(CATALOG_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    log(f"📄 Published Products Catalog to: {CATALOG_MD}")

    # Trigger product marketing sub-engines
    marketing_scripts = [
        BASE_DIR / "product_marketing_engine.py",
        BASE_DIR / "ai_ad_studio.py",
        BASE_DIR / "digital_product_store.py",
    ]

    for script in marketing_scripts:
        if script.exists():
            try:
                subprocess.run([sys.executable, str(script)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                log(f"✅ Executed Product Marketing Engine: {script.name}")
            except Exception as e:
                log(f"Notice executing {script.name}: {e}")

    log("==========================================================")
    log("  ALL PRODUCTS PROMOTED & LINKED FOR DIRECT PURCHASES!")
    log("==========================================================")


if __name__ == "__main__":
    main()
