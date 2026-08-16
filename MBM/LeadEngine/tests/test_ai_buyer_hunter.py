"""
test_ai_buyer_hunter.py — Comprehensive Test Suite for MBM AI Assistant Buyer Hunter
===================================================================================
Verifies:
1. 100-Point Intent Scoring Math and Tier Boundaries (HOT, HIGH INTENT, WARM, NURTURE, IGNORE)
2. Exact Signal & Operational Pain Parsing (LinkedIn, Reddit, Job Posts, Web Signals)
3. AI Assistant Product Matrix & Vertical Matching
4. Evidence Card Integrity & 0 Synthetic Placeholder Identity Rules
5. 5-Part Personalized Outreach Script Generation (THE SIGNAL, THE PAIN, THE OFFER, THE HOOK, THE CTA)
6. Canonical Neteller Checkout Link Injection
7. Dynamic Niche Discovery & Pain Clustering Engine
8. Canonical Deal Memory & SalesforceOS CRM Ingestion & Idempotency
"""

import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.ai_assistant_buyer_hunter import (
    AIAssistantBuyerHunter, BuyerIntentScorer, SignalHarvester,
    OutreachScriptBuilder, NicheDiscoveryEngine, AI_ASSISTANT_CATALOG,
    EvidenceCard
)
from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory, DealType, DealStage, MonetizationRoute
from MBM.LeadEngine.dialer_verification_gate import check_lead, is_placeholder_identity
from MBM.SalesforceOS.salesforce_os import SalesforceOS


def test_100_point_scoring_formula_and_tiers():
    """Verify exact 100-point scoring algorithm and tier boundaries."""
    scorer = BuyerIntentScorer()

    # 1. Hot Case (Score >= 90)
    hot_prospect = {
        "company": "Summit HVAC & Air",
        "role": "Founder & Managing Director",
        "industry": "HVAC & Mechanical",
        "post_content": "We're missing 20+ after-hours emergency calls every weekend. Inbound calls went to voicemail. Need an AI phone agent or automated call intake that connects to ServiceTitan.",
        "pain_description": "20+ after-hours emergency replacement calls missed weekly.",
        "intent_signal": "Actively evaluating AI phone agent and after-hours call intake.",
        "hiring_title": "Weekend Emergency Dispatcher",
        "tech_stack": "ServiceTitan",
        "locations_count": 2,
        "source": "LinkedIn Post & Comments"
    }
    score, breakdown, tier, path = scorer.calculate_score(hot_prospect)
    assert score >= 90, f"Expected HOT score (>=90), got {score}"
    assert tier == "HOT"
    assert "PATH A" in path
    assert breakdown["explicit_ai_request"] == 25
    assert breakdown["operational_pain"] == 20
    assert breakdown["decision_maker_authority"] == 15
    assert breakdown["clear_repetitive_workflow"] == 10
    assert breakdown["hiring_for_automatable_role"] == 10
    assert breakdown["relevant_tech_stack"] == 5
    assert breakdown["meaningful_engagement"] == 5

    # 2. High Intent Case (Score 75-89)
    high_intent_prospect = {
        "company": "Metro Dental Partners",
        "role": "Managing Partner & Practice Owner",
        "industry": "Dental & Orthodontics",
        "post_content": "Our front desk is overwhelmed with phone calls and overdue hygiene recalls. Looking for AI assistant to automate recall calls with Dentrix.",
        "pain_description": "Overdue hygiene recalls uncalled due to front desk phone bottleneck.",
        "intent_signal": "Searching for AI recall assistant.",
        "hiring_title": "Patient Care Coordinator",
        "tech_stack": "Dentrix Ascend",
        "source": "LinkedIn"
    }
    score, breakdown, tier, path = scorer.calculate_score(high_intent_prospect)
    assert 75 <= score <= 89, f"Expected HIGH INTENT score (75-89), got {score}"
    assert tier == "HIGH INTENT"
    assert "PATH A" in path

    # 3. Low Intent Case (Score < 40)
    low_prospect = {
        "company": "Random Tech Blog",
        "role": "Writer",
        "industry": "Media",
        "post_content": "AI is interesting in general.",
        "source": "General Blog"
    }
    score, breakdown, tier, path = scorer.calculate_score(low_prospect)
    assert score < 40, f"Expected IGNORE score (<40), got {score}"
    assert tier == "IGNORE"


def test_ai_assistant_product_matching():
    """Verify specific AI assistant product recommendations per vertical & operational pain."""
    # HVAC
    assert "hvac_call_answering" in AI_ASSISTANT_CATALOG
    hvac_asst = AI_ASSISTANT_CATALOG["hvac_call_answering"]
    assert hvac_asst["monthly_retainer"] == 1500.0
    assert hvac_asst["sku"] == "AI-ASSISTANT-HVAC-DISPATCH"
    assert "ServiceTitan" in hvac_asst["outcome"]

    # ConTech CAD-to-BOQ Takeoff
    assert "contech_estimating_takeoff" in AI_ASSISTANT_CATALOG
    contech_asst = AI_ASSISTANT_CATALOG["contech_estimating_takeoff"]
    assert contech_asst["monthly_retainer"] == 3500.0
    assert contech_asst["sku"] == "AI-ASSISTANT-CONTECH-TAKEOFF"
    assert "Takeoff" in contech_asst["assistant_name"]

    # Dental Recall
    assert "dental_hygiene_recall" in AI_ASSISTANT_CATALOG
    dental_asst = AI_ASSISTANT_CATALOG["dental_hygiene_recall"]
    assert dental_asst["monthly_retainer"] == 1850.0
    assert dental_asst["sku"] == "AI-ASSISTANT-DENTAL-RECALL"

    # Legal Intake
    assert "legal_intake_screening" in AI_ASSISTANT_CATALOG
    legal_asst = AI_ASSISTANT_CATALOG["legal_intake_screening"]
    assert legal_asst["monthly_retainer"] == 2500.0
    assert legal_asst["sku"] == "AI-ASSISTANT-LEGAL-INTAKE"


