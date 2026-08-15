#!/usr/bin/env python3
"""
Phase 4: Priority Ranking
=========================
Rank recovered candidates against existing 702 leads.
"""

import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
LEADENGINE_DIR = ROOT / "MBM" / "LeadEngine"
LOGS_DIR = ROOT / "logs" / "recovery"

DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
DIALER_GATE_RESULTS = LOGS_DIR / "dialer_gate_results.json"
OUTPUT_DIR = LOGS_DIR

def load_json(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_priority_score(lead: dict, dialer_leads: list) -> dict:
    """Calculate priority score for a lead."""
    score = 0
    signals = []
    
    # 1. Verified callable phone (max 20 points)
    if lead.get('verification', {}).get('phone_ok', False):
        score += 20
        signals.append('verified_phone')
    
    # 2. Seller intent / motivation (max 25 points)
    motivation_score = lead.get('motivation_score', 0)
    if motivation_score >= 70:
        score += 25
        signals.append('high_motivation')
    elif motivation_score >= 50:
        score += 15
        signals.append('medium_motivation')
    elif motivation_score >= 30:
        score += 8
        signals.append('low_motivation')
    
    # 3. Multiple corroborating signals (max 15 points)
    motivation_signals = lead.get('motivation_signals', [])
    signal_count = len(motivation_signals)
    if signal_count >= 3:
        score += 15
        signals.append('multi_signal')
    elif signal_count == 2:
        score += 10
        signals.append('dual_signal')
    elif signal_count == 1:
        score += 5
        signals.append('single_signal')
    
    # 4. Freshness (max 10 points) - based on presence in multiple queues
    # The RE queue is the primary source; check if also in other queues
    in_cold = lead.get('in_cold_queue', False)
    in_multi = lead.get('in_multi_queue', False)
    in_ulio = lead.get('in_ulio_queue', False)
    multi_queue_count = sum([in_cold, in_multi, in_ulio])
    if multi_queue_count >= 2:
        score += 10
        signals.append('multi_source')
    elif multi_queue_count == 1:
        score += 5
        signals.append('secondary_source')
    
    # 5. High equity indicators (max 10 points)
    est_arv = lead.get('est_arv')
    asking_price = lead.get('asking_price')
    target_offer = lead.get('target_cash_offer')
    equity_score = 0
    if est_arv and asking_price:
        try:
            arv = float(str(est_arv).replace('$', '').replace(',', ''))
            ask = float(str(asking_price).replace('$', '').replace(',', ''))
            if arv > 0:
                equity_pct = (arv - ask) / arv
                if equity_pct > 0.3:
                    equity_score = 10
                    signals.append('high_equity')
                elif equity_pct > 0.15:
                    equity_score = 7
                    signals.append('medium_equity')
                elif equity_pct > 0:
                    equity_score = 3
                    signals.append('some_equity')
        except:
            pass
    score += equity_score
    
    # 6. Vacancy indicators (max 8 points)
    if 'vacant' in str(lead.get('distress_signal', '')).lower():
        score += 8
        signals.append('vacant')
    if 'absentee' in motivation_signals:
        score += 5
        signals.append('absentee_owner')
    
    # 7. Absentee/out-of-state ownership (max 7 points)
    # Check city/state vs contact info
    contact_state = lead.get('state', '').upper()
    # If we had owner address vs property address, we could score this
    # For now, give points for absentee signal
    if 'absentee' in motivation_signals:
        score += 5
    
    # 8. Ownership tenure - not available in current data
    # Skip for now
    
    # 9. Distress/condition signals (max 5 points)
    distress = str(lead.get('distress_signal', '')).lower()
    distress_keywords = ['code', 'violation', 'foreclosure', 'tax', 'lien', 'damage', 'fire', 'repair']
    distress_count = sum(1 for kw in distress_keywords if kw in distress)
    if distress_count >= 2:
        score += 5
        signals.append('multi_distress')
    elif distress_count == 1:
        score += 3
        signals.append('distress')
    
    # 10. Property/deal suitability (max 5 points)
    # Based on vertical and role type
    if lead.get('role_type') == 'Seller':
        score += 3
        signals.append('direct_seller')
    if lead.get('vertical') == 'Master Catch-All':
        score += 2
        signals.append('priority_vertical')
    
    # Confidence calculation
    confidence_factors = 0
    if lead.get('verification', {}).get('phone_ok'): confidence_factors += 1
    if lead.get('verification', {}).get('name_ok'): confidence_factors += 1
    if lead.get('verification', {}).get('verified_ok'): confidence_factors += 1
    if not lead.get('is_placeholder'): confidence_factors += 1
    if lead.get('skip_trace_status') == 'VERIFIED': confidence_factors += 1
    
    confidence = 'high' if confidence_factors >= 4 else 'medium' if confidence_factors >= 2 else 'low'
    
    # Why call now
    why_parts = []
    if motivation_score >= 70:
        why_parts.append(f"High motivation ({motivation_score})")
    if 'absentee_owner' in signals:
        why_parts.append("Absentee owner")
    if 'high_equity' in signals:
        why_parts.append("High equity")
    if 'vacant' in signals:
        why_parts.append("Vacant property")
    if 'code_concern' in motivation_signals:
        why_parts.append("Code violations")
    if 'rental_registration' in motivation_signals:
        why_parts.append("Rental registration")
    why_call_now = '; '.join(why_parts) if why_parts else "Qualified lead"
    
    return {
        'priority_score': score,
        'top_signals': signals,
        'confidence': confidence,
        'why_call_now': why_call_now,
        'signal_breakdown': {
            'motivation': min(25, (motivation_score / 100) * 25),
            'signals': min(15, signal_count * 5),
            'multi_source': multi_queue_count * 5,
            'equity': equity_score,
            'vacancy_absentee': 5 if 'absentee' in motivation_signals else 0,
            'distress': distress_count * 2
        }
    }

def main():
    print("=" * 80)
    print("PHASE 4: PRIORITY RANKING")
    print("=" * 80)
    
    # Load data
    dialer = load_json(DIALER_DB)
    dialer_gate = load_json(DIALER_GATE_RESULTS)
    verified_leads = dialer_gate['verified_leads']
    
    print(f"Existing dialer leads: {len(dialer)}")
    print(f"Recovered verified leads: {len(verified_leads)}")
    
    # Calculate priority for recovered leads
    ranked_recovered = []
    for lead in verified_leads:
        priority = calculate_priority_score(lead, dialer)
        ranked_lead = {**lead, **priority}
        ranked_recovered.append(ranked_lead)
    
    # Sort by priority score descending
    ranked_recovered.sort(key=lambda x: -x['priority_score'])
    
    # Add rank
    for i, lead in enumerate(ranked_recovered):
        lead['priority_rank'] = i + 1
    
    # Also rank existing dialer leads for comparison
    ranked_dialer = []
    for lead in dialer:
        # Build similar structure for dialer leads
        dialer_lead = {
            'phone': lead.get('phone'),
            'name': lead.get('contact') or lead.get('company'),
            'company': lead.get('company'),
            'motivation_score': lead.get('motivation_score') or lead.get('deal_score'),
            'motivation_tier': lead.get('motivation_tier'),
            'motivation_signals': lead.get('details', {}).get('motivation_signals', []),
            'skip_trace_status': lead.get('skip_trace_status'),
            'vertical': lead.get('vertical'),
            'role_type': 'Seller' if 'seller' in (lead.get('vertical', '') or '').lower() else 'Other',
            'verification': {'phone_ok': True, 'name_ok': True, 'verified_ok': True},
            'is_placeholder': False
        }
        priority = calculate_priority_score(dialer_lead, dialer)
        ranked_dialer.append({**dialer_lead, **priority})
    
    ranked_dialer.sort(key=lambda x: -x['priority_score'])
    for i, lead in enumerate(ranked_dialer):
        lead['priority_rank'] = i + 1
    
    # Combined ranking
    combined = ranked_recovered + ranked_dialer
    combined.sort(key=lambda x: -x['priority_score'])
    for i, lead in enumerate(combined):
        lead['combined_rank'] = i + 1
    
    # Save results
    output = {
        'recovered_ranked': ranked_recovered,
        'dialer_ranked': ranked_dialer,
        'combined_ranked': combined,
        'summary': {
            'total_recovered': len(ranked_recovered),
            'total_dialer': len(ranked_dialer),
            'recovered_score_range': f"{ranked_recovered[-1]['priority_score']} - {ranked_recovered[0]['priority_score']}",
            'dialer_score_range': f"{ranked_dialer[-1]['priority_score']} - {ranked_dialer[0]['priority_score']}",
            'top_recovered_score': ranked_recovered[0]['priority_score'] if ranked_recovered else 0,
            'top_dialer_score': ranked_dialer[0]['priority_score'] if ranked_dialer else 0,
        }
    }
    
    output_path = OUTPUT_DIR / "priority_ranking.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n[OK] Priority ranking saved: {output_path}")
    
    print(f"\n{'='*80}")
    print("RECOVERED LEADS - PRIORITY RANKING:")
    print(f"Score range: {output['summary']['recovered_score_range']}")
    print(f"Top recovered score: {output['summary']['top_recovered_score']}")
    print(f"Top dialer score: {output['summary']['top_dialer_score']}")
    
    print(f"\nTOP 20 RECOVERED LEADS:")
    for lead in ranked_recovered[:20]:
        print(f"  #{lead['priority_rank']:2d} [{lead['priority_score']:2d}] {lead['name']} ({lead['phone']}) - {lead['why_call_now']}")
        print(f"         Confidence: {lead['confidence']} | Signals: {', '.join(lead['top_signals'])}")
    
    print(f"\n{'='*80}")
    print("COMBINED TOP 30 (Recovered + Existing):")
    for lead in combined[:30]:
        source = "RECOVERED" if lead in ranked_recovered else "EXISTING"
        print(f"  #{lead['combined_rank']:2d} [{lead['priority_score']:2d}] {source} {lead['name']} ({lead['phone']})")
    
    return output

if __name__ == "__main__":
    main()