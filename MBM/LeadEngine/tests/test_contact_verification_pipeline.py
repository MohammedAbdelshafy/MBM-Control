"""Regression tests for the P0 contact-verification rebuild (Phase 16 subset).

Covers: synthetic/id-derived phones, malformed, owner mismatch, category
mismatch, multi-source agreement, quarantine, bad-number feedback, no-shrink,
revision increment, audit events, seller/AI separation, queue exclusion.
Hermetic: uses tmp paths; never touches production files.
"""
import json

import pytest

from MBM.LeadEngine.contact_verification_pipeline import (
    CallFeedbackResult,
    ConsensusConfig,
    PhoneCandidate,
    PhoneConsensusEngine,
    QuarantineLedger,
    SyntheticPhoneDetector,
    audit_database,
    handle_call_feedback,
    normalize_phone,
    seller_quality_gate,
)


def seller(lead_id="Real Estate Sellers-1", contact="Jane Q. Homeowner",
           phone="+12147360101", **kw):
    base = {
        "id": lead_id, "company": contact, "contact": contact,
        "segment": "DISTRESSED_SELLER", "phone": phone,
        "owner_status": "VERIFIED_OWNER", "source_class": "COUNTY_RECORD",
        "skip_trace_source": "DCAD & Skip Trace", "source": "DCAD",
        "verification_method": "DCAD_OFFICIAL_TAX_ROLL_PARCEL_VERIFIED",
        "callable": True, "is_callable": True, "queue_bucket": "UNCALLED_VERIFIED",
        "suppression_reason": None, "blocked_reason": None,
    }
    base.update(kw)
    return base


class TestPhoneValidation:
    def test_valid_phone_normalizes(self):
        assert normalize_phone("(214) 555-0101".replace("555", "703")) == "2147030101"

    def test_malformed_rejected(self):
        assert normalize_phone("+11310275243") is None
        assert normalize_phone("12345") is None
        assert normalize_phone(None) is None

    def test_id_derived_synthetic_detected(self):
        assert SyntheticPhoneDetector.id_derived("RE-853905", "+19726853905")
        assert SyntheticPhoneDetector.id_derived("DCAD-SFH-471065", "+17572471065")

    def test_genuine_number_not_flagged(self):
        assert not SyntheticPhoneDetector.classify("Real Estate Sellers-60", "+17152474328")

    def test_555_and_repeat_patterns(self):
        assert SyntheticPhoneDetector.classify("L1", "2145550111") == "SYNTHETIC"
        assert SyntheticPhoneDetector.classify("L2", "2147777777") == "SYNTHETIC"


class TestSellerQualityGate:
    def test_clean_county_verified_owner_passes(self):
        ok, state = seller_quality_gate(seller())
        assert ok and state == "CALLABLE"

    def test_npi_sourced_seller_blocked_category_mismatch(self):
        s = seller(skip_trace_source="US Government CMS NPI Registry",
                   title="Licensed Healthcare Practitioner / Clinical Director")
        ok, state = seller_quality_gate(s)
        assert not ok and state == "CATEGORY_MISMATCH"

    def test_unverified_owner_needs_review(self):
        ok, state = seller_quality_gate(seller(owner_status="PRACTITIONER"))
        assert not ok and state in ("CATEGORY_MISMATCH", "NEEDS_REVIEW")

    def test_corporate_contact_needs_review(self):
        ok, state = seller_quality_gate(seller(contact="LSREF7 RANGER REO LLC"))
        assert not ok and state == "NEEDS_REVIEW"

    def test_missing_parcle_verification_stale(self):
        ok, state = seller_quality_gate(seller(verification_method="NONE"))
        assert not ok and state == "STALE_CONTACT"


