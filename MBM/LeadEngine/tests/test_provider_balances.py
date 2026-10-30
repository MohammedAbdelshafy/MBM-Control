"""Authoritative provider balance readers and fail-closed routing contracts."""

import json
from datetime import datetime, timedelta, timezone

from MBM.LeadEngine.connectors.provider_adapters import (
    BalanceStatus,
    apply_provider_balance,
    read_apollo_balance,
    read_explorium_balance,
    read_provider_balance,
)
from MBM.LeadEngine.connectors.provider_router import (
    ProviderCandidate,
    ProviderRouteStatus,
    route_provider,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_apollo_balance_uses_selected_credit_pool_and_valid_billing_cycle():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    payload = {
        "credit_usage_stats": {
            "lead_credit": {"limit": 80, "consumed": 30, "left_over": 50},
            "direct_dial_credit": {"limit": 160, "consumed": 100, "left_over": 60},
        },
        "current_credit_cycle": {
            "start_date": "2026-10-30T00:00:00Z",
            "end_date": "2026-11-30T00:00:00Z",
        },
    }
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen["timeout"] = timeout
        return FakeResponse(payload)

    result = read_apollo_balance(
        "secret-token",
        credit_pool="direct_dial_credit",
        now=now,
        opener=opener,
    )

    assert result.status is BalanceStatus.VERIFIED
    assert result.credits_remaining == 60
    assert result.credits_allocated == 160
    assert result.credit_pool == "direct_dial_credit"
    assert seen["url"] == "https://api.apollo.io/api/v1/usage_stats/credit_usage_stats"
    assert seen["method"] == "POST"
    assert seen["headers"]["x-api-key"] == "secret-token"
    assert "secret-token" not in seen["url"]


def test_apollo_expired_billing_cycle_is_stale_even_when_credits_remain():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    result = read_apollo_balance(
        "secret-token",
        credit_pool="lead_credit",
        now=now,
        opener=lambda request, timeout: FakeResponse({
            "credit_usage_stats": {
                "lead_credit": {"limit": 80, "consumed": 20, "left_over": 60}
            },
            "current_credit_cycle": {
                "start_date": "2026-09-30T00:00:00Z",
                "end_date": "2026-10-30T00:00:00Z",
            },
        }),
    )

    assert result.status is BalanceStatus.STALE
    assert result.credits_remaining == 60
    assert not result.is_authoritative_for_paid_work(now=now)


def test_apollo_missing_cycle_or_requested_pool_never_becomes_verified():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    no_cycle = read_apollo_balance(
        "secret-token",
        credit_pool="lead_credit",
        now=now,
        opener=lambda request, timeout: FakeResponse({
            "credit_usage_stats": {
                "lead_credit": {"limit": 80, "consumed": 20, "left_over": 60}
            }
        }),
    )
    no_pool = read_apollo_balance(
        "secret-token",
        credit_pool="phone_reveal_credit",
        now=now,
        opener=lambda request, timeout: FakeResponse({
            "credit_usage_stats": {
                "lead_credit": {"limit": 80, "consumed": 20, "left_over": 60}
            },
            "current_credit_cycle": {
                "start_date": "2026-10-30T00:00:00Z",
                "end_date": "2026-11-30T00:00:00Z",
            },
        }),
    )

    assert no_cycle.status is BalanceStatus.UNKNOWN
    assert no_pool.status is BalanceStatus.UNKNOWN


def test_explorium_meter_uses_live_account_balance_endpoint():
    seen = {}
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse({"allocated_credits": 1000, "remaining_credits": 745})

    result = read_explorium_balance("explorium-secret", now=now, opener=opener)

    assert result.status is BalanceStatus.VERIFIED
    assert result.credits_allocated == 1000
    assert result.credits_remaining == 745
    assert seen["url"] == "https://api.explorium.ai/v1/credits"
    assert seen["method"] == "GET"
    assert seen["headers"]["api_key"] == "explorium-secret"
    assert "explorium-secret" not in seen["url"]


def test_explorium_invalid_meter_payload_is_not_treated_as_zero_cost_or_free_credits():
    result = read_explorium_balance(
        "explorium-secret",
        now=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        opener=lambda request, timeout: FakeResponse({
            "allocated_credits": "unknown",
            "remaining_credits": None,
        }),
    )

    assert result.status is BalanceStatus.UNKNOWN
    assert result.credits_remaining is None


def test_clay_balance_stays_unknown_without_authoritative_meter_endpoint():
    result = read_provider_balance("CLAY", api_key="clay-secret")

    assert result.status is BalanceStatus.UNKNOWN
    assert result.credits_remaining is None
    assert "dashboard" in result.detail.lower()


def test_missing_credentials_return_unconfigured_without_network_call():
    def unexpected_network_call(request, timeout):
        raise AssertionError("meter call must not run without credentials")

    apollo = read_apollo_balance(
        "",
        credit_pool="lead_credit",
        opener=unexpected_network_call,
    )
    explorium = read_explorium_balance("", opener=unexpected_network_call)

    assert apollo.status is BalanceStatus.UNCONFIGURED
    assert explorium.status is BalanceStatus.UNCONFIGURED


def test_old_snapshot_is_not_applied_to_paid_provider_candidate():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    candidate = ProviderCandidate(
        provider="VIBE_PROSPECTING",
        capabilities=frozenset({"company_search"}),
        priority=1,
        credits_available=0,
        estimated_credits=5,
    )
    stale = read_explorium_balance(
        "explorium-secret",
        now=now - timedelta(minutes=10),
        opener=lambda request, timeout: FakeResponse({
            "allocated_credits": 1000,
            "remaining_credits": 900,
        }),
    )

    updated = apply_provider_balance(candidate, stale, now=now, max_age_seconds=60)
    decision = route_provider(
        required_capability="company_search",
        candidates=[updated],
    )

    assert updated.balance_verified is False
    assert updated.credits_available == 0
    assert decision.status is ProviderRouteStatus.NO_PROVIDER_AVAILABLE
    assert decision.skipped[0].reason == "BALANCE_UNVERIFIED"


def test_zero_credit_operation_can_use_meterless_provider_but_contact_gate_remains():
    candidate = ProviderCandidate(
        provider="CLAY",
        capabilities=frozenset({"people_search"}),
        priority=1,
        credits_available=0,
        estimated_credits=0,
        balance_verified=False,
    )

    decision = route_provider(
        required_capability="people_search",
        candidates=[candidate],
    )

    assert decision.status is ProviderRouteStatus.READY
    assert decision.selected.provider == "CLAY"

