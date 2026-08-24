"""
MBM LeadEngine — Test Land Acquisition Engine
=============================================
Tests the buyer-first architecture components and P0 regressions.
"""

import pytest
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from MBM.LeadEngine.canonical_lead_schema import CanonicalBuyer
from MBM.LeadEngine.buyer_matching_engine import BuyerMatchingEngine
from MBM.LeadEngine.land_property_source import LandPropertySource, SourceStatus as LandSourceStatus
from MBM.LeadEngine.buyer_discovery_engine import BuyerDiscoveryEngine, SourceStatus as BuyerSourceStatus
from MBM.LeadEngine.lead_quality_scorer import score_lead
from MBM.LeadEngine.daily_lead_factory import DailyLeadFactory

def test_buyer_discovery_no_source():
    # TEST 5 / TEST 6 concept for discovery engines
    engine = BuyerDiscoveryEngine(buyer_data_path=Path("dummy_does_not_exist.json"))
    status, buyers = engine.discover_active_buyers()
    assert status == BuyerSourceStatus.NO_SOURCE_CONFIGURED
    assert len(buyers) == 0

def test_buyer_matching_engine_8_cases():
    matcher = BuyerMatchingEngine()
    buyer = CanonicalBuyer(
        buyer_id="TEST-1", buyer_name="Test", company="Test", buyer_type="investor",
        market="Test", state="TX", county="Dallas", target_zip=[], 
        min_acres=0.5, max_acres=2.0, target_lot_size="", price_min=0, price_max=0,
        price_per_lot=0, zoning=["Residential"], utilities=[], road_access=[], property_type=[],
        lots_per_month=0, homes_per_year=0, buying_activity="ACTIVE", source="", source_url="",
        evidence="", observed_at="", confidence=90, status="ACTIVE"
    )
    
    # Case A: Perfect match (State, County, Acreage, Zoning, Absentee)
    prop_a = {"id": "A", "state": "TX", "county": "Dallas", "acreage": 1.0, "zoning": "Residential", "absentee_owner": True}
    match_a = matcher._calculate_match(prop_a, buyer)
    assert match_a.match_score == 100.0  # 40 + 20 + 20 + 10 + 10 (bonus)

    # Case B: State mismatch
    prop_b = {"id": "B", "state": "FL", "county": "Dallas", "acreage": 1.0, "zoning": "Residential"}
    match_b = matcher._calculate_match(prop_b, buyer)
    assert match_b.match_score == 0.0

    # Case C: State matches, County mismatches
    prop_c = {"id": "C", "state": "TX", "county": "Tarrant", "acreage": 1.0, "zoning": "Residential"}
    match_c = matcher._calculate_match(prop_c, buyer)
    assert match_c.match_score == 70.0  # 40 (State) + 0 (County) + 20 (Acreage) + 10 (Zoning)

    # Case D: Acreage too small
    prop_d = {"id": "D", "state": "TX", "county": "Dallas", "acreage": 0.1, "zoning": "Residential"}
    match_d = matcher._calculate_match(prop_d, buyer)
    assert match_d.match_score == 70.0  # 40 (State) + 20 (County) + 0 (Acreage) + 10 (Zoning)

    # Case E: Acreage too large
    prop_e = {"id": "E", "state": "TX", "county": "Dallas", "acreage": 5.0, "zoning": "Residential"}
    match_e = matcher._calculate_match(prop_e, buyer)
    assert match_e.match_score == 70.0  # 40 (State) + 20 (County) + 0 (Acreage) + 10 (Zoning)

    # Case F: Zoning mismatch
    prop_f = {"id": "F", "state": "TX", "county": "Dallas", "acreage": 1.0, "zoning": "Commercial"}
    match_f = matcher._calculate_match(prop_f, buyer)
    assert match_f.match_score == 80.0  # 40 (State) + 20 (County) + 20 (Acreage) + 0 (Zoning)

    # Case G: Absentee owner bonus
    prop_g = {"id": "G", "state": "TX", "county": "Tarrant", "acreage": 1.0, "zoning": "Commercial", "absentee_owner": True}
    match_g = matcher._calculate_match(prop_g, buyer)
    assert match_g.match_score == 70.0  # 40(S) + 0(C) + 20(A) + 0(Z) + 10(Absentee bonus)

    # Case H: Missing buyer buy-box criteria defaults safely
    buyer_h = CanonicalBuyer(
        buyer_id="TEST-2", buyer_name="Test", company="Test", buyer_type="investor",
        market="Test", state="", county="", target_zip=[], 
        min_acres=0.0, max_acres=0.0, target_lot_size="", price_min=0, price_max=0,
        price_per_lot=0, zoning=[], utilities=[], road_access=[], property_type=[],
        lots_per_month=0, homes_per_year=0, buying_activity="ACTIVE", source="", source_url="",
        evidence="", observed_at="", confidence=90, status="ACTIVE"
    )
    prop_h = {"id": "H", "state": "TX", "county": "Dallas", "acreage": 1.0, "zoning": "Commercial"}
    match_h = matcher._calculate_match(prop_h, buyer_h)
    assert match_h.match_score == 90.0  # 40 (State open) + 20 (County open) + 20 (Acreage open) + 10 (Zoning open)

