"""
test_owner_identity.py — Owner Identity Verification Layer Test Suite
======================================================================
Proves the system NEVER fabricates owner confirmation and clearly separates:

    DATABASE OWNERSHIP VERIFICATION  (records say owner)
    vs
    LIVE CALLER IDENTITY CONFIRMATION (person on the phone is the owner)

Rules under test:
  - Matching phone alone NEVER equals owner-confirmed
  - Matching address alone NEVER equals owner-confirmed
  - Company contact does NOT automatically equal property owner
  - Tenant does NOT equal owner
  - Relative does NOT equal owner
  - Wrong person can never remain seller-confirmed
  - An existing verified public record is NOT overwritten by an unsupported
    caller statement
  - OWNER_CONFIRMED requires a caller-confirmed name matching the verified
    record + property confirmation
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.owner_identity import (
    IdentityState,
    evaluate_lead_identity,
    score_owner_match,
    is_primary_eligible,
    apply_identity_to_lead,
    audit_identity,
    names_match,
)

# A realistic DCAD-verified lead (authoritative county record).
DCAD_LEAD = {
    "id": "DCAD-SFH-899566",
    "owner_status": "VERIFIED_OWNER",
    "source_class": "COUNTY_RECORD",
    "contact": "Mcleod Bruce B. Iii",
    "company": "10102 APPLE CREEK DR, DALLAS, TX, 75243",
    "phone": "+1 214-555-0133",
    "skip_trace_status": "VERIFIED",
    "contact_confidence": "HIGH",
    "details": {
        "Owner_Name": "Mcleod Bruce B. Iii",
        "property_address": "10102 APPLE CREEK DR, DALLAS, TX, 75243",
        "source": "Dallas County Appraisal District (DCAD) + Skip Trace",
    },
}


def test_matching_phone_alone_does_not_equal_owner_confirmed():
    """A number beside an address proves nothing about who answers."""
    result = evaluate_lead_identity(DCAD_LEAD)
    assert result.state != IdentityState.OWNER_CONFIRMED
    assert result.state in (IdentityState.OWNER_LIKELY, IdentityState.IDENTITY_UNCONFIRMED)
    assert result.score < 90


def test_matching_address_alone_does_not_equal_owner_confirmed():
    """Address evidence alone (no caller confirmation) cannot confirm identity."""
    scored = score_owner_match(DCAD_LEAD)
    # +20 authoritative +10 relationship = 30, well below owner-confirmed.
    assert scored["score"] < 90
    assert not scored["name_matched"]


def test_company_contact_does_not_equal_property_owner():
    """A corporate/company contact is not automatically the property owner."""
    company_lead = {
        "id": "B2B-1",
        "owner_status": "VERIFIED_DECISION_MAKER",
        "source_class": "BUSINESS_DIRECTORY",
        "contact": "Acquisitions Partner",
        "company": "BuyerGroup LLC",
        "phone": "+1 214-555-0144",
        "details": {"Owner_Name": "Acquisitions Partner", "source": "Business Directory"},
    }
    result = evaluate_lead_identity(company_lead)
    assert result.state != IdentityState.OWNER_CONFIRMED
    assert result.state != IdentityState.OWNER_LIKELY


def test_tenant_does_not_equal_owner():
    result = evaluate_lead_identity(DCAD_LEAD, relationship="TENANT",
                                    caller_name="Jane Renter", name_confirmed=True)
    assert result.state == IdentityState.TENANT
    assert not is_primary_eligible(result.state)


def test_relative_does_not_equal_owner():
    result = evaluate_lead_identity(DCAD_LEAD, relationship="RELATIVE_OR_ASSOCIATE",
                                    caller_name="Alex Mcleod", name_confirmed=True)
    assert result.state == IdentityState.RELATIVE_OR_ASSOCIATE
    assert not is_primary_eligible(result.state)


def test_wrong_person_cannot_remain_seller_confirmed():
    result = evaluate_lead_identity(DCAD_LEAD, relationship="WRONG_PERSON",
                                    caller_name="Someone Else", name_confirmed=True)
    assert result.state == IdentityState.WRONG_PERSON
    assert not is_primary_eligible(result.state)


def test_wrong_number_suppressed():
    result = evaluate_lead_identity(DCAD_LEAD, wrong_number=True)
    assert result.state == IdentityState.WRONG_NUMBER
    assert not is_primary_eligible(result.state)


def test_do_not_call_suppressed():
    result = evaluate_lead_identity(DCAD_LEAD, do_not_call=True)
    assert result.state == IdentityState.DO_NOT_CALL
    assert not is_primary_eligible(result.state)


def test_owner_confirmed_requires_name_match_and_property():
    """Full evidence + caller confirmation reaches OWNER_CONFIRMED only with
    a name matching the verified record AND property confirmation."""
    result = evaluate_lead_identity(
        DCAD_LEAD,
        caller_name="Bruce Mcleod", relationship="OWNER",
        property_confirmed=True, name_confirmed=True,
    )
    assert result.state == IdentityState.OWNER_CONFIRMED
    assert result.score >= 90
    assert is_primary_eligible(result.state)


def test_name_confirmed_without_property_is_likely_not_confirmed():
    result = evaluate_lead_identity(
        DCAD_LEAD,
        caller_name="Bruce Mcleod", relationship="OWNER",
        property_confirmed=False, name_confirmed=True,
    )
    assert result.state != IdentityState.OWNER_CONFIRMED
    assert result.state == IdentityState.OWNER_LIKELY


def test_unsupported_caller_statement_cannot_overwrite_verified_record():
    """An authoritative public record is never demoted to WRONG_PERSON by an
    unsupported statement — only by the caller explicitly claiming a
    non-owner relationship."""
    result = evaluate_lead_identity(DCAD_LEAD)  # no caller input at all
    assert result.state != IdentityState.WRONG_PERSON
    # DB record remains recognized as database-verified ownership.
    patched = apply_identity_to_lead(dict(DCAD_LEAD), result)
    assert patched["database_ownership_verified"] is True


def test_score_never_manufactures_certainty():
    """Database evidence alone (authoritative + relationship) caps below 90."""
    scored = score_owner_match(DCAD_LEAD)
    assert scored["score"] <= 60  # 20 + 10 (+ nothing call-derived)
    assert "name_match" not in scored["breakdown"]


def test_apply_identity_preserves_sales_data():
    """Identity updates never destroy dispositions/notes/attempts/stage."""
    lead = dict(DCAD_LEAD)
    lead["disposition"] = "callback"
    lead["notes"] = "Owner will call back Thursday"
    lead["attempts"] = 3
    lead["last_touch"] = "2026-08-15"
    result = evaluate_lead_identity(lead, relationship="TENANT", caller_name="X")
    patched = apply_identity_to_lead(lead, result)
    assert patched["disposition"] == "callback"
    assert patched["notes"] == "Owner will call back Thursday"
    assert patched["attempts"] == 3
    assert patched["last_touch"] == "2026-08-15"
    assert patched["identity_state"] == "TENANT"


def test_authorized_decision_maker_primary_eligible():
    result = evaluate_lead_identity(DCAD_LEAD, relationship="AUTHORIZED_DECISION_MAKER")
    assert result.state == IdentityState.AUTHORIZED_DECISION_MAKER
    assert is_primary_eligible(result.state)


def test_names_match_surname_overlap():
    assert names_match("Mcleod Bruce B. Iii", "Bruce Mcleod")
    assert names_match("Son Rosemary & Benjamin D. Lake", "Benjamin Lake")
    assert not names_match("Mcleod Bruce", "Jose Rodriguez")
    assert not names_match("", "")


def test_audit_identity_distinguishes_db_vs_caller():
    db_verified = dict(DCAD_LEAD)
    caller_confirmed = apply_identity_to_lead(
        dict(DCAD_LEAD),
        evaluate_lead_identity(DCAD_LEAD, caller_name="Bruce Mcleod",
                               relationship="OWNER", property_confirmed=True,
                               name_confirmed=True),
    )
    report = audit_identity([db_verified, caller_confirmed])
    assert report["database_ownership_verified"] == 2
    assert report["caller_identity_verified"] == 1
    assert report["owner_confirmed"] == 1


def test_is_primary_eligible_rejects_suppressed_and_accepts_clean():
    for state in (IdentityState.WRONG_PERSON, IdentityState.WRONG_NUMBER,
                  IdentityState.TENANT, IdentityState.RELATIVE_OR_ASSOCIATE,
                  IdentityState.DO_NOT_CALL, IdentityState.QUARANTINED):
        assert not is_primary_eligible(state)
    for state in (IdentityState.OWNER_CONFIRMED, IdentityState.OWNER_LIKELY,
                  IdentityState.AUTHORIZED_DECISION_MAKER, IdentityState.IDENTITY_UNCONFIRMED):
        assert is_primary_eligible(state)
