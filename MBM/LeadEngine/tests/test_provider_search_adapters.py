"""Provider-specific acquisition search adapters must honor cost and data gates."""

import json
from datetime import datetime, timezone

import pytest

from MBM.LeadEngine.connectors.provider_search_adapters import (
    fetch_explorium_businesses,
    fetch_explorium_prospects,
    search_apollo_organizations,
    search_apollo_people,
)
from MBM.LeadEngine.connectors.usage_gate import ProviderBudgetDenied


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def apollo_meter_payload():
    return {
        "credit_usage_stats": {
            "lead_credit": {"limit": 80, "consumed": 30, "left_over": 50}
        },
        "current_credit_cycle": {
            "start_date": "2026-10-30T00:00:00Z",
            "end_date": "2026-11-30T00:00:00Z",
        },
    }


def test_apollo_organization_search_spends_one_approved_credit_per_page():
    now = datetime.now(timezone.utc)
    seen = []

    def opener(request, timeout):
        body = request.data.decode("utf-8") if request.data else None
        seen.append({
            "url": request.full_url,
            "method": request.get_method(),
            "headers": {key.lower(): value for key, value in request.header_items()},
            "body": json.loads(body) if body else None,
            "timeout": timeout,
        })
        if request.full_url.endswith("/usage_stats/credit_usage_stats"):
            return FakeResponse(apollo_meter_payload())
        return FakeResponse({
            "organizations": [{"id": "org_1", "name": "Summit Dental", "website_url": "summit.test"}],
            "pagination": {"page": 1, "per_page": 25, "total_entries": 1},
        })

    result = search_apollo_organizations(
        filters={"q_organization_name": "dental", "organization_locations": ["texas"]},
        page=1,
        per_page=25,
        api_key="apollo-secret",
        approved=True,
        approval_reference="APPROVED-APOLLO-ORG-SEARCH",
        approved_max_credits=1,
        now=now,
        opener=opener,
    )

    assert result.provider == "APOLLO"
    assert result.operation == "organization_search"
    assert result.estimated_credits == 1
    assert result.records[0]["id"] == "org_1"
    assert result.total_results == 1
    assert len(seen) == 2
    assert seen[1]["url"] == "https://api.apollo.io/api/v1/mixed_companies/search"
    assert seen[1]["body"]["page"] == 1
    assert seen[1]["body"]["per_page"] == 25
    assert seen[1]["headers"]["x-api-key"] == "apollo-secret"
    assert "apollo-secret" not in seen[1]["url"]


def test_apollo_organization_search_rejects_more_than_one_page_or_unapproved_spend():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="per_page"):
        search_apollo_organizations(
            filters={"q_organization_name": "dental"},
            per_page=101,
            api_key="apollo-secret",
            approved=True,
            approval_reference="APPROVED",
            approved_max_credits=1,
            now=now,
            opener=lambda request, timeout: pytest.fail("must not call provider"),
        )

    calls = []
    with pytest.raises(ProviderBudgetDenied, match="explicit approval"):
        search_apollo_organizations(
            filters={"q_organization_name": "dental"},
            api_key="apollo-secret",
            approved=False,
            approval_reference=None,
            approved_max_credits=1,
            now=now,
            opener=lambda request, timeout: calls.append(request.full_url) or FakeResponse(
                apollo_meter_payload()
            ),
        )
    assert calls == []


def test_apollo_people_search_is_zero_credit_but_requires_contact_data_approval():
    now = datetime.now(timezone.utc)
    seen = []

    def opener(request, timeout):
        seen.append(request.full_url)
        return FakeResponse({
            "people": [{"id": "person_1", "name": "Riley Owner", "title": "Owner"}],
            "total_entries": 1,
        })

    with pytest.raises(ProviderBudgetDenied, match="contact-data approval"):
        search_apollo_people(
            filters={"person_titles": ["owner"], "organization_locations": ["texas"]},
            api_key="apollo-secret",
            contact_data_approved=False,
            opener=opener,
        )
    assert seen == []

    result = search_apollo_people(
        filters={"person_titles": ["owner"], "organization_locations": ["texas"]},
        api_key="apollo-secret",
        contact_data_approved=True,
        approval_reference="APPROVED-APOLLO-PEOPLE-SEARCH",
        opener=opener,
    )
    assert result.estimated_credits == 0
    assert result.records[0]["name"] == "Riley Owner"
    assert seen == ["https://api.apollo.io/api/v1/mixed_people/api_search"]


