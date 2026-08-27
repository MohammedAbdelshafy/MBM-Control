"""
MBM LeadEngine — Harden & Integration Tests
=============================================
Expanded test matrix covering:
  - Phase A: Demand signal classification (single source of truth)
  - Phase A: Buyer registration + demand persistence regression
  - Phase B: Environment mode enforcement
  - Phase D: Dialer adapter (local, no real DB)
  - Phase E: Follow-up executor (channel adapters)
  - Phase L: Revenue attribution chain
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
from MBM.LeadEngine.ad_followup_executor import FollowUpExecutor, ManualAdapter, SystemAdapter
from MBM.LeadEngine.buyer_buy_box_engine import BuyerBuyBox
from MBM.LeadEngine.deal_submission_engine import DealSubmission
from MBM.LeadEngine.social_cta_router import SocialInteraction


# ─── PHASE A: DEMAND SIGNAL CLASSIFICATION ──────────────────────

def test_demand_signal_classification():
    """Single source of truth for demand signal thresholds."""
    assert AdService._classify_demand(10, 5) == "HOT"
    assert AdService._classify_demand(5, 3) == "HOT"
    assert AdService._classify_demand(4, 2) == "WARM"
    assert AdService._classify_demand(3, 1) == "WARM"
    assert AdService._classify_demand(2, 0) == "NORMAL"
    assert AdService._classify_demand(1, 0) == "NORMAL"
    assert AdService._classify_demand(0, 2) == "WEAK"
    assert AdService._classify_demand(0, 0) == "UNKNOWN"
    print("PASS: test_demand_signal_classification")


def test_buyer_registration_demand_persistence():
    """Register a buyer → demand signal persists to repo → survives service reload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        buyer = BuyerBuyBox(
            buyer_id="B_REG_001",
            buyer_name="Regression Buyer",
            markets=["Dallas"],
            property_types=["SFR"],
            price_min=100000,
            price_max=300000,
            activity_score=80,
            verification_status="VERIFIED",
        )
        result = service.register_buyer(buyer)

        # Demand signal should be persisted
        signals = repo.get_demand_signals(market="Dallas")
        assert len(signals) >= 1
        dallas_signal = [s for s in signals if s.get("market") == "Dallas"]
        assert len(dallas_signal) >= 1
        assert dallas_signal[0]["signal"] in ("HOT", "WARM", "NORMAL", "WEAK", "UNKNOWN")

        # Create a second service instance — buyer should survive reload
        service2 = AdService(repo)
        assert "B_REG_001" in service2.buy_box_engine.buyers

        print("PASS: test_buyer_registration_demand_persistence")


def test_deal_submission_does_not_wipe_engine():
    """Submitting a deal should not destroy the in-memory buyer set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        # Register 3 buyers
        for i in range(3):
            buyer = BuyerBuyBox(
                buyer_id=f"B_WIPE_{i:03d}",
                buyer_name=f"Buyer {i}",
                markets=["Houston", "Dallas"],
                property_types=["SFR", "MULTI"],
                price_min=50000,
                price_max=500000,
                activity_score=70,
                verification_status="VERIFIED",
            )
            service.register_buyer(buyer)

        initial_count = len(service.buy_box_engine.buyers)
        assert initial_count == 3

        # Submit a deal — this used to wipe the engine
        deal = DealSubmission(
            address="123 Test Ave",
            city="Houston",
            state="TX",
            asking_price=200000,
            property_type="SFR",
            arv=350000,
            estimated_repairs=25000,
        )
        service.submit_and_score_deal(deal)

        # Engine should still have all buyers
        assert len(service.buy_box_engine.buyers) == initial_count

        print("PASS: test_deal_submission_does_not_wipe_engine")


# ─── PHASE B: ENVIRONMENT MODE ──────────────────────────────────

def test_production_mode_requires_supabase():
    """PRODUCTION mode without Supabase should raise RuntimeError."""
    import unittest.mock as mock

    with mock.patch("MBM.LeadEngine.ad_repository._get_supabase", return_value=None):
        try:
            repo = AdRepository(env_mode="PRODUCTION")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PRODUCTION" in str(e)

    print("PASS: test_production_mode_requires_supabase")


def test_test_mode_uses_temp_dir():
    """TEST mode should use the provided temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        assert repo.env_mode == "TEST"
        assert str(repo.storage_dir) == tmpdir

    print("PASS: test_test_mode_uses_temp_dir")


