import pytest
from datetime import datetime, timezone, timedelta
from MBM.LeadEngine.canonical_lead_schema import CanonicalCreator

def test_audience_19999_rejected():
    creator = CanonicalCreator(
        creator_id="test1",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=19999,
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "AUDIENCE_BELOW_THRESHOLD"

def test_audience_20000_qualified():
    creator = CanonicalCreator(
        creator_id="test2",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=20000,
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is True
    assert creator.rejection_reason is None

def test_audience_20001_qualified():
    creator = CanonicalCreator(
        creator_id="test3",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=20001,
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is True

def test_missing_evidence_fails_closed():
    creator = CanonicalCreator(
        creator_id="test4",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url=None
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "MISSING_EVIDENCE"

    creator_empty = CanonicalCreator(
        creator_id="test5",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url="   "
    )
    assert creator_empty.validate_creator_gate() is False

def test_malformed_evidence_fails_closed():
    # If evidence_url is just whitespace or unresolvable
    creator = CanonicalCreator(
        creator_id="test6",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url="\t\n"
    )
    assert creator.validate_creator_gate() is False

def test_stale_evidence_fails_closed():
    # Freshness semantics: if snapshot is older than 30 days, fail closed.
    old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    creator = CanonicalCreator(
        creator_id="test7",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url="https://example.com/proof",
        audience_snapshot_at=old_date
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "STALE_EVIDENCE"

def test_missing_audience_count():
    # Python defaults to 0 based on dataclass, which is < 20000
    creator = CanonicalCreator(
        creator_id="test8",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "AUDIENCE_BELOW_THRESHOLD"

def test_malformed_audience_count():
    creator = CanonicalCreator(
        creator_id="test9",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count="twenty thousand",
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "MALFORMED_AUDIENCE_COUNT"

def test_invalid_platform_contract():
    creator = CanonicalCreator(
        creator_id="test10",
        platform="",
        profile_url="url",  # < 5 chars
        audience_count=50000,
        evidence_url="https://example.com/proof"
    )
    assert creator.validate_creator_gate() is False
    assert creator.rejection_reason == "INVALID_PLATFORM_CONTRACT"

def test_human_approval_invariant():
    creator = CanonicalCreator(
        creator_id="test11",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url="https://example.com/proof",
        outreach_status="APPROVED_BYPASS"
    )
    # Even if someone tries to inject an approved state, the gate forces it back
    assert creator.validate_creator_gate() is True
    assert creator.outreach_status == "PENDING_APPROVAL"

def test_provenance_survives_handoff():
    creator = CanonicalCreator(
        creator_id="test12",
        platform="youtube",
        profile_url="https://youtube.com/c/test",
        audience_count=50000,
        evidence_url="https://example.com/proof"
    )
    creator.validate_creator_gate()
    data = creator.to_dict()
    assert data["qualification_passed"] is True
    assert data["evidence_url"] == "https://example.com/proof"
