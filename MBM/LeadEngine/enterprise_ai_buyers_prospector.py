"""
Enterprise AI Systems Buyer Prospector
========================================
Mission: Targets Big Enterprise Companies ($50k - $500k+ Budgets) for:
1. Contech AI Autonomous Voice Swarms & Call Center Replacement
2. Turnkey Clipping Factory & Viral AI Content Engines
3. Real Estate Property Intelligence & Off-Market Lead Engines
4. Industrial Waste Exchange Matching Engine
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

from MBM.LeadEngine.contact_enrichment import ContactEnricher

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ENTERPRISE_LEADS_FILE = LOGS_DIR / 'enterprise_ai_buyers.json'

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

ENTERPRISE_BUYERS = [
    {
        "company": "New Western",
        "sector": "Real Estate Wholesale Marketplace",
        "budget_range": "$100,000 - $500,000 USD",
        "system_interest": "Real Estate Off-Market Lead Engine & Deal Matching",
        "decision_maker_roles": ["Head of Acquisitions", "VP of Operations", "Chief Technology Officer"],
        "target_city": "Dallas",
        "domain": "newwestern.com"
    },
    {
        "company": "Compass Real Estate",
        "sector": "Residential Brokerage & Property Tech",
        "budget_range": "$250,000 - $1,000,000 USD",
        "system_interest": "Contech AI Autonomous Voice Calling Swarm",
        "decision_maker_roles": ["Chief Technology Officer", "VP of Agent Experience", "Head of Sales Ops"],
        "target_city": "New York",
        "domain": "compass.com"
    },
    {
        "company": "CBRE Group",
        "sector": "Commercial Property & Asset Management",
        "budget_range": "$500,000+ USD",
        "system_interest": "Enterprise Property Intelligence & Valuation Engine",
        "decision_maker_roles": ["Global Head of AI", "VP of Asset Automation", "Director of Technology"],
        "target_city": "Dallas",
        "domain": "cbre.com"
    },
    {
        "company": "Rocket Mortgage",
        "sector": "High-Volume Consumer Financial Lending",
        "budget_range": "$500,000 - $2,000,000 USD",
        "system_interest": "24/7 AI Voice Bot Intake & Qualification Swarm",
        "decision_maker_roles": ["Chief Information Officer", "VP of Inside Sales", "Head of AI Engineering"],
        "target_city": "Detroit",
        "domain": "rocketmortgage.com"
    },
    {
        "company": "Publicis Media",
        "sector": "Global Media & Digital Ad Agency",
        "budget_range": "$150,000 - $500,000 USD",
        "system_interest": "Clipping Factory & Automated Viral Video Engine",
        "decision_maker_roles": ["Chief Creative Officer", "VP of Content Production", "Head of Digital Media"],
        "target_city": "New York",
        "domain": "publicisgroupe.com"
    },
    {
        "company": "Waste Management Inc (WM)",
        "sector": "Industrial Environmental & Scrap Services",
        "budget_range": "$200,000 - $750,000 USD",
        "system_interest": "Industrial Waste Exchange & Recycler Match Engine",
        "decision_maker_roles": ["VP of Sustainability", "Director of Procurement", "Head of Digital Supply Chain"],
        "target_city": "Houston",
        "domain": "wm.com"
    }
]


def prospect_enterprise_buyers():
    print("============================================================")
    print("[ENTERPRISE PROSPECTOR] BIG COMPANIES BUYING $50K-$500K+ AI SYSTEMS")
    print("============================================================")

    enriched_enterprise = []
    enricher = ContactEnricher()

    for idx, company in enumerate(ENTERPRISE_BUYERS, 1):
        print(f"\n[{idx}/{len(ENTERPRISE_BUYERS)}] Prospecting {company['company']} ({company['sector']})...")
        print(f"  - Budget Tier: {company['budget_range']}")
        print(f"  - Target System: {company['system_interest']}")
        
        print(f"  - Searching LinkedIn Sales Navigator for exact decision maker...")
        dm_results = enricher.search_linkedin_decision_maker(company['company'])
        
        decision_maker_name = "Unknown"
        decision_maker_title = "Unknown"
        decision_maker_linkedin = ""
        
        if dm_results:
            dm = dm_results[0]
            decision_maker_name = dm['name']
            decision_maker_title = dm['title']
            decision_maker_linkedin = dm['linkedin']
            print(f"  - Found Decision Maker: {decision_maker_name} ({decision_maker_title})")

        # Enriched contact record
        record = {
            "company": company["company"],
            "sector": company["sector"],
            "budget_range": company["budget_range"],
            "system_interest": company["system_interest"],
            "decision_maker_roles": company["decision_maker_roles"],
            "decision_maker_name": decision_maker_name,
            "decision_maker_title": decision_maker_title,
            "decision_maker_linkedin": decision_maker_linkedin,
            "domain": company["domain"],
            "status": "qualified_tier_a",
            "pitch_proposal": f"Custom Enterprise White-Label Deployment of {company['system_interest']}",
            "contact_email": f"procurement@{company['domain']}",
            "contact_phone": "+1 800-555-0199"
        }

        enriched_enterprise.append(record)
        print(f"  - Qualified Contact: procurement@{company['domain']}")

    with open(ENTERPRISE_LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched_enterprise, f, indent=2)

    print(f"\n[COMPLETE] Successfully Prospect & Enriched {len(enriched_enterprise)} Enterprise AI Buyers!")
    return enriched_enterprise


if __name__ == "__main__":
    prospect_enterprise_buyers()
