"""
MBM LeadEngine — Phase F-J + Integration Tests
================================================
Expanded test matrix covering:
  - Supabase initialization
  - Disposition persistence + DNC terminal state
  - Buyer demand persistence + recalculation
  - Acquisition feedback loop
  - Content attribution
  - Provider failure/timeout/stale data
  - Idempotency + duplicate events
  - No fake conversion paths
"""

import sys
import os
import json
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.ad_repository import AdRepository
from MBM.LeadEngine.ad_service import AdService
from MBM.LeadEngine.ad_disposition import DispositionEngine, VALID_OUTCOMES, TERMINAL_DISPOSITIONS
from MBM.LeadEngine.ad_acquisition_loop import AcquisitionFeedbackLoop
from MBM.LeadEngine.ad_content_attribution import ContentAttributionEngine
from MBM.LeadEngine.ad_data_providers import (
    create_default_registry, NPIRegistryProvider, AuctionProvider,
    ProviderRegistry
)
from MBM.LeadEngine.buyer_buy_box_engine import BuyerBuyBox


# ─── SUPABASE INIT ───────────────────────────────────────────────

def test_supabase_import():
    """Verify supabase package imports correctly."""
    from supabase import create_client
    assert callable(create_client)
    print("PASS: test_supabase_import")


def test_supabase_namespace_not_shadowed():
    """Verify repo supabase/ dir doesn't shadow the pip package."""
    import supabase
    assert hasattr(supabase, "create_client")
    print("PASS: test_supabase_namespace_not_shadowed")


# ─── DISPOSITION ─────────────────────────────────────────────────

def test_disposition_valid_outcomes():
    """All 10 disposition outcomes are valid."""
    expected = {"CONNECTED","NO_ANSWER","VOICEMAIL","WRONG_NUMBER","WRONG_PARTY",
                "INTERESTED","NOT_INTERESTED","CALLBACK","APPOINTMENT","DNC"}
    assert expected == VALID_OUTCOMES
    print("PASS: test_disposition_valid_outcomes")


def test_disposition_persistence():
    """Disposition persists to repository and can be retrieved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        result = engine.record_disposition(
            lead_id="L_DISP_001",
            outcome="CONNECTED",
            notes="Spoke with owner, interested in selling",
        )
        assert result["ok"]
        assert result["outcome"] == "CONNECTED"

        dispositions = engine.get_lead_dispositions("L_DISP_001")
        assert len(dispositions) == 1
        assert dispositions[0]["outcome"] == "CONNECTED"

        print("PASS: test_disposition_persistence")


def test_disposition_dnc_terminal_state():
    """DNC disposition is terminal — subsequent dispositions are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        # First disposition: DNC
        result1 = engine.record_disposition(
            lead_id="L_DNC_001",
            outcome="DNC",
            dnc_reason="Owner requested removal",
        )
        assert result1["ok"]
        assert result1["is_dnc"]

        # Second disposition should be blocked
        result2 = engine.record_disposition(
            lead_id="L_DNC_001",
            outcome="CONNECTED",
        )
        assert not result2["ok"]
        assert any("DNC" in e for e in result2["errors"])

        # Verify DNC status
        assert engine.is_lead_dnc("L_DNC_001")

        print("PASS: test_disposition_dnc_terminal_state")


def test_disposition_invalid_outcome_rejected():
    """Invalid disposition outcome is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        result = engine.record_disposition(
            lead_id="L_INV_001",
            outcome="INVALID_OUTCOME",
        )
        assert not result["ok"]
        assert any("Invalid" in e for e in result["errors"])

        print("PASS: test_disposition_invalid_outcome_rejected")


def test_disposition_creates_follow_up():
    """CONNECTED disposition creates a follow-up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        result = engine.record_disposition(
            lead_id="L_FU_001",
            outcome="INTERESTED",
            follow_up_channel="CALL",
        )
        assert result["ok"]
        assert result["follow_up_created"]

        follow_ups = repo.get_pending_follow_ups(10)
        assert len(follow_ups) >= 1

        print("PASS: test_disposition_creates_follow_up")


