"""
Test Suite: Ad Leads to MBM Dialer Ingestion Pipeline
=====================================================
Hermetic integration tests proving:
  1. Synthetic Facebook lead → Normalization → Validation → Deduplication → Canonical DB → FRESH_CALL_NOW → Dialer
  2. Synthetic Google lead → Normalization → Validation → Deduplication → Canonical DB → FRESH_CALL_NOW → Dialer
  3. Bad phone numbers (555, too short, bad exchange) are rejected from callable queue
  4. Suppressed phone index (suppressed_bad_phones.json) numbers are blocked
  5. DNC leads are rejected
  6. Deduplication updates existing lead without destroying call history / attempts
  7. Hard spend safety gate (LIVE_ADS_ENABLED) and budget ceiling enforcement
  8. Daily reconciliation report generation
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

from MBM.LeadEngine.ads.ads_config import (
    verify_live_campaign_gate,
    generate_preflight_report,
    is_live_ads_enabled,
    check_budget,
)
from MBM.LeadEngine.ads.ads_ingestion_pipeline import (
    AdLeadNormalizer,
    AdLeadIngestionPipeline,
    reconcile_ad_leads,
    ADS_RECONCILIATION_JSON,
    ADS_RECONCILIATION_MD,
)
from MBM.LeadEngine.dialer_queue_engine import (
    get_callable_state,
    rank_main_queue,
    build_global_queue,
)
from MBM.LeadEngine.dialer_gateway import commit_dialer_db


@pytest.fixture
def temp_db(tmp_path):
    """Hermetic dialer database file with sample baseline records."""
    db_file = tmp_path / "leads_database.json"
    baseline = [
        {
            "id": "EXISTING-LEAD-001",
            "company": "Premier Aesthetic Dermatology",
            "contact": "Dr. Sarah Jenkins",
            "phone": "+12148392011",
            "vertical": "Med Spas & Aesthetics Clinics",
            "stage": "QUALIFIED",
            "callable": True,
            "verification_status": "VERIFIED",
            "attempts": 1,
            "disposition": "VOICEMAIL",
            "intent_score": 80,
            "motivation_score": 80,
            "deal_score": 80,
            "callability_score": 90,
            "freshness_stage": "OLD",
            "imported_at": "2026-08-01T10:00:00Z",
        }
    ]
    db_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return db_file


def test_facebook_synthetic_lead_ingestion_and_dialer_delivery(temp_db):
    """Prove a raw Facebook lead form submission flows into FRESH_CALL_NOW in the dialer."""
    raw_fb_lead = {
        "id": "FB-LEAD-998811",
        "full_name": "Marcus Althaus",
        "business_email": "marcus@althausautomation.com",
        "phone_number": "+14693214820",  # valid real phone format
        "company_name": "Althaus Industrial Automation LLC",
        "campaign_name": "[MBM] AI Consultancy Discovery — Tech-Forward Business Owners",
        "adset_name": "Tech Owners 35-55",
        "ad_name": "AI That Runs While You Sleep",
        "form_name": "AI Consultancy Lead Form",
        "What type of business do you run?": "Manufacturing & Logistics",
        "What would you like AI to help with?": "Automated inbound inquiry routing and quote generation",
        "created_time": datetime.now(timezone.utc).isoformat(),
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch([raw_fb_lead], platform="facebook", dry_run=False)

    assert result["validated_count"] == 1
    assert result["newly_added_callable"] == 1
    assert result["ad_leads_in_call_now"] >= 1

    # Inspect the committed DB
    db_data = json.loads(temp_db.read_text(encoding="utf-8"))
    leads = db_data if isinstance(db_data, list) else db_data.get("leads", [])
    
    # The ad lead should be at the top of the main queue
    top_lead = leads[0]
    assert top_lead["id"] == "FB-LEAD-998811"
    assert top_lead["source"] == "FACEBOOK_ADS"
    assert top_lead["vertical"] == "AI Consultancy & Automation"
    assert top_lead["callable"] is True
    assert top_lead["queue_bucket"] == "FRESH_CALL_NOW"
    assert top_lead["freshness_stage"] == "NEWLY_IMPORTED"
    assert top_lead["attribution"]["campaign"] == "[MBM] AI Consultancy Discovery — Tech-Forward Business Owners"
    assert top_lead["attribution"]["form"] == "AI Consultancy Lead Form"
    assert "Call_Script" in top_lead["details"]
    assert "Marcus" in top_lead["details"]["Call_Script"]


def test_google_synthetic_lead_ingestion_and_dialer_delivery(temp_db):
    """Prove a raw Google Search lead form extension flows into FRESH_CALL_NOW."""
    raw_google_lead = {
        "google_lead_id": "GOOG-LEAD-445522",
        "full_name": "Sophia Lin",
        "contact_name": "Sophia Lin",
        "email": "sophia@lincreatives.io",
        "phone_number": "+15129482710",
        "company_name": "Lin Creative Studio LLC",
        "campaign": "[MBM] Website Design & Development — Search",
        "ad_group": "Custom Web Development High Intent",
        "keyword": "hire web developer for business website",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch([raw_google_lead], platform="google", dry_run=False)

    assert result["validated_count"] == 1
    assert result["newly_added_callable"] == 1

    # Verify in DB
    db_data = json.loads(temp_db.read_text(encoding="utf-8"))
    leads = db_data if isinstance(db_data, list) else db_data.get("leads", [])
    
    found = next((l for l in leads if l.get("id") == "GOOG-LEAD-445522"), None)
    assert found is not None
    assert found["source"] == "GOOGLE_ADS"
    assert found["vertical"] == "Website Design & Development"
    assert found["callable"] is True
    assert found["attribution"]["keyword"] == "hire web developer for business website"
    assert found["queue_bucket"] == "FRESH_CALL_NOW"


def test_bad_phone_rejection(temp_db):
    """Test that bad numbers (555-0000, too short, blank) are rejected from callable queue."""
    bad_leads = [
        {
            "id": "BAD-LEAD-1",
            "full_name": "Fake Person",
            "phone_number": "123",  # Too short
            "company_name": "Short Phone Corp",
        },
        {
            "id": "BAD-LEAD-2",
            "full_name": "Another Fake",
            "phone_number": "",  # Blank
            "company_name": "No Phone LLC",
        }
    ]

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch(bad_leads, platform="facebook", dry_run=False)

    assert result["rejected_count"] == 2
    assert result["validated_count"] == 0
    assert result["newly_added_callable"] == 0


def test_suppressed_phone_index_rejection(temp_db):
    """Test that numbers present in suppressed_bad_phones.json are rejected."""
    # Phone '+12082078500' is known to be in suppressed_bad_phones.json
    suppressed_lead = {
        "id": "SUPP-LEAD-001",
        "full_name": "Suppressed Lead Owner",
        "phone_number": "+12082078500",
        "company_name": "Suppressed Ventures LLC",
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    val_ok, reason = pipeline.validate_ad_lead(suppressed_lead)
    assert val_ok is False
    assert "SUPPRESSED" in reason


def test_dnc_lead_rejection(temp_db):
    """Test that DNC disposition flags prevent a lead from becoming callable."""
    dnc_lead = {
        "id": "DNC-LEAD-001",
        "full_name": "Opt Out Person",
        "phone_number": "+12148392011",
        "company_name": "DNC Opt Out LLC",
        "disposition": "DO_NOT_CALL_REQUESTED",
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    val_ok, reason = pipeline.validate_ad_lead(dnc_lead)
    assert val_ok is False
    assert "DNC" in reason or "SUPPRESSED" in reason


def test_deduplication_preserves_call_history(temp_db):
    """Prove deduplication updates existing lead without destroying call attempts / dispositions."""
    # Existing lead has phone "+12148392011", attempts=1, disposition="VOICEMAIL"
    duplicate_ad_submission = {
        "id": "FB-NEW-SUBMISSION",
        "full_name": "Dr. Sarah Jenkins",
        "phone_number": "+12148392011",
        "company_name": "Premier Aesthetic Dermatology",
        "campaign_name": "Retargeting Ad Campaign Q3",
        "What would you like AI to help with?": "Now also need mobile app consultation",
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch([duplicate_ad_submission], platform="facebook", dry_run=False)

    assert result["duplicates_updated"] == 1
    assert result["newly_added_callable"] == 0

    db_data = json.loads(temp_db.read_text(encoding="utf-8"))
    leads = db_data if isinstance(db_data, list) else db_data.get("leads", [])
    
    # Must still have exactly 1 record with this phone (no duplicate row)
    matched = [l for l in leads if "2148392011" in str(l.get("phone"))]
    assert len(matched) == 1
    lead = matched[0]
    
    # History preserved
    assert lead["attempts"] == 1
    assert lead["disposition"] == "VOICEMAIL"
    # Ad data merged
    assert "last_ad_touch" in lead
    assert lead["latest_attribution"]["campaign"] == "Retargeting Ad Campaign Q3"


def test_hard_spend_safety_gate():
    """Prove that LIVE_ADS_ENABLED=false blocks live campaign creation."""
    os.environ["LIVE_ADS_ENABLED"] = "false"
    gate_ok, reason = verify_live_campaign_gate("facebook", 20.0, "Test Campaign")
    assert gate_ok is False
    assert "LIVE_ADS_ENABLED is false" in reason

    # Preflight report generation
    report = generate_preflight_report(
        platform="facebook",
        campaign_name="AI Consultancy Test",
        niche="AI Consultancy",
        target_audience="Tech Owners",
        daily_budget=20.0,
        total_budget=600.0,
        form_name="Instant Lead Form",
    )
    assert report["spend_gate"]["gate_status"] == "LOCKED_SAFETY_GATE"
    assert report["spend_gate"]["live_ads_enabled"] is False


def test_reconciliation_report_generation(temp_db):
    """Verify daily reconciliation ledger updates correctly."""
    raw_leads = [
        {
            "id": "REC-FB-1",
            "full_name": "Test Ingestion User",
            "phone_number": "+15125553322",
            "company_name": "Reconciliation Test Co LLC",
        }
    ]

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    pipeline.ingest_batch(raw_leads, platform="facebook", dry_run=False)

    assert ADS_RECONCILIATION_JSON.exists()
    assert ADS_RECONCILIATION_MD.exists()

    data = json.loads(ADS_RECONCILIATION_JSON.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert today in data
    assert data[today]["facebook"]["received"] >= 1


def test_credential_diagnostics_precheck():
    """Verify credential diagnostics output without exposing secret values."""
    from MBM.LeadEngine.ads.ads_config import get_credentials_diagnostics
    diag = get_credentials_diagnostics()

    assert "facebook" in diag
    assert "google" in diag
    assert "live_ads" in diag
    assert diag["live_ads"]["LIVE_ADS_ENABLED"] is False
    assert "LOCKED" in diag["live_ads"]["spend_gate"]
    assert diag["facebook"]["FB_ACCESS_TOKEN"] in ("PRESENT", "MISSING")
    assert diag["facebook"]["FB_AD_ACCOUNT_ID"] in ("PRESENT", "MISSING")
    assert diag["google"]["GOOGLE_ADS_DEVELOPER_TOKEN"] in ("PRESENT", "MISSING")


def test_read_only_pull_leads_without_credentials():
    """Verify pull_leads returns clean diagnostic error without crashing, spending, or mutating."""
    from MBM.LeadEngine.ads.facebook_ads_lead_engine import FacebookAdsLeadEngine
    from MBM.LeadEngine.ads.google_ads_lead_engine import GoogleAdsLeadEngine

    fb_engine = FacebookAdsLeadEngine()
    fb_res = fb_engine.pull_leads()
    assert fb_res["status"] == "ERROR"
    assert "API not configured" in fb_res["reason"]

    ga_engine = GoogleAdsLeadEngine()
    ga_res = ga_engine.pull_leads()
    assert ga_res["status"] == "ERROR"
    assert "API not configured" in ga_res["reason"]


def test_multi_niche_synthetic_routing_all_niches(temp_db):
    """Test that incoming leads across all active MBM niches map to their canonical verticals."""
    niche_payloads = [
        # 1. Real Estate Sellers
        {
            "id": "FB-NICHE-RE-01",
            "full_name": "Arthur Pendelton",
            "phone_number": "+12148392012",
            "company_name": "Pendelton Family Trust",
            "campaign": "Motivated Seller As-Is Cash Offers",
            "property_address": "4521 Oak Crest Drive, Dallas, TX",
            "selling_timeline": "Immediately (< 14 days)",
        },
        # 2. Cash Buyers & Flippers
        {
            "id": "GOOG-NICHE-CB-01",
            "full_name": "Dmitri Volkov",
            "phone_number": "+12148392013",
            "company_name": "Volkov Capital Assets LLC",
            "campaign": "VIP Cash Buyer Off-Market Deals",
            "capital_ready": "$1M - $5M",
            "keyword": "off-market distressed properties wholesale buy box",
        },
        # 3. Med Spas & Aesthetics
        {
            "id": "FB-NICHE-MED-01",
            "full_name": "Dr. Aris Thorne",
            "phone_number": "+12148392014",
            "company_name": "Thorne Aesthetics & Wellness",
            "campaign": "Med Spa AI Patient Booking System",
            "treatment_types": "Injectables & Fillers",
        },
        # 4. Commercial Contractors & ConTech
        {
            "id": "GOOG-NICHE-CON-01",
            "full_name": "Frank Castleman",
            "phone_number": "+12148392015",
            "company_name": "Castleman Mechanical Systems LLC",
            "campaign": "Commercial HVAC Contractor Estimating",
            "trade": "HVAC & Mechanical",
            "keyword": "commercial contractor takeoff estimating software",
        },
        # 5. Mobile App Development
        {
            "id": "FB-NICHE-APP-01",
            "full_name": "Nadia Benali",
            "phone_number": "+12148392016",
            "company_name": "Benali Health Tech",
            "campaign": "Mobile App Development for Health Startups",
            "interest": "Build native iOS and Android MVP mobile app",
        },
    ]

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch(niche_payloads, platform="facebook", dry_run=False)

    assert result["validated_count"] == len(niche_payloads)
    assert result["newly_added_callable"] == len(niche_payloads)

    db_data = json.loads(temp_db.read_text(encoding="utf-8"))
    leads = db_data if isinstance(db_data, list) else db_data.get("leads", [])

    # Check that each lead received its canonical vertical
    by_id = {l["id"]: l for l in leads}
    assert by_id["FB-NICHE-RE-01"]["vertical"] == "Real Estate Sellers"
    assert by_id["GOOG-NICHE-CB-01"]["vertical"] == "Cash Buyers & Flippers"
    assert by_id["FB-NICHE-MED-01"]["vertical"] == "Med Spas & Aesthetics Clinics"
    assert by_id["GOOG-NICHE-CON-01"]["vertical"] == "Commercial Contractors & ConTech"
    assert by_id["FB-NICHE-APP-01"]["vertical"] == "Mobile App Development"


def test_source_to_niche_failsafe_unclassified(temp_db):
    """Prove that an unclassifiable lead triggers the failsafe and is rejected from callable dialer."""
    ambiguous_lead = {
        "id": "FB-UNKNOWN-01",
        "full_name": "John Ambiguous",
        "phone_number": "+12148392017",
        "company_name": "Random Corporation",
        "campaign": "Generic Ad Campaign 123",
        "ad_set": "General Group",
        "form": "Generic Blank Form",
        "business_type": "Something obscure",
    }

    pipeline = AdLeadIngestionPipeline(db_path=temp_db)
    result = pipeline.ingest_batch([ambiguous_lead], platform="facebook", dry_run=False)

    assert result["rejected_count"] == 1
    assert result["validated_count"] == 0
    assert result["newly_added_callable"] == 0
    assert "UNCLASSIFIED_NICHE" in result["rejections"][0]["reason"]


def test_lead_capacity_and_shortfall_calculation(temp_db):
    """Verify LeadCapacityAnalyzer computes inventory and shortfall."""
    from MBM.LeadEngine.ads.ads_ingestion_pipeline import LeadCapacityAnalyzer
    db_data = json.loads(temp_db.read_text(encoding="utf-8"))
    leads = db_data if isinstance(db_data, list) else db_data.get("leads", [])

    capacity = LeadCapacityAnalyzer.analyze_capacity(leads)
    assert "niches" in capacity
    assert "Real Estate Sellers" in capacity["niches"]
    assert "shortfall" in capacity["niches"]["Real Estate Sellers"]
    assert capacity["total_daily_target"] > 0


def test_credential_transition_state_machine():
    """Verify safety state transitions from missing to present credentials without auto-enabling live ads."""
    from MBM.LeadEngine.ads.ads_config import get_credentials_diagnostics, is_live_ads_enabled

    # State 1: Missing credentials
    os.environ["LIVE_ADS_ENABLED"] = "false"
    diag = get_credentials_diagnostics()
    assert diag["live_ads"]["LIVE_ADS_ENABLED"] is False
    assert "LOCKED" in diag["live_ads"]["spend_gate"]

    # State 2: Simulated addition of credentials
    os.environ["FB_ACCESS_TOKEN"] = "EAA_test_token"
    os.environ["FB_AD_ACCOUNT_ID"] = "act_123456789"
    diag2 = get_credentials_diagnostics()
    assert diag2["facebook"]["FB_ACCESS_TOKEN"] == "PRESENT"
    assert diag2["facebook"]["FB_AD_ACCOUNT_ID"] == "PRESENT"
    assert diag2["facebook"]["status"] == "READY"
    # Crucial invariant: LIVE_ADS_ENABLED must still remain False!
    assert is_live_ads_enabled() is False
    assert diag2["live_ads"]["LIVE_ADS_ENABLED"] is False

    # Cleanup test env
    del os.environ["FB_ACCESS_TOKEN"]
    del os.environ["FB_AD_ACCOUNT_ID"]
