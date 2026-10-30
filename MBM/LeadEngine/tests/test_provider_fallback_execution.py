"""Runtime provider fallback contracts."""

import pytest

from MBM.LeadEngine.connectors.provider_router import (
    ProviderCandidate,
    ProviderRouteStatus,
    ProviderCreditsExhausted,
    ProviderTemporarilyUnavailable,
    execute_with_provider_fallback,
)


def candidate(provider, *, priority, credits=0, cost=0, approved=False,
              approval_reference=None, approved_cap=None):
    return ProviderCandidate(
        provider=provider,
        capabilities=frozenset({"people_search"}),
        priority=priority,
        credits_available=credits,
        estimated_credits=cost,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_cap,
    )


def test_runtime_credit_exhaustion_retries_next_compatible_provider():
    calls = []

    def apollo():
        calls.append("APOLLO")
        raise ProviderCreditsExhausted("Apollo reports no credits remaining")

    def vibe():
        calls.append("VIBE_PROSPECTING")
        return {"companies": ["verified-company"]}

    result = execute_with_provider_fallback(
        required_capability="people_search",
        candidates=[
            candidate(
                "APOLLO", priority=1, credits=5, cost=1,
                approved=True, approval_reference="APPROVAL-APOLLO-1",
                approved_cap=2,
            ),
            candidate("VIBE_PROSPECTING", priority=2, credits=0, cost=0),
        ],
        operations={"APOLLO": apollo, "VIBE_PROSPECTING": vibe},
    )

    assert result.status is ProviderRouteStatus.READY
    assert result.provider == "VIBE_PROSPECTING"
    assert result.result == {"companies": ["verified-company"]}
    assert calls == ["APOLLO", "VIBE_PROSPECTING"]
    assert [(a.provider, a.outcome) for a in result.attempts] == [
        ("APOLLO", "CREDITS_EXHAUSTED"),
        ("VIBE_PROSPECTING", "SUCCESS"),
    ]


def test_temporary_provider_outage_falls_back_without_repeating_primary():
    calls = []

    def apollo():
        calls.append("APOLLO")
        raise ProviderTemporarilyUnavailable("upstream timeout before execution")

    def clay():
        calls.append("CLAY")
        return {"accounts": 3}

    result = execute_with_provider_fallback(
        required_capability="people_search",
        candidates=[
            candidate(
                "APOLLO", priority=1, credits=5, cost=1,
                approved=True, approval_reference="APPROVAL-APOLLO-2",
                approved_cap=2,
            ),
            candidate("CLAY", priority=2, credits=0, cost=0),
        ],
        operations={"APOLLO": apollo, "CLAY": clay},
    )

    assert result.provider == "CLAY"
    assert calls == ["APOLLO", "CLAY"]
    assert result.attempts[0].outcome == "TEMPORARILY_UNAVAILABLE"


def test_fallback_does_not_retry_ambiguous_provider_errors():
    calls = []

    def apollo():
        calls.append("APOLLO")
        raise RuntimeError("connection lost after request; outcome unknown")

    def vibe():
        calls.append("VIBE_PROSPECTING")
        return {"companies": []}

    with pytest.raises(RuntimeError, match="outcome unknown"):
        execute_with_provider_fallback(
            required_capability="people_search",
            candidates=[
                candidate(
                    "APOLLO", priority=1, credits=5, cost=1,
                    approved=True, approval_reference="APPROVAL-APOLLO-3",
                    approved_cap=2,
                ),
                candidate("VIBE_PROSPECTING", priority=2, credits=0, cost=0),
            ],
            operations={"APOLLO": apollo, "VIBE_PROSPECTING": vibe},
        )

    assert calls == ["APOLLO"]


def test_runtime_exhaustion_never_spends_unapproved_paid_fallback():
    calls = []

    def apollo():
        calls.append("APOLLO")
        raise ProviderCreditsExhausted("quota exhausted")

    def clay():
        calls.append("CLAY")
        return {"accounts": 1}

    result = execute_with_provider_fallback(
        required_capability="people_search",
        candidates=[
            candidate(
                "APOLLO", priority=1, credits=5, cost=1,
                approved=True, approval_reference="APPROVAL-APOLLO-4",
                approved_cap=2,
            ),
            candidate("CLAY", priority=2, credits=20, cost=2),
        ],
        operations={"APOLLO": apollo, "CLAY": clay},
    )

    assert result.status is ProviderRouteStatus.NEEDS_APPROVAL
    assert result.provider is None
    assert result.approval_required.provider == "CLAY"
    assert calls == ["APOLLO"]


def test_missing_provider_adapter_is_skipped_without_network_call():
    result = execute_with_provider_fallback(
        required_capability="people_search",
        candidates=[
            candidate("APOLLO", priority=1, credits=0, cost=0),
            candidate("VIBE_PROSPECTING", priority=2, credits=0, cost=0),
        ],
        operations={"VIBE_PROSPECTING": lambda: {"count": 1}},
    )

    assert result.provider == "VIBE_PROSPECTING"
    assert result.attempts[0].outcome == "ADAPTER_NOT_CONFIGURED"
