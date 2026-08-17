"""
test_ai_buyer_hunter.py — Comprehensive Test Suite for MBM AI Assistant Buyer Hunter Engine
===========================================================================================
Verifies:
1. 100-Point Intent Scoring Math, Authority, Contactability, and Recency Timing
2. Negative Signal Filtering (Students, Job Seekers, AI Tool Vendors, Academic News)
3. Multi-Channel Outreach Generation (Phone Angle, Cold Email, LinkedIn DM, Reddit Research)
4. AI Assistant Product Matrix & 15 Vertical Workflow Fits
5. The 4 "WHY"s for every Hot / High-Intent Lead
6. Queryable Prospect Relevance Graph
7. Niche Discovery Engine (Solar, Emergency Vet, Auto Collision)
8. Canonical Deal Memory & SalesforceOS CRM Integration & Idempotency
9. Dialer Verification Gate Compliance & Zero Synthetic Identity Placeholders
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
    EvidenceCard, ProspectRelevanceGraph
)
from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory, DealType, DealStage, MonetizationRoute
from MBM.LeadEngine.dialer_verification_gate import check_lead, is_placeholder_identity
from MBM.SalesforceOS.salesforce_os import SalesforceOS


def test_100_point_scoring_formula_and_tiers():
    """Verify exact 100-point scoring algorithm, authority, contactability, and tier boundaries."""
    scorer = BuyerIntentScorer()

    # 1. Hot Case (Score >= 90)
    hot_prospect = {
        "company": "Summit HVAC & Air",
        "role": "Founder & Managing Director",
        "industry": "HVAC & Mechanical",
        "phone": "+12148849120",
        "email": "owner@summithvac.com",
        "website": "https://summithvac.com",
        "location": "Dallas, TX",
        "post_content": "We're missing 20+ after-hours emergency calls every weekend. Inbound calls went to voicemail. Need an AI phone agent or automated call intake that connects to ServiceTitan.",
        "pain_description": "20+ after-hours emergency replacement calls missed weekly.",
        "intent_signal": "Actively evaluating AI phone agent and after-hours call intake.",
        "hiring_title": "Weekend Emergency Dispatcher",
        "tech_stack": "ServiceTitan",
        "locations_count": 2,
        "source": "LinkedIn Post & Comments",
        "signal_age_days": 2
    }
    (
        intent_score, authority_score, contactability_score,
        confidence_score, recency_score, breakdown, tier, path
    ) = scorer.calculate_score(hot_prospect)

    assert intent_score >= 90, f"Expected HOT score (>=90), got {intent_score}"
    assert tier == "HOT"
    assert "PATH A" in path
    assert authority_score == 100
    assert contactability_score >= 80
    assert recency_score == 100
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
        "industry": "Dental Clinics & Orthodontics",
        "phone": "+19726658140",
        "email": "owner@metrodental.com",
        "website": "https://metrodental.com",
        "location": "Plano, TX",
        "post_content": "Our front desk is overwhelmed with phone calls and overdue hygiene recalls. Looking for automation tools to help with recall calls.",
        "pain_description": "Overdue hygiene recalls uncalled due to front desk phone bottleneck.",
        "intent_signal": "Searching for automation tools.",
        "hiring_title": "Front Desk Receptionist",
        "tech_stack": "Dentrix Ascend",
        "source": "LinkedIn Discussion",
        "signal_age_days": 5
    }
    (
        intent_score, authority_score, contactability_score,
        confidence_score, recency_score, breakdown, tier, path
    ) = scorer.calculate_score(high_intent_prospect)

    assert 75 <= intent_score <= 89, f"Expected HIGH INTENT score (75-89), got {intent_score}"
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
    (
        intent_score, authority_score, contactability_score,
        confidence_score, recency_score, breakdown, tier, path
    ) = scorer.calculate_score(low_prospect)

    assert intent_score < 40, f"Expected IGNORE score (<40), got {intent_score}"
    assert tier == "IGNORE"


def test_negative_signal_filtering():
    """Verify negative signals (students, job seekers, AI tool vendors) are penalized/filtered."""
    scorer = BuyerIntentScorer()

    student_prospect = {
        "company": "University Lab",
        "role": "PhD Candidate & Student",
        "industry": "Education",
        "post_content": "I am a student studying AI and looking for job opportunities in AGI.",
        "source": "LinkedIn"
    }
    (
        intent_score, authority_score, contactability_score,
        confidence_score, recency_score, breakdown, tier, path
    ) = scorer.calculate_score(student_prospect)

    assert breakdown["negative_penalty"] < 0
    assert tier == "IGNORE"

    vendor_prospect = {
        "company": "NewBotAI",
        "role": "Founder of AI Platform",
        "industry": "Software",
        "post_content": "We built an AI tool for customer service! DM me for demo.",
        "source": "Reddit"
    }
    (
        intent_score, authority_score, contactability_score,
        confidence_score, recency_score, breakdown, tier, path
    ) = scorer.calculate_score(vendor_prospect)

    assert breakdown["negative_penalty"] < 0


def test_ai_assistant_catalog_coverage():
    """Verify specific AI assistant product recommendations across 15 vertical fits."""
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

    # Solar Intake
    assert "solar_intake_qualifier" in AI_ASSISTANT_CATALOG
    solar_asst = AI_ASSISTANT_CATALOG["solar_intake_qualifier"]
    assert solar_asst["monthly_retainer"] == 1850.0

    # Vet Triage
    assert "vet_emergency_triage" in AI_ASSISTANT_CATALOG
    vet_asst = AI_ASSISTANT_CATALOG["vet_emergency_triage"]
    assert vet_asst["monthly_retainer"] == 2000.0

    # Auto Collision
    assert "auto_collision_status" in AI_ASSISTANT_CATALOG
    auto_asst = AI_ASSISTANT_CATALOG["auto_collision_status"]
    assert auto_asst["monthly_retainer"] == 1500.0

    # Accounting Tax Intake
    assert "accounting_tax_intake" in AI_ASSISTANT_CATALOG
    tax_asst = AI_ASSISTANT_CATALOG["accounting_tax_intake"]
    assert tax_asst["monthly_retainer"] == 1750.0


def test_multi_channel_outreach_script_builder():
    """Verify Phone, Email, LinkedIn, and Reddit outreach angle generation."""
    builder = OutreachScriptBuilder()
    hvac_asst = AI_ASSISTANT_CATALOG["hvac_call_answering"]

    angles = builder.build_angles(
        company="Apex Mechanical & Air Solutions",
        contact="Marcus Vance",
        role="Founder & Managing Director",
        industry="HVAC & Mechanical",
        signal_summary="Actively evaluating AI phone agent and after-hours call intake",
        observed_pain="missing 15+ after-hours emergency calls every weekend",
        assistant=hvac_asst
    )

    assert "PHONE_ANGLE" in angles
    assert "EMAIL_ANGLE" in angles
    assert "LINKEDIN_ANGLE" in angles
    assert "REDDIT_ANGLE" in angles
    assert "NETELLER_CHECKOUT_RAIL" in angles

    assert "Marcus" in angles["PHONE_ANGLE"]
    assert "Apex Mechanical & Air Solutions" in angles["EMAIL_ANGLE"]
    assert "24/7 AI Emergency Call Answering" in angles["FULL_OUTREACH_MESSAGE"]
    assert "member.neteller.com" in angles["NETELLER_CHECKOUT_RAIL"]
    assert "4599228811" in angles["NETELLER_CHECKOUT_RAIL"]


def test_prospect_relevance_graph_querying():
    """Verify structured graph queries across Vertical, Pain, Location, and Tier (REAL NPI supply)."""
    hunter = AIAssistantBuyerHunter()
    results = hunter.run_discovery_pipeline()
    graph_dict = results["graph"]
    assert graph_dict["total_nodes"] > 50

    # Test Graph Query Filter
    graph = ProspectRelevanceGraph(results["cards"])

    # 1. Query by Vertical (real medical verticals from the NPI registry)
    medical_nodes = graph.query(vertical="Medical")
    assert len(medical_nodes) >= 1

    # 2. Query by Location (nationwide NPI registry — TX present)
    tx_nodes = graph.query(location="TX")
    assert len(tx_nodes) >= 1

    # 3. Query by Tier
    high_nodes = graph.query(tier="HIGH INTENT")
    assert len(high_nodes) >= 1


def test_niche_discovery_clustering():
    """Verify automatic clustering of new market niches from signals."""
    harvester = SignalHarvester()
    signals = harvester.harvest_all_sources()
    niches = NicheDiscoveryEngine.discover_niches_from_signals(signals)

    assert len(niches) >= 3
    niche_titles = [n["niche"] for n in niches]
    assert any("Solar" in t for t in niche_titles)
    assert any("Veterinary" in t for t in niche_titles)
    assert any("Collision" in t for t in niche_titles)


def test_idempotent_crm_ingestion():
    """Verify that multiple runs do not create duplicate deals in CanonicalDealMemory and SalesforceOS."""
    memory = CanonicalDealMemory()
    crm = SalesforceOS()
    hunter = AIAssistantBuyerHunter(deal_memory=memory, crm=crm)

    # Run 1
    res1 = hunter.run_discovery_pipeline()
    count1 = len(memory.deals)

    # Run 2
    res2 = hunter.run_discovery_pipeline()
    count2 = len(memory.deals)

    assert count1 == count2, f"Expected idempotent deal count {count1}, got {count2}"
    assert res1["summary"]["hot_buyers"] == res2["summary"]["hot_buyers"]


def test_zero_synthetic_identity_placeholders():
    """Verify every high-intent card is REAL: passes the provenance gate, zero fabricated data."""
    from MBM.LeadEngine.lead_provenance import LeadProvenanceGate
    hunter = AIAssistantBuyerHunter()
    results = hunter.run_discovery_pipeline()
    gate = LeadProvenanceGate()

    assert results["summary"]["hot_buyers"] == 0, "Zero-synthetic rule: HOT personas must never appear"
    for card in results["cards"]:
        assert not is_placeholder_identity({"contact": card["decision_maker"], "company": card["company"]})
        assert len(card["phone"]) >= 10
        # Every card must pass the strict provenance gate (source, ref, method, timestamps).
        assert gate.evaluate(card)["ok"], f"Card failed provenance gate: {card['company']}"
        assert card["source"] == "CMS NPI Registry API v2.1"
        assert card["source_reference"] == "NPI-REGISTRY"
        assert card["verification_method"] == "npi_registry_api"
        assert card["why_this_company"]
        assert card["why_now"]
        assert card["outreach_phone_angle"]
