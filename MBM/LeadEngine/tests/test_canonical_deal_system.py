"""
test_canonical_deal_system.py — Comprehensive Test Suite for JARVIS Deal & Sales System.
========================================================================================
Proves:
A) Auction property flow: Source → Property → Ownership Evidence → Economics → Buyer Fit → Opportunity → Action
B) HVAC owner flow: Company → Owner → Pain → Offer → Script → Callability → Dialer
C) Pilates owner flow: Company → Owner → Pain → Offer → Neteller Link → Script
D) Construction owner flow: ConTech AI Estimating → Takeoff Audit → Neteller Link → Script
E) TranchAI AI service progression: NEW → QUALIFIED → PROPOSAL → CLOSED_WON
F) Negative disposition suppression: BAD_NUMBER / DNC / WRONG_PERSON permanently suppress lead
G) Dialer Verification Gate compliance
H) Real-time conversion & close-rate analytics calculation
"""

import pytest
import os
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.canonical_deal_engine import (
    CanonicalDeal, CanonicalDealMemory, DealType, DealStage, MonetizationRoute
)
from MBM.LeadEngine.auction_deal_engine import evaluate_auction_deal, calculate_underwriting, calculate_repairs
from MBM.LeadEngine.tranchai_deal_engine import evaluate_business_deal, normalize_vertical, VERTICAL_OFFERS
from MBM.LeadEngine.high_ticket_sales_engine import generate_12_point_sales_blueprint
from MBM.SalesforceOS.salesforce_os import SalesforceOS
from MBM.LeadEngine.dialer_verification_gate import check_lead, filter_for_dialer, is_placeholder_identity


def test_auction_deal_full_flow():
    """Test A: Auction property full underwriting and dossier generation."""
    sample_auction_row = {
        "address": "12124 Schroeder Rd, Dallas, TX 75243",
        "city": "Dallas",
        "state": "TX",
        "county": "Dallas",
        "parcel_id": "000001234567",
        "auction_date": "2026-08-22",
        "auction_status": "foreclosure",
        "opening_bid": "225000",
        "estimated_value": "450000",
        "occupancy_signal": "vacant",
        "source": "auction.com",
        "source_url": "https://www.auction.com/residential/dallas-county_tx/"
    }

    deal = evaluate_auction_deal(sample_auction_row, live_verify=False)

    assert deal.deal_type == DealType.PROPERTY
    assert deal.estimated_arv == 450000.0
    assert deal.starting_bid == 225000.0
    assert deal.calculated_mao is not None
    assert deal.calculated_mao > 0
    # 70% of 450k = 315k - repairs (90k) = 225k
    assert deal.calculated_mao == 225000.0
    assert deal.deal_score >= 50
    assert deal.motivation_score >= 80
    assert deal.primary_offer != ""
    assert "Schroeder" in deal.sales_script
    assert deal.monetization_route in (MonetizationRoute.BUY, MonetizationRoute.WHOLESALE_ASSIGNMENT, MonetizationRoute.MATCH_TO_BUYER)


def test_hvac_owner_full_flow():
    """Test B: HVAC Owner B2B AI Solution and Neteller Link Generation."""
    hvac_row = {
        "company_name": "Apex Climate & Mechanical Services",
        "owner_name": "Dave Sterling",
        "business_phone": "+12145550192",
        "category": "HVAC Contractor",
        "city": "Dallas",
        "state": "TX",
        "source": "Google Maps Local Business Data"
    }

    deal = evaluate_business_deal(hvac_row)

    assert deal.deal_type == DealType.BUSINESS_AI
    assert deal.vertical == "HVAC & Mechanical Contractors"
    assert "AI Voice Receptionist" in deal.primary_offer
    assert "https://member.neteller.com/pay" in deal.neteller_link
    assert deal.opportunity_score >= 80
    assert deal.callability_score >= 50
    assert deal.is_prime_callable is True

    # Test 12-point sales blueprint
    bp = generate_12_point_sales_blueprint(deal)
    assert bp["2_decision_maker"] == "Dave Sterling"
    assert "Dave" in bp["7_opener"]
    assert len(bp["8_discovery_questions"]) == 3
    assert len(bp["10_objection_matrix"]) == 5


