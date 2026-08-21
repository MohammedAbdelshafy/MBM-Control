"""
MBM Dialer Script Engine Quality & Invariant Tests
==================================================
Tests all 15 segment playbooks, natural dialogue ladders, prohibited
assumption checks, and dialer dataset script coverage.
"""

import os
import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_script_engine import (
    SegmentClassifier,
    DialerScriptEngine,
    enrich_leads_with_playbooks,
    SUPPORTED_SEGMENTS,
)

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"


class TestDialerScriptEngine:

    def test_all_15_segments_supported(self):
        """Verify all 15 segments have explicit generation pathways."""
        expected_segments = [
            "DISTRESSED_SELLER",
            "ABSENTEE_OWNER",
            "VACANT_PROPERTY",
            "HIGH_EQUITY",
            "FREE_AND_CLEAR",
            "TIRED_LANDLORD",
            "OUT_OF_STATE_OWNER",
            "SENIOR_OWNER",
            "LIKELY_TO_MOVE",
            "COMMERCIAL",
            "CONTRACTOR",
            "AI_CONSULTANCY",
            "WEBSITE_DESIGN",
            "MOBILE_APPS",
            "B2B_AGENCY",
        ]
        for seg in expected_segments:
            assert seg in SUPPORTED_SEGMENTS

    def test_segment_classification_accuracy(self):
        """Verify classification logic across diverse lead profiles."""
        lead_seller = {
            "id": "S1",
            "vertical": "Real Estate Sellers",
            "motivation_signals": ["TAX_DELINQUENT"],
            "details": {"distress_reason": "tax lien"},
        }
        assert SegmentClassifier.classify_segment(lead_seller) == "DISTRESSED_SELLER"

        lead_vacant = {
            "id": "S2",
            "vertical": "Real Estate Sellers",
            "motivation_signals": ["VACANT_PROPERTY"],
        }
        assert SegmentClassifier.classify_segment(lead_vacant) == "VACANT_PROPERTY"

        lead_contractor = {
            "id": "C1",
            "vertical": "Commercial Contractors & ConTech",
            "company": "Apex Mechanical HVAC LLC",
        }
        assert SegmentClassifier.classify_segment(lead_contractor) == "CONTRACTOR"

        lead_ai = {
            "id": "A1",
            "vertical": "AI Consultancy & Automation",
            "company": "Cognitive Scale AI",
        }
        assert SegmentClassifier.classify_segment(lead_ai) == "AI_CONSULTANCY"

        lead_web = {
            "id": "W1",
            "vertical": "Website Design & Development",
            "company": "Pixel Craft Studios",
        }
        assert SegmentClassifier.classify_segment(lead_web) == "WEBSITE_DESIGN"

        lead_app = {
            "id": "M1",
            "vertical": "Mobile App Development",
            "company": "AppFlow Systems",
        }
        assert SegmentClassifier.classify_segment(lead_app) == "MOBILE_APPS"

        lead_agency = {
            "id": "B1",
            "vertical": "Professional Services & B2B Agencies",
            "company": "Vanguard Growth Partners",
        }
        assert SegmentClassifier.classify_segment(lead_agency) == "B2B_AGENCY"

    def test_distressed_seller_script_prohibits_negative_assumptions(self):
        """
        Verify distressed-seller script does NOT accuse the owner of financial
        distress, bankruptcy, or foreclosure, and sounds completely natural.
        """
        lead = {
            "id": "TEST-SELLER-01",
            "contact": "Marcus Vance",
            "company": "742 Evergreen Terrace",
            "vertical": "Real Estate Sellers",
            "details": {
                "address": "742 Evergreen Terrace, Dallas, TX 75201",
                "city": "Dallas",
                "distress_reason": "pre-foreclosure notice",
            },
        }
        playbook = DialerScriptEngine.generate_playbook(lead)
        script = playbook["Call_Script"].lower()

        prohibited_phrases = [
            "are you distressed",
            "you are in foreclosure",
            "you are bankrupt",
            "financial trouble",
            "financial problems",
            "desperate to sell",
            "we know you are behind on taxes",
            "we know you owe money",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in script, f"Prohibited phrase '{phrase}' found in script!"

        # Must contain natural conversational milestones
        assert "do you have 30 seconds" in script or "mohammed" in script
        assert "as-is" in script
        assert "zero" in script or "fees" in script

    def test_script_structure_contains_all_10_stages(self):
        """Verify all 10 stages exist in generated playbook."""
        lead = {
            "id": "TEST-LEAD-02",
            "contact": "Dr. Sarah Jenkins",
            "company": "Jenkins Dental Group",
            "vertical": "Clinics & Medical Practices",
            "details": {"city": "Dallas"},
        }
        playbook = DialerScriptEngine.generate_playbook(lead)

        assert playbook["script_id"].startswith("SCRIPT-")
        assert playbook["segment"] != ""
        assert playbook["opening"] != ""
        assert playbook["context_confirmation"] != ""
        assert playbook["open_to_selling"] != ""
        assert playbook["motivation_discovery"] != ""
        assert playbook["timing_discovery"] != ""
        assert playbook["price_expectation"] != ""
        assert playbook["next_step"] != ""
        assert len(playbook["objection_handlers"]) >= 3
        assert playbook["polite_exit"] != ""
        assert playbook["offer"]["neteller_checkout_link"].startswith("https://member.neteller.com/pay")

    def test_malformed_data_does_not_crash_script_generation(self):
        """Ensure resilient fallback handling on empty or corrupted lead records."""
        corrupt_leads = [
            {},
            {"id": "NULL-01", "contact": None, "company": None},
            {"id": "WEIRD-02", "vertical": "", "details": None, "phone": "+12140000000"},
            {"id": "NUM-03", "contact": 12345, "company": 67890},
        ]
        for lead in corrupt_leads:
            playbook = DialerScriptEngine.generate_playbook(lead)
            assert playbook["script_id"] != ""
            assert len(playbook["Call_Script"]) > 50

    def test_canonical_dataset_full_script_enrichment(self):
        """Verify 100% of leads in leads_database.json have scripts and valid segment."""
        assert DIALER_DB.exists(), "leads_database.json must exist"
        leads = json.loads(DIALER_DB.read_text(encoding="utf-8"))

        assert len(leads) >= 1091, f"Total dataset cannot shrink below 1,091 (found {len(leads)})"

        for lead in leads:
            assert lead.get("script_id"), f"Lead {lead.get('id')} missing script_id"
            assert lead.get("Call_Script"), f"Lead {lead.get('id')} missing Call_Script"
            assert lead.get("segment"), f"Lead {lead.get('id')} missing segment"
            assert lead.get("sales_strategy"), f"Lead {lead.get('id')} missing sales_strategy"
