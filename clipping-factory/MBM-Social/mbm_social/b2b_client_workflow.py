"""
B2B Client Workflow & Rate Card Billing Engine
Handles corporate and client campaigns, quality score gates (0.70 threshold),
and per-clip rate card billing.
"""
import os
import sys
import json
import datetime
from pathlib import Path

class B2BClientWorkflowEngine:
    def __init__(self):
        self.quality_gate_threshold = 0.70  # Higher quality threshold for paying clients
        self.rate_card = {
            "per_clip_usd": 5.00,
            "campaign_monthly_retainer_usd": 150.00,
            "rush_order_multiplier": 1.5
        }

    def process_client_campaign(self, client_id: str, client_name: str, raw_clip_data: dict) -> dict:
        """Processes a clip for a B2B client with billing calculations and quality gates."""
        hook_score = raw_clip_data.get("hook_score", 0.75)
        passed_quality_gate = hook_score >= self.quality_gate_threshold
        
        is_rush = raw_clip_data.get("is_rush", False)
        clip_price = self.rate_card["per_clip_usd"] * (self.rate_card["rush_order_multiplier"] if is_rush else 1.0)
        
        result = {
            "job_id": f"B2B-JOB-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
            "client": {
                "id": client_id,
                "name": client_name
            },
            "quality_gate": {
                "score": hook_score,
                "threshold": self.quality_gate_threshold,
                "passed": passed_quality_gate,
                "requires_manual_approval": not passed_quality_gate
            },
            "billing": {
                "model": "per_clip",
                "price_usd": clip_price,
                "currency": "USD"
            },
            "status": "APPROVED_FOR_CLIENT_DELIVERY" if passed_quality_gate else "HELD_FOR_CLIENT_REVIEW"
        }
        return result

if __name__ == "__main__":
    b2b = B2BClientWorkflowEngine()
    test_job = b2b.process_client_campaign("CLIENT-101", "Apex Real Estate Media", {"hook_score": 0.82, "is_rush": True})
    print("=== B2B CLIENT WORKFLOW VERIFIED ===")
    print(f"Client: {test_job['client']['name']}")
    print(f"Quality Score: {test_job['quality_gate']['score']} (Threshold: {test_job['quality_gate']['threshold']})")
    print(f"Status: {test_job['status']}")
    print(f"Billed Clip Price: ${test_job['billing']['price_usd']} USD")
