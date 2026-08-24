#!/usr/bin/env python3
"""
GLM Revenue Intelligence
========================
Identifies high-fit prospects and high-intent signals.
Ranks opportunities using measurable evidence.
Recommends best offer, best channel, and best script.
"""

from typing import Dict, Any, List

class RevenueIntelligence:
    def __init__(self):
        # Baseline scoring weights
        self.weights = {
            "has_decision_maker": 30,
            "has_verified_phone": 30,
            "has_verified_email": 20,
            "recent_activity_signal": 10,
            "high_value_niche": 10
        }

    def score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores a lead based on evidence. Returns score and recommended action.
        """
        score = 0
        evidence = []
        
        # 1. Contact Info
        contact = lead_data.get("contact", "")
        if contact and contact.lower() not in ["unknown", "n/a", "info"]:
            score += self.weights["has_decision_maker"]
            evidence.append("Decision maker identified.")
            
        # 2. Phone
        phone = str(lead_data.get("phone", ""))
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) >= 10 and not phone.startswith("000"):
            score += self.weights["has_verified_phone"]
            evidence.append("Verified phone length/format.")
            
        # 3. Email
        email = lead_data.get("email", "")
        if email and "@" in email:
            score += self.weights["has_verified_email"]
            evidence.append("Email present.")
            
        # 4. Niche Value
        niche = lead_data.get("niche", "UNCLASSIFIED")
        if niche in ["AI Consultancy & Automation", "Commercial Contractors & ConTech"]:
            score += self.weights["high_value_niche"]
            evidence.append("High-value target niche.")
            
        # 5. Activity Signal
        details = lead_data.get("details", {})
        if details.get("recent_funding") or details.get("hiring") or details.get("recent_project"):
            score += self.weights["recent_activity_signal"]
            evidence.append("Recent business activity signal detected.")

        # Determine Tier and Recommendations
        if score >= 80:
            tier = "Tier A"
            action = "IMMEDIATE_DIAL_FRESH_CALL_NOW"
            channel = "DIALER"
        elif score >= 60:
            tier = "Tier B"
            action = "SCHEDULED_OUTREACH"
            channel = "EMAIL_THEN_DIAL"
        else:
            tier = "Tier C"
            action = "NURTURE_OR_ENRICH"
            channel = "SOCIAL_OR_EMAIL"
            
        return {
            "score": score,
            "tier": tier,
            "recommended_action": action,
            "recommended_channel": channel,
            "evidence": evidence
        }

if __name__ == "__main__":
    engine = RevenueIntelligence()
    sample_lead = {
        "contact": "Jane Doe",
        "phone": "2145551234",
        "niche": "AI Consultancy & Automation",
        "details": {"hiring": True}
    }
    print(engine.score_lead(sample_lead))
