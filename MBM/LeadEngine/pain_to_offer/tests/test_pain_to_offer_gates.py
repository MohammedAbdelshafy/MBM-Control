"""Hermetic gate tests for the Pain-to-Offer contract package.

Covers the six JARVIS-mandated proofs plus duplicates, determinism,
state transitions, and contact-class separation. No network, no fixtures
from production data.
"""
from pain_to_offer.gates import (
    SuppressionList,
    call_gate,
    copy_safety,
    email_gate,
    offer_binding_gate,
    pain_gate,
)
from pain_to_offer.schema import (
    Claim,
    CompanyEvidencePack,
    ContactClass,
    ContactRecord,
    EvidenceStatus,
    PipelineState,
    SourceRef,
)
from pain_to_offer.scoring import pain_score, rank_packs
from pain_to_offer.state_machine import validate_transition
from pain_to_offer.validation import (
    contact_dedupe_key,
    is_valid_us_phone,
    practice_dedupe_key,
)


def make_pack(
    company_id="NPI-DENTAL-0001",
    pain=EvidenceStatus.LEADING_HYPOTHESIS,
    with_pain_evidence=True,
):
    pack = CompanyEvidencePack(
        company_id=company_id,
        practice_name="Bright Smile Family Dentistry",
        practice_type="general dentistry",
        address="1200 Main St",
        city="Dallas",
        state="TX",
        website="https://brightsmiledental.example",
        npi_identifier="1234567890",
        npi_source=SourceRef(
            source="CMS NPI Registry", source_url="https://npiregistry.cms.hhs.gov/",
            verification_status="VERIFIED", confidence=1.0,
        ),
        npi_retrieval_timestamp="2026-08-24T00:00:00+00:00",
        business_phone="+19725550123",
        phone_source=SourceRef(
            source="CMS NPI Registry", source_url="https://npiregistry.cms.hhs.gov/",
            verification_status="VERIFIED", confidence=0.95,
        ),
        phone_retrieval_timestamp="2026-08-24T00:00:00+00:00",
        owner_or_decision_maker="Dr. Jane Doe",
        decision_maker_role="Owner / Practitioner",
        practice_location_count=1,
        targeting_evidence=[
            Claim(claim="Practice exists in NPI registry", status=EvidenceStatus.PROVEN),
        ],
        pain_hypothesis=pain,
        pain_confidence=0.6 if pain == EvidenceStatus.LEADING_HYPOTHESIS else 0.9,
    )
    if with_pain_evidence:
        pack.pain_evidence = [
            Claim(
                claim="Front-desk surge observed during morning window",
                status=pain,
                source="Cycle-2 controlled call sample",
                source_url="repo://CYCLE_2_REVENUE_VALIDATION_REPORT.md",
                confidence=0.6,
            ),
        ]
    return pack


def make_contact(company_id="NPI-DENTAL-0001", **overrides):
    c = ContactRecord(
        contact_id="CT-0001",
        company_id=company_id,
        name="Front Desk",
        role="Office Manager",
        contact_class=ContactClass.BUSINESS_PRACTICE,
        email="frontdesk@brightsmiledental.example",
        email_source="practice website contact page",
        email_source_url="https://brightsmiledental.example/contact",
        email_verification_status="VERIFIED",
        email_verified_at="2026-08-24T01:00:00+00:00",
        phone_e164="+19725550123",
        phone_source="CMS NPI Registry",
        phone_verification_status="VERIFIED",
        phone_verified_at="2026-08-24T00:00:00+00:00",
        phone_confidence=0.95,
        campaign_eligible=True,
    )
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


CLEAN = SuppressionList()


class TestMandatedGateProofs:
    def test_identity_and_phone_but_no_pain_is_not_email_ready(self):
        pack = make_pack(with_pain_evidence=False, pain=EvidenceStatus.UNVERIFIED)
        result = email_gate(pack, make_contact(), CLEAN)
        assert not result.passed
        assert any("pain" in r.lower() or "personaliz" in r.lower() for r in result.reasons)

    def test_supported_pain_is_eligible_for_scoring(self):
        pack = make_pack(pain=EvidenceStatus.LEADING_HYPOTHESIS)
        assert pain_gate(pack).passed
        assert pain_score(pack) > 0

    def test_unverified_claim_blocked_from_copy(self):
        claim = Claim(claim="Your practice misses calls", status=EvidenceStatus.UNVERIFIED)
        allowed, text, reason = copy_safety(claim)
        assert not allowed
        assert text == ""

    def test_missing_company_id_cannot_bind_canonical_offer(self):
        pack = make_pack()
        pack.company_id = ""
        binding = offer_binding_gate(pack, "DENTAL-MCR-001")
        assert not binding.bound
        assert any("company_id" in r for r in binding.reasons)

    def test_suppressed_contact_cannot_enter_outreach(self):
        sup = SuppressionList()
        sup.add("+19725550123")
        sup.add("frontdesk@brightsmiledental.example")
        pack = make_pack()
        assert not call_gate(pack, make_contact(), sup).passed
        assert not email_gate(pack, make_contact(), sup).passed

    def test_unverified_phone_cannot_be_call_ready(self):
        pack = make_pack()
        contact = make_contact(phone_verification_status="UNVERIFIED")
        assert not call_gate(pack, contact, CLEAN).passed