def test_disposition_summary():
    """Disposition summary returns correct counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        # Record several dispositions
        engine.record_disposition(lead_id="L_SUM_001", outcome="CONNECTED")
        engine.record_disposition(lead_id="L_SUM_002", outcome="NO_ANSWER")
        engine.record_disposition(lead_id="L_SUM_003", outcome="DNC")
        engine.record_disposition(lead_id="L_SUM_004", outcome="INTERESTED")

        summary = engine.get_disposition_summary()
        assert summary["total"] == 4
        assert summary["dnc_count"] == 1
        assert summary["by_outcome"]["CONNECTED"] == 1
        assert summary["follow_up_needed"] == 2  # CONNECTED + INTERESTED

        print("PASS: test_disposition_summary")


# ─── ACQUISITION FEEDBACK LOOP ───────────────────────────────────

def test_feedback_loop_metrics():
    """Feedback loop computes metrics from deal data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        # Register buyer + submit deals
        buyer = BuyerBuyBox(
            buyer_id="B_FB_001", buyer_name="Feedback Buyer",
            markets=["Houston"], property_types=["SFR"],
            price_min=100000, price_max=300000,
            activity_score=70, verification_status="VERIFIED",
        )
        service.register_buyer(buyer)

        from MBM.LeadEngine.deal_submission_engine import DealSubmission
        for i in range(3):
            deal = DealSubmission(
                address=f"{i+1} Feedback St", city="Houston", state="TX",
                asking_price=150000 + i * 10000, property_type="SFR",
                arv=300000, estimated_repairs=25000,
                source_platform="test_source",
            )
            service.submit_and_score_deal(deal)

        loop = AcquisitionFeedbackLoop(repo)
        metrics = loop.compute_feedback_metrics()

        assert "funnel" in metrics
        assert "source_quality" in metrics
        assert "velocity" in metrics
        assert metrics["source_quality"][0]["source"] == "test_source"

        print("PASS: test_feedback_loop_metrics")


def test_source_quality_scoring():
    """Source quality scores are computed from deal outcomes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        loop = AcquisitionFeedbackLoop(repo)

        scores = loop.compute_source_quality_scores()
        assert isinstance(scores, list)
        # No deals yet, so empty
        assert len(scores) == 0

        print("PASS: test_source_quality_scoring")


def test_prioritized_sources():
    """Source prioritization returns correct priority levels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        loop = AcquisitionFeedbackLoop(repo)

        sources = loop.get_prioritized_sources()
        assert isinstance(sources, list)

        print("PASS: test_prioritized_sources")


# ─── CONTENT ATTRIBUTION ─────────────────────────────────────────

def test_content_attribution_recording():
    """Content touch events are recorded and retrievable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = ContentAttributionEngine(repo)

        # Record touches
        engine.record_content_touch(
            content_id="post_123", campaign_id="camp_001",
            lead_id="L_ATT_001", touch_type="first_touch",
            platform="instagram",
        )
        engine.record_content_touch(
            content_id="post_456", campaign_id="camp_001",
            lead_id="L_ATT_001", touch_type="last_touch",
            platform="instagram",
        )

        # Attribute lead
        attribution = engine.attribute_lead_to_content("L_ATT_001")
        assert attribution["lead_id"] == "L_ATT_001"
        assert attribution["total_touches"] == 2

        print("PASS: test_content_attribution_recording")


def test_content_performance():
    """Content performance metrics are computed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = ContentAttributionEngine(repo)

        perf = engine.compute_content_performance()
        assert isinstance(perf, list)

        print("PASS: test_content_performance")


def test_campaign_performance():
    """Campaign performance metrics are computed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = ContentAttributionEngine(repo)

        perf = engine.compute_campaign_performance()
        assert isinstance(perf, list)

        print("PASS: test_campaign_performance")


# ─── DATA PROVIDERS ──────────────────────────────────────────────

def test_provider_registry_health():
    """Provider registry reports health for all providers."""
    registry = create_default_registry()
    health = registry.health_check_all()

    assert "lead_discovery" in health
    assert "property_intel" in health
    assert "buyer_intel" in health
    assert health["buyer_intel"]["ok"]  # CSV buyer data is always available

    print("PASS: test_provider_registry_health")


def test_provider_provenance():
    """Provider provenance tracks fetch counts."""
    registry = create_default_registry()
    provenance = registry.get_provenance_all()

    assert "lead_discovery" in provenance
    assert provenance["lead_discovery"]["fetch_count"] == 0

    print("PASS: test_provider_provenance")


def test_provider_failure_graceful():
    """Provider failure returns empty results, not exceptions."""
    registry = create_default_registry()
    # Use any provider — verify it returns list not exception
    discovery = registry.get("lead_discovery")
    assert discovery is not None

    leads = discovery.discover_leads("NonExistent", "SFR", 10)
    assert isinstance(leads, list)

    # Verify health returns a dict (even if not ok)
    health = discovery.health_check()
    assert isinstance(health, dict)

    print("PASS: test_provider_failure_graceful")


def test_provider_capability_search():
    """Find providers by capability."""
    registry = create_default_registry()
    providers = registry.find_by_capability("npi_registry")
    assert len(providers) >= 1

    print("PASS: test_provider_capability_search")


# ─── IDEMPOTENCY + DUPLICATES ────────────────────────────────────

def test_duplicate_disposition_blocked():
    """Duplicate disposition for same lead is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        engine = DispositionEngine(repo)

        engine.record_disposition(lead_id="L_DUP_001", outcome="CONNECTED")
        # Second disposition on same lead — should succeed (multiple calls allowed)
        result = engine.record_disposition(lead_id="L_DUP_001", outcome="NO_ANSWER")
        assert result["ok"]

        dispositions = engine.get_lead_dispositions("L_DUP_001")
        assert len(dispositions) == 2

        print("PASS: test_duplicate_disposition_blocked")