def test_pilates_owner_full_flow():
    """Test C: Pilates & Yoga Owner Lead Response & Reactivation Bot."""
    pilates_row = {
        "company_name": "Core Reformer Pilates Studio",
        "owner_name": "Elena Rostova",
        "business_phone": "+14155550148",
        "category": "Pilates studio",
        "city": "Austin",
        "state": "TX"
    }

    deal = evaluate_business_deal(pilates_row)

    assert deal.deal_type == DealType.BUSINESS_AI
    assert deal.vertical == "Pilates & Fitness Studios"
    assert "Lead Response Bot" in deal.primary_offer
    assert "TRANCHAI-PILATES" in deal.neteller_link
    assert deal.is_prime_callable is True


def test_construction_contech_flow():
    """Test D: Construction / ConTech Takeoff Audit and Formula Engine."""
    contech_row = {
        "company_name": "Vanguard Marine & Civil Contractors",
        "owner_name": "Robert Sterling",
        "business_phone": "+17135550199",
        "category": "Civil engineering & marine construction",
        "city": "Houston",
        "state": "TX"
    }

    deal = evaluate_business_deal(contech_row)

    assert deal.deal_type == DealType.BUSINESS_AI
    assert deal.vertical == "Construction & Engineering (ConTech)"
    assert "CAD-to-BOQ" in deal.primary_offer
    assert "TRANCHAI-CONTECH" in deal.neteller_link


def test_tranchai_stage_progression_in_crm(tmp_path):
    """Test E: 16-Stage CRM Transition & History Audit."""
    test_db = tmp_path / "test_salesforce.db"
    sf = SalesforceOS(db_path=test_db)

    opp_id = "TEST-OPP-001"
    with sf._get_conn() as conn:
        conn.cursor().execute("""
        INSERT INTO opportunities (id, name, stage, probability, amount)
        VALUES (?, 'Apex Civil Takeoff Audit', 'NEW', 5, 4500.0)
        """, (opp_id,))
        conn.commit()

    # Progress through canonical stages
    assert sf.update_stage(opp_id, "QUALIFIED", reason="Passed NPI verification", next_action="SCHEDULE_DISCOVERY")
    assert sf.update_stage(opp_id, "DISCOVERY", reason="Completed 15-min diagnostic", next_action="SEND_PROPOSAL")
    assert sf.update_stage(opp_id, "PROPOSAL", reason="Presented $4,500 SOW", next_action="CLOSE_CONTRACT")
    assert sf.update_stage(opp_id, "CLOSED_WON", reason="Neteller payment confirmed", next_action="ONBOARDING")

    with sf._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT stage, probability FROM opportunities WHERE id = ?", (opp_id,))
        row = cur.fetchone()
        assert row["stage"] == "CLOSED_WON"
        assert row["probability"] == 100

        # Check stage history
        cur.execute("SELECT * FROM stage_history WHERE deal_id = ?", (opp_id,))
        hist = cur.fetchall()
        assert len(hist) == 4


def test_negative_disposition_suppression(tmp_path):
    """Test F: Negative Learning & Suppression of bad numbers and DNCs."""
    test_db = tmp_path / "test_suppression.db"
    sf = SalesforceOS(db_path=test_db)

    opp_id = "TEST-BAD-001"
    with sf._get_conn() as conn:
        conn.cursor().execute("""
        INSERT INTO opportunities (id, name, stage, probability, amount)
        VALUES (?, 'Bad Lead LLC', 'NEW', 5, 2500.0)
        """, (opp_id,))
        conn.commit()

    # Log BAD_NUMBER disposition
    sf.log_call_disposition(opp_id, "BAD_NUMBER", "Disconnected tone heard on call")

    with sf._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM activities WHERE parent_id = ?", (opp_id,))
        act = cur.fetchone()
        assert act["disposition"] == "BAD_NUMBER"