class TestValidationAndDuplicates:
    def test_invalid_phone_rejected(self):
        assert not is_valid_us_phone("12345")
        assert not is_valid_us_phone("+447911123456")
        assert not is_valid_us_phone("0123456789")
        assert not is_valid_us_phone("(555) 123-4567")
        assert is_valid_us_phone("(972) 555-0123")

    def test_duplicate_businesses_share_key(self):
        a = practice_dedupe_key("Bright Smile Dental", "+19725550123")
        b = practice_dedupe_key("Bright Smile Dental PLLC", "(972) 555-0123")
        c = practice_dedupe_key("Completely Different Clinic", "")
        assert a == b
        assert a != c

    def test_duplicate_contacts_share_key(self):
        a = contact_dedupe_key("FrontDesk@BrightSmileDental.example")
        b = contact_dedupe_key("frontdesk+brightsmile@example.com" )
        same = contact_dedupe_key("frontdesk@brightsmiledental.example")
        assert a == same
        assert a != b

    def test_missing_phone_source_fails_binding(self):
        pack = make_pack()
        pack.phone_source.source = ""
        assert not offer_binding_gate(pack).bound

    def test_inferred_without_evidence_never_claims_pain(self):
        pack = make_pack(pain=EvidenceStatus.UNVERIFIED, with_pain_evidence=False)
        assert not pack.has_supported_pain()
        from pain_to_offer.gates import HEDGED_LINE, safe_outreach_claims
        claims = [Claim(claim="Your practice misses calls", status=EvidenceStatus.UNVERIFIED)]
        assert safe_outreach_claims(claims) == []
        assert HEDGED_LINE == "Potential missed-call recovery opportunity"


class TestCopySafety:
    def test_leading_hypothesis_forces_hedge(self):
        claim = Claim(claim="Your practice misses calls daily", status=EvidenceStatus.LEADING_HYPOTHESIS)
        allowed, text, _ = copy_safety(claim)
        assert not allowed
        assert text.startswith("Potential missed-call recovery opportunity")

    def test_proven_claim_allowed_verbatim(self):
        claim = Claim(claim="Practice reported missed calls in Q2 audit", status=EvidenceStatus.PROVEN)
        allowed, text, _ = copy_safety(claim)
        assert allowed and text == claim.claim

    def test_rejected_claim_blocked(self):
        claim = Claim(claim="anything", status=EvidenceStatus.REJECTED)
        allowed, _, _ = copy_safety(claim)
        assert not allowed


class TestPersonalContactsNeverOutreach:
    def test_personal_private_blocked_everywhere(self):
        pack = make_pack()
        personal = make_contact(
            contact_class=ContactClass.PERSONAL_PRIVATE,
            email="drdoe.personal@gmail.com",
        )
        assert not email_gate(pack, personal, CLEAN).passed
        assert not call_gate(pack, personal, CLEAN).passed


class TestScoringDeterminism:
    def test_same_input_same_score(self):
        packs = [make_pack(company_id=f"C{i}", pain=EvidenceStatus.PROVEN) for i in range(3)]
        scores_a = [pain_score(p) for p in packs]
        packs[1].practice_location_count = 9
        scores_b = [pain_score(p) for p in packs]
        assert scores_a == scores_b

    def test_ranking_tie_break_stable(self):
        p1 = make_pack(company_id="AAA", pain=EvidenceStatus.PROVEN)
        p2 = make_pack(company_id="BBB", pain=EvidenceStatus.PROVEN)
        ranked = rank_packs([p2, p1])
        assert [p.company_id for p, _ in ranked] == ["AAA", "BBB"]

    def test_targeting_size_never_adds_score(self):
        small = make_pack(company_id="S")
        big = make_pack(company_id="B")
        big.practice_location_count = 25
        assert pain_score(small) == pain_score(big)


class TestStateTransitions:
    def test_happy_path_legal(self):
        path = [
            PipelineState.DISCOVERED, PipelineState.RESEARCHING, PipelineState.RESEARCHED,
            PipelineState.SCORED, PipelineState.OFFER_READY, PipelineState.EMAIL_READY,
            PipelineState.CONTACTED, PipelineState.RESPONDED, PipelineState.MEETING_BOOKED,
            PipelineState.PILOT, PipelineState.WON,
        ]
        for cur, nxt in zip(path, path[1:]):
            assert validate_transition(cur, nxt).passed, f"{cur} -> {nxt}"

    def test_skip_states_illegal(self):
        assert not validate_transition(PipelineState.DISCOVERED, PipelineState.CALL_READY).passed
        assert not validate_transition(PipelineState.SCORED, PipelineState.CONTACTED).passed

    def test_suppress_and_invalid_reachable_until_terminal(self):
        for s in (PipelineState.DISCOVERED, PipelineState.OFFER_READY, PipelineState.PILOT):
            assert validate_transition(s, PipelineState.SUPPRESSED).passed
            assert validate_transition(s, PipelineState.INVALID).passed
        assert not validate_transition(PipelineState.WON, PipelineState.SUPPRESSED).passed
        assert not validate_transition(PipelineState.LOST, PipelineState.PILOT).passed
