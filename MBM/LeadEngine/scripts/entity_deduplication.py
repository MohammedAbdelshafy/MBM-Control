#!/usr/bin/env python3
"""
Phase 2: Entity-Level Deduplication
===================================
Build canonical identities for recovered RE leads.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
RE_QUEUE = LEADENGINE_DIR / "real_estate_calling_queue.json"
COLD_QUEUE = LEADENGINE_DIR / "cold_calling_queue.json"

DIAGNOSTIC = LOGS_DIR / "missing_re_diagnostic.json"
OUTPUT_DIR = LOGS_DIR

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+1{digits[1:]}"
    return phone

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # Remove common suffixes, normalize case, remove punctuation
    name = str(name).strip().lower()
    suffixes = [' llc', ' inc', ' corp', ' ltd', ' lp', ' llp', ' pllc', ' pc', ' pa', ' co']
    for s in suffixes:
        if name.endswith(s):
            name = name[:-len(s)]
    return re.sub(r'[^\w\s]', '', name).strip()

def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_canonical_identity(lead: dict, source: str) -> dict:
    """Build canonical identity from a lead record."""
    phone = normalize_phone(lead.get('phone') or lead.get('phone_number') or lead.get('verified_phone', ''))
    name = lead.get('contact_name') or lead.get('name') or lead.get('company') or lead.get('company_name') or ''
    company = lead.get('company_name') or lead.get('company') or ''
    address = lead.get('property_address') or lead.get('address') or ''
    city = lead.get('city') or ''
    state = lead.get('state') or ''
    
    return {
        'phone': phone,
        'name': name.strip(),
        'normalized_name': normalize_name(name),
        'company': company.strip(),
        'normalized_company': normalize_name(company),
        'address': address.strip(),
        'city': city.strip(),
        'state': state.strip(),
        'source': source,
        'skip_trace_status': lead.get('skip_trace_status'),
        'verified_source': lead.get('verified_source'),
        'motivation_score': lead.get('motivation_score'),
        'motivation_tier': lead.get('motivation_tier'),
        'motivation_signals': lead.get('motivation_signals', []),
        'distress_signal': lead.get('distress_signal'),
        'est_arv': lead.get('est_arv'),
        'asking_price': lead.get('asking_price'),
        'target_cash_offer': lead.get('target_cash_offer'),
        'pitch_angle': lead.get('pitch_angle'),
        'deal_id': lead.get('deal_id'),
        'vertical': lead.get('vertical'),
        'role_type': lead.get('role_type'),
        'email': lead.get('email')
    }

def find_entity_matches(canonical_lead: dict, all_canonical: list) -> list:
    """Find potential entity matches across all sources."""
    matches = []
    for other in all_canonical:
        if other is canonical_lead:
            continue
        
        match_reasons = []
        
        # Same phone
        if canonical_lead['phone'] and canonical_lead['phone'] == other['phone']:
            match_reasons.append('same_phone')
        
        # Same normalized entity name
        if canonical_lead['normalized_name'] and canonical_lead['normalized_name'] == other['normalized_name']:
            match_reasons.append('same_normalized_name')
        
        # Same normalized company name
        if canonical_lead['normalized_company'] and canonical_lead['normalized_company'] == other['normalized_company']:
            match_reasons.append('same_normalized_company')
        
        # Same address
        if canonical_lead['address'] and canonical_lead['address'] == other['address'] and canonical_lead['address']:
            match_reasons.append('same_address')
        
        # Name contains company or vice versa
        if (canonical_lead['normalized_name'] and other['normalized_company'] and 
            (canonical_lead['normalized_name'] in other['normalized_company'] or other['normalized_company'] in canonical_lead['normalized_name'])):
            match_reasons.append('name_contains_company')
        
        if match_reasons:
            matches.append({
                'matched_lead': other,
                'match_reasons': match_reasons
            })
    
    return matches

def main():
    print("=" * 80)
    print("PHASE 2: ENTITY-LEVEL DEDUPLICATION")
    print("=" * 80)
    
    # Load all sources
    dialer = load_json(DIALER_DB)
    re_queue = load_json(RE_QUEUE)
    
    # Load diagnostic to get the missing leads
    with open(DIAGNOSTIC, 'r', encoding='utf-8') as f:
        diagnostic = json.load(f)
    
    missing_leads_data = diagnostic['missing_leads']
    print(f"Processing {len(missing_leads_data)} missing RE leads...")
    
    # Build canonical identities for all dialer leads
    dialer_canonical = []
    for lead in dialer:
        canonical = build_canonical_identity(lead, 'dialer')
        canonical['original_lead'] = lead
        dialer_canonical.append(canonical)
    
    # Build canonical identities for all RE queue leads
    re_canonical = []
    for lead in re_queue:
        canonical = build_canonical_identity(lead, 're_queue')
        canonical['original_lead'] = lead
        re_canonical.append(canonical)
    
    # Build canonical identities for missing RE leads specifically
    missing_canonical = []
    for lead in missing_leads_data:
        canonical = build_canonical_identity(lead, 're_queue_missing')
        canonical['original_lead'] = lead
        missing_canonical.append(canonical)
    
    print(f"Built canonical identities:")
    print(f"  Dialer: {len(dialer_canonical)}")
    print(f"  RE Queue: {len(re_canonical)}")
    print(f"  Missing RE: {len(missing_canonical)}")
    
    # For each missing lead, find entity matches
    results = []
    for missing in missing_canonical:
        # Find matches in dialer
        dialer_matches = find_entity_matches(missing, dialer_canonical)
        
        # Find matches in full RE queue (including other missing leads)
        re_matches = find_entity_matches(missing, [l for l in re_canonical if l['phone'] != missing['phone']])
        
        # Determine canonical entity group
        entity_group = {
            'canonical_id': None,
            'phones': {missing['phone']},
            'names': {missing['name']},
            'companies': {missing['company']},
            'addresses': {missing['address']} if missing['address'] else set(),
            'sources': {'re_queue'},
            'leads': [missing]
        }
        
        # Add dialer matches to entity group
        for match in dialer_matches:
            entity_group['phones'].add(match['matched_lead']['phone'])
            entity_group['names'].add(match['matched_lead']['name'])
            entity_group['companies'].add(match['matched_lead']['company'])
            if match['matched_lead']['address']:
                entity_group['addresses'].add(match['matched_lead']['address'])
            entity_group['sources'].add('dialer')
            entity_group['leads'].append(match['matched_lead'])
        
        # Add RE queue matches to entity group
        for match in re_matches:
            entity_group['phones'].add(match['matched_lead']['phone'])
            entity_group['names'].add(match['matched_lead']['name'])
            entity_group['companies'].add(match['matched_lead']['company'])
            if match['matched_lead']['address']:
                entity_group['addresses'].add(match['matched_lead']['address'])
            entity_group['sources'].add('re_queue')
            entity_group['leads'].append(match['matched_lead'])
        
        # Generate canonical ID
        primary_name = missing['normalized_name'] or missing['normalized_company'] or missing['phone']
        safe_name = re.sub(r'[^\w]', '_', primary_name)
        entity_group['canonical_id'] = f"entity_{safe_name}_{missing['phone'][-4:]}"
        
        results.append({
            'missing_lead': missing,
            'dialer_matches': dialer_matches,
            're_queue_matches': re_matches,
            'entity_group': entity_group,
            'is_new_entity': len(dialer_matches) == 0,
            'is_alternate_phone': len(dialer_matches) > 0,
            'confidence': 'high' if dialer_matches else 'medium'
        })
    
    # Save results
    output_path = OUTPUT_DIR / "entity_deduplication.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n[OK] Entity deduplication saved: {output_path}")
    
    # Summary
    new_entities = [r for r in results if r['is_new_entity']]
    alt_phones = [r for r in results if r['is_alternate_phone']]
    
    print(f"\n{'='*80}")
    print("ENTITY DEDUPLICATION SUMMARY:")
    print(f"  Total missing leads analyzed: {len(results)}")
    print(f"  New entities (not in dialer): {len(new_entities)}")
    print(f"  Alternate phones for existing entities: {len(alt_phones)}")
    
    # Show alternate phone cases
    if alt_phones:
        print(f"\nALTERNATE PHONES FOR EXISTING ENTITIES:")
        for r in alt_phones:
            m = r['missing_lead']
            print(f"  {m['name']} ({m['phone']}) -> Matches: {[dm['matched_lead']['name'] + ' (' + dm['matched_lead']['phone'] + ')' for dm in r['dialer_matches']]}")
    
    # Show top new entities with strongest signals
    print(f"\nTOP NEW ENTITIES BY MOTIVATION SCORE:")
    scored_new = [(r, r['missing_lead'].get('motivation_score', 0)) for r in new_entities]
    scored_new.sort(key=lambda x: -x[1])
    for r, score in scored_new[:15]:
        m = r['missing_lead']
        signals = ', '.join(m.get('motivation_signals', []))
        print(f"  [{score}] {m['name']} ({m['phone']}) - {m['city']}, {m['state']} - Signals: {signals}")
    
    return results

if __name__ == "__main__":
    main()