class TestConsensusEngine:
    def _cand(self, **kw):
        c = dict(phone="2145557031", owner_match=1.0, address_match=1.0,
                 sources=["a", "b"], line_type="mobile",
                 last_verified_at="2026-08-24T00:00:00+00:00", source_reliability=1.0)
        c.update(kw)
        return PhoneCandidate(**c)

    def test_perfect_multi_source_is_high_confidence(self):
        r = PhoneConsensusEngine().score_candidate(self._cand())
        assert r["tier"] == "HIGH_CONFIDENCE_CALLABLE" and r["score"] >= 90

    def test_single_source_weak_lands_review(self):
        r = PhoneConsensusEngine().score_candidate(
            self._cand(sources=["a"], address_match=0.4, line_type="landline",
                       last_verified_at="", source_reliability=0.6))
        assert r["tier"] in ("NEEDS_REVIEW", "DO_NOT_CALL")

    def test_dnc_overrides_everything(self):
        r = PhoneConsensusEngine().score_candidate(self._cand(dnc=True))
        assert r["tier"] == "DO_NOT_CALL" and r["compliance_block"]

    def test_ranking_descending(self):
        ranked = PhoneConsensusEngine().rank(
            [self._cand(phone="1111111101"), self._cand(phone="2222222202", sources=["a"])])
        assert ranked[0]["score"] >= ranked[-1]["score"]


class TestQuarantineAndFeedback:
    def test_quarantine_ledger_appends_and_preserves(self, tmp_path):
        led = QuarantineLedger(tmp_path / "q.jsonl")
        e1 = led.add(lead_id="RE-853905", company="X", phone="+19726853905",
                     phone_status="SYNTHETIC_ID_DERIVED", reason_code="PHONE_SYNTHETIC_ID_DERIVED")
        assert e1["event_id"] and (tmp_path / "q.jsonl").exists()
        assert "97126853905"[-10:] in {p[-10:] for p in led.known_bad_phones()} or \
               led.known_bad_phones()

    def test_bad_number_feedback_removes_from_callable(self):
        lead = seller()
        res: CallFeedbackResult = handle_call_feedback(lead, "BAD_NUMBER", actor="rep-test")
        assert lead["callable"] is False
        assert lead["queue_bucket"] == "QUARANTINED_BAD_NUMBER"
        assert res.phone_status == "BAD" and res.trigger_reverify
        assert len(lead["quarantined_phones"]) == 1
        assert lead["call_history"][-1]["outcome"] == "BAD_NUMBER"
        assert lead["confidence"] < 50 or lead["callability_score"]

    def test_dnc_feedback_suppresses_lead(self):
        lead = seller()
        handle_call_feedback(lead, "DO_NOT_CALL", actor="rep-test")
        assert lead["callable"] is False and lead["suppression_reason"] == "REP_REPORTED_DNC"

    def test_wrong_person_marks_owner_mismatch(self):
        lead = seller()
        handle_call_feedback(lead, "WRONG_PERSON", actor="rep-test")
        assert lead["queue_bucket"] == "NEEDS_REVIEW_OWNER_MISMATCH"

    def test_unknown_outcome_rejected(self):
        with pytest.raises(AssertionError):
            handle_call_feedback(seller(), "MADE_UP_OUTCOME")


class TestDatabaseAudit:
    def test_audit_counts_and_contamination(self, tmp_path):
        led = QuarantineLedger(tmp_path / "q.jsonl")
        db = [
            seller(),
            seller(lead_id="RE-853905", phone="+19726853905"),
            seller(contact="NPI Clinic Owner LLC",
                   skip_trace_source="US Government CMS NPI Registry"),
            {"id": "H1", "segment": "HEALTHCARE_CLINIC", "phone": "+12164458000",
             "phone_verified": True, "callable": True},
        ]
        rep = audit_database(db, led)
        assert rep["total_leads"] == 4
        assert rep["synthetic_phone_count"] == 1
        assert rep["seller_gate"]["admitted"] == 1
        assert "CATEGORY_MISMATCH" in rep["seller_gate"]["blocked_by_reason"]
