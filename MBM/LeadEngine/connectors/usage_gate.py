"""Explicit approval and hard-budget gate for external data-provider usage.

This is a preflight policy check only. It does not call a provider, reserve
credits, enrich contacts, export records, or write to the canonical lead store.
Callers must run it immediately before a provider operation and still handle
the provider's authoritative usage meter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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

    if personal_contact_access and not contact_data_approved:
        raise ProviderBudgetDenied(
            "personal contact access requires separate contact-data approval"
        )

    credit_consuming = estimate is None or estimate > 0
    needs_approval = credit_consuming or personal_contact_access
    if needs_approval and not approved:
        raise ProviderBudgetDenied(
            "credit-consuming or contact-data operation requires explicit approval"
        )
    if needs_approval and not reference:
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
