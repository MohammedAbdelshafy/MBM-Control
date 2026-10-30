"""Provider gateway must preflight before executing external operations."""

import pytest

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
