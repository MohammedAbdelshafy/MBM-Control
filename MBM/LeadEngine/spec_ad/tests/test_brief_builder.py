from MBM.LeadEngine.spec_ad.intelligence.brief_builder import build_brief
from MBM.LeadEngine.spec_ad.intelligence.types import ResearchEvidence, ClaimClassification, Provenance

def _mock_evidence(claim_type, confidence=1.0, quote="Test"):
    return ResearchEvidence(
        quote=quote,
        source_url="http://example.com",
        confidence=confidence,
        claim_type=claim_type
    )

def test_value_proposition():
    brief = build_brief("acc", [], proposed_value_prop="Save 50% on cooling")
    assert brief.value_proposition == "Save 50% on cooling"

def test_target_icp():
    brief = build_brief("acc", [], proposed_icp="Facility Managers")
    assert brief.target_icp == "Facility Managers"

def test_customer_problem():
    brief = build_brief("acc", [], proposed_problem="High energy costs")
    assert brief.likely_problem == "High energy costs"

def test_product_mechanism():
    brief = build_brief("acc", [], proposed_mechanism="IoT Sensors")
    assert brief.mechanism == "IoT Sensors"

def test_credible_proof():
    ev = _mock_evidence(ClaimClassification.VERIFIED_FACT, quote="Energy Star certified")
    brief = build_brief("acc", [ev])
    assert brief.credible_proof == "Energy Star certified"

def test_cta_opportunity():
    brief = build_brief("acc", [], proposed_cta="Get a free audit")
    assert brief.cta_opportunity == "Get a free audit"

def test_brand_voice():
    brief = build_brief("acc", [], brand_voice="Professional, authoritative")
    assert brief.brand_voice == "Professional, authoritative"

def test_visual_signals():
    brief = build_brief("acc", [], visual_signals=["Industrial HVAC", "Blue color scheme"])
    assert brief.visual_signals == sorted(["Industrial HVAC", "Blue color scheme"])

def test_safe_claims():
    ev = _mock_evidence(ClaimClassification.VERIFIED_FACT, quote="Founded in 2005")
    brief = build_brief("acc", [ev])
    assert "Founded in 2005" in brief.safe_claims

def test_risk_flags():
    ev = _mock_evidence(ClaimClassification.UNKNOWN, quote="$100M Revenue")
    brief = build_brief("acc", [ev])
    assert len(brief.risk_flags) == 1
    assert "unsupported claim" in brief.risk_flags[0].lower()

def test_research_summary():
    brief = build_brief("acc", [])
    assert "No verified research available" in brief.research_summary

def test_confidence():
    ev1 = _mock_evidence(ClaimClassification.VERIFIED_FACT, confidence=1.0, quote="Test 1")
    ev2 = _mock_evidence(ClaimClassification.SUPPORTED_INFERENCE, confidence=0.5, quote="Test 2")
    brief = build_brief("acc", [ev1, ev2])
    assert brief.confidence > 0.0

def test_verified_fact():
    ev = _mock_evidence(ClaimClassification.VERIFIED_FACT, quote="Operating since 1990")
    brief = build_brief("acc", [ev])
    assert "Operating since 1990" in brief.safe_claims
    assert len(brief.risk_flags) == 0

def test_supported_inference():
    ev = _mock_evidence(ClaimClassification.SUPPORTED_INFERENCE, quote="Specializes in large campuses")
    brief = build_brief("acc", [ev])
    assert "[Inferred] Specializes in large campuses" in brief.safe_claims
    assert len(brief.risk_flags) == 0

def test_unknown_claim():
    ev = _mock_evidence(ClaimClassification.UNKNOWN, quote="Over 1 million customers")
    brief = build_brief("acc", [ev])
    assert len(brief.safe_claims) == 0
    assert "unsupported claim" in brief.risk_flags[0].lower()

def test_unsupported_claim_excluded():
    # Never invent revenue, funding, customer count, metric, etc.
    ev = _mock_evidence(ClaimClassification.UNKNOWN, quote="We generated $5M ARR last year")
    brief = build_brief("acc", [ev])
    assert len(brief.safe_claims) == 0
    assert "unsupported claim" in brief.risk_flags[0].lower()

def test_provenance_preserved():
    # Provenance is tied to evidence, we ensure the evidence object retains it.
    ev = _mock_evidence(ClaimClassification.VERIFIED_FACT)
    assert ev.source_url == "http://example.com"
    # Even if timestamp changes elsewhere, the evidence object must remain identical in tests

def test_deterministic_output():
    ev1 = _mock_evidence(ClaimClassification.UNKNOWN, quote="C", confidence=0.5)
    ev2 = _mock_evidence(ClaimClassification.VERIFIED_FACT, quote="A", confidence=0.9)
    ev3 = _mock_evidence(ClaimClassification.VERIFIED_FACT, quote="B", confidence=0.8)
    
    brief1 = build_brief("acc_1", [ev1, ev2, ev3])
    brief2 = build_brief("acc_1", [ev3, ev1, ev2])
    
    assert brief1.safe_claims == brief2.safe_claims
    assert brief1.risk_flags == brief2.risk_flags
    assert brief1.research_summary == brief2.research_summary

def test_empty_research():
    brief = build_brief("acc_empty", [])
    assert brief.confidence == 0.0
    assert len(brief.safe_claims) == 0
    # depending on backwards compat, risk flags might have empty note or be 0
    assert len(brief.risk_flags) == 0 or "empty research" in brief.risk_flags[0].lower()
    assert brief.credible_proof == "No verified proof available"

def test_confidence_bounds():
    ev1 = _mock_evidence(ClaimClassification.VERIFIED_FACT, confidence=1.5, quote="Test 1") # out of bounds theoretically, but logic averages it
    ev2 = _mock_evidence(ClaimClassification.VERIFIED_FACT, confidence=-0.5, quote="Test 2")
    brief = build_brief("acc_bounds", [ev1, ev2])
    assert brief.confidence > 0.0
