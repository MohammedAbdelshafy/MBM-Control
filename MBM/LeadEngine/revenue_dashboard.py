"""
Unified Revenue Dashboard & Morning Briefing
=============================================
Mission: Aggregate all revenue streams, calculate projections, and generate
a daily morning briefing showing total money-making capacity.

Revenue Streams Tracked:
  1. Lead Pipeline (real estate deals)
  2. Upwork/Fiverr freelancing
  3. Digital product sales
  4. B2B client retainers
  5. Affiliate commissions
  6. Voice agency billing
  7. Whop subscriptions
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DASHBOARD_FILE = LOGS_DIR / 'revenue_dashboard.json'
BRIEFING_FILE = LOGS_DIR / 'morning_briefing.md'


REVENUE_STREAMS = [
    {
        "stream": "Real Estate Deals",
        "source": "revenue_seeker.py",
        "type": "commission",
        "avg_deal_value": 15000,
        "monthly_deals_target": 5,
        "monthly_revenue_target": 75000,
        "current_status": "32 leads in pipeline",
    },
    {
        "stream": "Upwork/Fiverr Projects",
        "source": "upwork_monetization_hunter.py + fiverr_revenue_engine.py",
        "type": "project",
        "avg_project_value": 5000,
        "monthly_projects_target": 4,
        "monthly_revenue_target": 20000,
        "current_status": "3 proposals queued",
    },
    {
        "stream": "Digital Products",
        "source": "digital_product_store.py",
        "type": "passive",
        "avg_product_price": 120,
        "monthly_sales_target": 100,
        "monthly_revenue_target": 12000,
        "current_status": "7 products cataloged",
    },
    {
        "stream": "B2B Client Retainers",
        "source": "b2b_outreach_engine.py",
        "type": "recurring",
        "avg_retainer": 2000,
        "monthly_clients_target": 10,
        "monthly_revenue_target": 20000,
        "current_status": "4 segments targeted",
    },
    {
        "stream": "Affiliate Commissions",
        "source": "affiliate_revenue_engine.py",
        "type": "recurring",
        "avg_commission": 150,
        "monthly_referrals_target": 50,
        "monthly_revenue_target": 7500,
        "current_status": "7 programs tracked",
    },
    {
        "stream": "Voice Agency Billing",
        "source": "voice_agency_enhancer.py",
        "type": "recurring",
        "avg_client_value": 1500,
        "monthly_clients_target": 20,
        "monthly_revenue_target": 30000,
        "current_status": "3 bot templates ready",
    },
    {
        "stream": "Whop Subscriptions",
        "source": "whop_monetize.py",
        "type": "recurring",
        "avg_subscription": 497,
        "monthly_subscribers_target": 10,
        "monthly_revenue_target": 4970,
        "current_status": "Account being set up",
    },
]


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[REVENUE DASHBOARD] {timestamp} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))


def generate_dashboard():
    """Generate unified revenue dashboard."""
    log("=== UNIFIED REVENUE DASHBOARD ===")
    
    total_monthly_target = sum(s["monthly_revenue_target"] for s in REVENUE_STREAMS)
    total_annual_target = total_monthly_target * 12
    
    dashboard = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_monthly_revenue_target": f"${total_monthly_target:,.0f}",
        "total_annual_revenue_target": f"${total_annual_target:,.0f}",
        "streams": REVENUE_STREAMS,
        "stream_count": len(REVENUE_STREAMS),
    }
    
    with open(DASHBOARD_FILE, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, indent=2)
    
    print(json.dumps(dashboard, indent=2))
    log(f"Total monthly target: ${total_monthly_target:,.0f} | Annual: ${total_annual_target:,.0f}")
    
    return dashboard


def generate_morning_briefing():
    """Generate markdown morning briefing."""
    total_monthly = sum(s["monthly_revenue_target"] for s in REVENUE_STREAMS)
    total_annual = total_monthly * 12
    
    briefing = f"""# Morning Revenue Briefing
**Date:** {datetime.now().strftime('%B %d, %Y')}
**Total Monthly Target:** ${total_monthly:,.0f}
**Total Annual Target:** ${total_annual:,.0f}

## Revenue Streams

| Stream | Type | Monthly Target | Status |
|--------|------|---------------|--------|
"""
    
    for s in REVENUE_STREAMS:
        briefing += f"| {s['stream']} | {s['type']} | ${s['monthly_revenue_target']:,.0f} | {s['current_status']} |\n"
    
    briefing += f"""
## Priority Actions Today
1. **Fix Whop account** — Get new API key, create compliant products
2. **Submit Upwork proposals** — 3 high-ticket bids ready ($16K total)
3. **Launch Fiverr gigs** — 3 AI service listings to publish
4. **Send B2B cold emails** — Target 10 agencies/brokerages
5. **Publish digital products** — List starter kit on Gumroad

## Revenue Breakdown by Type
- **Recurring (Monthly):** ${sum(s['monthly_revenue_target'] for s in REVENUE_STREAMS if s['type'] == 'recurring'):,.0f}
- **Project-Based:** ${sum(s['monthly_revenue_target'] for s in REVENUE_STREAMS if s['type'] == 'project'):,.0f}
- **Commission:** ${sum(s['monthly_revenue_target'] for s in REVENUE_STREAMS if s['type'] == 'commission'):,.0f}
- **Passive:** ${sum(s['monthly_revenue_target'] for s in REVENUE_STREAMS if s['type'] == 'passive'):,.0f}

---
*Generated by Contech AI Revenue Dashboard*
"""
    
    with open(BRIEFING_FILE, 'w', encoding='utf-8') as f:
        f.write(briefing)
    
    log(f"Morning briefing saved to {BRIEFING_FILE.name}")
    return briefing


if __name__ == "__main__":
    generate_dashboard()
    print("\n" + "=" * 60 + "\n")
    generate_morning_briefing()
