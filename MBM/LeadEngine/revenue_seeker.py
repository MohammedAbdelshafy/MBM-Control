"""
Revenue Seeker Agent — High-Converting Opportunity Hunter
===========================================================
Mission: Actively seek high-value distress real estate & industrial by-product deals
across global markets. Prioritizes deals with the Antigravity Priority Score (Tier A/B/C)
and seeds verified opportunities into the pipeline.

Scoring Formula (Antigravity Priority Score):
  - 30% Decision Maker Quality (verified contact, owner/manager role)
  - 20% Asset / Material Match (distress property, plastic/scrap match)
  - 15% Volume / Asset Value (high upside potential)
  - 10% Location / Market Quality (active target city)
  - 10% Contact Data Confidence (phone + domain email)
  - 15% Closing Probability (motivated seller indicators)
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
GLOBAL_LEADS_FILE = BASE_DIR / 'global_leads.json'
SEEKER_LOG_FILE = LOGS_DIR / 'seeker_opportunities.json'
QUEUE_FILE = BASE_DIR / 'cold_calling_queue.json'

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[REVENUE SEEKER] {timestamp} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))
    log_file = LOGS_DIR / 'revenue_seeker.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _load_json(path, default=None):
    if default is None:
        default = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


class RevenueSeeker:
    """Seeker Agent — Finds and prioritizes high-confidence matched deals."""

    def __init__(self):
        self.log_file = SEEKER_LOG_FILE

    def compute_antigravity_score(self, lead):
        """
        Calculate Antigravity Priority Score (0-100%):
          - 30% Decision Maker Quality
          - 20% Asset Match
          - 15% Volume / Price Value
          - 10% Location
          - 10% Contact Confidence
          - 15% Closing Probability
        """
        score = 0.0

        agent = str(lead.get('agent', '') or lead.get('contact_name', '')).lower()
        phone = lead.get('phone') or lead.get('agent_phone')
        email = lead.get('email') or lead.get('agent_email')
        address = str(lead.get('address', '')).lower()
        price_str = str(lead.get('price', '')).lower()
        is_distress = lead.get('is_distress', False) or 'auction' in agent or 'distress' in address

        # 1. Decision Maker Quality (Max 30 pts)
        if any(role in agent for role in ['owner', 'director', 'manager', 'head', 'vp', 'executive']):
            score += 30.0
        elif agent and agent != 'real estate agent':
            score += 20.0
        else:
            score += 10.0

        # 2. Asset Match (Max 20 pts)
        if is_distress or 'auction' in agent or 'offers' in address:
            score += 20.0
        elif lead.get('is_lead', False):
            score += 15.0
        else:
            score += 10.0

        # 3. Volume / Price Value (Max 15 pts)
        if any(char.isdigit() for char in price_str):
            score += 15.0
        else:
            score += 8.0

        # 4. Location Quality & 80%+ US Market Dominance Bonus (Max 20 pts)
        us_priority_cities = ['new york', 'miami', 'los angeles', 'austin', 'chicago', 'houston', 'dallas', 'phoenix', 'atlanta', 'las vegas', 'seattle', 'tampa', 'orlando', 'san diego']
        global_priority_cities = ['manchester', 'london', 'birmingham', 'madrid', 'barcelona']
        
        is_us_deal = any(city in address for city in us_priority_cities) or '$' in price_str or 'usa' in address or 'tx' in address or 'fl' in address or 'ca' in address or 'ny' in address or 'zillow' in lead.get('id', '').lower()
        
        if is_us_deal:
            score += 20.0  # +10.0 US Dominance Bonus
        elif any(city in address for city in global_priority_cities):
            score += 10.0
        else:
            score += 6.0

        # 5. Contact Data Confidence (Max 10 pts)
        if phone and email:
            score += 10.0
        elif phone or email:
            score += 6.0
        else:
            score += 2.0

        # 6. Closing Probability (Max 15 pts)
        if is_distress:
            score += 15.0
        elif 'cash' in address or 'reduced' in price_str:
            score += 12.0
        else:
            score += 8.0

        return round(score, 1)

    def assign_tier(self, score):
        if score >= 75.0:
            return 'A'
        elif score >= 55.0:
            return 'B'
        else:
            return 'C'

    def estimate_commission(self, lead):
        """Estimate deal revenue / expected commission."""
        price_raw = str(lead.get('price', '0'))
        import re
        nums = re.findall(r'\d+', price_raw.replace(',', ''))
        val = int(nums[0]) if nums else 250000
        # Standard assignment / brokerage fee: 2% - 3%
        commission = round(val * 0.025, 2)
        return commission

    def seek_opportunities(self, target=30, markets=None):
        """
        Actively seek deals from scrapers / lead engines and prioritize them.
        """
        if not markets:
            markets = ["manchester", "london", "birmingham", "new york", "madrid"]

        log(f"SEEKING OPPORTUNITIES: Target = {target} deals across {len(markets)} markets...")

        # Load existing leads
        leads = _load_json(GLOBAL_LEADS_FILE, [])
        if not isinstance(leads, list):
            leads = []

        scored_leads = []
        tier_a_count = 0
        tier_b_count = 0
        tier_c_count = 0
        total_commission = 0.0

        for lead in leads:
            score = self.compute_antigravity_score(lead)
            tier = self.assign_tier(score)
            comm = self.estimate_commission(lead)

            lead['antigravity_priority_score'] = score
            lead['tier'] = tier
            lead['expected_commission'] = comm

            if tier == 'A':
                tier_a_count += 1
            elif tier == 'B':
                tier_b_count += 1
            else:
                tier_c_count += 1

            total_commission += comm
            scored_leads.append(lead)

        # Sort leads by highest priority score
        scored_leads.sort(key=lambda x: x.get('antigravity_priority_score', 0), reverse=True)

        # Write prioritized output
        _save_json(GLOBAL_LEADS_FILE, scored_leads)

        opportunities_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": target,
            "markets": markets,
            "total_found": len(scored_leads),
            "tier_breakdown": {
                "Tier_A": tier_a_count,
                "Tier_B": tier_b_count,
                "Tier_C": tier_c_count,
            },
            "total_estimated_commission": f"${total_commission:,.2f}",
            "top_tier_a_opportunities": [
                {
                    "id": l.get("id"),
                    "agent": l.get("agent"),
                    "address": l.get("address"),
                    "price": l.get("price"),
                    "score": l.get("antigravity_priority_score"),
                    "tier": l.get("tier"),
                    "expected_commission": f"${l.get('expected_commission'):,.2f}",
                }
                for l in scored_leads if l.get("tier") == "A"
            ][:10],
        }

        _save_json(SEEKER_LOG_FILE, opportunities_report)
        log(f"SEEK COMPLETE: Found {len(scored_leads)} deals. Tier A: {tier_a_count}, Tier B: {tier_b_count}. Total Commission Potential: ${total_commission:,.2f}")

        return {
            "status": "success" if scored_leads else "failure",
            "total_found": len(scored_leads),
            "tier_a": tier_a_count,
            "tier_b": tier_b_count,
            "total_commission": total_commission,
            "opportunities_file": str(SEEKER_LOG_FILE),
        }


# ─── Self-Test ───
def _run_self_test():
    print("=" * 60)
    print("REVENUE SEEKER AGENT — SELF-TEST")
    print("=" * 60)

    seeker = RevenueSeeker()
    res = seeker.seek_opportunities(target=30)

    print(json.dumps(res, indent=2))
    print("=" * 60)
    print("SEEKER SELF-TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Revenue Seeker Agent")
    parser.add_argument("command", nargs="?", default="seek", choices=["seek", "test"])
    args = parser.parse_args()

    if args.command == "test":
        _run_self_test()
    else:
        seeker = RevenueSeeker()
        res = seeker.seek_opportunities()
        print(json.dumps(res, indent=2))
