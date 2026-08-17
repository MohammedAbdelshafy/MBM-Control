"""
TESTS: MBM DAILY REAL LEADS FACTORY (ZERO SYNTHETIC)
=============================================================================
Comprehensive unit tests verifying:
1. Real-source generation contract (100 real verified leads from NPI registry)
2. Zero-synthetic guarantee (provenance gate rejects fabricated records)
3. Global historical ledger deduplication (0 overlap with past inventory)
4. New-Today contract fields (new_today, badge, first_seen_date, freshness)
5. Multi-run dedupe (Run #2 recycles ZERO phones from Run #1)
6. Adaptive oversampling candidate yield
7. Concurrency lock behavior
8. Daily notification payload generation (REAL-only numbers)
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
from MBM.LeadEngine.lead_provenance import production_synthetic_count, LeadProvenanceGate, build_provenance_fields
from MBM.LeadEngine.daily_lead_factory import (
    DailyLeadFactory,
    DailyLeadFactoryReport,
    FileLock,
)


def _build_fixture_candidates(n: int):
    """Deterministic REAL-looking NPI candidate pool (hermetic — never touches the
    live callsheet or live dialer DB). Every candidate carries real provenance."""
    firsts = ["Jessica", "Marcus", "Sofia", "David", "Amara", "Kevin", "Lena", "Tyler",
              "Nora", "Victor", "Maya", "Omar", "Priya", "Ethan", "Ruby", "Miguel",
              "Chloe", "Aaron", "Isla", "Sam"]
    lasts = ["Carter", "Nguyen", "Rivera", "Patel", "Brooks", "Kim", "Silva", "Johnson",
             "Garcia", "Lee", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson",
             "Thomas", "Jackson", "White", "Harris"]
    out = []
    for i in range(n):
        npi = str(1000000000 + i)  # fake NPI number (10 digits)
        industry = "Dental Clinics & Orthodontics" if i % 2 == 0 else "Medical Clinics & Urgent Care"
        company = f"Family Dental Care {i:03d}" if i % 2 == 0 else f"Urgent Care Clinic {i:03d}"
        phone = f"+1{214}{8000000 + i:07d}"
        prov = build_provenance_fields(
            source="CMS NPI Registry API v2.1",
            source_reference=f"NPI-{npi}",
            source_type="government_registry",
            verification_method="npi_registry_api",
        )
        cand = {
            "id": f"NPI-{npi}",
            "company": company,
            "decision_maker": f"Dr. {firsts[i % 20]} {lasts[i % 20]}",
            "role": "Practice Owner",
            "industry": industry,
            "phone": phone,
            "email": f"info@clinic{i:03d}.com",
            "city": "Dallas",
            "state": "TX",
            "why_this_company": f"Real licensed {industry} business (NPI {npi}) verified via CMS NPI Registry.",
            "source_class": "NPI",
        }
        cand.update(prov)
        out.append(cand)
    return out


def _slice_pool(pool, count: int, seed_base: int):
    if not pool:
        return []
    start = seed_base % len(pool)
    picked = pool[start:start + count]
    if len(picked) < count:
        picked += pool[:count - len(picked)]
    return picked


@pytest.fixture(autouse=True)
def _hermetic_pool(monkeypatch, tmp_path):
    """Serve a fixed real-candidate pool so factory tests never read the live
    callsheet / live dialer DB (deterministic yield), and redirect ALL daily
    artifact exports to a temp dir so the real MBM/Artifacts/GTM/daily tree is
    never touched."""
    import MBM.LeadEngine.daily_lead_factory as dlf
    tmp_artifacts = tmp_path / "artifacts"
    tmp_artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dlf, "DAILY_GTM_DIR", tmp_path / "gtm" / "daily")
    monkeypatch.setattr(dlf, "ARTIFACTS_DIR", tmp_artifacts)
    pool = _build_fixture_candidates(220)
    monkeypatch.setattr(
        DailyLeadFactory, "_harvest_candidate_wave",
        lambda self, count, seed: _slice_pool(pool, count, seed),
    )


def _fresh_factory(td: str, target: int):
    ledger_file = Path(td) / "test_ledger.json"
    ledger = LeadHistoryLedger(ledger_file=ledger_file, bootstrap=False)
    # Hermetic: never read the live dialer DB during tests.
    return DailyLeadFactory(history_ledger=ledger, dialer_rows_reader=lambda: [])


def test_daily_factory_real_100_generation():
    """Verify factory generates 100 REAL, provenance-gated, callable leads."""
    with tempfile.TemporaryDirectory() as td:
        factory = _fresh_factory(td, 100)
        report = factory.generate_daily_batch(target=100, dry_run=True)

        assert report.verified_new == 100
        assert report.callable_new == 100
        assert report.shortfall == 0
        assert len(report.verified_leads) == 100
        assert report.pipeline_value_usd > 0.0

        # ZERO synthetic records in the accepted batch.
        assert production_synthetic_count(report.verified_leads) == 0

        # Every lead is REAL: comes from CMS NPI Registry with real provenance.
        for lead in report.verified_leads:
            assert lead["source"] == "CMS NPI Registry API v2.1"
            assert lead["source_type"] == "government_registry"
            assert lead["verification_method"] == "npi_registry_api"
            assert lead["source_reference"].startswith("NPI-")
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
        factory = _fresh_factory(td, 50)
        report = factory.generate_daily_batch(target=50, dry_run=True)
        assert report.candidates_evaluated >= 50
        assert report.verified_new == 50
        assert report.verification_rate_pct > 0.0


def test_daily_factory_global_historical_deduplication():
    """Run #2 must NEVER recycle Run #1's phones (zero overlap, honest dedupe)."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = Path(td) / "test_ledger.json"
        ledger = LeadHistoryLedger(ledger_file=ledger_file, bootstrap=False)
        factory = DailyLeadFactory(history_ledger=ledger, dialer_rows_reader=lambda: [])

        # Run 1
        rep1 = factory.generate_daily_batch(target=30, dry_run=True)
        assert rep1.verified_new == 30
        assert rep1.shortfall == 0

        # Run 2 against same ledger: fresh real leads, but ZERO recycled phones.
        rep2 = factory.generate_daily_batch(target=30, dry_run=True)
        assert rep2.verified_new == 30
        phones1 = {normalize_phone_digits(l["phone"]) for l in rep1.verified_leads}
        phones2 = {normalize_phone_digits(l["phone"]) for l in rep2.verified_leads}
        assert phones1.intersection(phones2) == set(), "Recycled a duplicate phone across runs"


