#!/usr/bin/env python3
"""
Phase 7: Tonight's Real Estate Call Queue
==========================================
Create dedicated ranked export for tonight's calling session.
"""

import json
import re
import csv
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
PRIORITY_RANKING = LOGS_DIR / "priority_ranking.json"
MERGE_PREVIEW = LOGS_DIR / "dialer_merge_preview.json"

OUTPUT_DIR = ROOT / "MBM" / "LeadEngine"  # Output to LeadEngine dir as specified

def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_e164(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+1{digits[1:]}"
    return phone

def generate_opening(lead: dict) -> str:
    """Generate recommended opening for the call."""
    name = lead.get('contact') or lead.get('name') or lead.get('contact_name') or 'there'
    company = lead.get('company') or lead.get('company_name') or 'your property'
    signals = lead.get('motivation_signals', [])
    
    if 'absentee' in signals and 'rental_registration' in signals:
        return f"Hi {name}, this is Omar with MBM Acquisitions. I see you own {company} as a rental property and we buy as-is, close remotely, and pay cash with zero repairs. What's your timeline?"
    elif 'code_concern' in signals and 'absentee' in signals:
        return f"Hi {name}, Omar with MBM Acquisitions. I noticed {company} has some code concerns on the property. We specialize in buying properties with violations as-is, cash close in 7 days. Would a firm cash offer work for you?"
    elif 'absentee' in signals:
        return f"Hi {name}, Omar with MBM Acquisitions. You're an absentee owner of {company} - we buy as-is, close remotely, and pay cash with zero repairs. Open to a cash offer?"
    elif 'rental_registration' in signals:
        return f"Hi {name}, this is Omar with MBM Acquisitions. I see {company} is registered as a rental property. We buy rental properties as-is for cash with zero fees. What would make a direct sale compelling?"
    else:
        return f"Hi {name}, this is Omar with MBM Acquisitions. We buy properties in your area as-is for cash, zero fees, 7-day close. What would make a direct sale compelling for {company}?"

def main():
    print("=" * 80)
    print("PHASE 7: TONIGHT'S REAL ESTATE CALL QUEUE")
    print("=" * 80)
    
    # Load data
    dialer = load_json(DIALER_DB)
    priority_data = load_json(PRIORITY_RANKING)
    merge_preview = load_json(MERGE_PREVIEW)
    
    recovered_ranked = priority_data['recovered_ranked']
    
    # Filter to new entities only (not alternate phones)
    new_recovered = [r for r in recovered_ranked if r['is_new_entity']]
    
    # Combine with existing dialer leads for unified queue
    # Build unified queue with source tracking
    unified_queue = []
    
    # Add recovered leads (top priority)
    for lead in new_recovered:
        unified_queue.append({
            'source': 'recovered_re',
            'priority_rank': lead['priority_rank'],
            'combined_rank': lead.get('combined_rank', lead['priority_rank']),
            'name': lead.get('name') or lead.get('contact_name'),
            'company': lead.get('company') or lead.get('company_name'),
            'phone': lead.get('phone'),
            'property_address': lead.get('property_address', ''),
            'city': lead.get('city', ''),
            'state': lead.get('state', ''),
            'lead_score': lead.get('motivation_score'),
            'priority_score': lead.get('priority_score'),
            'skip_trace_status': lead.get('skip_trace_status'),
            'motivation_tier': lead.get('motivation_tier'),
            'motivation_signals': lead.get('motivation_signals', []),
            'why_call_now': lead.get('why_call_now'),
            'recommended_opening': generate_opening(lead),
            'confidence': lead.get('confidence'),
            'top_signals': lead.get('top_signals', []),
            'provenance': 'real_estate_calling_queue',
            'is_recovered': True
        })
    
    # Add existing dialer RE leads (filter for real estate vertical)
    dialer_re_leads = [l for l in dialer if 'seller' in (l.get('vertical', '') or '').lower()]
    for lead in dialer_re_leads:
        signals = lead.get('details', {}).get('motivation_signals', [])
        unified_queue.append({
            'source': 'existing_dialer',
            'priority_rank': None,
            'combined_rank': None,
            'name': lead.get('contact') or lead.get('company'),
            'company': lead.get('company'),
            'phone': lead.get('phone'),
            'property_address': lead.get('details', {}).get('property_address', ''),
            'city': lead.get('details', {}).get('city', ''),
            'state': lead.get('details', {}).get('state', ''),
            'lead_score': lead.get('motivation_score') or lead.get('deal_score'),
            'priority_score': None,
            'skip_trace_status': lead.get('skip_trace_status'),
            'motivation_tier': lead.get('motivation_tier'),
            'motivation_signals': signals,
            'why_call_now': 'Existing qualified lead',
            'recommended_opening': generate_opening({
                'name': lead.get('contact') or lead.get('company'),
                'company': lead.get('company'),
                'motivation_signals': signals
            }),
            'confidence': 'high',
            'top_signals': [],
            'provenance': 'dialer_db',
            'is_recovered': False
        })
    
    # Sort by priority score (recovered first, then by score)
    unified_queue.sort(key=lambda x: (
        -(x['priority_score'] or 0),
        x['source'] != 'recovered_re',  # recovered first
        -(x['lead_score'] or 0)
    ))
    
    # Add final rank
    for i, lead in enumerate(unified_queue):
        lead['final_rank'] = i + 1
    
    # Save JSON
    json_path = OUTPUT_DIR / "tonight_real_estate_call_queue.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_leads': len(unified_queue),
            'recovered_count': len(new_recovered),
            'existing_re_count': len(dialer_re_leads),
            'queue': unified_queue
        }, f, indent=2, default=str)
    
    # Save CSV
    csv_path = OUTPUT_DIR / "tonight_real_estate_call_queue.csv"
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'rank', 'source', 'name', 'company', 'phone', 'property_address',
            'city', 'state', 'lead_score', 'priority_score', 'skip_trace_status',
            'motivation_tier', 'motivation_signals', 'why_call_now',
            'recommended_opening', 'confidence', 'top_signals', 'provenance'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in unified_queue:
            row = {k: lead.get(k, '') for k in fieldnames}
            row['motivation_signals'] = '; '.join(lead.get('motivation_signals', []))
            row['top_signals'] = '; '.join(lead.get('top_signals', []))
            writer.writerow(row)
    
    # Save Markdown for easy reading
    md_path = OUTPUT_DIR / "tonight_real_estate_call_queue.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# 📞 TONIGHT'S REAL ESTATE CALL QUEUE\n\n")
        f.write(f"**Generated**: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"**Total Leads**: {len(unified_queue)}\n")
        f.write(f"**Recovered RE Leads**: {len(new_recovered)}\n")
        f.write(f"**Existing Dialer RE Leads**: {len(dialer_re_leads)}\n\n")
        
        f.write("## 🎯 TOP PRIORITY - RECOVERED LEADS (New Entities)\n\n")
        for lead in unified_queue:
            if lead['source'] == 'recovered_re':
                f.write(f"### #{lead['final_rank']} | {lead['name']} | {lead['company']}\n")
                f.write(f"- **Phone**: `{lead['phone']}` 📞\n")
                f.write(f"- **Property**: {lead['property_address'] or 'N/A'}, {lead['city']}, {lead['state']}\n")
                f.write(f"- **Lead Score**: {lead['lead_score']}/100 | **Priority Score**: {lead['priority_score']}/100\n")
                f.write(f"- **Skip Trace**: {lead['skip_trace_status']} | **Tier**: {lead['motivation_tier']}\n")
                f.write(f"- **Signals**: {', '.join(lead['motivation_signals'])}\n")
                f.write(f"- **Why Call Now**: {lead['why_call_now']}\n")
                f.write(f"- **Confidence**: {lead['confidence']}\n")
                f.write(f"- **Opening**: {lead['recommended_opening']}\n\n")
        
        f.write("## 📋 EXISTING DIALER RE LEADS\n\n")
        for lead in unified_queue:
            if lead['source'] == 'existing_dialer':
                f.write(f"### #{lead['final_rank']} | {lead['name']} | {lead['company']}\n")
                f.write(f"- **Phone**: `{lead['phone']}` 📞\n")
                f.write(f"- **Lead Score**: {lead['lead_score']}/100\n")
                f.write(f"- **Skip Trace**: {lead['skip_trace_status']} | **Tier**: {lead['motivation_tier']}\n")
                f.write(f"- **Signals**: {', '.join(lead['motivation_signals'])}\n")
                f.write(f"- **Opening**: {lead['recommended_opening']}\n\n")
    
    print(f"[OK] Tonight's call queue JSON: {json_path}")
    print(f"[OK] Tonight's call queue CSV: {csv_path}")
    print(f"[OK] Tonight's call queue MD: {md_path}")
    
    print(f"\n{'='*80}")
    print("TONIGHT'S CALL QUEUE SUMMARY:")
    print(f"  Total leads: {len(unified_queue)}")
    print(f"  Recovered (new): {len(new_recovered)}")
    print(f"  Existing dialer RE: {len(dialer_re_leads)}")
    
    print(f"\nTOP 15 CALLS FOR TONIGHT:")
    for lead in unified_queue[:15]:
        src = "[NEW]" if lead['is_recovered'] else "[EXIST]"
        print(f"  {src} #{lead['final_rank']:2d} [{lead['priority_score'] or lead['lead_score']:2d}] {lead['name']} ({lead['phone']}) - {lead['why_call_now'][:60]}")
    
    return unified_queue

if __name__ == "__main__":
    main()