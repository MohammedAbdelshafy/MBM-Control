"""Provider fallback router contracts."""

import pytest
from datetime import datetime, timedelta, timezone

from MBM.LeadEngine.connectors.provider_router import (
    ProviderCandidate,
    ProviderRouteStatus,
    route_provider,
)


def candidate(provider, *, capabilities=("people_search",), priority=100,
              credits=0, cost=0, available=True, approved=False,
              approval_reference=None, approved_cap=None,
              contact_access=False, contact_approved=False,
              balance_verified=True):
    return ProviderCandidate(
        provider=provider,
        capabilities=frozenset(capabilities),
        priority=priority,
        credits_available=credits,
        estimated_credits=cost,
        available=available,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_cap,
        personal_contact_access=contact_access,
        contact_data_approved=contact_approved,
        balance_verified=balance_verified,
    )


def test_exhausted_primary_provider_falls_back_to_next_zero_cost_compatible_provider():
    decision = route_provider(
        required_capability="people_search",
        candidates=[
            candidate("APOLLO", priority=10, credits=0, cost=1),
            candidate("VIBE_PROSPECTING", priority=20, credits=0, cost=0),
            candidate("CLAY", priority=30, credits=10, cost=1),
        ],
    )

    assert decision.status is ProviderRouteStatus.READY
    assert decision.selected.provider == "VIBE_PROSPECTING"
    assert [item.provider for item in decision.skipped] == ["APOLLO"]


def test_fallback_does_not_spend_second_provider_credits_without_prior_approval():
    decision = route_provider(
        required_capability="company_search",
        candidates=[
            candidate("APOLLO", capabilities=("company_search",), priority=10, credits=0, cost=1),
            candidate("CLAY", capabilities=("company_search",), priority=20, credits=100, cost=2),
        ],
    )

    assert decision.status is ProviderRouteStatus.NEEDS_APPROVAL
    assert decision.selected is None
    assert decision.approval_required is not None
    assert decision.approval_required.provider == "CLAY"


def test_fallback_uses_paid_provider_when_explicit_prior_approval_covers_it():
    decision = route_provider(
        required_capability="company_search",
        candidates=[
            candidate("APOLLO", capabilities=("company_search",), priority=10, credits=0, cost=1),
            candidate(
                "CLAY", capabilities=("company_search",), priority=20,
                credits=20, cost=2, approved=True,
                approval_reference="APPROVED-CLAY-SEARCH",
                approved_cap=5,
            ),
        ],
    )

    assert decision.status is ProviderRouteStatus.READY
    assert decision.selected.provider == "CLAY"
    assert decision.authorization.approval_reference == "APPROVED-CLAY-SEARCH"


def test_unavailable_provider_is_skipped_and_next_available_provider_is_selected():
    decision = route_provider(
        required_capability="company_search",
        candidates=[
            candidate("APOLLO", capabilities=("company_search",), priority=1, available=False),
            candidate("VIBE_PROSPECTING", capabilities=("company_search",), priority=2),
        ],
    )

    assert decision.status is ProviderRouteStatus.READY
    assert decision.selected.provider == "VIBE_PROSPECTING"
    assert decision.skipped[0].reason == "UNAVAILABLE"


def test_provider_without_required_capability_is_never_used_as_fallback():
    decision = route_provider(
        required_capability="direct_dial_enrichment",
        candidates=[
            candidate("APOLLO", capabilities=("people_search",), priority=1, credits=0),
            candidate("VIBE_PROSPECTING", capabilities=("company_search",), priority=2),
        ],
    )

    assert decision.status is ProviderRouteStatus.NO_COMPATIBLE_PROVIDER
    assert decision.selected is None


def test_contact_data_approval_is_preserved_across_fallback():
    decision = route_provider(
        required_capability="work_email_enrichment",
        candidates=[
            candidate(
                "APOLLO", capabilities=("work_email_enrichment",), priority=1,
                credits=0, cost=1, contact_access=True,
            ),
            candidate(
                "CLAY", capabilities=("work_email_enrichment",), priority=2,
                credits=20, cost=0, contact_access=True,
            ),
        ],
    )

    assert decision.status is ProviderRouteStatus.NEEDS_APPROVAL
    assert decision.selected is None
    assert decision.approval_required.provider == "CLAY"


def test_no_compatible_available_provider_returns_exhausted_with_reasons():
    decision = route_provider(
        required_capability="company_search",
        candidates=[
            candidate("APOLLO", capabilities=("company_search",), priority=1, credits=0, cost=1),
            candidate("CLAY", capabilities=("company_search",), priority=2, available=False),
        ],
    )

    assert decision.status is ProviderRouteStatus.NO_PROVIDER_AVAILABLE
    assert decision.selected is None
    assert {item.reason for item in decision.skipped} == {
        "INSUFFICIENT_CREDITS", "UNAVAILABLE"
    }


def test_router_rejects_unreviewed_provider_instead_of_trying_it():
    with pytest.raises(ValueError, match="unsupported provider"):
        route_provider(
            required_capability="company_search",
            candidates=[
                candidate("UNKNOWN_SCRAPER", capabilities=("company_search",)),
            ],
        )


def test_paid_operation_is_blocked_when_provider_balance_is_unverified_even_with_approval():
    decision = route_provider(
        required_capability="company_search",
        candidates=[
            candidate(
                "APOLLO", capabilities=("company_search",), priority=1,
                credits=100, cost=2, approved=True,
                approval_reference="APPROVED-SEARCH", approved_cap=5,
                balance_verified=False,
            )
        ],
    )

    assert decision.status is ProviderRouteStatus.NO_PROVIDER_AVAILABLE
    assert decision.selected is None
    assert decision.skipped[0].reason == "BALANCE_UNVERIFIED"


def test_zero_credit_operation_remains_available_without_a_meter():
    decision = route_provider(
        required_capability="people_search",
        candidates=[candidate(
            "CLAY", credits=0, cost=0, balance_verified=False,
        )],
    )

    assert decision.status is ProviderRouteStatus.READY
    assert decision.selected.provider == "CLAY"


def test_paid_operation_rejects_a_previously_verified_but_expired_snapshot():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    decision = route_provider(
        required_capability="company_search",
        candidates=[candidate(
            "APOLLO", capabilities=("company_search",), priority=1,
            credits=100, cost=2, approved=True,
            approval_reference="APPROVED-STALE", approved_cap=2,
            balance_verified=True,
            balance_observed_at=now - timedelta(minutes=5),
        )],
        now=now,
    )

    assert decision.status is ProviderRouteStatus.NO_PROVIDER_AVAILABLE
    assert decision.skipped[0].reason == "BALANCE_STALE"