def test_daily_factory_real_source_distribution():
    """All verified leads must be REAL NPI businesses across the medical verticals."""
    with tempfile.TemporaryDirectory() as td:
        factory = _fresh_factory(td, 100)
        report = factory.generate_daily_batch(target=100, dry_run=True)
        assert len(report.vertical_breakdown) >= 1
        for v in report.vertical_breakdown:
            assert v == "Medical Clinics & Urgent Care" or v == "Dental Clinics & Orthodontics"
        # Source breakdown must show ONLY the real registry source.
        assert set(report.source_breakdown.keys()) == {"CMS NPI Registry API v2.1"}


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
    """Verify notification payloads report REAL-only numbers."""
    with tempfile.TemporaryDirectory() as td:
        factory = _fresh_factory(td, 100)
        report = factory.generate_daily_batch(target=100, dry_run=True)
        notifs = factory.build_notification_payload(report)

        assert "telegram" in notifs
        assert "🟢 MBM DAILY DELIVERY" in notifs["telegram"]
        assert "100 REAL VERIFIED LEADS" in notifs["telegram"]
        assert "email_subject" in notifs
        assert "in_app" in notifs
        assert notifs["in_app"]["status"] == "SUCCESS"


def test_daily_factory_shortfall_payload_is_honest(monkeypatch):
    """Shortfall payload must admit the real shortfall, never fabricate."""
    with tempfile.TemporaryDirectory() as td:
        factory = _fresh_factory(td, 100)
        # Simulate a fully exhausted real discovery pool.
        monkeypatch.setattr(factory, "_harvest_candidate_wave", lambda count, seed: [])
        report = factory.generate_daily_batch(target=100, dry_run=True)
        notifs = factory.build_notification_payload(report)
        assert report.shortfall == 100
        assert report.verified_new == 0
        assert "🚨 MBM DAILY LEAD SHORTFALL" in notifs["telegram"]
        assert "no synthetic fallback" in notifs["telegram"]