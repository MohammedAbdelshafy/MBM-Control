"""Explicit approval and hard-budget gate for external data-provider usage.

This is a preflight policy check only. It does not call a provider, reserve
credits, enrich contacts, export records, or write to the canonical lead store.
Callers must run it immediately before a provider operation and still handle
the provider's authoritative usage meter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from MBM.LeadEngine.connectors.agent_quality import assess_agent_operation


SUPPORTED_PROVIDERS = frozenset({
    "VIBE_PROSPECTING",
    "APOLLO",
    "CLAY",
    "ZOOMINFO",
    "LINKEDIN",
    "CMS_NPPES",
    "OFFICIAL_RECORDS",
})


class ProviderBudgetDenied(RuntimeError):
    """Raised when a provider call exceeds its approved usage boundary."""


@dataclass(frozen=True)
class ProviderBudgetAuthorization:
    provider: str
    operation: str
    authorized: bool
    estimated_credits: Optional[int]
    approved_max_credits: Optional[int]
    credits_available: int
    credits_ceiling: int
    approval_reference: Optional[str]
    personal_contact_access: bool
    agent_policy_id: Optional[str] = None
    quality_passed: bool = False
    quality_score: Optional[float] = None
    daily_budget_limit: Optional[int] = None
    credits_spent_today: int = 0


def _non_negative_int(value: object, field: str, *, allow_none: bool = False) -> Optional[int]:
    if value is None and allow_none:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def authorize_provider_usage(
    *,
    provider: str,
    operation: str,
    estimated_credits: Optional[int],
    credits_available: int,
    approved: bool = False,
    approval_reference: Optional[str] = None,
    approved_max_credits: Optional[int] = None,
    personal_contact_access: bool = False,
    contact_data_approved: bool = False,
    quality_checks: Optional[Mapping[str, bool]] = None,
    agent_policy_id: Optional[str] = None,
    daily_budget_limit: Optional[int] = None,
    credits_spent_today: int = 0,
) -> ProviderBudgetAuthorization:
    """Authorize one provider operation against a visible approval and cap.

    Cost estimates must be conservative. For an unknown-cost operation, the
    approver must set an approved_max_credits hard ceiling. Contact-data access
    requires its own explicit approval even where the search endpoint is free.
    """
    provider_name = str(provider or "").strip().upper()
    operation_name = str(operation or "").strip().upper()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider_name or 'UNKNOWN'}")
    if not operation_name:
        raise ValueError("operation is required")

    estimate = _non_negative_int(
        estimated_credits, "estimated_credits", allow_none=True
    )
    available = _non_negative_int(credits_available, "credits_available")
    approved_cap = _non_negative_int(
        approved_max_credits, "approved_max_credits", allow_none=True
    )
    reference = str(approval_reference or "").strip() or None
    policy_id = str(agent_policy_id or "").strip() or None
    agent_mode = quality_checks is not None or policy_id is not None or daily_budget_limit is not None

    if agent_mode:
        if quality_checks is None or not policy_id:
            raise ProviderBudgetDenied(
                "agent operations require a quality report and a named agent policy"
            )
        daily_limit = _non_negative_int(
            daily_budget_limit, "daily_budget_limit", allow_none=True
        )
        spent_today = _non_negative_int(credits_spent_today, "credits_spent_today")
        if daily_limit is None:
            raise ProviderBudgetDenied(
                "agent operations require a configured daily budget limit"
            )
        assessment = assess_agent_operation(
            quality_checks,
            require_contact_scope=personal_contact_access,
        )
        if not assessment.passed:
            failed = ", ".join((*assessment.missing_checks, *assessment.failed_checks))
            raise ProviderBudgetDenied(
                f"agent quality check failed: {failed}"
            )
        if estimate is None:
            raise ProviderBudgetDenied(
                "unknown-cost provider operations are blocked until a deterministic cost ceiling exists"
            )
        ceiling = estimate
        remaining_today = max(0, daily_limit - spent_today)
        if spent_today + ceiling > daily_limit:
            raise ProviderBudgetDenied(
                "provider operation exceeds the daily agent budget"
            )
        if ceiling > available:
            raise ProviderBudgetDenied(
                "provider credit ceiling exceeds currently available credits"
            )
        return ProviderBudgetAuthorization(
            provider=provider_name,
            operation=operation_name,
            authorized=True,
            estimated_credits=estimate,
            approved_max_credits=None,
            credits_available=available,
            credits_ceiling=ceiling,
            approval_reference=None,
            personal_contact_access=personal_contact_access,
            agent_policy_id=policy_id,
            quality_passed=True,
            quality_score=assessment.score,
            daily_budget_limit=daily_limit,
            credits_spent_today=spent_today,
        )

    if personal_contact_access and not contact_data_approved:
        raise ProviderBudgetDenied(
            "personal contact access requires separate contact-data approval"
        )

    credit_consuming = estimate is None or estimate > 0
    if credit_consuming and not approved:
        raise ProviderBudgetDenied(
            "credit-consuming operation requires explicit approval"
        )
    if (credit_consuming or personal_contact_access) and not reference:
        raise ProviderBudgetDenied(
            "an approval reference is required for this operation"
        )

    if estimate is None:
        if approved_cap is None:
            raise ProviderBudgetDenied(
                "unknown provider cost requires an approved known upper bound"
            )
        ceiling = approved_cap
    else:
        ceiling = estimate
        if approved_cap is not None and estimate > approved_cap:
            raise ProviderBudgetDenied(
                "estimated provider credits exceed the approved cap"
            )

    if ceiling > available:
        raise ProviderBudgetDenied(
            "provider credit ceiling exceeds currently available credits"
        )

    return ProviderBudgetAuthorization(
        provider=provider_name,
        operation=operation_name,
        authorized=True,
        estimated_credits=estimate,
        approved_max_credits=approved_cap,
        credits_available=available,
        credits_ceiling=ceiling,
        approval_reference=reference,
        personal_contact_access=personal_contact_access,
    )
