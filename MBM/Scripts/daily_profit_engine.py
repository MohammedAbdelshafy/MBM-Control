"""
MBM AI Automation Agency - Daily Profit Engine
================================================
Runs every day:
1. Discovers pain points
2. Sends Wolf of Wall Street outreach
3. Tracks pipeline
4. Generates revenue report

Usage: python daily_profit_engine.py
"""

import os
import sys
import json
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
TODAY = datetime.now().strftime('%Y-%m-%d')

sys.path.insert(0, os.path.join(MBM_ROOT, "Scripts"))

def run_profit_engine():
    """Run the complete profit engine."""
    print(f"{'='*60}")
    print(f"MBM AI AUTOMATION AGENCY - DAILY PROFIT ENGINE")
    print(f"Date: {TODAY}")
    print(f"{'='*60}\n")
    
    # 1. Generate Lead Pack
    print("[STEP 1] Generating daily lead pack...")
    from daily_lead_pack import generate_lead_pack
    pack_dir, manifest = generate_lead_pack()
    
    # 2. Discover Pain Points
    print(f"\n[STEP 2] Discovering pain points...")
    from pain_point_discovery import discover_pain_points
    pain_points, pain_file = discover_pain_points()
    
    # 3. Run Outreach Campaign
    print(f"\n[STEP 3] Running Wolf of Wall Street outreach...")
    from wolf_outreach import run_outreach_campaign
    campaign_log = run_outreach_campaign()
    
    # 4. Generate Revenue Report
    print(f"\n[STEP 4] Generating revenue report...")
    generate_revenue_report(pain_points, campaign_log, manifest)
    
    print(f"\n{'='*60}")
    print(f"PROFIT ENGINE COMPLETE")
    print(f"{'='*60}")
    print(f"Leads Generated: {manifest['total_leads']}")
    print(f"Outreach Sent: {campaign_log['sent']}")
    print(f"Potential Revenue: ${campaign_log['potential_revenue']['min']:,} - ${campaign_log['potential_revenue']['max']:,}")
    print(f"{'='*60}")

def generate_revenue_report(pain_points, campaign_log, manifest):
    """Generate revenue tracking report."""
    report = {
        'date': TODAY,
        'leads_generated': manifest['total_leads'],
        'sellers': manifest['distressed_sellers'],
        'wholesalers': manifest['wholesalers'],
        'outreach_sent': campaign_log['sent'],
        'potential_deals': campaign_log['potential_revenue'],
        'pipeline': []
    }
    
    for pp in pain_points:
        report['pipeline'].append({
            'company': pp['business'],
            'solution': pp['solution'],
            'deal_value': pp['potential_deal'],
            'status': 'outreach_sent',
            'next_action': 'follow_up_3_days'
        })
    
    # Save report
    report_file = os.path.join(MBM_ROOT, "Logs", f"revenue_report_{TODAY}.json")
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"  Revenue report saved: {report_file}")

if __name__ == "__main__":
    run_profit_engine()