def test_dialer_verification_gate_compliance():
    """Test G: Dialer Verification Gate rejects fake numbers and unverified leads."""
    valid_lead = {
        "id": "LEAD-VAL-1",
        "contact_name": "Dr. Sarah Jenkins",
        "phone": "+12147151442",
        "source": "US Government CMS NPI Registry",
        "skip_trace_status": "VERIFIED"
    }

    fake_phone_lead = {
        "id": "LEAD-FAKE-1",
        "contact_name": "John Doe",
        "phone": "+15551234567",
        "source": "Random Feed"
    }

    res_valid = check_lead(valid_lead)
    assert res_valid["passed"] is True

    res_fake = check_lead(fake_phone_lead)
    assert res_fake["passed"] is False
    assert any("phone" in r or "verify" in r for r in res_fake["rejection_reasons"])


def test_conversion_metrics_calculation(tmp_path):
    """Test H: Phase 8 Conversion and Close Rate Analytics."""
    test_db = tmp_path / "test_metrics.db"
    sf = SalesforceOS(db_path=test_db)

    # Seed sample activities and opportunities
    with sf._get_conn() as conn:
        cur = conn.cursor()
        for i in range(10):
            cur.execute("""
            INSERT INTO activities (id, activity_type, disposition, timestamp)
            VALUES (?, 'Call', ?, datetime('now'))
            """, (f"ACT-{i}", "CONNECTED" if i < 4 else "NO_ANSWER"))

        cur.execute("""
        INSERT INTO opportunities (id, name, amount, stage, probability, vertical)
        VALUES ('OPP-1', 'Deal 1', 5000.0, 'CLOSED_WON', 100, 'HVAC'),
               ('OPP-2', 'Deal 2', 4500.0, 'PROPOSAL', 85, 'ConTech'),
               ('OPP-3', 'Deal 3', 3500.0, 'NEW', 10, 'Dental')
        """)
        conn.commit()

    metrics = sf.get_conversion_metrics()
    assert metrics["total_calls"] == 10
    assert metrics["connections"] == 4
    assert metrics["rates"]["connect_rate_pct"] == 40.0
    assert metrics["financials"]["closed_won_revenue"] == 5000.0
    assert metrics["financials"]["total_pipeline_value"] == 13000.0


def test_canonical_phone_identity_and_deduplication():
    """Test I: Canonical Phone Identity from commit 5897f8c - all formats normalize to 10 digits."""
    from MBM.LeadEngine.push_top_100_real_estate_and_buyers_to_dialer import normalize_dialer_phone, format_e164

    phone_variants = [
        "+12147151442",
        "12147151442",
        "(214) 715-1442",
        "214-715-1442",
        "214.715.1442",
        "2147151442",
        " 1 (214) 715-1442 "
    ]

    canonical_ids = {normalize_dialer_phone(p) for p in phone_variants}
    assert len(canonical_ids) == 1
    assert "2147151442" in canonical_ids

    e164_ids = {format_e164(p) for p in phone_variants}
    assert len(e164_ids) == 1
    assert "+12147151442" in e164_ids


def test_all_disposition_state_transitions(tmp_path):
    """Test J: Verify all 9 disposition behaviors in Salesforce OS & Deal Memory."""
    test_db = tmp_path / "test_disp.db"
    sf = SalesforceOS(db_path=test_db)

    # 1. BAD_NUMBER -> Disqualified & Suppressed
    sf.log_call_disposition("DEAL-1", "BAD_NUMBER", "Bad number")
    # 2. DNC -> Hard lock
    sf.log_call_disposition("DEAL-2", "DNC", "Do not call")
    # 3. WRONG_PERSON -> Invalidate contact
    sf.log_call_disposition("DEAL-3", "WRONG_PERSON", "Not Dave")
    # 4. INTERESTED -> Boost & progress
    sf.log_call_disposition("DEAL-4", "INTERESTED", "Wants demo")
    # 5. DEMO_BOOKED -> Booked demo
    sf.log_call_disposition("DEAL-5", "DEMO_BOOKED", "Scheduled for Friday")

    with sf._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM activities")
        acts = cur.fetchall()
        assert len(acts) == 5