def test_local_mode_falls_back_to_json():
    """LOCAL mode should fall back to JSON when Supabase unavailable."""
    import unittest.mock as mock

    with mock.patch("MBM.LeadEngine.ad_repository._get_supabase", return_value=None):
        repo = AdRepository(env_mode="LOCAL")
        assert not repo._use_supabase()

    print("PASS: test_local_mode_falls_back_to_json")


# ─── PHASE D: DIALER ADAPTER ────────────────────────────────────

def test_dialer_adapter_read_write():
    """Dialer adapter can read/write leads_database.json atomically."""
    from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "leads_database.json"
        adapter = DialerAdapter(dialer_db=db_path)

        # Empty read
        leads = adapter.read_leads()
        assert leads == []

        # Write leads
        test_leads = [
            {"id": "L001", "contact": "Test Lead 1", "phone": "555-0001", "status": "NEW"},
            {"id": "L002", "contact": "Test Lead 2", "phone": "555-0002", "status": "HOT"},
        ]
        assert adapter._write_leads(test_leads)

        # Read back
        leads = adapter.read_leads()
        assert len(leads) == 2
        assert leads[0]["id"] == "L001"

        # Patch
        assert adapter.patch_lead("L001", {"status": "CONTACTED"})
        leads = adapter.read_leads()
        patched = [l for l in leads if l["id"] == "L001"][0]
        assert patched["status"] == "CONTACTED"

        print("PASS: test_dialer_adapter_read_write")


def test_dialer_adapter_aftercall():
    """Aftercall records interaction on dialer lead."""
    from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "leads_database.json"
        adapter = DialerAdapter(dialer_db=db_path)

        # Seed a lead
        adapter._write_leads([{"id": "L100", "contact": "Aftercall Test", "phone": "555-100"}])

        # Record aftercall
        result = adapter.record_aftercall("L100", "Spoke with owner, motivated, needs follow-up")
        assert result["ok"]
        assert result["lead"]["call_count"] == 1
        assert result["lead"]["last_called_at"] is not None
        assert len(result["lead"]["interaction_log"]) == 1

        # Second aftercall
        result2 = adapter.record_aftercall("L100", "Left voicemail", disposition="FOLLOW_UP")
        assert result2["ok"]
        assert result2["lead"]["call_count"] == 2
        assert result2["lead"]["disposition"] == "FOLLOW_UP"

        print("PASS: test_dialer_adapter_aftercall")


def test_dialer_adapter_deal_to_lead():
    """Deal-to-lead conversion maps fields correctly."""
    from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter

    adapter = DialerAdapter()
    deal = {
        "id": "D_CONV_001",
        "address": "456 Conversion St",
        "city": "Dallas",
        "state": "TX",
        "zip_code": "75201",
        "property_type": "SFR",
        "asking_price": 180000,
        "arv": 300000,
        "estimated_repairs": 20000,
        "status": "SCORED",
        "source_name": "Test Wholesaler",
        "source_phone": "555-9999",
        "demand_signal": "WARM",
    }
    lead = adapter.deal_to_lead(deal, score={"overall_score": 82})

    assert lead["id"] == "D_CONV_001"
    assert lead["address"] == "456 Conversion St"
    assert lead["asking_price"] == 180000
    assert lead["score"] == 82
    assert lead["status"] == "QUALIFIED"  # SCORED → QUALIFIED
    assert lead["demand_signal"] == "WARM"
    assert lead["source"] == "ad_engine"

    print("PASS: test_dialer_adapter_deal_to_lead")


# ─── PHASE E: FOLLOW-UP EXECUTOR ────────────────────────────────

def test_followup_executor_manual_channel():
    """Manual follow-up executes without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        # Create a buyer and follow-up
        buyer = BuyerBuyBox(
            buyer_id="B_FU_001",
            buyer_name="Follow-Up Test",
            markets=["Houston"],
            property_types=["SFR"],
            price_min=100000,
            price_max=250000,
            activity_score=60,
        )
        service.register_buyer(buyer)

        fu = service.create_follow_up(
            entity_id="B_FU_001",
            entity_type="buyer",
            reason="Test manual follow-up",
            channel="MANUAL",
        )

        executor = FollowUpExecutor(repo, env_mode="TEST")
        result = executor.execute_one(fu)

        assert result["ok"]
        assert result["status"] == "COMPLETED"
        assert result["channel"] == "MANUAL"

        print("PASS: test_followup_executor_manual_channel")


def test_followup_executor_system_channel():
    """System follow-up executes without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        fu = service.create_follow_up(
            entity_id="SYS_001",
            entity_type="deal",
            reason="Auto-score update",
            channel="SYSTEM",
        )

        executor = FollowUpExecutor(repo, env_mode="TEST")
        result = executor.execute_one(fu)

        assert result["ok"]
        assert result["status"] == "COMPLETED"
        assert result["channel"] == "SYSTEM"

        print("PASS: test_followup_executor_system_channel")


