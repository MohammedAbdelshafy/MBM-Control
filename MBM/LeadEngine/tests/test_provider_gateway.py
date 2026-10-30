"""Provider gateway must preflight before executing external operations."""

import pytest
from datetime import datetime, timezone, timedelta

from MBM.LeadEngine.connectors.provider_gateway import (
    execute_provider_operation,
)
from MBM.LeadEngine.connectors.usage_gate import ProviderBudgetDenied


def test_denied_provider_operation_never_executes_callback():
    called = []

    with pytest.raises(ProviderBudgetDenied, match="explicit approval"):
        execute_provider_operation(
            provider="APOLLO",
            operation="PEOPLE_ENRICHMENT",
            estimated_credits=9,
            credits_available=80,
            operation_callback=lambda: called.append("called"),
        )

    assert called == []


def test_authorized_operation_executes_once_and_returns_approval_receipt():
    calls = []
    result = execute_provider_operation(
        provider="APOLLO",
        operation="PEOPLE_SEARCH",
        estimated_credits=0,
        credits_available=80,
        operation_callback=lambda: calls.append("called") or {"people": []},
    )

    assert calls == ["called"]
    assert result.result == {"people": []}
    assert result.authorization.authorized is True
    assert result.authorization.credits_ceiling == 0


def test_provider_errors_propagate_after_successful_preflight():
    def fail():
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        execute_provider_operation(
            provider="APOLLO",
            operation="PEOPLE_SEARCH",
            estimated_credits=0,
            credits_available=80,
            operation_callback=fail,
        )


def test_approved_paid_operation_still_requires_verified_provider_balance():
    calls = []
    with pytest.raises(ProviderBudgetDenied, match="authoritative provider balance"):
        execute_provider_operation(
            provider="APOLLO",
            operation="PEOPLE_ENRICHMENT",
            estimated_credits=2,
            credits_available=80,
            approved=True,
            approval_reference="APPROVED-ENRICHMENT",
            approved_max_credits=2,
            operation_callback=lambda: calls.append("called"),
        )
    assert calls == []


def test_approved_paid_operation_runs_only_after_fresh_balance_verification():
    calls = []
    result = execute_provider_operation(
        provider="APOLLO",
        operation="PEOPLE_ENRICHMENT",
        estimated_credits=2,
        credits_available=80,
        approved=True,
        approval_reference="APPROVED-ENRICHMENT",
        approved_max_credits=2,
        balance_verified=True,
        balance_observed_at=datetime.now(timezone.utc),
        operation_callback=lambda: calls.append("called") or {"enriched": 1},
    )
    assert calls == ["called"]
    assert result.result == {"enriched": 1}


def test_gateway_rejects_expired_meter_even_when_verified_flag_is_true():
    calls = []
    with pytest.raises(ProviderBudgetDenied, match="authoritative provider balance"):
        execute_provider_operation(
            provider="APOLLO",
            operation="PEOPLE_ENRICHMENT",
            estimated_credits=2,
            credits_available=80,
            approved=True,
            approval_reference="APPROVED-STALE-ENRICHMENT",
            approved_max_credits=2,
            balance_verified=True,
            balance_observed_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            operation_callback=lambda: calls.append("called"),
        )
    assert calls == []