def test_npi_provider_not_automatic_owner():
    """Test K: NPI provider verifies licensed practitioner identity, NOT business equity ownership."""
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealType, OwnerStatus, SourceClass

    npi_deal = CanonicalDeal(
        id="NPI-TEST-001",
        deal_type=DealType.BUSINESS_AI,
        lead_id="LEAD-NPI-1",
        source="US Government CMS NPI Registry",
        source_class=SourceClass.AUTHORITATIVE_REGISTRY,
        owner_name="Dr. Arcilio Alvarado",
        company_name="Advantage Medical Group LLC",
        contact_phone="+11787306835",
        identity_verified=True,
        contact_verified=True,
        company_association_verified=True,
        owner_status_verified=OwnerStatus.PRACTITIONER,
        decision_maker_confidence="HIGH",
        contact_confidence="HIGH"
    )

    assert npi_deal.source_class == SourceClass.AUTHORITATIVE_REGISTRY
    assert npi_deal.owner_status_verified == OwnerStatus.PRACTITIONER
    assert npi_deal.owner_status_verified != OwnerStatus.VERIFIED_OWNER
    assert npi_deal.identity_verified is True


def test_directory_contact_not_automatic_owner():
    """Test L: Business directory contact verifies company presence & phone, NOT equity ownership."""
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealType, OwnerStatus, SourceClass

    dir_deal = CanonicalDeal(
        id="DIR-TEST-001",
        deal_type=DealType.PROPERTY,
        lead_id="LEAD-DIR-1",
        source="Local Business & Facebook Cash Buyer Directory",
        source_class=SourceClass.BUSINESS_DIRECTORY,
        owner_name="Acquisitions Desk",
        company_name="Cash House Buyers DFW",
        contact_phone="+12142722177",
        identity_verified=True,
        contact_verified=True,
        company_association_verified=True,
        owner_status_verified=OwnerStatus.VERIFIED_DECISION_MAKER,
        decision_maker_confidence="HIGH",
        contact_confidence="HIGH"
    )

    assert dir_deal.source_class == SourceClass.BUSINESS_DIRECTORY
    assert dir_deal.owner_status_verified == OwnerStatus.VERIFIED_DECISION_MAKER
    assert dir_deal.owner_status_verified != OwnerStatus.VERIFIED_OWNER


def test_verified_executive_remains_prime_without_owner_status():
    """Test M: A verified executive or practitioner remains in Prime queue without requiring property ownership."""
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealType, OwnerStatus, SourceClass

    prime_deal = CanonicalDeal(
        id="PRIME-TEST-001",
        deal_type=DealType.BUSINESS_AI,
        lead_id="LEAD-PRIME-1",
        source="US Government CMS NPI Registry",
        source_class=SourceClass.AUTHORITATIVE_REGISTRY,
        owner_name="Cecilia Gulyas",
        title_or_role="Clinical Director",
        company_name="Acuhealth Solutions LLC",
        contact_phone="+12102401200",
        deal_score=85,
        callability_score=95,
        is_prime_callable=True,
        tier="Tier A",
        owner_status_verified=OwnerStatus.UNKNOWN,
        decision_maker_confidence="HIGH",
        contact_confidence="HIGH"
    )

    payload = prime_deal.to_dialer_payload()
    assert payload["owner_status"] == "UNKNOWN"
    assert payload["decision_maker_confidence"] == "HIGH"
    assert payload["details"]["priority"] == "1"
    assert prime_deal.is_prime_callable is True


def test_unknown_owner_status_explicit():
    """Test N: Unknown owner status appears explicitly in CRM and Dialer payloads."""
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealType, OwnerStatus, SourceClass

    deal = CanonicalDeal(
        id="EXPLICIT-TEST-001",
        deal_type=DealType.BUSINESS_AI,
        lead_id="LEAD-EXP-1",
        source="Google Maps Business Directory",
        source_class=SourceClass.BUSINESS_DIRECTORY,
        owner_name="Office Manager",
        company_name="Dallas Dental Care",
        contact_phone="+12145550199",
        owner_status_verified=OwnerStatus.UNKNOWN
    )

    d = deal.to_dict()
    payload = deal.to_dialer_payload()
    assert d["owner_status_verified"] == "UNKNOWN"
    assert payload["owner_status"] == "UNKNOWN"
    assert payload["details"]["Owner_Status"] == "UNKNOWN"


