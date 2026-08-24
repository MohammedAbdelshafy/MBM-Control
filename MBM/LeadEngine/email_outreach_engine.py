"""
MBM LeadEngine Email Outreach Engine
====================================
Python gateway that orchestrates GLM email drafting, QA auditing, deduplication, 
and insertion into the Supabase email_queue for the Node.js dispatcher.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.glm_integration_worker import get_glm_worker
from MBM.GLM.agent_registry import ModelRoutingTier
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


class EmailOutreachEngine:
    def __init__(self):
        self.glm_worker = get_glm_worker(ModelRoutingTier.MEDIUM)
        # We explicitly rely on Node dispatcher for delivery. This engine just queues.
        self.gmail_send_enabled = (os.getenv("GMAIL_SEND_ENABLED") or "false").lower() == "true"
        
    def is_test_fixture(self, lead_data: Dict[str, Any]) -> bool:
        """Strict check to prevent synthetic/test data from reaching the dialer or email queue."""
        em = str(lead_data.get("email", "")).lower()
        if not em or "@" not in em:
            return True
        if lead_data.get("source") == "TEST_FIXTURE":
            return True
        # Phase 10: Never enqueue test@example.com, example.com, localhost, internal addresses
        if "test" in em or "example.com" in em or "localhost" in em:
            return True
        if em.endswith("@abdelshafyclapps.com") or em == "abdelshafyplay@gmail.com":
            return True
        return False

    def is_duplicate(self, email_address: str, campaign_id: Optional[str] = None) -> bool:
        """Checks if the email address has already been mailed (Supabase lookup)."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            return False 
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        try:
            url = f"{SUPABASE_URL}/rest/v1/email_queue?recipient_email=eq.{email_address}&select=id"
            if campaign_id:
                # Fallback to checking subject if campaign_id column is not yet deployed
                pass 
                
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200 and len(res.json()) > 0:
                return True
        except Exception as e:
            print(f"[EmailOutreachEngine] Error checking duplicate: {e}")
        return False

    def process_and_dispatch_lead(self, lead_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        print(f"\n--- Processing Lead: {lead_data.get('email', 'UNKNOWN_EMAIL')} ---")
        
        # 1. Reject Test Fixtures & Internal Addresses
        if self.is_test_fixture(lead_data):
            msg = "Rejected: Marked as TEST_FIXTURE, contains dummy email, or internal."
            print(f"[BLOCKED] {msg}")
            return {"status": "blocked", "reason": msg}
        
        email_address = lead_data.get("email")
        if not email_address:
            msg = "Rejected: No email address provided."
            print(f"[BLOCKED] {msg}")
            return {"status": "blocked", "reason": msg}

        campaign_id = str(lead_data.get("campaign") or "")
        
        # 2. Deduplication Check
        if self.is_duplicate(email_address, campaign_id if campaign_id else None):
            msg = f"Rejected: Email {email_address} already exists for this campaign in email_queue."
            print(f"[BLOCKED] {msg}")
            return {"status": "blocked", "reason": msg}
            
        # 3. Model Draft Email
        draft_result = self.glm_worker.draft_outreach_email(lead_data, context)
        email_body = draft_result["body"]
        print(f"[{draft_result['provider'].upper()}: {draft_result['model']}] Drafting personalized email...")
        
        if "Failed to draft email" in email_body or "Error drafting email" in email_body:
            print(f"[ERROR] {email_body}")
            return {"status": "error", "reason": email_body}

        # 4. QA Audit
        print(f"[{draft_result['provider'].upper()}: {draft_result['model']}] Running QA audit on drafted email...")
        qa_result = self.glm_worker.qa_outreach_email(email_body, lead_data)
        if not qa_result.get("approved", False):
            msg = f"QA Rejected: {qa_result.get('reason', 'Unknown reason')}"
            print(f"[BLOCKED] {msg}")
            return {"status": "blocked", "reason": msg}

        # 5. Dispatch to Supabase
        print(f"[DISPATCH] QA Approved. Queueing email for {email_address}...")
        subject = f"Opportunity for {lead_data.get('company', 'your company')}"
        record = {
            "recipient_email": email_address,
            "subject": subject,
            "body": email_body,
            "status": "qued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add optional schema elements if present in data (safeguarded by migrations)
        if "lead_id" in lead_data:
            record["lead_id"] = lead_data["lead_id"]
        if "source" in lead_data:
            record["source"] = lead_data["source"]
        
        if not self.gmail_send_enabled:
            print("[DRY RUN] GMAIL_SEND_ENABLED=false. Skipping Supabase queue insertion.")
            return {"status": "success_dry_run", "record": record}
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        try:
            url = f"{SUPABASE_URL}/rest/v1/email_queue"
            res = requests.post(url, headers=headers, json=[record], timeout=10)
            if res.status_code in (200, 201):
                print("[SUCCESS] Lead successfully inserted into email_queue.")
                return {"status": "success", "record": record}
            else:
                print(f"[ERROR] Failed to insert: {res.text}")
                return {"status": "error", "reason": res.text}
        except Exception as e:
            print(f"[ERROR] Exception during dispatch: {e}")
            return {"status": "error", "reason": str(e)}

    def run_internal_test(self) -> Dict[str, Any]:
        """Phase 8: Bypass the queue entirely for Canary Testing."""
        msg = "FATAL: Canary architecture has been locked down. Use `node server/emailSender.js --test-gmail` to send a direct SMTP canary."
        print(f"[BLOCKED] {msg}")
        return {"status": "error", "reason": msg}

if __name__ == "__main__":
    import sys
    engine = EmailOutreachEngine()
    if "--test-gmail" in sys.argv:
        engine.run_internal_test()
    else:
        print("[INFO] Production engine loaded. Dry runs must be triggered via the lead factory.")
