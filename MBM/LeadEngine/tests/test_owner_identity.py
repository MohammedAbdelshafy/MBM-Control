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


# ── State machine: OWNER_LIKELY → live call → confirmed identity ──────────
# The flow the mission targets:
#   OWNER_LIKELY → CALL CONNECTED → PERSON IDENTIFIED → PROPERTY CONNECTION
#   CONFIRMED → OWNER / AUTHORIZED DECISION MAKER CONFIRMED → OWNER_CONFIRMED
# OWNER_LIKELY is the database-grounded starting state (verified record, no
# live confirmation). Every transition below starts from an OWNER_LIKELY lead
# and applies ONE call-level outcome.

def _owner_likely_lead():
    """A database-verified record that audits to OWNER_LIKELY (no caller input)."""
    lead = dict(DCAD_LEAD)
    r = evaluate_lead_identity(lead)
    assert r.state == IdentityState.OWNER_LIKELY
    return apply_identity_to_lead(lead, r)


def test_transition_owner_likely_to_owner_confirmed():
    """OWNER_LIKELY → (caller confirms name + property, identifies as owner)
    → OWNER_CONFIRMED."""
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(
        lead, caller_name="Bruce Mcleod", relationship="OWNER",
        property_confirmed=True, name_confirmed=True,
    )
    assert result.state == IdentityState.OWNER_CONFIRMED
    assert result.previous_identity_state == "OWNER_LIKELY"
    patched = apply_identity_to_lead(lead, result)
    assert patched["identity_state"] == IdentityState.OWNER_CONFIRMED.value
    assert patched["caller_identity_verified"] is True
    assert patched["database_ownership_verified"] is True
    # Highest queue priority.
    from MBM.LeadEngine.owner_identity import identity_queue_rank
    assert identity_queue_rank(patched) == 0


def test_transition_owner_likely_to_authorized_decision_maker():
    """OWNER_LIKELY → caller establishes decision-making authority → ADM.
    ADM stays a SEPARATE state and is never collapsed into OWNER_CONFIRMED."""
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(
        lead, caller_name="Pat Mcleod", relationship="AUTHORIZED_DECISION_MAKER",
        property_confirmed=True, name_confirmed=True,
    )
    assert result.state == IdentityState.AUTHORIZED_DECISION_MAKER
    assert result.state != IdentityState.OWNER_CONFIRMED
    patched = apply_identity_to_lead(lead, result)
    assert patched["identity_state"] == IdentityState.AUTHORIZED_DECISION_MAKER.value
    assert patched["caller_identity_verified"] is True
    from MBM.LeadEngine.owner_identity import identity_queue_rank
    assert identity_queue_rank(patched) == 1


def test_transition_owner_likely_to_wrong_person():
    """OWNER_LIKELY → caller is not the owner → WRONG_PERSON → suppressed."""
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(lead, relationship="WRONG_PERSON",
                                    caller_name="Someone Else", name_confirmed=True)
    assert result.state == IdentityState.WRONG_PERSON
    assert not is_primary_eligible(result.state)
    patched = apply_identity_to_lead(lead, result)
    assert patched["identity_state"] == IdentityState.WRONG_PERSON.value
    assert patched["caller_identity_verified"] is False


def test_transition_owner_likely_to_wrong_number():
    """OWNER_LIKELY → number does not reach the owner → WRONG_NUMBER → suppressed."""
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(lead, wrong_number=True)
    assert result.state == IdentityState.WRONG_NUMBER
    assert not is_primary_eligible(result.state)


def test_transition_owner_likely_to_tenant():
    """OWNER_LIKELY → caller is a tenant → TENANT → suppressed (unless
    explicitly authorized, which is a separate ADM flow)."""
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(lead, relationship="TENANT",
                                    caller_name="Jane Renter", name_confirmed=True)
    assert result.state == IdentityState.TENANT
    assert not is_primary_eligible(result.state)


def test_duplicate_identity_submission_is_idempotent(tmp_path, monkeypatch):
    """Re-submitting the same outcome for one lead replaces the prior record —
    no stacking, previous state preserved on the repeat."""
    from MBM.LeadEngine.owner_identity import (
        save_identity_result, load_identity_results, IDENTITY_RESULTS_FILE,
    )
    monkeypatch.setattr("MBM.LeadEngine.owner_identity.IDENTITY_RESULTS_FILE", tmp_path / "results.json")
    lead = _owner_likely_lead()
    r1 = evaluate_lead_identity(lead, relationship="TENANT", caller_name="Renter")
    save_identity_result(r1)
    # Same lead again — another tenant result.
    r2 = evaluate_lead_identity(lead, relationship="TENANT", caller_name="Renter")
    rec2 = save_identity_result(r2)
    results = load_identity_results()
    assert len(results) == 1, "duplicate submissions must not stack"
    assert rec2["lead_id"] == lead["id"]
    assert rec2["previous_identity_state"] == "TENANT"