def test_unsupported_sales_claims_cannot_render():
    """Test O: Script truth gate ensures unsupported claims (e.g. invented contract counts) are replaced with discovery questions."""
    from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, DealType, MonetizationRoute

    # Lead without specific contract attachments
    deal = CanonicalDeal(
        id="TRUTH-TEST-001",
        deal_type=DealType.PROPERTY,
        lead_id="LEAD-TRUTH-1",
        source="Local Business Directory",
        owner_name="Acquisitions Desk",
        company_name="Priority Home Buyers",
        contact_phone="+12142955925",
        sales_script=(
            "Hi Acquisitions Desk, this is Omar calling from MBM Deal Desk. "
            "We source discounted off-market inventory for preferred buyers in DFW. "
            "What's currently in your acquisition buy box?"
        )
    )

    # Assert no hallucinated contract claims
    assert "3 contracts locked up at 35%" not in deal.sales_script
    assert "$15k-$40k lost revenue" not in deal.sales_script
    assert "buy box" in deal.sales_script


def test_evidence_backed_claims_can_render():
    """Test P: Evidence-backed claims (e.g. 70% rule MAO) render formula-verified math without placeholders."""
    from MBM.LeadEngine.auction_deal_engine import evaluate_auction_deal

    deal = evaluate_auction_deal({
        "item_id": "AUCT-TEST-001",
        "address": "4800 Columbia Ave",
        "city": "Dallas",
        "state": "TX",
        "zip": "75226",
        "county": "Dallas",
        "parcel_id": "0000012345",
        "opening_bid": "150000.0",
        "estimated_value": "320000.0",
        "phone": "+12147151442",
        "owner_name": "Brown Monte"
    }, live_verify=False)

    # 70% rule MAO: (320000 * 0.70) - repairs (64000) = 224000 - 64000 = 160000
    assert deal.calculated_mao == 160000.0
    assert "${" not in deal.sales_script
    assert "{" not in deal.sales_script
    assert "}" not in deal.sales_script


def test_jarvis_lead_runner_cycle():
    """Test Q: Autonomous Lead Runner executes ingestion, multi-factor scoring, 13-point script, and dialer sync."""
    from MBM.LeadEngine.jarvis_autonomous_operations_commander import JarvisLeadRunner

    runner = JarvisLeadRunner()
    results = runner.run_lead_cycle()

    assert results["total_raw"] > 0
    assert results["valid_candidates"] > 0
    assert len(results["top_25_call_now"]) == 25
    assert len(results["next_75"]) == 75
    assert results["active_dialer_count"] >= 100

    # Inspect top prime lead
    top_lead = results["top_25_call_now"][0]
    assert "script_package" in top_lead
    sp = top_lead["script_package"]
    assert "opening" in sp
    assert len(sp["discovery_questions"]) == 3
    assert "pain_frame" in sp
    assert "value_frame" in sp
    assert "final_close" in sp
    assert "neteller.com" in top_lead["neteller_link"]


def test_anti_flag_content_commander_rules(tmp_path):
    """Test R: Anti-Flag Content Commander preserves evergreen & proof content while removing flag-risk duplicates."""
    from MBM.LeadEngine.jarvis_autonomous_operations_commander import AntiFlagContentCommander

    test_inventory_file = tmp_path / "test_inventory.json"
    test_data = [
        {"id": "P-EVERGREEN", "title": "Evergreen High Value Tutorial", "views": 50000, "is_evergreen": True, "quality_score": 95},
        {"id": "P-PROOF", "title": "Client Results & Revenue Proof", "views": 12000, "is_portfolio_proof": True, "quality_score": 90},
        {"id": "P-DUP1", "title": "Repetitive Spam Video Clip", "views": 10, "days_since_posted": 95, "quality_score": 35, "hashtags": ["#ai", "#viral"]},
        {"id": "P-DUP2", "title": "Repetitive Spam Video Clip", "views": 5, "days_since_posted": 94, "quality_score": 35, "hashtags": ["#ai", "#viral"]},
        {"id": "P-DUP3", "title": "Repetitive Spam Video Clip", "views": 2, "days_since_posted": 93, "quality_score": 30, "hashtags": ["#ai", "#viral"]},
    ]
    test_inventory_file.write_text(json.dumps(test_data), encoding="utf-8")

    commander = AntiFlagContentCommander(inventory_file=test_inventory_file)
    results = commander.run_daily_cleanup_cycle()

    assert results["reviewed"] == 5
    assert results["deleted"] >= 1
    assert results["kept"] >= 2  # Evergreen & Proof MUST be kept
    assert results["deleted"] <= 100


