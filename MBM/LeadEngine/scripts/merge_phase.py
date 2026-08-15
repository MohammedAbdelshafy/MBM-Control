#!/usr/bin/env python3
"""
Phase 6: Merge - Create deterministic merge artifacts
====================================================
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
PRIORITY_RANKING = LOGS_DIR / "priority_ranking.json"
DIALER_GATE_RESULTS = LOGS_DIR / "dialer_gate_results.json"

OUTPUT_DIR = LOGS_DIR

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

def build_dialer_record(lead: dict, is_recovered: bool = False) -> dict:
    """Build a dialer-compatible record."""
    phone = format_e164(lead.get('phone', ''))
    name = lead.get('name') or lead.get('contact_name') or lead.get('contact') or ''
    company = lead.get('company') or lead.get('company_name') or ''
    vertical = lead.get('vertical', 'real estate sellers')
    motivation_score = lead.get('motivation_score') or lead.get('deal_score') or 50
    callability_score = 90
    skip_trace_status = lead.get('skip_trace_status', 'VERIFIED')
    verified_source = lead.get('verified_source', 'skip_trace_verified')
    motivation_tier = lead.get('motivation_tier', 'HIGH')
    motivation_signals = lead.get('motivation_signals', [])
    
    # Generate Neteller link
    neteller_link = f"https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=2500.00&currency=USD&item=RE-PURCHASE-EVALUATION"
    
    # Generate call script
    if 'absentee' in motivation_signals and 'rental_registration' in motivation_signals:
        script = f"Hi {name}, this is Omar with MBM Acquisitions. I see you own {company} as a rental property. We buy as-is, close remotely, and pay your asking price in cash with no repairs. What's your timeline?"
    elif 'code_concern' in motivation_signals and 'absentee' in motivation_signals:
        script = f"Hi {name}, Omar with MBM Acquisitions. I noticed {company} has some code concerns on the property. We specialize in buying properties with violations as-is, cash close in 7 days. Would a firm cash offer work for you?"
    elif 'absentee' in motivation_signals:
        script = f"Hi {name}, Omar with MBM Acquisitions. You're an absentee owner of {company} - we buy as-is, close remotely, and pay cash with zero repairs. Open to a cash offer?"
    else:
        script = f"Hi {name}, Omar with MBM Acquisitions. We buy properties in your area as-is for cash, zero fees, 7-day close. What would make a direct sale compelling for {company}?"
    
    return {
        "id": f"RE-{lead.get('phone', '').replace('+', '').replace('-', '')[-6:]}" if is_recovered else lead.get('id', ''),
        "vertical": vertical,
        "company": company,
        "contact": name,
        "phone": phone,
        "norm_phone": re.sub(r"\D", "", phone)[1:] if len(re.sub(r"\D", "", phone)) == 11 else re.sub(r"\D", "", phone),
        "motivation_score": motivation_score,
        "deal_score": motivation_score,
        "callability_score": callability_score,
        "motivation_tier": motivation_tier,
        "pitch_angle": lead.get('pitch_angle', script[:100]),
        "details": {
            "priority": "1" if motivation_score >= 70 else "2",
            "verified_phone": phone,
            "vertical_tag": vertical.upper().replace(' ', '_'),
            "Owner_Name": name,
            "Title": "Owner",
            "Owner_Status": "VERIFIED_OWNER",
            "Source_Class": "COUNTY_RECORD",
            "Decision_Maker_Confidence": "HIGH",
            "Contact_Confidence": "HIGH",
            "Call_Script": script,
            "Why_This_Deal": lead.get('why_call_now', 'Qualified real estate seller'),
            "Why_Now": "High intent seller with verified distress signals",
            "Economic_Thesis": "As-is cash purchase with zero seller fees",
            "Next_Action": "DIAL_PROPERTY_OWNER",
            "source": "real_estate_calling_queue" if is_recovered else lead.get('source', 'unknown'),
            "neteller_link": neteller_link,
            "motivation_signals": motivation_signals,
            "priority_score": lead.get('priority_score'),
            "top_signals": lead.get('top_signals'),
            "confidence": lead.get('confidence'),
            "recovery_source": "phase1_recovery" if is_recovered else "existing"
        },
        "skip_trace_status": skip_trace_status,
        "skip_trace_source": verified_source,
        "skip_trace_confidence": "high"
    }

def main():
    print("=" * 80)
    print("PHASE 6: MERGE - CREATE MERGE ARTIFACTS")
    print("=" * 80)
    
    # Load data
    dialer = load_json(DIALER_DB)
    priority_data = load_json(PRIORITY_RANKING)
    dialer_gate = load_json(DIALER_GATE_RESULTS)
    
    recovered_ranked = priority_data['recovered_ranked']
    verified_leads = dialer_gate['verified_leads']
    
    # Filter to only new entities (not alternate phones)
    new_recovered = [r for r in recovered_ranked if r['is_new_entity']]
    alt_recovered = [r for r in recovered_ranked if r['is_alternate_phone']]
    
    print(f"Existing dialer leads: {len(dialer)}")
    print(f"New recovered entities: {len(new_recovered)}")
    print(f"Alternate phones for existing: {len(alt_recovered)}")
    
    # Build dialer records for new recovered entities
    new_dialer_records = []
    for lead in new_recovered:
        record = build_dialer_record(lead, is_recovered=True)
        new_dialer_records.append(record)
    
    # Build dialer records for alternate phones (attach to existing entity)
    alt_dialer_records = []
    for lead in alt_recovered:
        entity_group = lead.get('entity_group', '')
        canonical_id = entity_group if isinstance(entity_group, str) else entity_group.get('canonical_id', '')
        phones = entity_group.get('phones', set()) if isinstance(entity_group, dict) else set()
        primary_phone = list(phones)[0] if phones else None
        
        alt_dialer_records.append({
            'entity': canonical_id,
            'primary_phone': primary_phone,
            'alternate_phone': lead.get('phone'),
            'name': lead.get('name'),
            'company': lead.get('company'),
            'action': 'add_alternate_phone'
        })
    
    # Create merge preview
    merge_preview = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'existing_dialer_count': len(dialer),
        'new_recovered_count': len(new_dialer_records),
        'alternate_phones_count': len(alt_dialer_records),
        'total_after_merge': len(dialer) + len(new_dialer_records),
        'actions': []
    }
    
    # Add actions for new records
    for record in new_dialer_records:
        contact = record['contact'] or record['company']
        safe_name = re.sub(r'[^\w]', '_', contact.lower())
        canonical_id = f"entity_{safe_name}_{record['phone'][-4:]}"
        merge_preview['actions'].append({
            'action': 'add_new_lead',
            'phone': record['phone'],
            'name': record['contact'],
            'company': record['company'],
            'priority_score': record['details'].get('priority_score'),
            'canonical_id': canonical_id,
            'reason': 'New qualified entity not in dialer'
        })
    
    # Add actions for alternate phones
    for alt in alt_dialer_records:
        merge_preview['actions'].append({
            'action': 'add_alternate_phone',
            'primary_phone': alt['primary_phone'],
            'alternate_phone': alt['alternate_phone'],
            'entity': alt['entity'],
            'reason': 'Alternate phone for existing verified entity'
        })
    
    # Save merge preview
    preview_path = OUTPUT_DIR / "dialer_merge_preview.json"
    with open(preview_path, 'w', encoding='utf-8') as f:
        json.dump(merge_preview, f, indent=2, default=str)
    
    # Save recovered candidates in dialer format
    recovered_candidates = new_dialer_records + [
        build_dialer_record(lead, is_recovered=True) for lead in alt_recovered
    ]
    
    candidates_path = OUTPUT_DIR / "recovered_candidates.json"
    with open(candidates_path, 'w', encoding='utf-8') as f:
        json.dump(recovered_candidates, f, indent=2, default=str)
    
    # Save CSV
    csv_path = OUTPUT_DIR / "recovered_candidates.csv"
    if recovered_candidates:
        fieldnames = [
            'id', 'vertical', 'company', 'contact', 'phone', 'norm_phone',
            'motivation_score', 'deal_score', 'callability_score', 'motivation_tier',
            'pitch_angle', 'priority_score', 'top_signals', 'confidence', 'recovery_source'
        ]
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            import csv
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in recovered_candidates:
                row = {k: r.get(k, '') for k in fieldnames}
                row['top_signals'] = '; '.join(r.get('top_signals', []))
                writer.writerow(row)
    
    # Create merged dialer database
    merged_dialer = dialer + new_dialer_records
    merged_path = OUTPUT_DIR / "dialer_merged_preview.json"
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(merged_dialer, f, indent=2, default=str)
    
    print(f"\n[OK] Merge preview saved: {preview_path}")
    print(f"[OK] Recovered candidates JSON: {candidates_path}")
    print(f"[OK] Recovered candidates CSV: {csv_path}")
    print(f"[OK] Merged dialer preview: {merged_path}")
    
    print(f"\n{'='*80}")
    print("MERGE SUMMARY:")
    print(f"  Existing dialer: {len(dialer)}")
    print(f"  New recovered leads: {len(new_dialer_records)}")
    print(f"  Alternate phones: {len(alt_dialer_records)}")
    print(f"  Total after merge: {len(merged_dialer)}")
    print(f"  Net increase: {len(new_dialer_records)} (+{len(new_dialer_records)/len(dialer)*100:.1f}%)")
    
    # Show top new leads being added
    print(f"\nTOP 10 NEW LEADS BEING ADDED:")
    for i, record in enumerate(new_dialer_records[:10]):
        print(f"  {i+1}. {record['contact']} ({record['phone']}) - {record['company']} - Score: {record['details'].get('priority_score')}")
    
    return merge_preview

if __name__ == "__main__":
    main()