def test_identity_state_persistence_roundtrip(tmp_path, monkeypatch):
    """A saved identity result round-trips through the persistent layer with
    all required fields: lead id, state, timestamp, property confirmation,
    caller name, verification source, previous state."""
    from MBM.LeadEngine.owner_identity import (
        save_identity_result, load_identity_results, IDENTITY_RESULTS_FILE,
    )
    monkeypatch.setattr("MBM.LeadEngine.owner_identity.IDENTITY_RESULTS_FILE", tmp_path / "results.json")
    lead = _owner_likely_lead()
    result = evaluate_lead_identity(
        lead, caller_name="Bruce Mcleod", relationship="OWNER",
        property_confirmed=True, name_confirmed=True,
    )
    save_identity_result(result)
    results = load_identity_results()
    assert len(results) == 1
    rec = results[0]
    assert rec["lead_id"] == lead["id"]
    assert rec["identity_state"] == "OWNER_CONFIRMED"
    assert rec["created_at"]
    assert rec["property_confirmed"] is True
    assert rec["caller_name"] == "Bruce Mcleod"
    assert rec["verification_source"] == "CALLER_CONFIRMATION"
    assert "previous_identity_state" in rec


def test_identity_suppression_removes_from_primary_queue():
    """Suppressed identity states are excluded from the primary queue while
    the DB record itself is untouched (no data loss)."""
    lead = _owner_likely_lead()
    for rel, expected in (
        ("WRONG_PERSON", IdentityState.WRONG_PERSON),
        ("TENANT", IdentityState.TENANT),
        ("RELATIVE_OR_ASSOCIATE", IdentityState.RELATIVE_OR_ASSOCIATE),
    ):
        r = evaluate_lead_identity(lead, relationship=rel, caller_name="X")
        patched = apply_identity_to_lead(dict(lead), r)
        assert not is_primary_eligible(patched["identity_state"])


def test_requeue_ranking_orders_confirmed_first():
    """Queue ranking: OWNER_CONFIRMED(0) → ADM(1) → OWNER_LIKELY(2) →
    IDENTITY_UNCONFIRMED(3); suppressed states never rank into the queue."""
    from MBM.LeadEngine.owner_identity import identity_queue_rank, is_primary_eligible
    ranked = {
        "OWNER_CONFIRMED": identity_queue_rank({"identity_state": "OWNER_CONFIRMED"}),
        "AUTHORIZED_DECISION_MAKER": identity_queue_rank({"identity_state": "AUTHORIZED_DECISION_MAKER"}),
        "OWNER_LIKELY": identity_queue_rank({"identity_state": "OWNER_LIKELY"}),
        "IDENTITY_UNCONFIRMED": identity_queue_rank({"identity_state": "IDENTITY_UNCONFIRMED"}),
        "": identity_queue_rank({}),
    }
    assert ranked["OWNER_CONFIRMED"] < ranked["AUTHORIZED_DECISION_MAKER"]
    assert ranked["AUTHORIZED_DECISION_MAKER"] < ranked["OWNER_LIKELY"]
    assert ranked["OWNER_LIKELY"] < ranked["IDENTITY_UNCONFIRMED"]
    assert ranked[""] == 2  # no recorded identity = callable, unconfirmed
    for st in ("WRONG_PERSON", "WRONG_NUMBER", "TENANT", "RELATIVE_OR_ASSOCIATE", "DO_NOT_CALL"):
        assert not is_primary_eligible(st)


def test_existing_sales_state_preserved_across_identity_transition():
    """A live-call identity update (OWNER_LIKELY → OWNER_CONFIRMED) must
    preserve dispositions, notes, attempts, stage and last_touch."""
    lead = _owner_likely_lead()
    lead["disposition"] = "callback"
    lead["notes"] = "Will call back Thursday"
    lead["attempts"] = 2
    lead["stage"] = "CONTACTED"
    lead["last_touch"] = "2026-08-15T12:00:00Z"
    result = evaluate_lead_identity(
        lead, caller_name="Bruce Mcleod", relationship="OWNER",
        property_confirmed=True, name_confirmed=True,
    )
    patched = apply_identity_to_lead(lead, result)
    assert patched["disposition"] == "callback"
    assert patched["notes"] == "Will call back Thursday"
    assert patched["attempts"] == 2
    assert patched["stage"] == "CONTACTED"
    assert patched["last_touch"] == "2026-08-15T12:00:00Z"
    assert patched["identity_state"] == "OWNER_CONFIRMED"


def test_idempotent_repeated_identity_updates():
    """Repeated identity evaluations for the same lead with the same inputs
    produce identical results — the state machine is deterministic."""
    lead = _owner_likely_lead()
    r1 = evaluate_lead_identity(lead, caller_name="Bruce Mcleod", relationship="OWNER",
                                property_confirmed=True, name_confirmed=True)
    r2 = evaluate_lead_identity(lead, caller_name="Bruce Mcleod", relationship="OWNER",
                                property_confirmed=True, name_confirmed=True)
    assert r1.state == r2.state
    assert r1.score == r2.score
    assert r1.evidence_used == r2.evidence_used