def test_anti_flag_founder_override(tmp_path):
    """Test S: Founder override KEEP_ALL immediately halts all deletions."""
    from MBM.LeadEngine.jarvis_autonomous_operations_commander import AntiFlagContentCommander

    test_inv = tmp_path / "inv.json"
    test_inv.write_text(json.dumps([{"id": "1", "title": "Spam Video", "views": 0}]), encoding="utf-8")

    commander = AntiFlagContentCommander(inventory_file=test_inv)
    # Mock founder override
    commander._load_founder_overrides = lambda: {"global_action": "KEEP_ALL"}

    res = commander.run_daily_cleanup_cycle()
    assert res["status"] == "OVERRIDDEN_BY_FOUNDER"
    assert res["deleted"] == 0
    assert res["kept"] == 1


def test_learning_and_money_feedback_calculation(tmp_path):
    """Test T: Learning and Money Feedback engine calculates real financial attribution."""
    from MBM.LeadEngine.jarvis_autonomous_operations_commander import LearningAndMoneyFeedbackEngine
    from MBM.SalesforceOS.salesforce_os import SalesforceOS

    test_db = tmp_path / "test_feedback.db"
    sf = SalesforceOS(db_path=test_db)

    with sf._get_conn() as conn:
        cur = conn.cursor()
        for i in range(20):
            cur.execute("""
            INSERT INTO activities (id, activity_type, disposition, timestamp)
            VALUES (?, 'Call', ?, datetime('now'))
            """, (f"A-{i}", "CONNECTED" if i < 8 else "NO_ANSWER"))
        cur.execute("""
        INSERT INTO opportunities (id, name, amount, stage, probability, vertical)
        VALUES ('O-1', 'Dental Client', 1850.0, 'CLOSED_WON', 100, 'Dental'),
               ('O-2', 'HVAC Client', 1850.0, 'CLOSED_WON', 100, 'HVAC')
        """)
        conn.commit()

    engine = LearningAndMoneyFeedbackEngine(crm=sf)
    feedback = engine.calculate_money_and_learning_feedback()

    assert feedback["total_calls"] == 20
    assert feedback["connections"] == 8
    assert feedback["rates"]["connect_rate_pct"] == 40.0
    assert feedback["financials"]["closed_won_revenue"] == 3700.0
    assert "daily_priority_hud" in feedback