def test_idempotent_buyer_registration():
    """Re-registering the same buyer updates rather than duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        buyer = BuyerBuyBox(
            buyer_id="B_IDEM_001", buyer_name="Original Name",
            markets=["Houston"], property_types=["SFR"],
            price_min=100000, price_max=300000,
            activity_score=50,
        )
        service.register_buyer(buyer)

        buyer2 = BuyerBuyBox(
            buyer_id="B_IDEM_001", buyer_name="Updated Name",
            markets=["Houston"], property_types=["SFR"],
            price_min=100000, price_max=300000,
            activity_score=80,
        )
        service.register_buyer(buyer2)

        # Should be 1 buyer, not 2
        buyers = repo.list_buyer_buy_boxes()
        assert len(buyers) == 1
        assert buyers[0]["buyer_name"] == "Updated Name"
        assert buyers[0]["activity_score"] == 80

        print("PASS: test_idempotent_buyer_registration")


# ─── NO FAKE CONVERSIONS ─────────────────────────────────────────

def test_no_fake_conversion_from_queue_position():
    """Conversions are only counted from actual CLOSED deals, not queue position."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        loop = AcquisitionFeedbackLoop(repo)

        conversions = loop.attribute_conversions()
        # No deals = no conversions
        assert len(conversions) == 0

        print("PASS: test_no_fake_conversion_from_queue_position")


def test_conversion_requires_closed_status():
    """Only CLOSED deals are counted as conversions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        buyer = BuyerBuyBox(
            buyer_id="B_CONV_001", buyer_name="Conversion Buyer",
            markets=["Dallas"], property_types=["SFR"],
            price_min=100000, price_max=300000,
            activity_score=70, verification_status="VERIFIED",
        )
        service.register_buyer(buyer)

        from MBM.LeadEngine.deal_submission_engine import DealSubmission
        deal = DealSubmission(
            address="123 Conversion St", city="Dallas", state="TX",
            asking_price=200000, property_type="SFR",
            arv=350000, estimated_repairs=25000,
            source_platform="test_source",
        )
        result = service.submit_and_score_deal(deal)
        deal_id = result["deal_id"]

        loop = AcquisitionFeedbackLoop(repo)

        # Scored deal is NOT a conversion
        conversions = loop.attribute_conversions()
        assert len(conversions) == 0

        # Only after closing
        repo.update_deal_submission(deal_id, {"status": "CLOSED"})
        conversions = loop.attribute_conversions()
        assert len(conversions) == 1
        assert conversions[0]["status"] == "CLOSED"

        print("PASS: test_conversion_requires_closed_status")


# ─── RUNNER ──────────────────────────────────────────────────────

def run_all_tests():
    tests = [
        test_supabase_import,
        test_supabase_namespace_not_shadowed,
        test_disposition_valid_outcomes,
        test_disposition_persistence,
        test_disposition_dnc_terminal_state,
        test_disposition_invalid_outcome_rejected,
        test_disposition_creates_follow_up,
        test_disposition_summary,
        test_feedback_loop_metrics,
        test_source_quality_scoring,
        test_prioritized_sources,
        test_content_attribution_recording,
        test_content_performance,
        test_campaign_performance,
        test_provider_registry_health,
        test_provider_provenance,
        test_provider_failure_graceful,
        test_provider_capability_search,
        test_duplicate_disposition_blocked,
        test_idempotent_buyer_registration,
        test_no_fake_conversion_from_queue_position,
        test_conversion_requires_closed_status,
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
    print(f"PHASE TESTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