def test_followup_executor_call_channel_local():
    """CALL follow-up in LOCAL mode logs intent without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        # Create a buyer with phone
        buyer = BuyerBuyBox(
            buyer_id="B_CALL_001",
            buyer_name="Call Test",
            markets=["Houston"],
            property_types=["SFR"],
            price_min=100000,
            price_max=250000,
            activity_score=60,
            phone="555-0101",
        )
        service.register_buyer(buyer)

        fu = service.create_follow_up(
            entity_id="B_CALL_001",
            entity_type="buyer",
            reason="Verify buy box",
            channel="CALL",
        )

        executor = FollowUpExecutor(repo, env_mode="LOCAL")
        result = executor.execute_one(fu)

        assert result["ok"]
        assert result["status"] == "COMPLETED"
        assert result["channel"] == "CALL"

        print("PASS: test_followup_executor_call_channel_local")


def test_followup_executor_pending_batch():
    """Execute pending follow-ups processes due items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        # Create 3 follow-ups with next_attempt in the past (due now)
        for i in range(3):
            service.create_follow_up(
                entity_id=f"BATCH_{i:03d}",
                entity_type="buyer",
                reason=f"Batch test {i}",
                channel="MANUAL",
                scheduled_at=now,
            )

        executor = FollowUpExecutor(repo, env_mode="TEST")
        results = executor.execute_pending(limit=5)

        assert len(results) == 3
        assert all(r["ok"] for r in results)
        assert all(r["status"] == "COMPLETED" for r in results)

        summary = executor.get_execution_summary()
        assert summary["total_pending"] == 0  # all completed

        print("PASS: test_followup_executor_pending_batch")


def test_followup_executor_backoff_on_failure():
    """Failed follow-up gets rescheduled with backoff (not marked FAILED immediately)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        # Create a CALL follow-up for entity with no phone — will fail
        fu = service.create_follow_up(
            entity_id="NO_PHONE_001",
            entity_type="buyer",
            reason="Call buyer",
            channel="CALL",
        )

        executor = FollowUpExecutor(repo, env_mode="TEST")
        result = executor.execute_one(fu)

        # First attempt: should be rescheduled (PENDING), not FAILED
        assert result["attempt"] == 1
        # Check the follow-up was rescheduled (next_attempt set)
        pending = repo.get_pending_follow_ups(10)
        rescheduled = [f for f in pending if f.get("id") == fu["id"]]
        assert len(rescheduled) == 1  # still pending with backoff

        print("PASS: test_followup_executor_backoff_on_failure")


# ─── PHASE L: REVENUE ATTRIBUTION ───────────────────────────────

def test_revenue_attribution_chain():
    """Revenue event records correct net_amount and attribution path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        service = AdService(repo)

        event = service.record_revenue(
            deal_id="D_REV_001",
            revenue_type="ASSIGNMENT_FEE",
            gross_amount=15000,
            fees=1500,
            attribution_path=["ig_post_123", "seller_dm", "contract", "close"],
        )

        assert event["gross_amount"] == 15000
        assert event["fees"] == 1500
        assert event["net_amount"] == 13500
        assert event["attribution_path"] == ["ig_post_123", "seller_dm", "contract", "close"]
        assert event["currency"] == "USD"

        # Verify in repo
        events = repo.get_revenue_events({"deal_id": "D_REV_001"})
        assert len(events) == 1
        assert events[0]["net_amount"] == 13500

        print("PASS: test_revenue_attribution_chain")


# ─── RUNNER ──────────────────────────────────────────────────────

def run_all_tests():
    tests = [
        test_demand_signal_classification,
        test_buyer_registration_demand_persistence,
        test_deal_submission_does_not_wipe_engine,
        test_production_mode_requires_supabase,
        test_test_mode_uses_temp_dir,
        test_local_mode_falls_back_to_json,
        test_dialer_adapter_read_write,
        test_dialer_adapter_aftercall,
        test_dialer_adapter_deal_to_lead,
        test_followup_executor_manual_channel,
        test_followup_executor_system_channel,
        test_followup_executor_call_channel_local,
        test_followup_executor_pending_batch,
        test_followup_executor_backoff_on_failure,
        test_revenue_attribution_chain,
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
    print(f"HARDEN TESTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
