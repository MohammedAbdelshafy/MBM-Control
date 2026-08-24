#!/usr/bin/env python3
"""
GLM Script Intelligence
=======================
Builds a reusable script-intelligence layer mapping lead provenance, segment,
and business signals to highly specific script structures, objection handling,
and follow-up timing.

NO generic medical fallbacks. NO invented facts.
"""

from typing import Dict, Any, List

# Defines the script logic mapped directly to niches
NICHE_SCRIPT_MAP = {
    "AI Consultancy & Automation": {
        "script_id": "SCRIPT_AI_CONSULTING_01",
        "opening": "Hi {name}, I saw {company} has been scaling recently. We help consultancies automate client onboarding.",
        "pain_angle": "Are you currently spending more than 10 hours a week on manual data entry and report generation?",
        "qualification_questions": [
            "What CRM or project management tools do you use?",
            "How many clients are you currently onboarding per month?"
        ],
        "objection_handling": {
            "too_expensive": "Our setup fee is covered by the time saved in the first month alone.",
            "not_interested": "Understood. Is automating operations a priority for Q3 or Q4?"
        },
        "cta": "Can we schedule a 15-minute technical discovery call next Tuesday?",
        "follow_up_strategy": "Email case study on workflow automation + LinkedIn connection request in 2 days."
    },
    "Commercial Contractors & ConTech": {
        "script_id": "SCRIPT_CONTECH_01",
        "opening": "Hi {name}, noticing {company}'s recent commercial projects. We build automated BOQ takeoff systems.",
        "pain_angle": "How many hours per week is your estimating team spending on manual DXF/CAD takeoffs?",
        "qualification_questions": [
            "Are you currently using Procore or PlanSwift?",
            "What is your average turnaround time for a commercial bid?"
        ],
        "objection_handling": {
            "too_expensive": "This system typically increases bid volume by 30% without adding headcount.",
            "not_interested": "No problem. Are you satisfied with your current bid win rate?"
        },
        "cta": "Can I send you a 2-minute video showing how it parses a standard commercial DXF?",
        "follow_up_strategy": "Email video demo + SMS text 1 day later."
    },
    # Add other niches as needed...
}

DEFAULT_SCRIPT = {
    "script_id": "SCRIPT_DEFAULT_01",
    "opening": "Hi {name}, reaching out to {company} regarding your current operations.",
    "pain_angle": "What is the biggest operational bottleneck you are facing right now?",
    "qualification_questions": ["What tools are you currently using to manage your workflow?"],
    "objection_handling": {
        "too_expensive": "We focus on ROI and operational efficiency.",
        "not_interested": "Understood, thank you for your time."
    },
    "cta": "Can we schedule a brief call next week?",
    "follow_up_strategy": "Email in 3 days."
}


class ScriptIntelligence:
    def __init__(self):
        self.script_map = NICHE_SCRIPT_MAP

    def generate_script_strategy(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a segment-specific script strategy based on lead provenance.
        """
        niche = lead_data.get("niche", "UNCLASSIFIED")
        name = lead_data.get("contact", "there")
        company = lead_data.get("company", "your business")
        
        template = self.script_map.get(niche, DEFAULT_SCRIPT).copy()
        
        # Personalize template
        template["opening"] = template["opening"].format(name=name, company=company)
        template["niche_matched"] = niche
        template["confidence"] = 0.95 if niche in self.script_map else 0.50
        
        return template

if __name__ == "__main__":
    engine = ScriptIntelligence()
    sample_lead = {"contact": "John", "company": "Texas Builders Inc.", "niche": "Commercial Contractors & ConTech"}
    print(engine.generate_script_strategy(sample_lead))
