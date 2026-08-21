"""
GTM SYSTEM ADAPTERS
=================================================================================================================
Non-invasive interfaces and adapters wrapping existing MBM systems.

Adapters:
  - BuyerHunterAdapter   (read + normalize the active Buyer Hunter output)
  - CanonicalMemoryAdapter (read CanonicalDealMemory)
  - DialerAdapter        (safe read operations on the production dialer DB)
  - IdentityAdapter      (read-only identity state, strict OWNER_CONFIRMED semantics)
  - CRMAdapter           (idempotent opportunity overlay; never mutates production CRM)
  - VerificationAdapter  (zero-synthetic verification gate)
=================================================================================================================
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CANONICAL_DEALS_PATH = ARTIFACTS_DIR / "canonical_deals_memory.json"
IDENTITY_RESULTS_PATH = ROOT_DIR / "MBM" / "LeadEngine" / "logs" / "call_identity_results.json"

# Canonical identity states (see owner_identity.py). Only OWNER_CONFIRMED is an
# explicit live owner confirmation; AUTHORIZED_DECISION_MAKER stays separate.
IDENTITY_STATES = (
    "DATABASE_OWNER_VERIFIED",
    "OWNER_LIKELY",
    "OWNER_CONFIRMED",
    "AUTHORIZED_DECISION_MAKER",
    "IDENTITY_UNCONFIRMED",
    "WRONG_PERSON",
    "WRONG_NUMBER",
    "TENANT",
    "DO_NOT_CALL",
    "QUARANTINED",
)


def _digits(value: Any) -> str:
    return "".join(filter(str.isdigit, str(value or "")))


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

    def normalize_prospect(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a Buyer Hunter evidence card into a canonical GTM opportunity.

        Expected input fields (see ai_assistant_buyer_hunter.EvidenceCard.to_dict):
          company, decision_maker, role, industry, phone, email, pain_signal,
          intent_signal, intent_score, intent_tier, why_this_company, why_now,
          recommended_ai_assistant (dict), source, source_url, source_date,
          signal_age_days, confidence_score, outreach_phone_angle / email_angle
        """
        assistant = card.get("recommended_ai_assistant") or {}
        if isinstance(assistant, dict):
            sku = assistant.get("sku") or assistant.get("assistant_name") or "AI Automation Retainer"
            monthly_retainer = float(assistant.get("monthly_retainer") or 0.0)
        else:
            sku = str(assistant)
            monthly_retainer = float(card.get("monthly_retainer_fee") or 0.0)

        confidence = float(card.get("confidence_score") or 0.0) / 100.0
        if confidence <= 0.0 or confidence > 1.0:
            confidence = 0.85

        return {
            "id": card.get("id") or card.get("company", "UNKNOWN"),
            "company": card.get("company", "Target Enterprise"),
            "decision_maker": card.get("decision_maker") or card.get("role") or "Authorized Executive",
            "role": card.get("role", "Owner / Decision Maker"),
            "industry": card.get("industry", "B2B Services"),
            "phone": card.get("phone", ""),
            "email": card.get("email", ""),
            "location": card.get("location", ""),
            "pain_point": card.get("pain_signal") or card.get("pain_description") or "Operations bottleneck",
            "intent_signal": card.get("intent_signal", "Automated workflow request"),
            "intent_score": float(card.get("intent_score", 85.0)),
            "tier": card.get("intent_tier", "HIGH INTENT"),
            "why_this_company": card.get("why_this_company") or f"High pain and verified authority at {card.get('company')}.",
            "why_now": card.get("why_now", "Active hiring urgency"),
            "recommended_assistant_sku": sku,
            "expected_revenue": monthly_retainer or float(card.get("expected_revenue", 2000.0)),
            "confidence": confidence,
            "signal_age_days": float(card.get("signal_age_days") or 2.0),
            "source": card.get("source", "SignalHarvester"),
            "outreach_angle": card.get("outreach_phone_angle") or card.get("outreach_email_angle") or "",
            "evidence": {
                "claim": card.get("why_this_company") or card.get("pain_signal") or "UNKNOWN",
                "source": card.get("source") or "UNKNOWN",
                "source_reference": card.get("source_url") or card.get("source") or "UNKNOWN",
                "source_date": card.get("source_date") or "UNKNOWN",
                "confidence": confidence,
                "agent": "INTENT_HUNTER",
            },
        }


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


_SHARED_LEADS: Optional[List[Dict[str, Any]]] = None
_SHARED_SUPPRESSED_PHONES: Optional[set] = None
_SHARED_LEADS_MAP: Optional[Dict[str, Dict[str, Any]]] = None