def test_explorium_business_fetch_requires_live_meter_and_fixed_approved_ceiling():
    now = datetime.now(timezone.utc)
    seen = []

    def opener(request, timeout):
        body = request.data.decode("utf-8") if request.data else None
        seen.append({
            "url": request.full_url,
            "method": request.get_method(),
            "headers": {key.lower(): value for key, value in request.header_items()},
            "body": json.loads(body) if body else None,
        })
        if request.full_url.endswith("/credits"):
            return FakeResponse({"allocated_credits": 1000, "remaining_credits": 745})
        return FakeResponse({"businesses": [{"business_id": "biz_1", "name": "Northstar HVAC"}]})

    result = fetch_explorium_businesses(
        filters={"country_code": {"values": ["us"]}, "company_size": {"values": ["11-50"]}},
        size=20,
        page_size=20,
        api_key="explorium-secret",
        approved=True,
        approval_reference="APPROVED-EXPLORIUM-BUSINESSES",
        approved_max_credits=20,
        now=now,
        opener=opener,
    )

    assert result.provider == "VIBE_PROSPECTING"
    assert result.operation == "business_fetch"
    assert result.estimated_credits is None
    assert result.approved_max_credits == 20
    assert result.records[0]["business_id"] == "biz_1"
    assert seen[1]["url"] == "https://api.explorium.ai/v1/businesses"
    assert seen[1]["body"]["size"] == 20
    assert seen[1]["body"]["page_size"] == 20
    assert seen[1]["body"]["filters"]["country_code"]["values"] == ["us"]
    assert seen[1]["headers"]["api_key"] == "explorium-secret"


def test_explorium_prospect_fetch_requires_contact_data_approval_before_fetch():
    now = datetime.now(timezone.utc)
    calls = []

    with pytest.raises(ProviderBudgetDenied, match="contact-data approval"):
        fetch_explorium_prospects(
            filters={"company_country_code": {"values": ["us"]}},
            size=10,
            page_size=10,
            api_key="explorium-secret",
            approved=True,
            approval_reference="APPROVED-PROSPECTS",
            approved_max_credits=10,
            contact_data_approved=False,
            now=now,
            opener=lambda request, timeout: calls.append(request.full_url) or FakeResponse({
                "allocated_credits": 1000, "remaining_credits": 900
            }),
        )
    assert calls == []


def test_explorium_fetch_rejects_unbounded_or_invalid_page_sizes_without_network():
    with pytest.raises(ValueError, match="size"):
        fetch_explorium_businesses(
            filters={"country_code": {"values": ["us"]}},
            size=10001,
            page_size=100,
            api_key="explorium-secret",
            approved=True,
            approval_reference="APPROVED",
            approved_max_credits=100,
            opener=lambda request, timeout: pytest.fail("must not call provider"),
        )

    with pytest.raises(ValueError, match="page_size"):
        fetch_explorium_prospects(
            filters={"company_country_code": {"values": ["us"]}},
            size=10,
            page_size=101,
            api_key="explorium-secret",
            approved=True,
            approval_reference="APPROVED",
            approved_max_credits=10,
            contact_data_approved=True,
            opener=lambda request, timeout: pytest.fail("must not call provider"),
        )


def test_search_adapters_reject_non_mapping_filters_without_network():
    with pytest.raises(ValueError, match="filters"):
        search_apollo_people(
            filters=["not", "a", "mapping"],
            api_key="apollo-secret",
            contact_data_approved=True,
            opener=lambda request, timeout: pytest.fail("must not call provider"),
        )

    with pytest.raises(ValueError, match="filters"):
        fetch_explorium_businesses(
            filters=None,
            size=10,
            page_size=10,
            api_key="explorium-secret",
            approved=True,
            approval_reference="APPROVED",
            approved_max_credits=10,
            opener=lambda request, timeout: pytest.fail("must not call provider"),
        )
