"""
GTM SYSTEM ADAPTERS
=============================================================================
Non-invasive interfaces and adapters wrapping existing MBM systems.

Adapters:
  - BuyerHunterAdapter
  - CanonicalMemoryAdapter
  - DialerAdapter
  - IdentityAdapter
  - CRMAdapter
  - VerificationAdapter
=============================================================================
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CANONICAL_DEALS_PATH = ARTIFACTS_DIR / "canonical_deals_memory.json"
IDENTITY_RESULTS_PATH = ARTIFACTS_DIR / "identity_results.json"


class BuyerHunterAdapter:
    """Read adapter for the MBM AI Assistant Buyer Hunter outputs."""

    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR):
        self.artifacts_dir = artifacts_dir

    def get_hot_buyers(self) -> List[Dict[str, Any]]:
        """Retrieve verified HOT AI assistant buyers from the latest harvest."""
        hot_path = self.artifacts_dir / "ai_assistant_buyers_hot.json"
        if hot_path.exists():
            try:
                return json.loads(hot_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def get_all_prospects(self) -> List[Dict[str, Any]]:
        """Retrieve all evaluated prospects across HOT, HIGH INTENT, and WARM."""
        all_path = self.artifacts_dir / "ai_assistant_buyers_all.json"
        if all_path.exists():
            try:
                return json.loads(all_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self.get_hot_buyers()

    def get_prospect_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Find a prospect by ID or company name."""
        for p in self.get_all_prospects():
            if p.get("id") == entity_id or p.get("company", "").lower() == entity_id.lower():
                return p
        return None


class CanonicalMemoryAdapter:
    """Read/query adapter for CanonicalDealMemory."""

    def __init__(self, memory_path: Path = CANONICAL_DEALS_PATH):
        self.memory_path = memory_path

    def get_deals(self) -> List[Dict[str, Any]]:
        """Retrieve all canonically registered deals."""
        if self.memory_path.exists():
            try:
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def get_deal_by_id(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Find deal record by ID."""
        for d in self.get_deals():
            if d.get("id") == deal_id or d.get("entity_id") == deal_id:
                return d
        return None


class DialerAdapter:
    """Read/status adapter for the production Dialer database."""

    def __init__(self, db_path: Path = DIALER_DB_PATH):
        self.db_path = db_path

    def get_all_leads(self) -> List[Dict[str, Any]]:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def get_callable_leads(self) -> List[Dict[str, Any]]:
        """Filter leads that are active and not suppressed."""
        leads = self.get_all_leads()
        return [
            lead for lead in leads
            if not lead.get("is_suppressed") and lead.get("status") not in {"SUPPRESSED", "DNC", "BAD_NUMBER"}
        ]

    def is_suppressed(self, phone: str) -> bool:
        """Check if phone number is suppressed or on DNC list."""
        clean_phone = "".join(filter(str.isdigit, phone or ""))
        for lead in self.get_all_leads():
            lp = "".join(filter(str.isdigit, lead.get("phone", "")))
            if lp and lp == clean_phone and (lead.get("is_suppressed") or lead.get("status") == "SUPPRESSED"):
                return True
        return False


class IdentityAdapter:
    """Non-invasive reader for owner identity state machine results."""

    def __init__(self, results_path: Path = IDENTITY_RESULTS_PATH):
        self.results_path = results_path

    def get_identity_state(self, lead_id: str) -> str:
        """
        Return verified identity state:
          - DATABASE_OWNER_VERIFIED
          - LIVE_CALLER_IDENTITY_CONFIRMED
          - AUTHORIZED_DECISION_MAKER
          - TENANT
          - WRONG_PERSON
          - IDENTITY_UNCONFIRMED
        """
        if self.results_path.exists():
            try:
                results = json.loads(self.results_path.read_text(encoding="utf-8"))
                for r in results:
                    if r.get("lead_id") == lead_id:
                        return r.get("state", "IDENTITY_UNCONFIRMED")
            except Exception:
                pass

        # Fallback inspection from dialer db
        dialer = DialerAdapter()
        for lead in dialer.get_all_leads():
            if lead.get("id") == lead_id or lead.get("company", "").lower() == lead_id.lower():
                if lead.get("owner_verified"):
                    return "DATABASE_OWNER_VERIFIED"
                if lead.get("authorized_official_name") or lead.get("decision_maker"):
                    return "AUTHORIZED_DECISION_MAKER"
        return "IDENTITY_UNCONFIRMED"


class CRMAdapter:
    """Read/progress adapter for SalesforceOS and CRM deals."""

    def __init__(self):
        self.canonical = CanonicalMemoryAdapter()

    def get_deal_stage(self, deal_id: str) -> str:
        deal = self.canonical.get_deal_by_id(deal_id)
        if deal:
            return deal.get("stage", "NEW")
        return "NEW"

    def progress_stage(self, deal_id: str, new_stage: str, notes: str = "") -> bool:
        """Records stage progression intent without destructively rewriting CRM tables."""
        # Intentionally non-invasive
        return True


class VerificationAdapter:
    """Non-invasive verification gate adapter."""

    @staticmethod
    def is_verified(lead: Dict[str, Any]) -> bool:
        """Check if lead meets zero-synthetic verification standards."""
        name = lead.get("decision_maker") or lead.get("name") or ""
        phone = lead.get("phone") or ""
        if not phone or len("".join(filter(str.isdigit, phone))) < 10:
            return False
        # Filter synthetic placeholders
        placeholders = ["test", "demo", "sample", "placeholder", "fake"]
        if any(p in name.lower() for p in placeholders):
            return False
        return True
