"""
Digital Product Store & Passive Income Engine
==============================================
Mission: Create, list, and sell digital products across multiple marketplaces
for passive recurring revenue.

Products:
  1. AI Voice Agent Starter Kit ($47 - $197)
  2. Real Estate Lead Gen Playbook ($97 - $297)
  3. Cold Calling Script Templates ($27 - $67)
  4. White-Label Agency Setup Guide ($197 - $497)
  5. Automation Workflow Templates ($37 - $147)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PRODUCTS_FILE = LOGS_DIR / 'digital_products_catalog.json'
SALES_LOG = LOGS_DIR / 'digital_product_sales.json'


DIGITAL_PRODUCTS = [
    {
        "id": "DP-001",
        "name": "AI Voice Agent Starter Kit",
        "description": "Complete codebase + tutorial for building AI voice agents with Twilio + ElevenLabs + GPT-4. Includes 3 pre-built templates.",
        "price": 97,
        "platforms": ["gumroad", "whop", "lecde"],
        "delivery_format": "ZIP (source code + docs)",
        "estimated_monthly_sales": 20,
        "monthly_revenue_potential": "$1,940",
    },
    {
        "id": "DP-002",
        "name": "Real Estate Lead Gen Playbook",
        "description": "Step-by-step guide to building automated RE lead pipelines. Includes scraper scripts, skip-tracing setup, and outreach templates.",
        "price": 147,
        "platforms": ["gumroad", "whop"],
        "delivery_format": "PDF + Python scripts",
        "estimated_monthly_sales": 15,
        "monthly_revenue_potential": "$2,205",
    },
    {
        "id": "DP-003",
        "name": "Cold Calling Script Vault",
        "description": "50+ proven cold calling scripts for real estate, solar, insurance, and B2B SaaS. Includes objection handling playbooks.",
        "price": 47,
        "platforms": ["gumroad", "etsy", "whop"],
        "delivery_format": "PDF + Google Docs",
        "estimated_monthly_sales": 40,
        "monthly_revenue_potential": "$1,880",
    },
    {
        "id": "DP-004",
        "name": "White-Label AI Agency Blueprint",
        "description": "Complete guide to launching a white-label AI voice agency. Includes pricing models, client acquisition, and billing setup.",
        "price": 297,
        "platforms": ["gumroad", "whop"],
        "delivery_format": "PDF + Video Course",
        "estimated_monthly_sales": 8,
        "monthly_revenue_potential": "$2,376",
    },
    {
        "id": "DP-005",
        "name": "Automation Workflow Templates",
        "description": "25+ ready-to-deploy automation workflows: lead scoring, email sequences, appointment booking, CRM sync.",
        "price": 77,
        "platforms": ["gumroad", "whop"],
        "delivery_format": "JSON configs + Python scripts",
        "estimated_monthly_sales": 25,
        "monthly_revenue_potential": "$1,925",
    },
    {
        "id": "DP-006",
        "name": "Skip Tracing API Access (10K Credits)",
        "description": "Pre-loaded skip tracing API credits for finding phone numbers and emails. Works with any Python/Node.js project.",
        "price": 67,
        "platforms": ["whop"],
        "delivery_format": "API key + documentation",
        "estimated_monthly_sales": 30,
        "monthly_revenue_potential": "$2,010",
    },
    {
        "id": "DP-007",
        "name": "AI Voice Agent Monthly Reseller License",
        "description": "Monthly license to resell our AI voice agent platform. Includes 100 calling credits/month, white-label dashboard, and support.",
        "price": 197,
        "platforms": ["whop"],
        "delivery_format": "SaaS access + API key",
        "estimated_monthly_sales": 10,
        "monthly_revenue_potential": "$1,970",
        "recurring": True,
    },
]


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[DIGITAL STORE] {timestamp} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))


def create_product_catalog():
    """Create and save the product catalog."""
    log("Creating digital product catalog...")
    
    total_monthly = sum(
        p["price"] * p["estimated_monthly_sales"] for p in DIGITAL_PRODUCTS
    )
    
    catalog = {
        "store_name": "Contech AI Digital Store",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_products": len(DIGITAL_PRODUCTS),
        "total_monthly_revenue_potential": f"${total_monthly:,.0f}",
        "products": DIGITAL_PRODUCTS,
    }
    
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2)
    
    log(f"Catalog created: {len(DIGITAL_PRODUCTS)} products, ${total_monthly:,.0f}/mo potential")
    print(json.dumps(catalog, indent=2))
    
    return catalog


def generate_listing_copy(product):
    """Generate marketplace listing copy for a product."""
    return {
        "gumroad": {
            "title": product["name"],
            "description": product["description"],
            "price": f"${product['price']}",
            "tags": product["id"].lower(),
        },
        "whop": {
            "title": product["name"],
            "description": product["description"],
            "price": product["price"],
        },
    }


if __name__ == "__main__":
    create_product_catalog()
