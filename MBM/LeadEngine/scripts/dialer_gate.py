#!/usr/bin/env python3
"""
Phase 3: Dialer Gate - Run recovered candidates through verification
==================================================================
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

sys.path.insert(0, str(LEADENGINE_DIR))

from dialer_verification_gate import (
    filter_for_dialer, check_lead, is_placeholder_identity,
    is_valid_phone, is_valid_name, is_verified
)

ENTITY_DEDUP = LOGS_DIR / "entity_deduplication.json"
OUTPUT_DIR = LOGS_DIR

def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_lead_for_verification(missing_lead: dict) -> dict:
    """Build a lead dict compatible with dialer_verification_gate."""
    phone = missing_lead.get('phone', '')
    name = missing_lead.get('contact_name') or missing_lead.get('name') or missing_lead.get('company_name') or ''
    company = missing_lead.get('company_name') or missing_lead.get('company') or ''
    
    return {
        'phone': phone,
        'phone_number': phone,
        'verified_phone': missing_lead.get('verified_phone', phone),
        'contact_name': name,
        'name': name,
        'company_name': company,
        'company': company,
        'skip_trace_status': missing_lead.get('skip_trace_status', 'VERIFIED'),
        'verified_source': missing_lead.get('verified_source', 'skip_trace_verified'),
        'vertical': missing_lead.get('vertical', 'real estate sellers'),
        'source': missing_lead.get('source', 'real_estate_calling_queue'),
        'details': {
            'source': missing_lead.get('source', 'real_estate_calling_queue'),
            'Owner_Name': name,
            'verified_phone': phone
        },
        'motivation_score': missing_lead.get('motivation_score'),
        'deal_score': missing_lead.get('motivation_score'),
        'callability_score': 90,
        'motivation_tier': missing_lead.get('motivation_tier'),
        'motivation_signals': missing_lead.get('motivation_signals', []),
        'distress_signal': missing_lead.get('distress_signal'),
        'est_arv': missing_lead.get('est_arv'),
        'asking_price': missing_lead.get('asking_price'),
        'target_cash_offer': missing_lead.get('target_cash_offer'),
    }

def main():
    print("=" * 80)
    print("PHASE 3: DIALER GATE - VERIFICATION")
    print("=" * 80)
    
    # Load entity deduplication results
    entity_results = load_json(ENTITY_DEDUP)
    
    # Process each missing lead through verification gate
    verified_leads = []
    rejected_leads = []
    
    for result in entity_results:
        missing = result['missing_lead']
        
        # Build lead for verification
        lead = build_lead_for_verification(missing)
        
        # Run through verification gate
        check_result = check_lead(lead)
        
        # Also check placeholder identity
        is_placeholder = is_placeholder_identity(lead)
        
        record = {
            'phone': missing['phone'],
            'name': missing.get('contact_name') or missing.get('name'),
            'company': missing.get('company_name') or missing.get('company'),
            'skip_trace_status': missing.get('skip_trace_status'),
            'motivation_score': missing.get('motivation_score'),
            'motivation_tier': missing.get('motivation_tier'),
            'motivation_signals': missing.get('motivation_signals', []),
            'is_new_entity': result['is_new_entity'],
            'is_alternate_phone': result['is_alternate_phone'],
            'dialer_matches': len(result['dialer_matches']),
            'verification': check_result,
            'is_placeholder': is_placeholder,
            'entity_group': result['entity_group']['canonical_id']
        }
        
        if check_result['passed'] and not is_placeholder:
            verified_leads.append(record)
        else:
            rejected_leads.append(record)
    
    print(f"\nVerification Results:")
    print(f"  Verified (passed gate): {len(verified_leads)}")
    print(f"  Rejected: {len(rejected_leads)}")
    
    # Rejection breakdown
    if rejected_leads:
        reason_counts = defaultdict(int)
        for r in rejected_leads:
            for reason in r['verification']['rejection_reasons']:
                reason_counts[reason] += 1
        
        print(f"\nRejection Reasons:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")
    
    # Placeholder check
    placeholders = [r for r in verified_leads if r['is_placeholder']]
    if placeholders:
        print(f"\nWARNING: {len(placeholders)} verified leads flagged as placeholder identities!")
        for p in placeholders:
            print(f"  {p['name']} ({p['phone']})")
    
    # Save results
    output = {
        'verified_leads': verified_leads,
        'rejected_leads': rejected_leads,
        'summary': {
            'total_processed': len(entity_results),
            'verified': len(verified_leads),
            'rejected': len(rejected_leads),
            'new_entities_verified': len([r for r in verified_leads if r['is_new_entity']]),
            'alternate_phones_verified': len([r for r in verified_leads if r['is_alternate_phone']]),
        }
    }
    
    output_path = OUTPUT_DIR / "dialer_gate_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n[OK] Dialer gate results saved: {output_path}")
    
    # Show top verified leads
    new_verified = [r for r in verified_leads if r['is_new_entity']]
    new_verified.sort(key=lambda x: -x.get('motivation_score', 0))
    
    print(f"\nTOP NEW ENTITIES PASSED VERIFICATION:")
    for r in new_verified[:20]:
        print(f"  [{r['motivation_score']}] {r['name']} ({r['phone']}) - Tier: {r['motivation_tier']} - Signals: {', '.join(r['motivation_signals'])}")
    
    return verified_leads, rejected_leads

if __name__ == "__main__":
    from collections import defaultdict
    main()