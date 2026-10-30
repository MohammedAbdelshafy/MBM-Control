"""Capability-aware provider fallback routing with spend and data gates.

The router plans one provider for one operation. It can skip exhausted,
unavailable or incompatible providers automatically, but it will not cross a
credit or contact-data approval boundary. The caller must refresh balances and
execute through provider_gateway immediately before the real provider request.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

from MBM.LeadEngine.connectors.provider_gateway import execute_provider_operation

from MBM.LeadEngine.connectors.usage_gate import (
    SUPPORTED_PROVIDERS,
    ProviderBudgetAuthorization,
    ProviderBudgetDenied,
    authorize_provider_usage,
)


class ProviderCreditsExhausted(RuntimeError):
    """The provider definitively rejected the request because its quota is exhausted."""


class ProviderTemporarilyUnavailable(RuntimeError):
    """The provider confirms the request did not execute and may be retried elsewhere."""


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    outcome: str
    detail: str


@dataclass(frozen=True)
class ProviderFallbackExecutionResult:
    status: "ProviderRouteStatus"
    provider: Optional[str]
    result: Any
    attempts: tuple[ProviderAttempt, ...]
    approval_required: Optional["ProviderCandidate"] = None
    approval_reason: Optional[str] = None


class ProviderRouteStatus(str, Enum):
    READY = "READY"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    NO_COMPATIBLE_PROVIDER = "NO_COMPATIBLE_PROVIDER"
    NO_PROVIDER_AVAILABLE = "NO_PROVIDER_AVAILABLE"


@dataclass(frozen=True)
class ProviderCandidate:
    provider: str
    capabilities: frozenset[str]
    priority: int
    credits_available: int
    estimated_credits: Optional[int]
    available: bool = True
    approved: bool = False
    approval_reference: Optional[str] = None
    approved_max_credits: Optional[int] = None
    personal_contact_access: bool = False
    contact_data_approved: bool = False
    quality_checks: Optional[Mapping[str, bool]] = None
    agent_policy_id: Optional[str] = None
    daily_budget_limit: Optional[int] = None
    credits_spent_today: int = 0


@dataclass(frozen=True)
class ProviderSkip:
    provider: str
    reason: str
    detail: str


@dataclass(frozen=True)
class ProviderRouteDecision:
    status: ProviderRouteStatus
    selected: Optional[ProviderCandidate]
    authorization: Optional[ProviderBudgetAuthorization]
    skipped: tuple[ProviderSkip, ...]
    approval_required: Optional[ProviderCandidate] = None
    approval_reason: Optional[str] = None


def route_provider(
    *,
    required_capability: str,
    candidates: Sequence[ProviderCandidate],
) -> ProviderRouteDecision:
    """Choose the highest-priority viable provider for a required capability.

    Candidates are explicit provider configuration supplied by the calling
    workflow. Credit balances and cost estimates must be refreshed for the
    requested operation, not copied from a previous run.
    """
    capability = str(required_capability or "").strip()
    if not capability:
        raise ValueError("required_capability is required")

    for candidate in candidates:
        provider_name = str(candidate.provider or "").strip().upper()
        if provider_name not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported provider: {provider_name or 'UNKNOWN'}")

    compatible = [
        candidate for candidate in candidates
        if capability in candidate.capabilities
    ]
    if not compatible:
        return ProviderRouteDecision(
            status=ProviderRouteStatus.NO_COMPATIBLE_PROVIDER,
            selected=None,
            authorization=None,
            skipped=(),
        )

    ordered = sorted(compatible, key=lambda item: item.priority)
    skipped: list[ProviderSkip] = []
    approval_candidate: Optional[ProviderCandidate] = None
    approval_reason: Optional[str] = None

    for candidate in ordered:
        provider = str(candidate.provider or "").strip().upper()
        if not candidate.available:
            skipped.append(ProviderSkip(
                provider=provider,
                reason="UNAVAILABLE",
                detail="Provider is disabled, unavailable or in a cooldown window.",
            ))
            continue

        if (
            candidate.estimated_credits is not None
            and candidate.estimated_credits > candidate.credits_available
        ):
            skipped.append(ProviderSkip(
                provider=provider,
                reason="INSUFFICIENT_CREDITS",
                detail=(
                    f"Estimated cost {candidate.estimated_credits} exceeds "
                    f"reported balance {candidate.credits_available}."
                ),
            ))
            continue

        try:
            authorization = authorize_provider_usage(
                provider=provider,
                operation=capability,
                estimated_credits=candidate.estimated_credits,
                credits_available=candidate.credits_available,
                approved=candidate.approved,
                approval_reference=candidate.approval_reference,
                approved_max_credits=candidate.approved_max_credits,
                personal_contact_access=candidate.personal_contact_access,
                contact_data_approved=candidate.contact_data_approved,
                quality_checks=candidate.quality_checks,
                agent_policy_id=candidate.agent_policy_id,
                daily_budget_limit=candidate.daily_budget_limit,
                credits_spent_today=candidate.credits_spent_today,
            )
        except ProviderBudgetDenied as exc:
            detail = str(exc)
            is_approval_boundary = any(
                marker in detail.lower()
                for marker in (
                    "explicit approval",
                    "approval reference",
                    "contact-data approval",
                    "approved known upper bound",
                )
            )
            if is_approval_boundary and approval_candidate is None:
                approval_candidate = candidate
                approval_reason = detail
            skipped.append(ProviderSkip(
                provider=provider,
                reason="APPROVAL_REQUIRED" if is_approval_boundary else "BUDGET_BLOCKED",
                detail=detail,
            ))
            continue
        except ValueError as exc:
            skipped.append(ProviderSkip(
                provider=provider,
                reason="PROVIDER_CONFIGURATION_INVALID",
                detail=str(exc),
            ))
            continue

        return ProviderRouteDecision(
            status=ProviderRouteStatus.READY,
            selected=candidate,
            authorization=authorization,
            skipped=tuple(skipped),
        )

    if approval_candidate is not None:
        return ProviderRouteDecision(
            status=ProviderRouteStatus.NEEDS_APPROVAL,
            selected=None,
            authorization=None,
            skipped=tuple(skipped),
            approval_required=approval_candidate,
            approval_reason=approval_reason,
        )

    return ProviderRouteDecision(
        status=ProviderRouteStatus.NO_PROVIDER_AVAILABLE,
        selected=None,
        authorization=None,
        skipped=tuple(skipped),
    )



def execute_with_provider_fallback(
    *,
    required_capability: str,
    candidates: Sequence[ProviderCandidate],
    operations: Mapping[str, Callable[[], Any]],
) -> ProviderFallbackExecutionResult:
    """Execute the selected provider and retry only definitive safe failures.

    Provider adapters must translate a vendor response into
    ProviderCreditsExhausted only when the vendor explicitly confirms the
    operation was rejected for lack of credits. ProviderTemporarilyUnavailable
    is reserved for failures known to occur before execution. Generic timeout,
    connection-loss and ambiguous responses propagate without retry.
    """
    remaining = list(candidates)
    attempts: list[ProviderAttempt] = []

    while True:
        decision = route_provider(
            required_capability=required_capability,
            candidates=remaining,
        )
        if decision.status is not ProviderRouteStatus.READY or decision.selected is None:
            return ProviderFallbackExecutionResult(
                status=decision.status,
                provider=None,
                result=None,
                attempts=tuple(attempts),
                approval_required=decision.approval_required,
                approval_reason=decision.approval_reason,
            )

        selected = decision.selected
        provider = str(selected.provider).strip().upper()
        callback = operations.get(provider)
        if callback is None:
            attempts.append(ProviderAttempt(
                provider=provider,
                outcome="ADAPTER_NOT_CONFIGURED",
                detail="No operation callback is registered for this provider.",
            ))
            remaining = [
                replace(item, available=False) if item is selected else item
                for item in remaining
            ]
            continue

        try:
            operation_result = execute_provider_operation(
                provider=provider,
                operation=required_capability,
                estimated_credits=selected.estimated_credits,
                credits_available=selected.credits_available,
                operation_callback=callback,
                approved=selected.approved,
                approval_reference=selected.approval_reference,
                approved_max_credits=selected.approved_max_credits,
                personal_contact_access=selected.personal_contact_access,
                contact_data_approved=selected.contact_data_approved,
                quality_checks=selected.quality_checks,
                agent_policy_id=selected.agent_policy_id,
                daily_budget_limit=selected.daily_budget_limit,
                credits_spent_today=selected.credits_spent_today,
            )
        except ProviderCreditsExhausted as exc:
            attempts.append(ProviderAttempt(
                provider=provider,
                outcome="CREDITS_EXHAUSTED",
                detail=str(exc),
            ))
            remaining = [
                replace(item, available=False) if item is selected else item
                for item in remaining
            ]
            continue
        except ProviderTemporarilyUnavailable as exc:
            attempts.append(ProviderAttempt(
                provider=provider,
                outcome="TEMPORARILY_UNAVAILABLE",
                detail=str(exc),
            ))
            remaining = [
                replace(item, available=False) if item is selected else item
                for item in remaining
            ]
            continue

        attempts.append(ProviderAttempt(
            provider=provider,
            outcome="SUCCESS",
            detail="Provider returned a result after preflight authorization.",
        ))
        return ProviderFallbackExecutionResult(
            status=ProviderRouteStatus.READY,
            provider=provider,
            result=operation_result.result,
            attempts=tuple(attempts),
        )
