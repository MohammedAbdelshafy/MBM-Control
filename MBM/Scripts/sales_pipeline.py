"""
MBM AI Automation Agency - Sales Pipeline Tracker
===================================================
Track all deals, follow-ups, and revenue.
"""

import os
import json
import csv
from datetime import datetime, timedelta

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
PIPELINE_DIR = os.path.join(MBM_ROOT, "Pipeline")
os.makedirs(PIPELINE_DIR, exist_ok=True)

TODAY = datetime.now().strftime('%Y-%m-%d')

# Pipeline stages
STAGES = [
    "prospect",
    "outreach_sent",
    "follow_up_1",
    "follow_up_2",
    "call_scheduled",
    "proposal_sent",
    "negotiation",
    "closed_won",
    "closed_lost"
]

def load_pipeline():
    """Load pipeline from CSV."""
    pipeline_file = os.path.join(PIPELINE_DIR, "pipeline.csv")
    if not os.path.exists(pipeline_file):
        return []
    
    deals = []
    with open(pipeline_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            deals.append(row)
    return deals

def save_pipeline(deals):
    """Save pipeline to CSV."""
    pipeline_file = os.path.join(PIPELINE_DIR, "pipeline.csv")
    fieldnames = ['company', 'email', 'phone', 'solution', 'deal_value', 'stage', 'last_touch', 'next_followup', 'notes']
    
    with open(pipeline_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deals)

def add_deal(company, email, phone, solution, deal_value, stage="prospect"):
    """Add a new deal to pipeline."""
    deals = load_pipeline()
    
    # Check if exists
    for d in deals:
        if d['company'] == company:
            print(f"  Deal already exists: {company}")
            return False
    
    new_deal = {
        'company': company,
        'email': email,
        'phone': phone,
        'solution': solution,
        'deal_value': deal_value,
        'stage': stage,
        'last_touch': TODAY,
        'next_followup': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
        'notes': ''
    }
    deals.append(new_deal)
    save_pipeline(deals)
    print(f"  Added: {company} - {deal_value}")
    return True

def update_deal(company, stage, notes=""):
    """Update deal stage."""
    deals = load_pipeline()
    for d in deals:
        if d['company'] == company:
            d['stage'] = stage
            d['last_touch'] = TODAY
            if notes:
                d['notes'] = notes
            # Set next follow-up based on stage
            if stage == "outreach_sent":
                d['next_followup'] = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            elif stage == "follow_up_1":
                d['next_followup'] = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
            elif stage == "call_scheduled":
                d['next_followup'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            save_pipeline(deals)
            print(f"  Updated: {company} -> {stage}")
            return True
    print(f"  Not found: {company}")
    return False

def get_pipeline_stats():
    """Get pipeline statistics."""
    deals = load_pipeline()
    
    stats = {
        'total_deals': len(deals),
        'by_stage': {},
        'total_pipeline_value': 0,
        'closed_value': 0,
        'pending_followups': []
    }
    
    for stage in STAGES:
        stats['by_stage'][stage] = 0
    
    for d in deals:
        stats['by_stage'][d['stage']] = stats['by_stage'].get(d['stage'], 0) + 1
        
        # Calculate value
        value_str = d['deal_value'].replace('$', '').replace(',', '')
        try:
            if '-' in value_str:
                avg = sum(int(x) for x in value_str.split('-')) / 2
            else:
                avg = int(value_str)
            stats['total_pipeline_value'] += avg
            if d['stage'] == 'closed_won':
                stats['closed_value'] += avg
        except:
            pass
        
        # Check for pending follow-ups
        if d['next_followup'] <= TODAY and d['stage'] not in ['closed_won', 'closed_lost']:
            stats['pending_followups'].append(d)
    
    return stats

def print_pipeline():
    """Print pipeline status."""
    deals = load_pipeline()
    stats = get_pipeline_stats()
    
    print(f"\n{'='*60}")
    print(f"SALES PIPELINE - {TODAY}")
    print(f"{'='*60}")
    
    print(f"\nTotal Deals: {stats['total_deals']}")
    print(f"Pipeline Value: ${stats['total_pipeline_value']:,.0f}")
    print(f"Closed Value: ${stats['closed_value']:,.0f}")
    
    print(f"\nBy Stage:")
    for stage, count in stats['by_stage'].items():
        if count > 0:
            print(f"  {stage}: {count}")
    
    if stats['pending_followups']:
        print(f"\nPending Follow-ups ({len(stats['pending_followups'])}):")
        for d in stats['pending_followups']:
            print(f"  - {d['company']}: {d['stage']} (due {d['next_followup']})")
    
    print(f"\nDeals:")
    for d in deals:
        print(f"  [{d['stage']}] {d['company']} - {d['deal_value']}")
    
    print(f"{'='*60}")

def import_pain_points():
    """Import pain points into pipeline."""
    pain_file = os.path.join(MBM_ROOT, "PainPoints", f"PAINPOINTS_{TODAY}.json")
    if os.path.exists(pain_file):
        with open(pain_file, 'r') as f:
            pain_points = json.load(f)
        
        for pp in pain_points:
            add_deal(
                company=pp['business'],
                email=pp.get('contact', ''),
                phone=pp.get('phone', ''),
                solution=pp['solution'],
                deal_value=pp['potential_deal'],
                stage='outreach_sent'
            )
        print(f"  Imported {len(pain_points)} deals from pain points")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print_pipeline()
        elif sys.argv[1] == "import":
            import_pain_points()
        elif sys.argv[1] == "update" and len(sys.argv) >= 4:
            update_deal(sys.argv[2], sys.argv[3])
    else:
        print_pipeline()
