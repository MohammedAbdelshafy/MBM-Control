"""
Tests for Unified dbt, NVIDIA NIM, and Groq Intelligence Architecture
Verifies canonical lead contracts, AI provenance, Groq fast classification,
NVIDIA heavy reasoning routing, dual-model consensus, and deterministic dialer gates.
"""

import os
import sys
from pathlib import Path
import pytest

# Bootstrap root
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.canonical_lead_schema import (
    CanonicalLead, CanonicalProperty, CanonicalOwner, CanonicalPhone, AIProvenance
)
from MBM.LeadEngine.groq_fast_classifier import GroqFastClassifier
from MBM.LeadEngine.nvidia_model_registry import NVIDIAModelRegistry
from MBM.LeadEngine.ai_orchestrator import AIOrchestrator, TaskType
from MBM.LeadEngine.lead_volume_auditor import LeadVolumeAuditor


class TestCanonicalLeadSchema:
    """Tests zero-hallucination invariants and deterministic dialer gating."""

    def test_phone_normalization_e164(self):
        assert CanonicalPhone.normalize_phone("817-685-0631") == "+18176850631"
        assert CanonicalPhone.normalize_phone("18176850631") == "+18176850631"
        assert CanonicalPhone.normalize_phone("+18176850631") == "+18176850631"
        assert CanonicalPhone.normalize_phone("invalid") is None

    def test_deterministic_gate_valid_lead(self):
        prop = CanonicalProperty(
            property_id="P-01",
            site_address="1200 MAIN ST",
            site_city="DALLAS",
            site_state="TX",
            site_zip="75202",
            county="DALLAS"
        )
        owner = CanonicalOwner(
            owner_id="O-01",
            owner_name="ACME HOLDINGS LLC",
            ownership_verified=True
        )
        phone = CanonicalPhone(
            phone_raw="817-685-0631",
            phone_e164="+18176850631",
            is_callable=True,
            is_dnc=False,
            verification_status="VERIFIED"
        )
        lead = CanonicalLead(
            lead_id="L-01",
            property=prop,
            owner=owner,
            phones=[phone]
        )
        assert lead.validate_deterministic_gate() is True
        assert lead.dialer_gate_passed is True
        assert lead.dialer_rejection_reason is None

    def test_deterministic_gate_blocks_no_phone(self):
        prop = CanonicalProperty(
            property_id="P-02",
            site_address="1200 MAIN ST",
            site_city="DALLAS",
            site_state="TX",
            site_zip="75202",
            county="DALLAS"
        )
        owner = CanonicalOwner(
            owner_id="O-02",
            owner_name="ACME HOLDINGS LLC"
        )
        lead = CanonicalLead(
            lead_id="L-02",
            property=prop,
            owner=owner,
            phones=[]
        )
        assert lead.validate_deterministic_gate() is False
        assert lead.dialer_rejection_reason == "NO_CALLABLE_PHONE"

    def test_deterministic_gate_blocks_anonymous_owner(self):
        prop = CanonicalProperty(
            property_id="P-03",
            site_address="1200 MAIN ST",
            site_city="DALLAS",
            site_state="TX",
            site_zip="75202",
            county="DALLAS"
        )
        owner = CanonicalOwner(
            owner_id="O-03",
            owner_name="UNKNOWN"
        )
        phone = CanonicalPhone(
            phone_raw="817-685-0631",
            phone_e164="+18176850631",
            is_callable=True,
            is_dnc=False
        )
        lead = CanonicalLead(
            lead_id="L-03",
            property=prop,
            owner=owner,
            phones=[phone]
        )
        assert lead.validate_deterministic_gate() is False
        assert lead.dialer_rejection_reason == "UNVERIFIED_OWNER"

    def test_ai_provenance_contract(self):
        prov = AIProvenance(
            field_name="seller_intent",
            source="nvidia_nim:meta/llama-3.3-70b-instruct",
            model="meta/llama-3.3-70b-instruct",
            confidence=0.95,
            reasoning_signals=["TAX_DELINQUENT", "ABSENTEE_OWNER"],
            validation_result="VALIDATED"
        )
        d = prov.to_dict()
        assert d["field_name"] == "seller_intent"
        assert d["confidence"] == 0.95
        assert "TAX_DELINQUENT" in d["reasoning_signals"]
        assert d["validation_result"] == "VALIDATED"


class TestGroqFastClassifier:
    """Tests sub-500ms classification and bilingual objection parsing."""

    def test_seller_intent_classification(self):
        classifier = GroqFastClassifier()
        res = classifier.classify_seller_intent(["TAX_DELINQUENT", "VACANT_PROPERTY", "UPCOMING_AUCTION"])
        assert res["intent"] in ["HIGH", "MEDIUM"]
        assert res["confidence"] >= 0.70
        assert "latency_ms" in res

    def test_english_objection_classification(self):
        classifier = GroqFastClassifier()
        res = classifier.classify_objection("Please put me on your do not call list")
        assert res["category"] == "DO_NOT_CALL"
        assert res["is_dnc"] is True
        assert res["detected_lang"] == "en"

    def test_arabic_objection_classification(self):
        classifier = GroqFastClassifier()
        res = classifier.classify_objection("أنا مش مهتم خالص ولا أريد البيع")
        assert res["category"] == "NOT_INTERESTED"
        assert res["detected_lang"] == "ar"


class TestAIOrchestrator:
    """Tests task-aware model routing and dual-model verification."""

    def test_task_routing_heavy_reasoning(self):
        orchestrator = AIOrchestrator()
        res = orchestrator.route(
            TaskType.DEAL_ANALYSIS,
            {"property": "1200 MAIN ST", "tax_delinquent": True, "equity": 150000}
        )
        assert res["task_type"] == "DEAL_ANALYSIS"
        assert "nvidia" in res["model"] or "llama" in res["model"]
        assert "provenance" in res

    def test_task_routing_fast_classification(self):
        orchestrator = AIOrchestrator()
        res = orchestrator.route(
            TaskType.OBJECTION_HANDLING,
            "What is your cash offer ballpark?"
        )
        assert "category" in res or "intent" in res
        assert "latency_ms" in res

    def test_dual_model_verification_consensus(self):
        orchestrator = AIOrchestrator()
        res = orchestrator.verify_high_impact_decision(
            decision_context="Commercial warehouse with $200k equity and verified owner",
            proposed_action="Send firm cash offer contract for $450,000 as-is"
        )
        assert "consensus_reached" in res
        assert "escalate_to_human" in res
        assert "latency_ms" in res


class TestLeadVolumeAuditor:
    """Tests funnel drop-off measurement and lead accounting."""

    def test_full_lead_audit(self):
        auditor = LeadVolumeAuditor()
        report = auditor.run_full_audit()
        assert "funnel" in report
        assert "drop_off_breakdown" in report
        assert report["funnel"]["raw"] > 0
        assert report["funnel"]["dialer_ready"] > 0
        assert report["funnel"]["top_priority"] > 0
