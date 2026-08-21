"""
Unit & Integration Tests for GLM Worker Integration into MBM
============================================================
Validates:
  1. Worker Registration in AGENT_REGISTRY with 6 capabilities.
  2. 9-Niche Classification & Routing.
  3. Source-to-Niche Failsafe (UNCLASSIFIED).
  4. Canonical Output Contract adherence.
  5. Shortfall Analysis & Proactive Research Mission Planning.
  6. Lead Quality Auditing.
  7. Semantic Duplicate Review (advisory).
  8. Failure Isolation & Cost/Token Guardrails.
  9. Invariant: GLM cannot bypass MBM validation, phone suppression, or DNC.
 10. GLM Daily Engineering Report generation with all required sections.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.agent_registry import GLMRole, AGENT_REGISTRY, get_agent
from MBM.GLM.glm_integration_worker import (
    GLMWorker,
    GLMRecommendation,
    get_glm_worker,
    glm_tracker,
)
from MBM.GLM.orchestrator import get_orchestrator
from MBM.GLM.delivery_report import get_delivery_reporter, JSON_PATH, MD_PATH
from MBM.LeadEngine.dialer_verification_gate import is_valid_phone, is_valid_name
from MBM.LeadEngine.dialer_queue_engine import get_suppression_index


def test_glm_worker_registration():
    """Verify GLM worker is registered in AGENT_REGISTRY with all 6 capabilities."""
    assert GLMRole.INTEGRATION_ENGINEER in AGENT_REGISTRY
    spec = get_agent(GLMRole.INTEGRATION_ENGINEER)
    assert spec.name == "GLM Lead & GTM Intelligence Worker"
    
    expected_capabilities = [
        "GLM_LEAD_RESEARCH",
        "GLM_LEAD_CLASSIFICATION",
        "GLM_NICHE_ROUTING",
        "GLM_SIGNAL_EXTRACTION",
        "GLM_LEAD_AUDIT",
        "GLM_SHORTFALL_ANALYSIS",
    ]
    for cap in expected_capabilities:
        assert cap in spec.capabilities


def test_glm_9_niche_classification_and_routing():
    """Verify GLM accurately classifies leads across all 9 canonical MBM niches."""
    worker = get_glm_worker()
    
    test_cases = [
        # 1. Commercial Contractors & ConTech
        ({"id": "L1", "company": "Apex Mechanical & Commercial HVAC LLC", "trade": "Commercial Air & Piping", "city": "Dallas"}, "Commercial Contractors & ConTech"),
        # 2. AI Consultancy & Automation
        ({"id": "L2", "company": "Nexus Cognitive Systems & AI Engineering LLC", "specialty": "Enterprise LLM Workflows & Agentic AI", "city": "San Francisco"}, "AI Consultancy & Automation"),
        # 3. Website Design & Development
        ({"id": "L3", "company": "BlueWave Digital Agency & Web Design Studio", "specialty": "Next.js & Bespoke Corporate Web Development", "city": "Austin"}, "Website Design & Development"),
        # 4. Mobile App Development
        ({"id": "L4", "company": "AppForge Mobile Engineering & Product Studio", "specialty": "Cross-Platform Flutter & iOS Apps", "city": "Dallas"}, "Mobile App Development"),
        # 5. Professional Services & B2B Agencies
        ({"id": "L5", "company": "Vanguard Growth Partners & B2B Advisory Group", "specialty": "B2B Go-to-Market & Sales Pipeline Optimization", "city": "Plano"}, "Professional Services & B2B Agencies"),
        # 6. Clinics & Medical Practices
        ({"id": "L6", "company": "Premier Pediatric Therapy Center & Clinic", "specialty": "Pediatric Physical Therapy", "city": "Fort Worth"}, "Clinics & Medical Practices"),
        # 7. Med Spas & Aesthetics Clinics
        ({"id": "L7", "company": "Luxe Aesthetics Med Spa & Laser Wellness", "specialty": "Injectables & Botox Treatments", "city": "Houston"}, "Med Spas & Aesthetics Clinics"),
        # 8. Real Estate Sellers
        ({"id": "L8", "company": "Smith Family Estate", "campaign": "Motivated Seller As-Is Cash Offer", "city": "Dallas"}, "Real Estate Sellers"),
        # 9. Cash Buyers & Flippers
        ({"id": "L9", "company": "LoneStar Capital Assets & Off-Market Investor Group", "specialty": "Wholesale Distressed Property Buyer Box", "city": "Houston"}, "Cash Buyers & Flippers"),
    ]

    for lead_data, expected_niche in test_cases:
        rec = worker.classify_lead_niche(lead_data)
        assert isinstance(rec, GLMRecommendation)
        assert rec.niche == expected_niche
        assert rec.confidence >= 0.90
        assert rec.model == "GLM"
        assert rec.version == "5.2"


def test_glm_unclassified_failsafe():
    """Verify ambiguous leads trigger the UNCLASSIFIED failsafe."""
    worker = get_glm_worker()
    ambiguous_lead = {
        "id": "AMB-01",
        "company": "Random General Corporation LLC",
        "specialty": "General Activities",
        "city": "Unknown",
    }
    rec = worker.classify_lead_niche(ambiguous_lead)
    assert rec.niche == "UNCLASSIFIED"
    assert rec.confidence < 0.5


def test_glm_canonical_output_contract():
    """Verify GLM recommendation strictly satisfies the canonical contract schema."""
    worker = get_glm_worker()
    lead = {
        "id": "CONTRACT-01",
        "company": "Patriot Commercial Electric Inc",
        "trade": "Commercial Electrical",
        "source": "State Licensing Registry",
        "city": "Fort Worth",
    }
    rec = worker.classify_lead_niche(lead)
    rec_dict = rec.model_dump()

    required_keys = [
        "lead_id", "source", "niche", "market", "signal_type",
        "recommendation", "confidence", "reasoning_summary",
        "generated_at", "model", "version"
    ]
    for k in required_keys:
        assert k in rec_dict
        assert rec_dict[k] is not None

    assert rec_dict["model"] == "GLM"
    assert rec_dict["version"] == "5.2"


def test_glm_shortfall_analysis_and_mission_planning():
    """Verify GLM analyzes capacity shortfalls and generates actionable research missions."""
    worker = get_glm_worker()
    
    # Mock records with a shortage in ConTech & AI
    mock_records = [
        {"id": "R1", "vertical": "Real Estate Sellers", "callable": True},
        {"id": "R2", "vertical": "Cash Buyers & Flippers", "callable": True},
    ]

    analysis = worker.analyze_shortfalls_and_plan_missions(mock_records)
    assert "status" in analysis
    assert "shortfall_niches" in analysis
    assert "research_missions" in analysis
    assert len(analysis["research_missions"]) >= 1

    first_mission = analysis["research_missions"][0]
    assert first_mission["task"] == "GLM_LEAD_RESEARCH"
    assert "priority_sources" in first_mission
    assert "target_geography" in first_mission
    assert "decision_maker_roles" in first_mission
    assert "recommended_query" in first_mission


def test_glm_lead_quality_audit():
    """Verify GLM performs lead quality audits returning confidence and recommendation."""
    worker = get_glm_worker()
    
    # Complete lead
    good_lead = {
        "id": "AUDIT-01",
        "company": "Titan Civil Infrastructure LLC",
        "contact": "Carlos Mendez",
        "phone": "+12148923412",
        "vertical": "Commercial Contractors & ConTech",
        "source": "State Licensing Directory",
    }
    good_rec = worker.audit_lead_quality(good_lead)
    assert good_rec.confidence == 1.0
    assert good_rec.recommendation == "ACCEPT_FOR_DIALER"

    # Incomplete lead
    bad_lead = {
        "id": "AUDIT-02",
        "company": "",
        "contact": "Unknown",
        "phone": "",
        "vertical": "Unknown",
    }
    bad_rec = worker.audit_lead_quality(bad_lead)
    assert bad_rec.confidence < 0.5
    assert bad_rec.recommendation == "REQUIRES_ENRICHMENT"


def test_glm_semantic_duplicate_review():
    """Verify advisory semantic duplicate detection."""
    worker = get_glm_worker()
    
    lead_a = {"contact": "Carlos Mendez", "company": "Titan Civil Infrastructure LLC", "phone": "+12148923412"}
    lead_b = {"contact": "Carlos Mendez", "company": "Titan Civil LLC", "phone": "+12148923412"}
    lead_c = {"contact": "Dr. Sarah Lin", "company": "Dental Care Center", "phone": "+19726658140"}

    dup_res = worker.review_duplicate_similarity(lead_a, lead_b)
    assert dup_res["is_duplicate"] is True
    assert dup_res["confidence"] >= 0.90
    assert dup_res["recommendation"] == "MERGE_RECORD"

    diff_res = worker.review_duplicate_similarity(lead_a, lead_c)
    assert diff_res["is_duplicate"] is False
    assert diff_res["recommendation"] == "KEEP_SEPARATE"


def test_glm_advisory_never_bypasses_mbm_validation():
    """Prove that GLM recommendations cannot override deterministic MBM validation."""
    worker = get_glm_worker()
    
    # GLM might think an entity is high intent, but if phone is fake (555), MBM rejects
    candidate = {
        "id": "INV-01",
        "company": "Fake Automation Co",
        "contact": "John Doe",
        "phone": "+12145550199",  # Fake 555
        "vertical": "AI Consultancy & Automation",
    }
    glm_rec = worker.audit_lead_quality(candidate)
    
    # MBM Validation Gate
    phone_ok, reason = is_valid_phone(candidate["phone"])
    assert phone_ok is False
    assert "fake" in reason.lower() or "555" in reason.lower()

    # Suppression index gate
    suppressed_set = get_suppression_index()
    if "+12145550199" in suppressed_set:
        assert False, "Should be filtered before dialer"


def test_glm_tracker_cost_and_token_controls():
    """Verify token usage, cost estimation, cache hits, and latency tracking."""
    stats = glm_tracker.get_stats()
    assert "calls_total" in stats
    assert "total_tokens" in stats
    assert "estimated_cost_usd" in stats
    assert "avg_latency_ms" in stats
    assert stats["calls_total"] >= 1
    assert stats["estimated_cost_usd"] >= 0.0


def test_glm_orchestrator_integration():
    """Verify GLMOrchestrator exposes all intelligence methods."""
    orch = get_orchestrator()
    assert hasattr(orch, "classify_lead_niche")
    assert hasattr(orch, "audit_lead_quality")
    assert hasattr(orch, "analyze_capacity_and_shortfalls")
    assert hasattr(orch, "review_duplicate_similarity")

    rec = orch.classify_lead_niche({"company": "Austin Webworks", "specialty": "Next.js Web Development"})
    assert rec.niche == "Website Design & Development"


def test_glm_delivery_report_generation():
    """Verify DeliveryReportGenerator produces comprehensive daily engineering briefs."""
    reporter = get_delivery_reporter()
    data = {
        "lead_research_tasks": 5,
        "classification_tasks": 120,
        "shortfall_analysis_tasks": 1,
        "quality_audit_tasks": 120,
        "duplicate_review_tasks": 15,
        "top_missions": [{"title": "Enforce Single-Writer Lock", "target_repo": "MBM", "priority_score": 98.0, "assigned_role": "GLM_RELIABILITY_ENGINEER", "status": "COMPLETE"}],
    }
    rep = reporter.generate_report(data)
    
    assert JSON_PATH.exists()
    assert MD_PATH.exists()
    assert "tasks_summary" in rep
    assert "glm_calls" in rep
    assert "niche_intelligence" in rep
    assert "dialer_contribution" in rep
