from MBM.LeadEngine.intelligence.types import IntelligenceEvent, Provenance, AffiliateOffer
from MBM.LeadEngine.intelligence.opportunity_engine import OpportunityEngine, ScoringConfig
from MBM.LeadEngine.intelligence.anderro_adapter import AnderroAdapter

def _evt(title, topics=None, freshness=3600, conf=0.8):
    return IntelligenceEvent(id="evt1", source="worldmonitor", category="tech", title=title, topics=topics or [], freshnessSeconds=freshness, confidence=conf, provenance=Provenance(provider="worldmonitor"))

def test_anderro_without_key_returns_not_verified():
    a = AnderroAdapter(api_key="")
    offers = a.list_offers(vertical="tech")
    assert len(offers) == 1
    assert offers[0].status == "NOT_VERIFIED"
    assert offers[0].commissionRate is None

def test_opportunity_scoring_weights_configurable():
    cfg = ScoringConfig.for_tests()
    eng = OpportunityEngine(cfg)
    evt = _evt("AI services for clinics raise funding", topics=["ai", "clinic"], freshness=100, conf=0.9)
    offer = AffiliateOffer(offerId="off1", vertical="ai services", commissionRate=0.4, verifiedAt="2026-09-01T00:00:00Z", confidence=1.0, status="VERIFIED")
    ranked = eng.rank([evt], [offer], top_n=1)
    assert ranked[0]["score"] > 0.5
    assert ranked[0]["matched_offer"]["offerId"] == "off1"

def test_opportunity_without_offer_is_neutral():
    eng = OpportunityEngine(ScoringConfig.for_tests())
    evt = _evt("Some tech news", freshness=100000)
    ranked = eng.rank([evt], [], top_n=1)
    assert ranked[0]["score"] >= 0 and ranked[0]["score"] <= 1

def test_anderro_never_invents_rate_from_placeholder():
    a = AnderroAdapter(api_key="")
    offers = a.list_offers(vertical="saas")
    # placeholder has no invented commission
    assert offers[0].commissionRate is None
    assert offers[0].confidence == 0.0
