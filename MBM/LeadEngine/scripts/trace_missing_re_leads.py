#!/usr/bin/env python3
"""
Phase 1: Trace the 78 Missing Real-Estate Leads
================================================
Diagnostic analysis of why 78 RE phone numbers are missing from dialer DB.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

LEADENGINE_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]

DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
RE_QUEUE = LEADENGINE_DIR / "real_estate_calling_queue.json"
COLD_QUEUE = LEADENGINE_DIR / "cold_calling_queue.json"
MULTI_QUEUE = LEADENGINE_DIR / "multi_touch_queue.json"
ULIO_QUEUE = LEADENGINE_DIR / "ulio_voice_queue.json"

OUTPUT_DIR = ROOT / "logs" / "recovery"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def normalize_phone(phone: str) -> str:
    """Normalize to E.164 format for comparison."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+1{digits[1:]}"
    elif digits.startswith("+"):
        return "+" + digits
    return phone

def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    print("=" * 80)
    print("PHASE 1: TRACE THE 78 MISSING REAL-ESTATE LEADS")
    print("=" * 80)
    
    # Load all sources
    dialer = load_json(DIALER_DB)
    re_queue = load_json(RE_QUEUE)
    cold_queue = load_json(COLD_QUEUE)
    multi_queue = load_json(MULTI_QUEUE)
    ulio_queue = load_json(ULIO_QUEUE)
    
    print(f"\nLoaded sources:")
    print(f"  Dialer DB: {len(dialer)} records")
    print(f"  RE Queue: {len(re_queue)} records")
    print(f"  Cold Queue: {len(cold_queue)} records")
    print(f"  Multi Queue: {len(multi_queue)} records")
    print(f"  Ulio Queue: {len(ulio_queue)} records")
    
    # Build phone sets
    dialer_phones = {normalize_phone(l.get('phone', '')) for l in dialer if l.get('phone')}
    re_phones = {normalize_phone(l.get('phone', '')) for l in re_queue if l.get('phone')}
    cold_phones = {normalize_phone(l.get('phone', '')) for l in cold_queue if l.get('phone')}
    multi_phones = {normalize_phone(l.get('phone', '')) for l in multi_queue if l.get('phone')}
    ulio_phones = {normalize_phone(l.get('phone', '')) for l in ulio_queue if l.get('phone')}
    
    print(f"\nPhone analysis:")
    print(f"  Unique dialer phones: {len(dialer_phones)}")
    print(f"  Unique RE phones: {len(re_phones)}")
    print(f"  Unique Cold phones: {len(cold_phones)}")
    print(f"  Unique Multi phones: {len(multi_phones)}")
    print(f"  Unique Ulio phones: {len(ulio_phones)}")
    
    # Find missing RE phones
    missing_re = re_phones - dialer_phones
    already_in_dialer = re_phones & dialer_phones
    
    print(f"\n  RE phones already in dialer: {len(already_in_dialer)}")
    print(f"  RE phones MISSING from dialer: {len(missing_re)}")
    
    # For each missing RE lead, gather full diagnostic info
    missing_leads = []
    for lead in re_queue:
        phone = normalize_phone(lead.get('phone', ''))
        if phone in missing_re:
            # Check other sources
            in_cold = phone in cold_phones
            in_multi = phone in multi_phones
            in_ulio = phone in ulio_phones
            
            # Get cold queue match if exists
            cold_match = None
            if in_cold:
                cold_match = next((l for l in cold_queue if normalize_phone(l.get('phone', '')) == phone), None)
            
            # Get multi queue match if exists
            multi_match = None
            if in_multi:
                multi_match = next((l for l in multi_queue if normalize_phone(l.get('phone', '')) == phone), None)
            
            # Check for entity/name matches in dialer (different phone, same entity)
            entity_matches = []
            lead_name = (lead.get('contact_name') or lead.get('company_name') or '').strip().lower()
            if lead_name:
                for d in dialer:
                    d_name = (d.get('contact') or d.get('company') or '').strip().lower()
                    if d_name and (d_name == lead_name or lead_name in d_name or d_name in lead_name):
                        entity_matches.append({
                            'dialer_name': d.get('contact') or d.get('company'),
                            'dialer_phone': d.get('phone'),
                            'dialer_vertical': d.get('vertical')
                        })
            
            # Determine likely reason for missing
            reason = "not_exported"  # default
            if in_cold:
                reason = "in_cold_queue_not_merged"
            if entity_matches:
                reason = "entity_collision_different_phone"
            if not lead.get('verified_phone') and not lead.get('phone_number'):
                reason = "missing_phone_field"
            if lead.get('skip_trace_status') != 'VERIFIED':
                reason = "unverified_skip_trace"
            
            missing_leads.append({
                'phone': phone,
                'contact_name': lead.get('contact_name'),
                'company_name': lead.get('company_name'),
                'role_type': lead.get('role_type'),
                'email': lead.get('email'),
                'property_address': lead.get('property_address'),
                'city': lead.get('city'),
                'state': lead.get('state'),
                'distress_signal': lead.get('distress_signal'),
                'est_arv': lead.get('est_arv'),
                'asking_price': lead.get('asking_price'),
                'target_cash_offer': lead.get('target_cash_offer'),
                'skip_trace_status': lead.get('skip_trace_status'),
                'verified_source': lead.get('verified_source'),
                'vertical': lead.get('vertical'),
                'deal_id': lead.get('deal_id'),
                'motivation_score': lead.get('motivation_score'),
                'motivation_tier': lead.get('motivation_tier'),
                'motivation_signals': lead.get('motivation_signals', []),
                'pitch_angle': lead.get('pitch_angle'),
                'in_cold_queue': in_cold,
                'in_multi_queue': in_multi,
                'in_ulio_queue': in_ulio,
                'cold_match_name': cold_match.get('name') if cold_match else None,
                'cold_match_company': cold_match.get('company') if cold_match else None,
                'entity_matches_in_dialer': entity_matches,
                'likely_missing_reason': reason
            })
    
    # Save diagnostic report
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'dialer_total': len(dialer),
            're_queue_total': len(re_queue),
            're_unique_phones': len(re_phones),
            'already_in_dialer': len(already_in_dialer),
            'missing_from_dialer': len(missing_leads),
            'missing_in_cold': sum(1 for m in missing_leads if m['in_cold_queue']),
            'missing_in_multi': sum(1 for m in missing_leads if m['in_multi_queue']),
            'missing_in_ulio': sum(1 for m in missing_leads if m['in_ulio_queue']),
            'entity_collisions': sum(1 for m in missing_leads if m['entity_matches_in_dialer'])
        },
        'missing_leads': missing_leads
    }
    
    # Write JSON report
    json_path = OUTPUT_DIR / "missing_re_diagnostic.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"\n[OK] Diagnostic report saved: {json_path}")
    
    # Write CSV for easy review
    csv_path = OUTPUT_DIR / "missing_re_diagnostic.csv"
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        if missing_leads:
            fieldnames = [
                'phone', 'contact_name', 'company_name', 'role_type', 'city', 'state',
                'property_address', 'distress_signal', 'est_arv', 'asking_price',
                'target_cash_offer', 'skip_trace_status', 'verified_source',
                'motivation_score', 'motivation_tier', 'motivation_signals',
                'pitch_angle', 'in_cold_queue', 'in_multi_queue', 'in_ulio_queue',
                'cold_match_name', 'cold_match_company', 'entity_collisions',
                'likely_missing_reason'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in missing_leads:
                row = {k: m.get(k, '') for k in fieldnames}
                row['motivation_signals'] = '; '.join(m.get('motivation_signals', []))
                row['entity_collisions'] = len(m.get('entity_matches_in_dialer', []))
                writer.writerow(row)
    print(f"[OK] CSV report saved: {csv_path}")
    
    # Print summary by reason
    reason_counts = defaultdict(int)
    for m in missing_leads:
        reason_counts[m['likely_missing_reason']] += 1
    
    print(f"\n{'='*80}")
    print("MISSING REASON BREAKDOWN:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    
    # Show entity collisions
    collisions = [m for m in missing_leads if m['entity_matches_in_dialer']]
    if collisions:
        print(f"\n{'='*80}")
        print(f"ENTITY COLLISIONS ({len(collisions)}): Same entity, different phone in dialer")
        for m in collisions[:10]:
            for match in m['entity_matches_in_dialer']:
                print(f"  RE: {m['contact_name']} ({m['phone']}) -> Dialer: {match['dialer_name']} ({match['dialer_phone']}) [{match['dialer_vertical']}]")
    
    # Show leads that ARE in cold queue but missing from dialer
    in_cold = [m for m in missing_leads if m['in_cold_queue']]
    print(f"\n{'='*80}")
    print(f"IN COLD QUEUE BUT MISSING FROM DIALER ({len(in_cold)}):")
    for m in in_cold[:10]:
        print(f"  {m['contact_name']} ({m['phone']}) - RE: {m['skip_trace_status']}, Cold: {m['cold_match_company']}")

if __name__ == "__main__":
    import csv
    main()