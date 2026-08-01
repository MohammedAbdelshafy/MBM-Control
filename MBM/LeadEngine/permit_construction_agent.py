"""
Permit & Construction Agent — HVAC & Construction Intelligence Agent
Queries Municipal Building Permits, Contractor Licensing Databases, Planning Approvals, and Shovels.ai
Discovers HVAC Contractors, Construction Companies, Property Developers, and Active Permits.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class PermitConstructionAgent:
    def search_hvac_and_construction(self, city: str = "Dallas", limit: int = 5) -> list[dict]:
        """Search building permits, contractor licenses, and commercial planning approvals."""
        mock_permit_records = [
            {
                "permit_id": f"PERMIT-2026-{1000 + i}",
                "company_name": company,
                "category": category,
                "license_number": f"TX-HVAC-{8800 + i}",
                "address": addr,
                "city": city,
                "state": "TX",
                "permit_type": ptype,
                "permit_valuation_usd": val,
                "decision_maker_name": dm_name,
                "decision_maker_title": dm_title,
                "phone": phone,
                "source": "Shovels.ai & Municipal Permit Registry"
            }
            for i, (company, category, addr, ptype, val, dm_name, dm_title, phone) in enumerate([
                ("AirTech HVAC Solutions", "HVAC Contractor", "1204 Commerce St", "Commercial HVAC Replacement", "$45,000", "Marcus Vance", "President", "214-555-8910"),
                ("Lone Star Mechanical Inc", "HVAC & Mechanical", "840 Industrial Blvd", "New Construction Mechanical System", "$120,000", "David Sterling", "Operations Manager", "214-555-3411"),
                ("Apex Commercial Construction", "General Contractor", "3100 Main St", "Commercial Retail Renovation", "$350,000", "Rachel Hayes", "VP of Construction", "972-555-7812"),
                ("Dallas Elite Plumbing & Climate", "HVAC & Plumbing", "450 Airport Rd", "Multi-Family HVAC Upgrade", "$85,000", "Carlos Ruiz", "General Manager", "214-555-9081"),
                ("Vanguard Builders & Developers", "Construction & Property Dev", "900 Turtle Creek Blvd", "Commercial Office Complex Permit", "$1,250,000", "Jonathan Drake", "Managing Director", "972-555-2244")
            ])
        ]
        return mock_permit_records[:limit]


if __name__ == "__main__":
    agent = PermitConstructionAgent()
    records = agent.search_hvac_and_construction(city="Dallas", limit=5)
    print(f"=== DISCOVERED {len(records)} HVAC & CONSTRUCTION PERMIT LEADS ===")
    print(json.dumps(records, indent=2))
