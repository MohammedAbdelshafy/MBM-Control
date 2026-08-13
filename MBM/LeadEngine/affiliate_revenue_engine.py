"""
Affiliate Marketing & Referral Revenue Engine
==============================================
Mission: Earn commissions by promoting relevant SaaS tools and services
to our existing client base and email list.

Affiliate Programs:
  1. Twilio ($100 per referral)
  2. ElevenLabs (20% recurring)
  3. GoHighLevel ($500 per referral)
  4. Vapi.ai (15% recurring)
  5. Retell.ai (10% recurring)
  6. Supabase ($50 per referral)
  7. Railway ($50 per referral)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

AFFILIATE_FILE = LOGS_DIR / 'affiliate_programs.json'
AFFILIATE_LOG = LOGS_DIR / 'affiliate_revenue_log.json'


AFFILIATE_PROGRAMS = [
    {
        "program": "Twilio",
        "type": "per_referral",
        "commission": 100,
        "cookie_days": 30,
        "affiliate_url": "https://www.twilio.com/partners",
        "relevance": "Core infrastructure for our AI voice agents",
        "monthly_referral_potential": 20,
        "monthly_revenue_potential": "$2,000",
    },
    {
        "program": "ElevenLabs",
        "type": "recurring",
        "commission_pct": 20,
        "cookie_days": 90,
        "affiliate_url": "https://elevenlabs.io/affiliates",
        "relevance": "Voice cloning for our AI agents",
        "monthly_referral_potential": 15,
        "monthly_revenue_potential": "$1,500",
    },
    {
        "program": "GoHighLevel",
        "type": "per_referral",
        "commission": 500,
        "cookie_days": 30,
        "affiliate_url": "https://www.gohighlevel.com/affiliates",
        "relevance": "CRM integration for our agency clients",
        "monthly_referral_potential": 10,
        "monthly_revenue_potential": "$5,000",
    },
    {
        "program": "Vapi.ai",
        "type": "recurring",
        "commission_pct": 15,
        "cookie_days": 60,
        "affiliate_url": "https://vapi.ai/partners",
        "relevance": "AI voice platform alternative",
        "monthly_referral_potential": 12,
        "monthly_revenue_potential": "$1,800",
    },
    {
        "program": "Retell.ai",
        "type": "recurring",
        "commission_pct": 10,
        "cookie_days": 30,
        "affiliate_url": "https://www.retellai.com/partners",
        "relevance": "AI voice agent platform",
        "monthly_referral_potential": 8,
        "monthly_revenue_potential": "$800",
    },
    {
        "program": "Supabase",
        "type": "per_referral",
        "commission": 50,
        "cookie_days": 30,
        "affiliate_url": "https://supabase.com/partners",
        "relevance": "Backend for our lead pipeline",
        "monthly_referral_potential": 25,
        "monthly_revenue_potential": "$1,250",
    },
    {
        "program": "Railway",
        "type": "recurring",
        "commission_pct": 15,
        "cookie_days": 30,
        "affiliate_url": "https://railway.app/affiliates",
        "relevance": "Deployment platform for client projects",
        "monthly_referral_potential": 10,
        "monthly_revenue_potential": "$750",
    },
]


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[AFFILIATE ENGINE] {timestamp} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))


def setup_affiliate_programs():
    """Initialize affiliate program tracking."""
    log("Setting up affiliate marketing programs...")
    
    with open(AFFILIATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(AFFILIATE_PROGRAMS, f, indent=2)
    
    total_monthly = sum(
        p.get("commission", 0) * p.get("monthly_referral_potential", 0)
        if p["type"] == "per_referral"
        else p.get("monthly_referral_potential", 0) * 100  # estimate
        for p in AFFILIATE_PROGRAMS
    )
    
    log(f"Tracked {len(AFFILIATE_PROGRAMS)} affiliate programs")
    print(json.dumps({
        "programs": len(AFFILIATE_PROGRAMS),
        "total_monthly_potential": f"${total_monthly:,.0f}",
    }, indent=2))
    
    return AFFILIATE_PROGRAMS


if __name__ == "__main__":
    setup_affiliate_programs()
