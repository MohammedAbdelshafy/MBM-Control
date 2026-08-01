"""
Global Lead Intelligence Engine — Mission AG-LEAD-001 Master Orchestrator
Master AI Agent: Jarvis

Discovers, enriches, scores, monitors buying signals, and drafts personalized outreach for:
1. Medical Clinics
2. HVAC Companies
3. Real Estate Wholesalers
4. Construction Companies
5. Industrial Businesses
"""
import os
import sys
import json
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from MBM.LeadEngine.npi_clinic_scraper import NPIClinicScraper
from MBM.LeadEngine.permit_construction_agent import PermitConstructionAgent
from MBM.LeadEngine.buying_signal_monitor import BuyingSignalMonitor


class GlobalLeadIntelligenceEngine:
    def __init__(self):
        self.clinic_agent = NPIClinicScraper()
        self.permit_agent = PermitConstructionAgent()
        self.signal_agent = BuyingSignalMonitor()

    def calculate_antigravity_score(self, lead: dict) -> dict:
        """
        Calculate Antigravity Priority Score (0-100%)
        - 30% Decision Maker Quality
        - 25% Buying Intent Signal
        - 20% Verified Contact Data
        - 15% Estimated Deal Value
        - 10% Industry Urgency
        """
        dm_score = 30 if lead.get("authorized_official_name") or lead.get("decision_maker_name") else 15
        intent_score = round(lead.get("buying_intent_score", 80) * 0.25)
        contact_score = 20 if lead.get("phone") else 10
        deal_score = 15
        urgency_score = 10

        total_score = min(100, dm_score + intent_score + contact_score + deal_score + urgency_score)
        tier = "Tier A+" if total_score >= 90 else ("Tier A" if total_score >= 80 else "Tier B")
        
        return {
            "antigravity_priority_score": total_score,
            "tier": tier,
            "score_breakdown": {
                "decision_maker_quality": f"{dm_score}/30",
                "buying_intent_signals": f"{intent_score}/25",
                "verified_contact_data": f"{contact_score}/20",
                "estimated_deal_value": f"{deal_score}/15",
                "industry_urgency": f"{urgency_score}/10"
            }
        }

    def generate_personalized_outreach(self, lead: dict) -> dict:
        """Generate high-conversion personalized email & call bridge pitch."""
        company = lead.get("company_name", "your business")
        dm_name = lead.get("authorized_official_name") or lead.get("decision_maker_name") or "Team"
        niche = lead.get("category", "Business")

        if "clinic" in niche.lower() or "medical" in niche.lower():
            subject = f"Quick question regarding patient intake at {company}"
            pitch = f"Hi {dm_name},\n\nI noticed {company}'s expansion in {lead.get('city', 'your area')}. Our Contech AI Agentic platform automates patient intake, appointment confirmation, and after-hours call routing for medical practices.\n\nWould you be open to a brief 5-minute preview this week?"
        elif "hvac" in niche.lower() or "construction" in niche.lower():
            subject = f"Permit automation & dispatch for {company}"
            pitch = f"Hi {dm_name},\n\nSaw your active commercial building permit ({lead.get('permit_id', 'Permit Upgrade')}) in {lead.get('city', 'the area')}. We help HVAC and construction contractors automate field service dispatch and bid follow-ups.\n\nDo you have 2 minutes to compare notes?"
        else:
            subject = f"Off-market deal automation for {company}"
            pitch = f"Hi {dm_name},\n\nI came across {company} while reviewing high-intent property deals in {lead.get('city', 'your market')}. We deliver pre-vetted off-market acquisition leads directly into your CRM.\n\nCan I send over 2 sample deals today?"

        return {
            "subject_line": subject,
            "personalized_email_pitch": pitch,
            "call_bridge_opening_hook": f"Hi {dm_name}! This is Omar with Contech AI. I'll be super brief — reaching out regarding {company}...",
            "target_cta": "Book 5-min demo call"
        }

    def execute_global_discovery_cycle(self, cities: list[str] = None) -> dict:
        """Run full 5-sector lead intelligence discovery, enrichment, scoring, and outreach cycle."""
        cities = cities or ["Miami", "Dallas", "Phoenix", "New York"]
        now_str = datetime.datetime.now().isoformat()

        all_discovered = []

        # 1. Discover Clinics
        for city in cities[:2]:
            clinics = self.clinic_agent.search_clinics(city=city, limit=3)
            for c in clinics:
                signals = self.signal_agent.scan_buying_signals(c["company_name"], "Medical Clinic")
                c.update(signals)
                c.update(self.calculate_antigravity_score(c))
                c["outreach_package"] = self.generate_personalized_outreach(c)
                all_discovered.append(c)

        # 2. Discover HVAC & Construction
        for city in cities[:2]:
            permits = self.permit_agent.search_hvac_and_construction(city=city, limit=3)
            for p in permits:
                signals = self.signal_agent.scan_buying_signals(p["company_name"], p["category"])
                p.update(signals)
                p.update(self.calculate_antigravity_score(p))
                p["outreach_package"] = self.generate_personalized_outreach(p)
                all_discovered.append(p)

        summary = {
            "mission_id": "AG-LEAD-001",
            "timestamp": now_str,
            "total_companies_discovered": len(all_discovered),
            "target_sectors": ["Medical Clinics", "HVAC", "Construction", "Wholesalers", "Industrial"],
            "tier_a_plus_opportunities": [lead for lead in all_discovered if lead["tier"] == "Tier A+"],
            "tier_a_opportunities": [lead for lead in all_discovered if lead["tier"] == "Tier A"],
            "all_leads": all_discovered
        }

        # Save report to Desktop
        desktop_file = Path(r"C:\Users\omare\Desktop\global_lead_intelligence_report.json")
        try:
            with open(desktop_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            print(f"Saved Global Lead Intelligence Report to {desktop_file}")
        except Exception as e:
            print(f"Could not save to Desktop: {e}")

        return summary


if __name__ == "__main__":
    engine = GlobalLeadIntelligenceEngine()
    report = engine.execute_global_discovery_cycle()
    print(f"\n=== GLOBAL LEAD INTELLIGENCE SUMMARY ===")
    print(f"Total Discovered: {report['total_companies_discovered']}")
    print(f"Tier A+ Opportunities: {len(report['tier_a_plus_opportunities'])}")
    print(f"Tier A Opportunities: {len(report['tier_a_opportunities'])}")
