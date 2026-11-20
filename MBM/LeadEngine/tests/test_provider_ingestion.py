"""Provider ingestion tests: provenance, contact-field gates and no writes."""

import pytest

from MBM.LeadEngine.connectors.providers import normalize_provider_record


def test_apollo_company_claims_enter_existing_evidence_envelope():
    result = normalize_provider_record(
        lead_id="B2B-001",
        provider="apollo_io",
        claims={
            "company_name": "Northstar HVAC",
            "domain": "northstar.example",
            "industry": "HVAC",
            "employee_range": "11-50",
            "email": None,
        },
        source="apollo-company-profile",
        reference="https://app.apollo.io/#/companies/example",
        observed_at="2026-10-30T20:00:00+00:00",
        confidence="HIGH",
    )

    payload = result.envelope.as_dict()
    assert payload["provider"] == "APOLLO"
    assert payload["lead_id"] == "B2B-001"
    assert payload["evidence"][0]["source"] == "apollo-company-profile"
    assert payload["evidence"][0]["reference"] == "https://app.apollo.io/#/companies/example"
    assert set(result.included_fields) == {"company_name", "domain", "industry", "employee_range"}
    assert result.withheld_contact_fields == ()


def test_person_level_contact_fields_are_withheld_by_default():
    result = normalize_provider_record(
        lead_id="CLINIC-001",
        provider="VIBE",
        claims={
            "company_name": "Example Dental",
            "public_business_phone": "+12145550101",
            "decision_maker_name": "Practice Owner",
            "email": "owner@example.test",
            "direct_dial": "+12145550102",
        },
        source="official-practice-site",
    )

    evidence_fields = {item["field"] for item in result.envelope.as_dict()["evidence"]}
    assert "company_name" in evidence_fields
    assert "public_business_phone" in evidence_fields
    assert "decision_maker_name" not in evidence_fields
    assert "email" not in evidence_fields
    assert "direct_dial" not in evidence_fields
    assert set(result.withheld_contact_fields) == {
        "decision_maker_name", "email", "direct_dial"
    }


def test_contact_authorization_is_field_specific():
    result = normalize_provider_record(
        lead_id="CLINIC-002",
        provider="CLAY",
        claims={
            "company_name": "Example Dental",
            "email": "owner@example.test",
            "mobile_phone": "+12145550102",
            "person_linkedin_url": "https://linkedin.example/in/person",
        },
        source="approved-contact-enrichment",
        approved_contact_fields={"email"},
    )

    fields = {item["field"] for item in result.envelope.as_dict()["evidence"]}
    assert "email" in fields
    assert "mobile_phone" not in fields
    assert "person_linkedin_url" not in fields
    assert set(result.withheld_contact_fields) == {"mobile_phone", "person_linkedin_url"}


def test_provider_aliases_normalize_and_unknown_providers_fail_closed():
    result = normalize_provider_record(
        lead_id="HEALTH-001",
        provider="NPPES",
        claims={"npi": "1234567890", "taxonomy": "General Practice"},
        source="cms-nppes",
    )
    assert result.envelope.provider == "CMS_NPPES"

    with pytest.raises(ValueError, match="unsupported acquisition provider"):
        normalize_provider_record(
            lead_id="LEAD-UNKNOWN",
            provider="UNREVIEWED_SCRAPER",
            claims={"company_name": "Unknown"},
            source="unverified-source",
        )


def test_provider_ingestion_requires_source_and_lead_identity():
    with pytest.raises(ValueError, match="lead_id"):
        normalize_provider_record(
            lead_id="",
            provider="APOLLO",
            claims={"company_name": "Example"},
            source="apollo",
        )

    with pytest.raises(ValueError, match="source"):
        normalize_provider_record(
            lead_id="B2B-002",
            provider="APOLLO",
            claims={"company_name": "Example"},
            source="",
        )
