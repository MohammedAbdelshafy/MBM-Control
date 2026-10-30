"""Preflight-before-call wrapper for provider adapters.

Provider-specific connectors must use this gateway instead of invoking a
credit-bearing search or enrichment operation directly. The approval receipt is
returned with the result for caller-side audit logging; this module does not
persist customer data or reserve vendor credits.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, Optional, TypeVar

from MBM.LeadEngine.connectors.usage_gate import (
    ProviderBudgetAuthorization,
    authorize_provider_usage,
)

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderOperationResult(Generic[T]):
    authorization: ProviderBudgetAuthorization
    result: T


def execute_provider_operation(
    *,
    provider: str,
    operation: str,
    estimated_credits: Optional[int],
    credits_available: int,
    operation_callback: Callable[[], T],
    approved: bool = False,
    approval_reference: Optional[str] = None,
    approved_max_credits: Optional[int] = None,
    personal_contact_access: bool = False,
    contact_data_approved: bool = False,
    quality_checks: Optional[Mapping[str, bool]] = None,
    agent_policy_id: Optional[str] = None,
    daily_budget_limit: Optional[int] = None,
    credits_spent_today: int = 0,
) -> ProviderOperationResult[T]:
    """Authorize then execute exactly once; propagate provider exceptions."""
    authorization = authorize_provider_usage(
        provider=provider,
        operation=operation,
        estimated_credits=estimated_credits,
        credits_available=credits_available,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_max_credits,
        personal_contact_access=personal_contact_access,
        contact_data_approved=contact_data_approved,
        quality_checks=quality_checks,
        agent_policy_id=agent_policy_id,
        daily_budget_limit=daily_budget_limit,
        credits_spent_today=credits_spent_today,
    )
    result = operation_callback()
    return ProviderOperationResult(
        authorization=authorization,
        result=result,
    )
