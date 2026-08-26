from MBM.LeadEngine.airtable_sync import _lead_to_fields


def test_airtable_mirror_contains_stable_identity_and_safe_fields():
    lead = {
        "id": "NPI-123",
        "company": "Example Clinic",
        "contact": "Jane Doe",
        "phone": "+12025550123",
        "segment": "HEALTHCARE_CLINIC",
        "script_id": "clinic_v1",
        "sales_strategy": "Direct pitch",
        "skip_trace_status": "VERIFIED",
        "phone_status": "VERIFIED_PRIMARY",
        "phone_verified_at": "2026-08-26T12:00:00Z",
        "contact_identity_verified": True,
        "dnc": False,
        "suppressed": False,
    }
    fields = _lead_to_fields(lead)
    assert fields["Lead ID"] == "NPI-123"
    assert fields["Business Name"] == "Example Clinic"
    assert fields["Phone Status"] == "VERIFIED_PRIMARY"
    assert fields["Contact Verified"] is True
    assert fields["DNC"] is False
    assert fields["Suppressed"] is False


def test_airtable_never_creates_callable_field():
    lead = {"id": "NPI-124", "company": "Example", "phone": "+12025550124"}
    fields = _lead_to_fields(lead)
    assert "callable" not in fields
    assert "CALL_READY" not in fields
