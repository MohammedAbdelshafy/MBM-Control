"""
TESTS: MBM DAILY 100+ VERIFIED FRESH LEADS FACTORY
=============================================================================
Comprehensive unit tests verifying:
1. Target generation contract (>= 100 verified new leads per run)
2. Global historical ledger deduplication (0 overlap with past inventory)
3. New-Today contract fields (new_today, badge, first_seen_date, freshness)
4. Multi-run idempotency (Run #1 and Run #2 have 0 duplicate phones)
5. Adaptive oversampling candidate yield
6. Vertical and geographic distribution across the ICP matrix
7. Concurrency lock behavior
8. Daily notification payload generation
=============================================================================
"""

import sys
import json
import pytest
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.lead_history_ledger import LeadHistoryLedger, normalize_phone_digits
from MBM.LeadEngine.daily_lead_factory import (
    DailyLeadFactory,
    DailyLeadFactoryReport,
    FileLock,
    ICP_VERTICALS,
    GEOGRAPHIC_REGIONS,
)


def test_daily_factory_target_100_generation():
    """Verify daily factory generates at least 100 verified, callable leads."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file)
        factory = DailyLeadFactory(history_ledger=ledger)

        report = factory.generate_daily_batch(target=100, dry_run=True)

        assert report.verified_new == 100
        assert report.callable_new == 100
        assert report.shortfall == 0
        assert len(report.verified_leads) == 100
        assert report.pipeline_value_usd > 0.0

        # Verify every lead in batch adheres to New Lead Contract
        for lead in report.verified_leads:
            assert lead["phone"].startswith("+1")
            assert len(lead["phone"]) == 12  # +1 + 10 digits
            assert lead["decision_maker"] not in ("UNKNOWN", "", "N/A")
            assert lead["intent_score"] >= 75.0
            assert lead["recommended_ai_assistant"] != ""
            assert lead["new_today"] is True
            assert lead["badge"] == "🟢 NEW TODAY"
            assert lead["freshness"] == "NEW_TODAY"
            assert lead["first_seen_date"] != ""
            assert lead["neteller_link"].startswith("https://member.neteller.com/pay?")


def test_daily_factory_oversampling_and_yield():
    """Verify adaptive oversampling harvests sufficient candidate waves."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file)
        factory = DailyLeadFactory(history_ledger=ledger)

        report = factory.generate_daily_batch(target=50, dry_run=True)
        assert report.candidates_evaluated >= 50
        assert report.verified_new == 50
        assert report.verification_rate_pct > 0.0


def test_daily_factory_global_historical_deduplication():
    """Verify second run against same historical ledger produces zero duplicate phones."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file)
        factory = DailyLeadFactory(history_ledger=ledger)

        # Run 1
        rep1 = factory.generate_daily_batch(target=30, dry_run=True)
        assert rep1.verified_new == 30

        # Run 2 against same ledger
        rep2 = factory.generate_daily_batch(target=30, dry_run=True)
        assert rep2.verified_new == 30

        # Ensure no overlap between Run 1 and Run 2 phones
        phones1 = {normalize_phone_digits(l["phone"]) for l in rep1.verified_leads}
        phones2 = {normalize_phone_digits(l["phone"]) for l in rep2.verified_leads}
        intersection = phones1.intersection(phones2)
        assert len(intersection) == 0, f"Found overlapping duplicate phones: {intersection}"


def test_daily_factory_vertical_and_geo_distribution():
    """Verify factory distributes opportunities across rotating ICP verticals and regions."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file)
        factory = DailyLeadFactory(history_ledger=ledger)

        report = factory.generate_daily_batch(target=100, dry_run=True)
        assert len(report.vertical_breakdown) >= 10, "Should distribute across at least 10 verticals"
        assert len(report.geography_breakdown) >= 5, "Should distribute across at least 5 geographic regions"


def test_daily_factory_concurrency_lock():
    """Verify file lock prevents concurrent duplicate executions."""
    with tempfile.TemporaryDirectory() as td:
        lock_path = Path(td) / "test.lock"
        lock1 = FileLock(lock_path=lock_path)
        lock2 = FileLock(lock_path=lock_path)

        assert lock1.acquire() is True
        assert lock2.acquire() is False  # Lock 2 should be rejected

        lock1.release()
        assert lock2.acquire() is True  # Now lock 2 succeeds
        lock2.release()


def test_notification_payload_generation():
    """Verify notification payloads format properly for telegram, email, and in-app."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file)
        factory = DailyLeadFactory(history_ledger=ledger)

        report = factory.generate_daily_batch(target=100, dry_run=True)
        notifs = factory.build_notification_payload(report)

        assert "telegram" in notifs
        assert "🟢 MBM DAILY DELIVERY" in notifs["telegram"]
        assert "100 NEW VERIFIED LEADS" in notifs["telegram"]
        assert "email_subject" in notifs
        assert "in_app" in notifs
        assert notifs["in_app"]["status"] == "SUCCESS"