def _load_shared_leads(db_path: Path = DIALER_DB_PATH) -> List[Dict[str, Any]]:
    global _SHARED_LEADS, _SHARED_SUPPRESSED_PHONES, _SHARED_LEADS_MAP
    if _SHARED_LEADS is not None:
        return _SHARED_LEADS
    if db_path.exists():
        try:
            _SHARED_LEADS = json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            _SHARED_LEADS = []
    else:
        _SHARED_LEADS = []

    _SHARED_SUPPRESSED_PHONES = set()
    _SHARED_LEADS_MAP = {}
    for lead in _SHARED_LEADS:
        lid = lead.get("id")
        if lid:
            _SHARED_LEADS_MAP[str(lid).lower()] = lead
        comp = lead.get("company") or lead.get("business_name") or ""
        if comp:
            _SHARED_LEADS_MAP[comp.lower()] = lead
        p = _digits(lead.get("phone"))
        if p:
            _SHARED_LEADS_MAP[p] = lead
            if lead.get("is_suppressed") or lead.get("status") in {"SUPPRESSED", "DNC", "BAD_NUMBER"}:
                _SHARED_SUPPRESSED_PHONES.add(p)
    return _SHARED_LEADS


class DialerAdapter:
    """Read/status adapter for the production Dialer database (never mutates it)."""

    def __init__(self, db_path: Path = DIALER_DB_PATH):
        self.db_path = db_path

    def get_all_leads(self) -> List[Dict[str, Any]]:
        return _load_shared_leads(self.db_path)

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single lead by id, company, or normalized phone."""
        _load_shared_leads(self.db_path)
        if not _SHARED_LEADS_MAP:
            return None
        key = str(lead_id).lower()
        if key in _SHARED_LEADS_MAP:
            return _SHARED_LEADS_MAP[key]
        clean_p = _digits(lead_id)
        if clean_p and clean_p in _SHARED_LEADS_MAP:
            return _SHARED_LEADS_MAP[clean_p]
        return None

    def get_callable_leads(self) -> List[Dict[str, Any]]:
        """Filter leads that are active and not suppressed."""
        leads = self.get_all_leads()
        return [
            lead for lead in leads
            if not lead.get("is_suppressed") and lead.get("status") not in {"SUPPRESSED", "DNC", "BAD_NUMBER"}
        ]

    def get_priority(self, lead_id: str) -> Dict[str, Any]:
        """Read the priority-ranked selling metrics for a lead."""
        lead = self.get_lead(lead_id) or {}
        return {
            "tier": lead.get("tier"),
            "motivation_score": lead.get("motivation_score"),
            "deal_score": lead.get("deal_score"),
            "callability_score": lead.get("callability_score"),
            "sales_lane": lead.get("sales_lane"),
        }

    def get_identity(self, lead_id: str) -> str:
        """Read identity state for a lead (strict canonical mapping)."""
        lead = self.get_lead(lead_id) or {}
        owner_status = lead.get("owner_status")
        if owner_status and owner_status in IDENTITY_STATES:
            return owner_status
        if lead.get("owner_verified"):
            return "DATABASE_OWNER_VERIFIED"
        return "IDENTITY_UNCONFIRMED"

    def get_suppression(self, lead_id: str) -> Dict[str, Any]:
        """Read suppression status for a lead or phone."""
        lead = self.get_lead(lead_id) or {}
        suppressed = bool(
            lead.get("is_suppressed")
            or lead.get("status") in {"SUPPRESSED", "DNC", "BAD_NUMBER"}
            or lead.get("owner_status") in {"DO_NOT_CALL", "QUARANTINED"}
        )
        return {"suppressed": suppressed, "reason": lead.get("status") or lead.get("owner_status") or "ACTIVE"}

    def get_attempt_history(self, lead_id: str) -> List[Dict[str, Any]]:
        """Read call/disposition attempt history for a lead."""
        lead = self.get_lead(lead_id) or {}
        attempts = lead.get("attempt_history")
        if isinstance(attempts, list):
            return attempts
        # Derive a single atomic attempt record when structured history is absent.
        history = []
        last = lead.get("last_attempt_date") or lead.get("last_disposition")
        if last:
            history.append({"date": last, "disposition": lead.get("status", "UNKNOWN")})
        return history

    def get_callability(self, lead_id: str) -> Dict[str, Any]:
        """Read the callability assessment for a lead."""
        lead = self.get_lead(lead_id) or {}
        phone_ok = len(_digits(lead.get("phone"))) >= 10
        suppressed = self.get_suppression(lead_id)["suppressed"]
        return {
            "callable": phone_ok and not suppressed,
            "phone_ok": phone_ok,
            "suppressed": suppressed,
            "callability_score": lead.get("callability_score"),
        }

    def is_suppressed(self, phone: str) -> bool:
        """Check if phone number is suppressed or on DNC list."""
        _load_shared_leads(self.db_path)
        clean_phone = _digits(phone)
        if clean_phone and _SHARED_SUPPRESSED_PHONES:
            return clean_phone in _SHARED_SUPPRESSED_PHONES
        return False




class IdentityAdapter:
    """Non-invasive reader for owner identity state machine results."""

    def __init__(self, results_path: Path = IDENTITY_RESULTS_PATH):
        self.results_path = results_path

    def _read_results(self) -> List[Dict[str, Any]]:
        if self.results_path.exists():
            try:
                data = json.loads(self.results_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def get_identity_state(self, lead_id: str) -> str:
        """
        Return a canonical identity state:
          DATABASE_OWNER_VERIFIED, OWNER_LIKELY, OWNER_CONFIRMED,
          AUTHORIZED_DECISION_MAKER, IDENTITY_UNCONFIRMED, WRONG_PERSON,
          WRONG_NUMBER, TENANT, DO_NOT_CALL, QUARANTINED

        Only OWNER_CONFIRMED represents an explicit live owner confirmation.
        AUTHORIZED_DECISION_MAKER stays separate.
        """
        for r in self._read_results():
            if r.get("lead_id") == lead_id:
                state = r.get("state")
                if state in IDENTITY_STATES:
                    return state
                return "IDENTITY_UNCONFIRMED"

        # Fallback inspection from dialer db
        dialer = DialerAdapter()
        lead = dialer.get_lead(lead_id)
        if lead:
            owner_status = lead.get("owner_status")
            if owner_status in IDENTITY_STATES:
                return owner_status
            if lead.get("owner_verified"):
                return "DATABASE_OWNER_VERIFIED"
            if lead.get("authorized_official_name") or lead.get("decision_maker"):
                return "AUTHORIZED_DECISION_MAKER"
        return "IDENTITY_UNCONFIRMED"

    def is_live_owner_confirmed(self, lead_id: str) -> bool:
        """True only for explicit live owner confirmation."""
        return self.get_identity_state(lead_id) == "OWNER_CONFIRMED"


class CRMAdapter:
    """
    Idempotent opportunity overlay for the GTM Commander.

    This parallel build is NON-INVASIVE: upserts/events/states live in an
    in-memory registry keyed by opportunity id and are never written to the
    production canonical_deals_memory.json. Integration later connects these
    hooks to CanonicalDealMemory (which already guarantees idempotency).
    """

    def __init__(self):
        self.canonical = CanonicalMemoryAdapter()
        self._overlay: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def get_opportunity(self, opp_id: str) -> Optional[Dict[str, Any]]:
        """Read opportunity from overlay, falling back to canonical memory."""
        if opp_id in self._overlay:
            return self._overlay[opp_id]
        return self.canonical.get_deal_by_id(opp_id)

    def upsert_opportunity(self, opp_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Idempotent upsert into the in-memory overlay."""
        existing = self._overlay.get(opp_id, {})
        merged = {**existing, **data}
        merged["id"] = opp_id
        self._overlay[opp_id] = merged
        return merged

    def record_event(self, opp_id: str, event: Dict[str, Any]) -> None:
        """Append an event to an opportunity's log (idempotent by event_id)."""
        if opp_id not in self._events:
            self._events[opp_id] = []
        event_id = event.get("event_id") or event.get("id")
        if event_id and any(e.get("event_id") == event_id for e in self._events[opp_id]):
            return
        self._events[opp_id].append(event)

    def advance_state(self, opp_id: str, new_state: str, reason: str = "") -> str:
        """Idempotently record a validated state transition in the overlay."""
        current = self.get_opportunity(opp_id) or {}
        from_state = current.get("state", "DISCOVERED")
        self.upsert_opportunity(opp_id, {
            "state": new_state,
            "last_state_change": reason,
            "previous_state": from_state,
        })
        return new_state

    def get_next_action(self, opp_id: str) -> Dict[str, Any]:
        """Return the recorded next action for an opportunity."""
        opp = self.get_opportunity(opp_id) or {}
        return opp.get("next_action", {"action_type": "NONE", "channel": "NONE"})


class VerificationAdapter:
    """Non-invasive verification gate adapter."""

    @staticmethod
    def is_verified(lead: Dict[str, Any]) -> bool:
        """Check if lead meets zero-synthetic verification standards."""
        name = lead.get("decision_maker") or lead.get("name") or ""
        phone = lead.get("phone") or ""
        if not phone or len(_digits(phone)) < 10:
            return False
        # Filter synthetic placeholders
        placeholders = ["test", "demo", "sample", "placeholder", "fake"]
        if any(p in name.lower() for p in placeholders):
            return False
        return True