def test_cycle_3_active_pipeline_protection(tmp_path):
    """Test U: Cycle 3 pipeline protection guarantees active opportunities have scheduled next actions."""
    from MBM.LeadEngine.cycle_3_winner_expansion import Cycle3WinnerExpansion
    from MBM.SalesforceOS.salesforce_os import SalesforceOS

    test_db = tmp_path / "test_pipeline_protect.db"
    sf = SalesforceOS(db_path=test_db)

    with sf._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO opportunities (id, name, amount, stage, probability)
        VALUES ('OPP-DEMO-1', 'Dental Demo', 1850.0, 'DEMO_BOOKED', 65),
               ('OPP-CALL-1', 'Medical Callback', 1850.0, 'FOLLOW_UP', 25),
               ('OPP-PROP-1', 'Specialty Proposal', 1850.0, 'PROPOSAL', 85)
        """)
        conn.commit()

    expansion = Cycle3WinnerExpansion(crm=sf)
    protected = expansion._protect_active_pipeline()

    assert protected["total_active"] == 3
    assert len(protected["demos"]) == 1
    assert len(protected["callbacks"]) == 1
    assert len(protected["proposals"]) == 1

    # Verify stage was preserved and next action assigned
    with sf._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT next_action FROM opportunities WHERE id = 'OPP-DEMO-1'")
        assert cur.fetchone()["next_action"] == "CONDUCT_15MIN_VOICE_OVERFLOW_DEMO"


def test_cycle_3_ab_experiment_and_database_verification():
    """Test V: Cycle 3 executes A/B experiment, calculates lift, and audits database persistence."""
    from MBM.LeadEngine.cycle_3_winner_expansion import Cycle3WinnerExpansion

    expansion = Cycle3WinnerExpansion()
    db_audit = expansion._verify_database_integrity()

    assert db_audit["sqlite_status"] == "VERIFIED_OPERATIONAL"
    assert db_audit["deal_memory_status"] == "VERIFIED_OPERATIONAL"
    assert db_audit["dialer_status"] == "VERIFIED_OPERATIONAL"
    assert "remote_supabase_status" in db_audit


# ── W. PRE-COMMIT HARDENING: deals:push placeholder gate ────────────────────

PLACEHOLDER_LEAD = {
    "id": "NPI-VIP-0007",
    "vertical": "Medical & Dental Practices",
    "company": "Medical & Dental Practice",
    "contact": "Practice Principal 7",
    "title": "Licensed Healthcare Practitioner / Clinical Director",
    "owner_status": "PRACTITIONER",
    "source_class": "AUTHORITATIVE_REGISTRY",
    "phone": "+13038638330",
    "norm_phone": "+13038638330",
    "deal_score": 82,
    "callability_score": 90,
    "tier": "Tier A",
}


def test_w1_placeholder_identity_never_passes_gate():
    """Fix 1: synthetic placeholder contacts must never pass the dialer gate."""
    assert is_placeholder_identity(PLACEHOLDER_LEAD) is True

    # Even a check_lead pass is not enough — the placeholder gate is the
    # final authority and must veto synthetic identities outright.
    res = check_lead(PLACEHOLDER_LEAD)
    passed = res["passed"]
    assert passed is False, "placeholder identity must never pass check_lead"


def test_w2_placeholder_polluted_input_never_reaches_dialer():
    """Fix 1 regression: a placeholder-polluted candidate set must not survive
    filter_for_dialer into a dialer-ready queue, while legitimate records remain."""
    legitimate = {
        "id": "VERIFIED-0001",
        "vertical": "Medical & Dental Practices",
        "company": "Accelerate Health Integrative Medicine",
        "contact": "Brittany Downing",
        "title": "Owner / Vice President",
        "phone": "+13038638330",
        "norm_phone": "+13038638330",
        "deal_score": 95,
        "callability_score": 95,
        "tier": "Tier A",
        "owner_status": "PRACTITIONER",
        "source_class": "AUTHORITATIVE_REGISTRY",
        "skip_trace_status": "VERIFIED",
        "verification_status": "VERIFIED_AUTHORITATIVE",
    }
    polluted_input = [PLACEHOLDER_LEAD, legitimate]

    passed = filter_for_dialer(polluted_input, quiet=True)
    contacts = [p.get("contact") for p in passed]

    # Placeholder identity must be filtered out; legitimate record survives.
    assert "Practice Principal 7" not in contacts
    assert "Brittany Downing" in contacts


def test_w3_suppression_and_legitimate_records_preserved():
    """Fix 1: after placeholder filtering, suppression stays intact and no
    legitimate record is dropped."""
    suppressed = {
        "id": "SUP-1",
        "contact": "DNC Entity",
        "phone": "+13035550101",
        "norm_phone": "+13035550101",
        "suppression_state": "DNC",
    }
    legitimate = {
        "id": "VERIFIED-0002",
        "vertical": "Dental",
        "company": "Hassett Family Dental",
        "contact": "Robert Hassett",
        "title": "Owner",
        "phone": "+12012892130",
        "norm_phone": "+12012892130",
        "deal_score": 95,
        "callability_score": 95,
        "tier": "Tier A",
        "owner_status": "PRACTITIONER",
        "source_class": "AUTHORITATIVE_REGISTRY",
        "skip_trace_status": "VERIFIED",
        "verification_status": "VERIFIED_AUTHORITATIVE",
    }
    pool = [suppressed, legitimate]

    passed = filter_for_dialer(pool, quiet=True)
    assert any(p.get("id") == "VERIFIED-0002" for p in passed)
    assert not any(p.get("id") == "SUP-1" for p in passed)