def test_lead_quality_scorer_land_tiers():
    lead = {
        "id": "1",
        "address": "123 Dirt Rd",
        "city": "Dallas",
        "state": "TX",
        "acreage": 2.5,
        "zoning": "Residential",
        "buyer_match_score": 95,
        "verified_phone": "+15550100000",
        "verified_source": "DCAD",
        "verified_at": "2026-08-24T12:00:00Z"
    }
    
    res = score_lead(lead)
    assert res["factors"]["property_fit"]["score"] > 0
    assert res["factors"]["buyer_demand"]["score"] == 95

def test_p0_daily_lead_factory_retention_all_sources_active(monkeypatch):
    """
    Covers Tests 1, 2, 4: Land + match survives, Land + mismatch survives, Normal non-land survives.
    """
    DailyLeadFactory._real_pool = None
    factory = DailyLeadFactory()
    
    non_land_leads = [{"id": "NPI-1", "company": "Doc 1"}, {"id": "NPI-2", "company": "Doc 2"}]
    monkeypatch.setattr(factory, "_load_real_ai_buyers_from_npi", lambda: non_land_leads)
    
    class MockLandSource:
        def load_properties(self):
            return LandSourceStatus.READY, [
                {"id": "SELLER-MATCH", "state": "TX", "acreage": 1.0},
                {"id": "SELLER-MISMATCH", "state": "FL", "acreage": 10.0}
            ]
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.LandPropertySource", MockLandSource)
    
    class MockBuyerEngine:
        def discover_active_buyers(self):
            b = CanonicalBuyer(
                buyer_id="TEST-1", buyer_name="Test", company="Test", buyer_type="investor",
                market="Test", state="TX", county="", target_zip=[], 
                min_acres=0.5, max_acres=2.0, target_lot_size="", price_min=0, price_max=0,
                price_per_lot=0, homes_per_year=0, buying_activity="ACTIVE", source="", source_url="",
                evidence="", observed_at="", confidence=90, status="ACTIVE"
            )
            return BuyerSourceStatus.READY, [b]
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.BuyerDiscoveryEngine", MockBuyerEngine)
    
    pool = factory._load_real_candidate_pool()
    assert len(pool) == 4
    
    seller_match = next(p for p in pool if p["id"] == "SELLER-MATCH")
    seller_mismatch = next(p for p in pool if p["id"] == "SELLER-MISMATCH")
    assert seller_match.get("buyer_match_score", 0) > 0
    assert seller_mismatch.get("buyer_match_score", 0) == 0

def test_p0_daily_lead_factory_retention_no_buyer_source(monkeypatch):
    """
    Covers Tests 3, 5: Land + no buyer survives, Buyer source unavailable -> pipeline functional.
    """
    DailyLeadFactory._real_pool = None
    factory = DailyLeadFactory()
    non_land_leads = [{"id": "NPI-1", "company": "Doc 1"}, {"id": "NPI-2", "company": "Doc 2"}]
    monkeypatch.setattr(factory, "_load_real_ai_buyers_from_npi", lambda: non_land_leads)
    
    class MockLandSource:
        def load_properties(self):
            return LandSourceStatus.READY, [{"id": "SELLER-MATCH", "state": "TX", "acreage": 1.0}]
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.LandPropertySource", MockLandSource)
    
    class MockBuyerEngineNoSource:
        def discover_active_buyers(self):
            return BuyerSourceStatus.NO_SOURCE_CONFIGURED, []
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.BuyerDiscoveryEngine", MockBuyerEngineNoSource)
    
    pool = factory._load_real_candidate_pool()
    assert len(pool) == 3
    ids = [p["id"] for p in pool]
    assert "SELLER-MATCH" in ids
    assert "NPI-1" in ids

def test_p0_daily_lead_factory_retention_no_land_source(monkeypatch):
    """
    Covers Test 6: LandPropertySource unavailable -> safe failure, normal leads survive.
    """
    DailyLeadFactory._real_pool = None
    factory = DailyLeadFactory()
    non_land_leads = [{"id": "NPI-1", "company": "Doc 1"}, {"id": "NPI-2", "company": "Doc 2"}]
    monkeypatch.setattr(factory, "_load_real_ai_buyers_from_npi", lambda: non_land_leads)
    
    class MockLandSourceNoSource:
        def load_properties(self):
            return LandSourceStatus.NO_SOURCE_CONFIGURED, []
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.LandPropertySource", MockLandSourceNoSource)
    
    class MockBuyerEngine:
        def discover_active_buyers(self):
            return BuyerSourceStatus.READY, []
    monkeypatch.setattr("MBM.LeadEngine.daily_lead_factory.BuyerDiscoveryEngine", MockBuyerEngine)
    
    pool = factory._load_real_candidate_pool()
    assert len(pool) == 2
    ids = [p["id"] for p in pool]
    assert "NPI-1" in ids
