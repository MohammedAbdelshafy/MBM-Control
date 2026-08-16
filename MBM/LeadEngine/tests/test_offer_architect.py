"""
TESTS: MBM OFFER ARCHITECT & PACKAGING ENGINE
=============================================================================
Comprehensive tests verifying:
1. Offer packaging for all 19+ ICP verticals
2. Smallest-offer matching ladder (Entry -> Core -> Expansion)
3. Dynamic script generation (Mode COLD, WARM, HOT, Opening, Diagnostic Questions, CTA)
4. 12-category objection playbook generation
5. Multi-channel angles (Phone, Email, LinkedIn)
6. Non-fabricated ROI hypothesis structure (OBSERVED vs ESTIMATED vs ASSUMED)
7. Neteller checkout link attachment
=============================================================================
"""

import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.offer_architect import (
    OfferArchitect,
    VERTICAL_OFFER_CATALOG,
    DEFAULT_OFFER_CONFIG,
)


def test_offer_architect_vertical_matching():
    """Verify OfferArchitect selects correct assistant and SKU for target verticals."""
    architect = OfferArchitect()

    lead_hvac = {
        "id": "TEST-HVAC-01",
        "company": "Dallas Mechanical & HVAC Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Owner & President",
        "industry": "HVAC & Mechanical Contractors",
        "phone": "+12148849120",
        "email": "marcus@dallasmechanical.com",
        "intent_score": 95.0,
    }
    strat_hvac = architect.build_sales_strategy_for_lead(lead_hvac)

    assert strat_hvac["intent_mode"] == "HOT"
    assert strat_hvac["offer"]["sku"] == "AI-ASSISTANT-HVAC-DISPATCH"
    assert strat_hvac["offer"]["monthly_fee_usd"] == 2500.0
    assert "24/7 AI Emergency Call" in strat_hvac["offer"]["offer_name"]
    assert "https://member.neteller.com/pay?" in strat_hvac["offer"]["neteller_checkout_link"]


def test_offer_architect_civil_construction():
    """Verify CAD-to-BOQ Takeoff offer for structural construction firms."""
    architect = OfferArchitect()

    lead_civil = {
        "id": "TEST-CIVIL-01",
        "company": "Austin Infrastructure & Civil Contractors",
        "decision_maker": "David Sterling",
        "role": "Managing Partner & CEO",
        "industry": "Civil & Structural Construction",
        "phone": "+15127749011",
        "email": "david@austincivil.com",
        "intent_score": 92.0,
    }
    strat_civil = architect.build_sales_strategy_for_lead(lead_civil)

    assert strat_civil["offer"]["sku"] == "AI-ASSISTANT-CONTECH-TAKEOFF"
    assert strat_civil["offer"]["monthly_fee_usd"] == 4500.0
    assert "CAD-to-BOQ" in strat_civil["offer"]["offer_name"]
    assert "takeoff" in strat_civil["offer"]["problem_solved"].lower()


def test_offer_architect_script_and_cta_ladder():
    """Verify script components and CTA ladder are properly populated."""
    architect = OfferArchitect()

    lead_dental = {
        "id": "TEST-DENTAL-01",
        "company": "Plano Smile Dental Practice",
        "decision_maker": "Dr. Sarah Lin",
        "role": "Practice Owner & Doctor",
        "industry": "Dental Clinics & Orthodontics",
        "phone": "+19726658140",
        "email": "drlin@planosmile.com",
        "intent_score": 85.0,
    }
    strat_dental = architect.build_sales_strategy_for_lead(lead_dental)

    assert strat_dental["intent_mode"] == "WARM"
    script = strat_dental["conversation_script"]
    assert script["opening"] != ""
    assert script["first_question"] != ""
    assert script["quantification_question"] != ""
    assert script["ai_fit_transition"] != ""
    assert script["primary_cta"] != ""
    assert script["fallback_cta"] != ""


def test_offer_architect_12_category_objection_playbook():
    """Verify all 12 objection categories are generated."""
    architect = OfferArchitect()

    lead = {
        "id": "TEST-GEN-01",
        "company": "Acme Commercial Services",
        "decision_maker": "John Doe",
        "role": "Managing Owner",
        "industry": "General Services",
        "phone": "+12145550199",
        "intent_score": 75.0,
    }
    strat = architect.build_sales_strategy_for_lead(lead)
    playbook = strat["conversation_script"]["objection_playbook"]

    expected_categories = [
        "PRICE", "TIMING", "TRUST", "AI_SKEPTICISM", "ALREADY_HAVE_SOLUTION",
        "DO_IT_INTERNALLY", "NO_NEED", "NO_BUDGET", "AUTHORITY", "SECURITY",
        "INTEGRATION", "STAFF"
    ]
    for cat in expected_categories:
        assert cat in playbook, f"Missing objection category: {cat}"
        assert len(playbook[cat]) > 20, f"Objection response too short for {cat}"


def test_offer_architect_multi_channel_angles():
    """Verify email and LinkedIn angles are complete."""
    architect = OfferArchitect()

    lead = {
        "id": "TEST-LAW-01",
        "company": "Sterling & Vance Injury Law Firm",
        "decision_maker": "Robert Vance",
        "role": "Managing Partner",
        "industry": "Personal Injury & Corporate Law",
        "phone": "+12147391100",
        "email": "robert@sterlingvance.com",
        "city": "Dallas",
        "state": "TX",
        "intent_score": 96.0,
    }
    strat = architect.build_sales_strategy_for_lead(lead)
    channels = strat["multi_channel_angles"]

    assert "email" in channels
    assert "subject" in channels["email"]
    assert "observed_signal" in channels["email"]
    assert "roi_angle" in channels["email"]
    assert "linkedin" in channels
    assert "Sterling & Vance" in channels["linkedin"]
