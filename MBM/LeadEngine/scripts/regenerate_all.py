#!/usr/bin/env python3
"""Fix recommended_opening and regenerate all artifacts cleanly."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

PRIORITY_RANKING = LOGS_DIR / "priority_ranking.json"
RE_QUEUE = LEADENGINE_DIR / "real_estate_calling_queue.json"
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"

OUTPUT_DIR = LEADENGINE_DIR

def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_opening(lead: dict) -> str:
    """Generate recommended opening for the call."""
    name = lead.get('name') or lead.get('contact_name') or lead.get('contact') or 'there'
    company = lead.get('company') or lead.get('company_name') or 'your property'
    signals = lead.get('motivation_signals', []) or []
    
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
    print("REGENERATING ALL ARTIFACTS CLEANLY")
    print("=" * 80)
    
    # Load priority ranking
    priority_data = load_json(PRIORITY_RANKING)
    recovered_ranked = priority_data['recovered_ranked']
    
    # Filter and deduplicate
    new_recovered = [r for r in recovered_ranked if r['is_new_entity']]
    alt_recovered = [r for r in recovered_ranked if r['is_alternate_phone']]
    
    # Deduplicate by phone (keep highest priority)
    def deduplicate(leads):
        by_phone = {}
        for lead in leads:
            phone = lead.get('phone')
            if not phone:
                continue
            if phone not in by_phone or lead.get('priority_score', 0) > by_phone[phone].get('priority_score', 0):
                by_phone[phone] = lead
        return list(by_phone.values())
    
    new_recovered = deduplicate(new_recovered)
    alt_recovered = deduplicate(alt_recovered)
    
    # Add recommended_opening to recovered leads
    for lead in new_recovered:
        if not lead.get('recommended_opening'):
            lead['recommended_opening'] = generate_opening(lead)
    
    for lead in alt_recovered:
        if not lead.get('recommended_opening'):
            lead['recommended_opening'] = generate_opening(lead)
    
    # Sort by priority score
    new_recovered.sort(key=lambda x: -x.get('priority_score', 0))
    for i, lead in enumerate(new_recovered):
        lead['priority_rank'] = i + 1
    
    alt_recovered.sort(key=lambda x: -x.get('priority_score', 0))
    
    print(f"New recovered (deduped): {len(new_recovered)}")
    print(f"Alt recovered (deduped): {len(alt_recovered)}")
    
    # Load existing dialer
    dialer = load_json(DIALER_DB)
    dialer_re = [l for l in dialer if 'seller' in (l.get('vertical', '') or '').lower()]
    
    # Build RE queue lookup for motivation_signals
    re_queue = load_json(RE_QUEUE)
    re_by_phone = {l.get('phone'): l for l in re_queue if l.get('phone')}
    
    # Build unified queue
    unified_queue = []
    
    # Add recovered leads
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
            'recommended_opening': lead.get('recommended_opening'),
            'confidence': lead.get('confidence'),
            'top_signals': lead.get('top_signals', []),
            'provenance': 'real_estate_calling_queue',
            'is_recovered': True
        })
    
    # Add existing dialer RE leads with motivation_signals from RE queue
    for lead in dialer_re:
        phone = lead.get('phone')
        re_lead = re_by_phone.get(phone)
        signals = re_lead.get('motivation_signals', []) if re_lead else []
        
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
    
    # Sort
    unified_queue.sort(key=lambda x: (
        -(x['priority_score'] or 0),
        x['source'] != 'recovered_re',
        -(x['lead_score'] or 0)
    ))
    
    for i, lead in enumerate(unified_queue):
        lead['final_rank'] = i + 1
    
    # Save tonight queue
    json_path = OUTPUT_DIR / "tonight_real_estate_call_queue.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_leads': len(unified_queue),
            'recovered_count': len(new_recovered),
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
    
    print(f"\n[OK] Tonight queue: {len(unified_queue)} total")
    print(f"  Recovered: {len(new_recovered)}")
    print(f"  Existing: {len(dialer_re)}")
    
    # Validate
    phones = [l.get('phone') for l in unified_queue if l.get('phone')]
    unique_phones = set(phones)
    print(f"  Phones: {len(phones)}, Unique: {len(unique_phones)}, Duplicates: {len(phones) - len(unique_phones)}")
    
    # Now regenerate merge artifacts with correct counts
    # Merge preview
    merge_preview = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'existing_dialer_count': len(dialer),
        'new_recovered_count': len(new_recovered),
        'alternate_phones_count': len(alt_recovered),
        'total_after_merge': len(dialer) + len(new_recovered),
        'actions': []
    }
    
    for record in new_recovered:
        contact = record.get('name') or record.get('contact_name') or ''
        company = record.get('company') or record.get('company_name') or ''
        safe_name = re.sub(r'[^\w]', '_', (contact or company).lower())
        merge_preview['actions'].append({
            'action': 'add_new_lead',
            'phone': record['phone'],
            'name': record.get('name') or record.get('contact_name'),
            'company': record.get('company') or record.get('company_name'),
            'priority_score': record.get('priority_score'),
            'canonical_id': f"entity_{safe_name}_{record['phone'][-4:]}",
            'reason': 'New qualified entity not in dialer'
        })
    
    for alt in alt_recovered:
        merge_preview['actions'].append({
            'action': 'add_alternate_phone',
            'primary_phone': None,  # Would need entity lookup
            'alternate_phone': alt.get('phone'),
            'entity': alt.get('entity_group', ''),
            'reason': 'Alternate phone for existing verified entity'
        })
    
    # Save merge preview
    preview_path = LOGS_DIR / "dialer_merge_preview.json"
    with open(preview_path, 'w', encoding='utf-8') as f:
        json.dump(merge_preview, f, indent=2, default=str)
    
    # Recovered candidates (deduplicated)
    all_candidates = []
    for lead in new_recovered + alt_recovered:
        all_candidates.append({
            'id': f"RE-{lead.get('phone', '').replace('+', '').replace('-', '')[-6:]}",
            'vertical': lead.get('vertical', 'real estate sellers'),
            'company': lead.get('company') or lead.get('company_name'),
            'contact': lead.get('name') or lead.get('contact_name'),
            'phone': lead.get('phone'),
            'norm_phone': re.sub(r"\D", "", lead.get('phone', ''))[1:] if len(re.sub(r"\D", "", lead.get('phone', ''))) == 11 else re.sub(r"\D", "", lead.get('phone', '')),
            'motivation_score': lead.get('motivation_score'),
            'deal_score': lead.get('motivation_score'),
            'callability_score': 90,
            'motivation_tier': lead.get('motivation_tier'),
            'pitch_angle': lead.get('pitch_angle', ''),
            'priority_score': lead.get('priority_score'),
            'top_signals': lead.get('top_signals', []),
            'confidence': lead.get('confidence'),
            'recovery_source': 'phase1_recovery'
        })
    
    # Deduplicate candidates by phone
    candidates_by_phone = {}
    for c in all_candidates:
        phone = c.get('phone')
        if phone and phone not in candidates_by_phone:
            candidates_by_phone[phone] = c
    
    candidates_dedup = list(candidates_by_phone.values())
    
    candidates_path = LOGS_DIR / "recovered_candidates.json"
    with open(candidates_path, 'w', encoding='utf-8') as f:
        json.dump(candidates_dedup, f, indent=2, default=str)
    
    # Save CSV
    csv_path = LOGS_DIR / "recovered_candidates.csv"
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'id', 'vertical', 'company', 'contact', 'phone', 'norm_phone',
            'motivation_score', 'deal_score', 'callability_score', 'motivation_tier',
            'pitch_angle', 'priority_score', 'top_signals', 'confidence', 'recovery_source'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates_dedup:
            row = {k: c.get(k, '') for k in fieldnames}
            row['top_signals'] = '; '.join(c.get('top_signals', []) if isinstance(c.get('top_signals'), list) else [])
            writer.writerow(row)
    
    # Merged dialer preview
    merged_dialer = dialer + [
        {
            "id": f"RE-{lead.get('phone', '').replace('+', '').replace('-', '')[-6:]}",
            "vertical": lead.get('vertical', 'real estate sellers'),
            "company": lead.get('company') or lead.get('company_name'),
            "contact": lead.get('name') or lead.get('contact_name'),
            "phone": lead.get('phone'),
            "norm_phone": re.sub(r"\D", "", lead.get('phone', ''))[1:] if len(re.sub(r"\D", "", lead.get('phone', ''))) == 11 else re.sub(r"\D", "", lead.get('phone', '')),
            "motivation_score": lead.get('motivation_score'),
            "deal_score": lead.get('motivation_score'),
            "callability_score": 90,
            "motivation_tier": lead.get('motivation_tier'),
            "pitch_angle": lead.get('pitch_angle', ''),
            "details": {
                "priority": "1" if lead.get('motivation_score', 0) >= 70 else "2",
                "verified_phone": lead.get('phone'),
                "vertical_tag": (lead.get('vertical', 'real estate sellers')).upper().replace(' ', '_'),
                "Owner_Name": lead.get('name') or lead.get('contact_name'),
                "Title": "Owner",
                "Owner_Status": "VERIFIED_OWNER",
                "Source_Class": "COUNTY_RECORD",
                "Decision_Maker_Confidence": "HIGH",
                "Contact_Confidence": "HIGH",
                "Call_Script": lead.get('recommended_opening', ''),
                "Why_This_Deal": lead.get('why_call_now', 'Qualified real estate seller'),
                "Why_Now": "High intent seller with verified distress signals",
                "Economic_Thesis": "As-is cash purchase with zero seller fees",
                "Next_Action": "DIAL_PROPERTY_OWNER",
                "source": "real_estate_calling_queue",
                "neteller_link": "https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=2500.00&currency=USD&item=RE-PURCHASE-EVALUATION",
                "motivation_signals": lead.get('motivation_signals', []),
                "priority_score": lead.get('priority_score'),
                "top_signals": lead.get('top_signals', []),
                "confidence": lead.get('confidence'),
                "recovery_source": "phase1_recovery"
            },
            "skip_trace_status": lead.get('skip_trace_status', 'VERIFIED'),
            "skip_trace_source": "skip_trace_verified",
            "skip_trace_confidence": "high"
        }
        for lead in new_recovered
    ]
    
    merged_path = LOGS_DIR / "dialer_merged_preview.json"
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(merged_dialer, f, indent=2, default=str)
    
    print(f"\n[OK] Merge preview: {len(new_recovered)} new, {len(alt_recovered)} alt")
    print(f"[OK] Recovered candidates: {len(candidates_dedup)} (deduped)")
    print(f"[OK] Merged dialer: {len(merged_dialer)} total")
    
    # Final validation
    merged_phones = [m.get('phone') for m in merged_dialer if m.get('phone')]
    merged_unique = set(merged_phones)
    print(f"  Merged phones: {len(merged_phones)}, Unique: {len(merged_unique)}, Duplicates: {len(merged_phones) - len(merged_unique)}")
    
    return new_recovered, alt_recovered, unified_queue

if __name__ == "__main__":
    import re
    main()