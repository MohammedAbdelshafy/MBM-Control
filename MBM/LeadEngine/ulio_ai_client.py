"""
Ulio.ai AI Voice Agent & Telephony Integration Client
=====================================================
White-label B2B AI Receptionist, Lead Finder, Inbound/Outbound Telephony API.

Features:
  1. Auto-build AI Receptionist Agent by URL or Custom Persona.
  2. Outbound Cold Calling & Lead Follow-up.
  3. Inbound Call Handling & Live Appointment Scheduling.
  4. Webhook Reconciler for CRM / MBM Lead Engine.
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

ULIO_API_KEY = os.getenv("ULIO_API_KEY", "")
ULIO_BASE_URL = os.getenv("ULIO_BASE_URL", "https://api.ulio.ai/v1")

class UlioAIClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ULIO_API_KEY
        self.base_url = ULIO_BASE_URL.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MBM-LeadEngine-UlioAI/1.0"
        }

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def create_voice_agent(self, name: str, website_url: str = "", persona_prompt: str = "") -> Dict[str, Any]:
        """Create or clone a 60-second Ulio.ai Voice Receptionist from website URL or custom prompt."""
        if not self.is_configured():
            # Simulated response if API key not set yet
            return {
                "status": "success_simulated",
                "agent_id": f"ulio-agent-{int(datetime.now().timestamp())}",
                "name": name,
                "website_url": website_url,
                "created_at": datetime.now().isoformat(),
                "message": "Simulated Ulio.ai Agent Creation. Set ULIO_API_KEY in .env for live API."
            }

        endpoint = f"{self.base_url}/agents/create"
        payload = {
            "name": name,
            "website_url": website_url,
            "persona_prompt": persona_prompt,
            "settings": {
                "inbound_appointment_booking": True,
                "sms_followup_enabled": True,
                "voice_type": "natural_female_professional"
            }
        }
        try:
            res = requests.post(endpoint, headers=self.headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return res.json()
            else:
                return {"status": "error", "code": res.status_code, "error": res.text}
        except Exception as e:
            return {"status": "error", "exception": str(e)}

    def make_outbound_call(self, phone: str, agent_id: str, lead_name: str = "Customer", script_vars: Optional[Dict] = None) -> Dict[str, Any]:
        """Trigger an outbound AI call via Ulio.ai Voice Engine."""
        if not self.is_configured():
            return {
                "status": "initiated_simulated",
                "call_id": f"ulio-call-{int(datetime.now().timestamp())}",
                "to_phone": phone,
                "lead_name": lead_name,
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat()
            }

        endpoint = f"{self.base_url}/calls/outbound"
        payload = {
            "agent_id": agent_id,
            "to_phone": phone,
            "variables": {
                "lead_name": lead_name,
                **(script_vars or {})
            }
        }
        try:
            res = requests.post(endpoint, headers=self.headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return res.json()
            else:
                return {"status": "error", "code": res.status_code, "error": res.text}
        except Exception as e:
            return {"status": "error", "exception": str(e)}

    def batch_outreach(self, leads: List[Dict[str, Any]], agent_id: str) -> Dict[str, Any]:
        """Dispatch batch AI voice calls across a list of verified leads."""
        results = []
        initiated = 0
        for lead in leads:
            phone = lead.get("phone")
            name = lead.get("contact") or lead.get("name", "Prospect")
            if not phone or "N/A" in phone:
                continue
            res = self.make_outbound_call(phone, agent_id, name, script_vars=lead.get("details"))
            results.append(res)
            initiated += 1

        return {
            "status": "completed",
            "total_leads": len(leads),
            "calls_initiated": initiated,
            "results": results
        }

if __name__ == "__main__":
    client = UlioAIClient()
    print("Testing Ulio.ai Integration...")
    agent = client.create_voice_agent("MBM Healthcare Receptionist", "https://advantage-medical.com")
    print("Agent Result:", json.dumps(agent, indent=2))
    call = client.make_outbound_call("+12145550199", agent.get("agent_id", "demo"), "Dr. Alvarado")
    print("Call Result:", json.dumps(call, indent=2))
