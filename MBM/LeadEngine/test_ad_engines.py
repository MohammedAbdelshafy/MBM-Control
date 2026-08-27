"""
MBM LeadEngine — Acquisition-Disposition Engine Tests
=====================================================
Hermetic tests for all P0 engines.
No network calls, no external dependencies.
"""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.buyer_buy_box_engine import BuyerBuyBoxEngine, BuyerBuyBox, MatchResult
from MBM.LeadEngine.deal_scoring_engine import DealScoringEngine, DealScore
from MBM.LeadEngine.deal_submission_engine import DealSubmissionEngine, DealSubmission
from MBM.LeadEngine.social_cta_router import SocialCTARouter, SocialInteraction, IntentType
from MBM.LeadEngine.next_best_action_engine import NextBestActionEngine, ActionType


def test_buyer_buy_box_registration():
    """Test buyer buy box creation and retrieval."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        engine = BuyerBuyBoxEngine(storage_path=path)

        buyer = BuyerBuyBox(
            buyer_id="B001",
            buyer_name="John Smith",
            company="Smith Investments",
            markets=["Houston"],
            property_types=["SFR"],
            price_min=100000,
            price_max=250000,
            arv_min=150000,
            arv_max=400000,
            rehab_max=40000,
            strategy=["FIX_AND_FLIP"],
            cash_or_finance=["CASH"],
            closing_speed_days=14,
            activity_score=80,
            verification_status="VERIFIED",
        )

        registered = engine.register_buyer(buyer)
        assert registered.buyer_id == "B001"
        assert registered.buyer_name == "John Smith"

        retrieved = engine.get_buyer("B001")
        assert retrieved is not None
        assert retrieved.markets == ["Houston"]

        active = engine.get_active_buyers()
        assert len(active) == 1

        print("PASS: test_buyer_buy_box_registration")
    finally:
        path.unlink(missing_ok=True)


def test_buyer_match_score():
    """Test deal-to-buyer matching scoring."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        engine = BuyerBuyBoxEngine(storage_path=path)

        buyer = BuyerBuyBox(
            buyer_id="B001",
            buyer_name="Test Buyer",
            markets=["Houston"],
            property_types=["SFR"],
            price_min=100000,
            price_max=250000,
            arv_min=150000,
            arv_max=400000,
            rehab_max=40000,
            strategy=["FIX_AND_FLIP"],
            activity_score=80,
            verification_status="VERIFIED",
        )
        engine.register_buyer(buyer)

        # Perfect match deal
        deal = {
            "id": "D001",
            "city": "Houston",
            "property_type": "SFR",
            "asking_price": 150000,
            "arv": 280000,
            "estimated_repairs": 25000,
            "zip_code": "77001",
        }

        results = engine.match_deal_to_buyers(deal)
        assert len(results) >= 1
        assert results[0].match_score >= 60
        assert "market_match" in results[0].positive_matches
        assert "price_in_range" in results[0].positive_matches

        print("PASS: test_buyer_match_score")
    finally:
        path.unlink(missing_ok=True)


def test_demand_signal():
    """Test demand signal calculation."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        engine = BuyerBuyBoxEngine(storage_path=path)

        # Add 5 active buyers for Houston SFR
        for i in range(5):
            buyer = BuyerBuyBox(
                buyer_id=f"B{i:03d}",
                buyer_name=f"Buyer {i}",
                markets=["Houston"],
                property_types=["SFR"],
                price_min=100000,
                price_max=250000,
                activity_score=70,
                verification_status="VERIFIED",
            )
            engine.register_buyer(buyer)

        demand = engine.calculate_demand("Houston", "SFR", 100000, 250000)
        assert demand.signal == "HOT"
        assert demand.active_buyers == 5

        # No buyers for Dallas
        demand_dallas = engine.calculate_demand("Dallas", "SFR", 100000, 250000)
        assert demand_dallas.signal == "UNKNOWN"

        print("PASS: test_demand_signal")
    finally:
        path.unlink(missing_ok=True)


def test_deal_scoring():
    """Test deal scoring with MAO calculation."""
    engine = DealScoringEngine()

    # Excellent deal
    deal = {
        "id": "D001",
        "address": "123 Main St",
        "asking_price": 120000,
        "arv": 280000,
        "arv_source": "COMPS_VERIFIED",
        "estimated_repairs": 25000,
        "repair_source": "CONTRACTOR_BID",
        "property_type": "SFR",
        "closing_date": "2026-09-15",
    }

    score = engine.score_deal(deal, demand_signal="HOT", active_buyers=8)

    assert score.overall_score >= 70
    assert score.quality_grade in ("A+", "A", "B+")
    assert score.mao is not None
    assert score.mao == (280000 * 0.70) - 25000  # 171000
    assert score.margin == 280000 - 120000 - 25000  # 135000
    assert score.confidence > 0.5

    # Bad deal (negative margin)
    bad_deal = {
        "id": "D002",
        "address": "456 Oak Ave",
        "asking_price": 250000,
        "arv": 280000,
        "estimated_repairs": 50000,
        "property_type": "SFR",
    }

    bad_score = engine.score_deal(bad_deal, demand_signal="WEAK", active_buyers=1)
    assert bad_score.margin is not None
    assert bad_score.margin < 0

    print("PASS: test_deal_scoring")


def test_deal_submission():
    """Test deal submission and validation."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        engine = DealSubmissionEngine(storage_path=path)

        # Complete deal
        deal = DealSubmission(
            address="123 Main St",
            city="Houston",
            state="TX",
            asking_price=150000,
            property_type="SFR",
            arv=250000,
            estimated_repairs=30000,
        )

        submitted = engine.submit_deal(deal)
        assert submitted.status == "INTAKE"

        validation = engine.validate_deal(submitted)
        assert validation.is_valid
        assert len(validation.missing_critical) == 0

        # Incomplete deal
        incomplete = DealSubmission(
            address="",
            city="",
            state="",
            asking_price=0,
        )

        submitted2 = engine.submit_deal(incomplete)
        validation2 = engine.validate_deal(submitted2)
        assert not validation2.is_valid
        assert len(validation2.missing_critical) > 0

        print("PASS: test_deal_submission")
    finally:
        path.unlink(missing_ok=True)


