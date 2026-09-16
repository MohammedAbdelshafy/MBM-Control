import pytest
from datetime import datetime, timedelta, timezone
from MBM.LeadEngine.creator_qualification import CreatorRecord, qualify_creator

def test_creator_valid_20k():
    creator = CreatorRecord(
        creator_id="C1",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator",
        audience_count=20000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "qualified"
    
def test_creator_valid_over_20k():
    creator = CreatorRecord(
        creator_id="C2",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator2",
        audience_count=50000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator2/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "qualified"

def test_creator_invalid_19999():
    creator = CreatorRecord(
        creator_id="C3",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator3",
        audience_count=19999,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator3/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "below 20,000" in result.rejection_reason

def test_creator_missing_evidence():
    creator = CreatorRecord(
        creator_id="C4",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator4",
        audience_count=25000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "Missing or malformed evidence" in result.rejection_reason

def test_creator_malformed_evidence():
    creator = CreatorRecord(
        creator_id="C4b",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator4",
        audience_count=25000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="not-a-url",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "Missing or malformed evidence" in result.rejection_reason

def test_creator_stale_evidence():
    stale_date = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    creator = CreatorRecord(
        creator_id="C5",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator5",
        audience_count=25000,
        audience_type="subscribers",
        audience_snapshot_at=stale_date,
        evidence_url="https://youtube.com/@somecreator5/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "Stale evidence" in result.rejection_reason

def test_creator_missing_count():
    creator = CreatorRecord(
        creator_id="C6",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator6",
        audience_count=None,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator6/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "Malformed audience count" in result.rejection_reason

def test_creator_malformed_profile():
    creator = CreatorRecord(
        creator_id="C7",
        platform="youtube",
        profile_url="badurl",
        audience_count=25000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator7/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="source_123"
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "profile" in result.rejection_reason

def test_creator_invalid_provenance():
    creator = CreatorRecord(
        creator_id="C8",
        platform="youtube",
        profile_url="https://youtube.com/@somecreator8",
        audience_count=25000,
        audience_type="subscribers",
        audience_snapshot_at=datetime.now(timezone.utc).isoformat(),
        evidence_url="https://youtube.com/@somecreator8/about",
        evidence_source="direct",
        niche="tech",
        contact_path="email",
        outreach_status="pending",
        provenance_key="abc" # too short
    )
    result = qualify_creator(creator)
    assert result.state == "rejected"
    assert "provenance" in result.rejection_reason
