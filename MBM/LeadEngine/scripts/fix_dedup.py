#!/usr/bin/env python3
"""Fix deduplication and regenerate artifacts."""

import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

PRIORITY_RANKING = LOGS_DIR / "priority_ranking.json"
RE_QUEUE = LEADENGINE_DIR / "real_estate_calling_queue.json"

def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def deduplicate_leads(leads: list) -> list:
    """Deduplicate leads by phone, keeping highest priority score."""
    by_phone = {}
    for lead in leads:
        phone = lead.get('phone')
        if not phone:
            continue
        if phone not in by_phone:
            by_phone[phone] = lead
        else:
            # Keep the one with higher priority score
            existing_score = by_phone[phone].get('priority_score', 0)
            new_score = lead.get('priority_score', 0)
            if new_score > existing_score:
                by_phone[phone] = lead
    return list(by_phone.values())

def main():
    print("=" * 80)
    print("FIXING DEDUPLICATION AND REGENERATING ARTIFACTS")
    print("=" * 80)
    
    # Load priority ranking
    priority_data = load_json(PRIORITY_RANKING)
    recovered_ranked = priority_data['recovered_ranked']
    
    # Filter to new entities only
    new_recovered = [r for r in recovered_ranked if r['is_new_entity']]
    alt_recovered = [r for r in recovered_ranked if r['is_alternate_phone']]
    
    print(f"Before deduplication: {len(new_recovered)} new recovered")
    
    # Deduplicate new recovered
    new_recovered_dedup = deduplicate_leads(new_recovered)
    print(f"After deduplication: {len(new_recovered_dedup)} new recovered")
    
    # Also deduplicate alt recovered
    alt_recovered_dedup = deduplicate_leads(alt_recovered)
    print(f"Alt recovered after deduplication: {len(alt_recovered_dedup)}")
    
    # Sort by priority score
    new_recovered_dedup.sort(key=lambda x: -x.get('priority_score', 0))
    for i, lead in enumerate(new_recovered_dedup):
        lead['priority_rank'] = i + 1
    
    alt_recovered_dedup.sort(key=lambda x: -x.get('priority_score', 0))
    
    # Save updated priority ranking
    priority_data['recovered_ranked'] = new_recovered_dedup + alt_recovered_dedup
    # Rebuild combined ranking
    # (skip for now, just update recovered)
    
    with open(PRIORITY_RANKING, 'w', encoding='utf-8') as f:
        json.dump(priority_data, f, indent=2, default=str)
    
    print(f"[OK] Updated priority ranking")
    
    # Now regenerate merge phase with deduplicated data
    # (We'll just update the merge preview and tonight queue)
    
    # Regenerate tonight queue with deduplicated recovered leads
    # Load existing dialer
    with open(ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json", 'r') as f:
        dialer = json.load(f)
    
    dialer_re = [l for l in dialer if 'seller' in (l.get('vertical', '') or '').lower()]
    
    # Build unified queue
    unified_queue = []
    
    # Add recovered leads (deduplicated)
    for lead in new_recovered_dedup:
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
            'recommended_opening': lead.get('recommended_opening', ''),
            'confidence': lead.get('confidence'),
            'top_signals': lead.get('top_signals', []),
            'provenance': 'real_estate_calling_queue',
            'is_recovered': True
        })
    
    # Add existing dialer RE leads with motivation_signals from RE queue
    # Build lookup from RE queue
    re_queue = load_json(RE_QUEUE)
    re_by_phone = {l.get('phone'): l for l in re_queue if l.get('phone')}
    
    for lead in dialer_re:
        phone = lead.get('phone')
        re_lead = re_by_phone.get(phone)
        signals = []
        if re_lead:
            signals = re_lead.get('motivation_signals', [])
        
        unified_queue.append({
            'source': 'existing_dialer',
            'priority_rank': None,
            'combined_rank': None,
            'name': lead.get('contact') or lead.get('company'),
            'company': lead.get('company'),
            'phone': phone,
            'property_address': re_lead.get('property_address', '') if re_lead else lead.get('details', {}).get('property_address', ''),
            'city': re_lead.get('city', '') if re_lead else lead.get('details', {}).get('city', ''),
            'state': re_lead.get('state', '') if re_lead else lead.get('details', {}).get('state', ''),
            'lead_score': lead.get('motivation_score') or lead.get('deal_score'),
            'priority_score': None,
            'skip_trace_status': lead.get('skip_trace_status'),
            'motivation_tier': lead.get('motivation_tier'),
            'motivation_signals': signals,
            'why_call_now': 'Existing qualified lead',
            'recommended_opening': f"Hi {lead.get('contact') or lead.get('company')}, this is Omar with MBM Acquisitions. We buy properties as-is for cash, zero fees, 7-day close.",
            'confidence': 'high',
            'top_signals': [],
            'provenance': 'dialer_db',
            'is_recovered': False
        })
    
    # Sort
    unified_queue.sort(key=lambda x: (
        -(x['priority_score'] or 0),
        x['source'] != 'recovered_re',
        -(x['lead_score'] or 0)
    ))
    
    for i, lead in enumerate(unified_queue):
        lead['final_rank'] = i + 1
    
    # Save updated tonight queue
    from datetime import datetime, timezone
    OUTPUT_DIR = LEADENGINE_DIR
    
    json_path = OUTPUT_DIR / "tonight_real_estate_call_queue.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_leads': len(unified_queue),
            'recovered_count': len(new_recovered_dedup),
            'existing_re_count': len(dialer_re),
            'queue': unified_queue
        }, f, indent=2, default=str)
    
    # Save CSV
    import csv
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
            row['motivation_signals'] = '; '.join(lead.get('motivation_signals', []) if isinstance(lead.get('motivation_signals'), list) else [])
            row['top_signals'] = '; '.join(lead.get('top_signals', []) if isinstance(lead.get('top_signals'), list) else [])
            writer.writerow(row)
    
    print(f"\n[OK] Updated tonight queue: {len(unified_queue)} total")
    print(f"  Recovered (deduped): {len(new_recovered_dedup)}")
    print(f"  Existing dialer RE: {len(dialer_re)}")
    
    # Validate
    phones = [l.get('phone') for l in unified_queue if l.get('phone')]
    unique_phones = set(phones)
    print(f"  Phones: {len(phones)}, Unique: {len(unique_phones)}, Duplicates: {len(phones) - len(unique_phones)}")
    
    return new_recovered_dedup

if __name__ == "__main__":
    main()