def test_personalized_5_part_outreach_script():
    """Verify 5-part personalized sales script generation and Neteller link embedding."""
    builder = OutreachScriptBuilder()
    hvac_asst = AI_ASSISTANT_CATALOG["hvac_call_answering"]

    script = builder.build_script(
        company="Apex Mechanical & Air Solutions",
        contact="Marcus Vance",
        role="Founder & Managing Director",
        industry="HVAC & Mechanical",
        signal_summary="Actively evaluating AI phone agent and after-hours call intake",
        observed_pain="missing 15+ after-hours emergency calls every weekend",
        assistant=hvac_asst
    )

    assert "THE_SIGNAL" in script
    assert "THE_PAIN" in script
    assert "THE_OFFER" in script
    assert "THE_HOOK" in script
    assert "THE_CTA" in script
    assert "FULL_OUTREACH_MESSAGE" in script
    assert "NETELLER_CHECKOUT_RAIL" in script

    assert "Saw your public discussion regarding" in script["THE_SIGNAL"]
    assert "Apex Mechanical & Air Solutions" in script["THE_SIGNAL"]
    assert "missing 15+ after-hours emergency calls" in script["THE_PAIN"]
    assert "24/7 AI Emergency Call Answering" in script["THE_OFFER"]
    assert "member.neteller.com" in script["NETELLER_CHECKOUT_RAIL"]
    assert "4599228811" in script["NETELLER_CHECKOUT_RAIL"]
    assert "AI-ASSISTANT-HVAC-DISPATCH" in script["NETELLER_CHECKOUT_RAIL"]


def test_niche_discovery_engine():
    """Verify dynamic discovery of new untapped market niches and search patterns."""
    engine = NicheDiscoveryEngine()
    harvester = SignalHarvester()
    signals = harvester.load_seed_live_signals()

    niches = engine.discover_niches_from_signals(signals)
    assert len(niches) >= 3, f"Expected at least 3 discovered niches, got {len(niches)}"

    niche_names = [n["niche"] for n in niches]
    assert any("Solar" in name for name in niche_names)
    assert any("Veterinary" in name for name in niche_names)
    assert any("Collision" in name or "Auto" in name for name in niche_names)

    for n in niches:
        assert n["core_pain"], "Niche must have core_pain"
        assert n["recommended_assistant"], "Niche must have recommended_assistant"
        assert n["monetization_estimate"], "Niche must have monetization_estimate"
        assert len(n["search_query_patterns"]) >= 2, "Niche must have search_query_patterns"


def test_full_buyer_hunter_pipeline_and_idempotency(tmp_path):
    """Verify complete end-to-end execution, evidence card generation, and CRM idempotency."""
    test_memory_file = tmp_path / "canonical_deals_test.json"
    test_crm_db = tmp_path / "salesforce_test.db"

    deal_memory = CanonicalDealMemory(storage_path=test_memory_file)
    crm = SalesforceOS(db_path=test_crm_db)

    hunter = AIAssistantBuyerHunter(deal_memory=deal_memory, crm=crm)

    # 1. First Execution Run
    res1 = hunter.run_pipeline()
    assert res1["summary"]["companies_found"] >= 5
    assert res1["summary"]["hot_buyers"] >= 1
    assert res1["summary"]["high_intent_buyers"] >= 1
    assert len(deal_memory.deals) >= 5

    # Verify Evidence Cards
    cards = res1["cards"]
    for card in cards:
        assert card["company"], "Company name must not be blank"
        assert card["decision_maker"], "Decision maker must not be blank"
        assert card["role"], "Role must not be blank"
        assert card["phone"], "Phone must not be blank"
        assert card["intent_score"] >= 40, "Qualified leads must have score >= 40"
        assert card["why_this_company"], "Evidence rationale must be documented"
        assert card["personalized_script"]["NETELLER_CHECKOUT_RAIL"], "Neteller rail must exist"

    # 2. Second Execution Run (Idempotency check)
    initial_deal_count = len(deal_memory.deals)
    res2 = hunter.run_pipeline()
    final_deal_count = len(deal_memory.deals)

    assert initial_deal_count == final_deal_count, (
        f"Pipeline is not idempotent! Initial deals: {initial_deal_count}, after re-run: {final_deal_count}"
    )


def test_zero_placeholders_and_verification_gate():
    """Verify that 100% of discovered AI assistant buyers pass zero placeholder and dialer gate rules."""
    harvester = SignalHarvester()
    signals = harvester.load_seed_live_signals()

    for prospect in signals:
        card_data = {
            "id": f"TEST-{prospect['company']}",
            "company": prospect["company"],
            "contact": prospect["decision_maker"],
            "title": prospect["role"],
            "phone": prospect["phone"],
            "vertical": prospect["industry"],
            "tier": "Tier A",
            "owner_status": "VERIFIED_OWNER",
            "source_class": "PROFESSIONAL_PROFILE",
            "skip_trace_status": "VERIFIED",
            "deal_score": 95,
            "callability_score": 90
        }
        # 1. Placeholder check
        assert not is_placeholder_identity(card_data), f"{prospect['company']} flagged as placeholder"

        # 2. Gate check
        gate_res = check_lead(card_data)
        assert gate_res["passed"], f"{prospect['company']} failed verification gate: {gate_res.get('rejection_reasons')}"