def test_social_cta_routing():
    """Test social CTA keyword extraction and routing."""
    router = SocialCTARouter()

    # Deal source
    interaction = SocialInteraction(
        platform="instagram",
        username="wholesaler123",
        message="I have a DEAL in Houston, under contract, asking $150K",
    )
    result = router.route_interaction(interaction)
    assert result.intent == "deal_source"
    assert result.pipeline == "deal_source"
    assert "DEAL" in result.matched_keywords

    # Seller
    interaction2 = SocialInteraction(
        platform="facebook",
        username="motivated_seller",
        message="I need to SELL my house, going through DIVORCE",
    )
    result2 = router.route_interaction(interaction2)
    assert result2.intent == "seller"
    assert result2.priority == "HOT"  # DIVORCE is a high-priority signal

    # Buyer
    interaction3 = SocialInteraction(
        platform="instagram",
        username="cash_buyer",
        message="I'm a CASH BUYER looking for FLIP opportunities in Houston",
    )
    result3 = router.route_interaction(interaction3)
    assert result3.intent == "buyer"
    assert result3.pipeline == "buyer"

    # JV Partner
    interaction4 = SocialInteraction(
        platform="facebook",
        username="dispo_agent",
        message="Looking for JV partners, I do DISPO for wholesalers",
    )
    result4 = router.route_interaction(interaction4)
    assert result4.intent == "partner"
    assert result4.pipeline == "jv_partner"

    print("PASS: test_social_cta_routing")


def test_next_best_action_seller():
    """Test next-best-action for sellers."""
    engine = NextBestActionEngine()

    # Hot seller with phone
    action = engine.compute_seller_action({
        "id": "S001",
        "status": "NEW",
        "motivation_score": 80,
        "phone": "+15551234567",
        "has_offer": False,
    })
    assert action.action == ActionType.CALL_NOW
    assert action.priority <= 2

    # Seller needing follow-up
    action2 = engine.compute_seller_action({
        "id": "S002",
        "status": "CONTACTED",
        "motivation_score": 50,
        "phone": "+15551234567",
        "last_contact_at": "2026-08-20T00:00:00+00:00",  # 7 days ago
    })
    assert action2.action == ActionType.FOLLOW_UP

    print("PASS: test_next_best_action_seller")


def test_next_best_action_buyer():
    """Test next-best-action for buyers."""
    engine = NextBestActionEngine()

    # Buyer with incomplete buy box
    action = engine.compute_buyer_action({
        "id": "B001",
        "has_buy_box": False,
        "buy_box_completeness": 20,
        "activity_score": 50,
        "verification_status": "UNVERIFIED",
    })
    assert action.action == ActionType.CAPTURE_BUY_BOX

    # Verified buyer with matched deals
    action2 = engine.compute_buyer_action({
        "id": "B002",
        "has_buy_box": True,
        "buy_box_completeness": 90,
        "activity_score": 80,
        "verification_status": "VERIFIED",
        "matched_deals_count": 3,
    })
    assert action2.action == ActionType.SEND_MATCHED_DEAL

    print("PASS: test_next_best_action_buyer")


def test_next_best_action_deal():
    """Test next-best-action for deals."""
    engine = NextBestActionEngine()

    # New deal
    action = engine.compute_deal_action({
        "id": "D001",
        "status": "INTAKE",
    })
    assert action.action == ActionType.UNDERWRITE_NOW

    # Scored deal with matches
    action2 = engine.compute_deal_action({
        "id": "D002",
        "status": "SCORED",
        "buyer_matches_count": 5,
    })
    assert action2.action == ActionType.SEND_DEAL

    # Stale deal
    action3 = engine.compute_deal_action({
        "id": "D003",
        "status": "OUTREACH_SENT",
        "days_active": 10,
    })
    assert action3.action == ActionType.EXPAND_SEARCH

    print("PASS: test_next_best_action_deal")


def test_mao_calculation():
    """Test MAO (70% Rule) calculation."""
    engine = DealScoringEngine()

    deal = {
        "id": "D001",
        "asking_price": 100000,
        "arv": 200000,
        "estimated_repairs": 20000,
    }

    score = engine.score_deal(deal)

    # MAO = (ARV * 0.70) - Repairs = (200000 * 0.70) - 20000 = 120000
    assert score.mao == 120000

    # Margin = ARV - Asking - Repairs = 200000 - 100000 - 20000 = 80000
    assert score.margin == 80000

    # Spread = ARV - Asking = 200000 - 100000 = 100000
    assert score.spread == 100000

    print("PASS: test_mao_calculation")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_buyer_buy_box_registration,
        test_buyer_match_score,
        test_demand_signal,
        test_deal_scoring,
        test_deal_submission,
        test_social_cta_routing,
        test_next_best_action_seller,
        test_next_best_action_buyer,
        test_next_best_action_deal,
        test_mao_calculation,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
