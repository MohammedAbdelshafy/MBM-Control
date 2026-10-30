"""Metered, provenance-aware acquisition search adapters for Apollo and Explorium.

This module is read-only. It fetches provider search results and returns them
with source metadata; it does not enrich contact details, export, send outreach,
or write leads to the canonical Dialer store.

All credit-bearing calls pass through provider_gateway. Explorium fetch costs
are treated as variable and therefore require a caller-approved hard ceiling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from MBM.LeadEngine.connectors.provider_adapters import (
    ProviderBalanceSnapshot,
    read_apollo_balance,
    read_explorium_balance,
)
from MBM.LeadEngine.connectors.provider_gateway import execute_provider_operation
from MBM.LeadEngine.connectors.usage_gate import ProviderBudgetDenied


APOLLO_ORGANIZATION_SEARCH_URL = (
    "https://api.apollo.io/api/v1/mixed_companies/search"
)
APOLLO_PEOPLE_SEARCH_URL = (
    "https://api.apollo.io/api/v1/mixed_people/api_search"
)
EXPLORIUM_BUSINESSES_URL = "https://api.explorium.ai/v1/businesses"
EXPLORIUM_PROSPECTS_URL = "https://api.explorium.ai/v1/prospects"
DEFAULT_TIMEOUT_SECONDS = 20


class ProviderSearchError(RuntimeError):
    """A provider search failed without returning an admissible result."""


@dataclass(frozen=True)
class ProviderSearchResult:
    provider: str
    operation: str
    records: tuple[dict[str, Any], ...]
    page: int
    page_size: int
    total_results: Optional[int]
    estimated_credits: Optional[int]
    approved_max_credits: Optional[int]
    observed_at: datetime
    source_endpoint: str
    request_reference: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "records": [dict(record) for record in self.records],
            "page": self.page,
            "page_size": self.page_size,
            "total_results": self.total_results,
            "estimated_credits": self.estimated_credits,
            "approved_max_credits": self.approved_max_credits,
            "observed_at": self.observed_at.isoformat(),
            "source_endpoint": self.source_endpoint,
            "request_reference": self.request_reference,
        }


def _utc(value: Optional[datetime]) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _validate_filters(filters: object) -> dict[str, Any]:
    if not isinstance(filters, Mapping):
        raise ValueError("filters must be a mapping")
    if not filters:
        raise ValueError("filters must contain at least one targeting constraint")
    # JSON round-trip both validates provider payload serializability and
    # detaches the request from caller-owned mutable objects.
    try:
        validated = json.loads(json.dumps(dict(filters), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("filters must contain JSON-compatible values") from exc
    if not isinstance(validated, dict):
        raise ValueError("filters must be a JSON object")
    return validated


def _validate_paging(page: int, page_size: int, *, max_page_size: int) -> None:
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= max_page_size:
        raise ValueError(f"page_size must be between 1 and {max_page_size}")


def _read_json(
    *,
    url: str,
    method: str,
    headers: Mapping[str, str],
    payload: Optional[Mapping[str, Any]],
    opener: Callable[..., Any],
    timeout: int,
    provider: str,
) -> Mapping[str, Any]:
    data = (
        json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if payload is not None
        else None
    )
    request = Request(
        url,
        data=data,
        headers=dict(headers),
        method=method,
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
        result = json.loads(body)
    except HTTPError as exc:
        # Do not surface response bodies: upstream errors can echo user data.
        raise ProviderSearchError(
            f"{provider} request failed with HTTP {exc.code}."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderSearchError(
            f"{provider} request failed before a response was received."
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderSearchError(
            f"{provider} returned invalid JSON."
        ) from None
    except ProviderSearchError:
        raise
    except Exception:
        raise ProviderSearchError(f"{provider} request failed.") from None

    if not isinstance(result, Mapping):
        raise ProviderSearchError(f"{provider} response must be a JSON object.")
    return result


def _require_records(
    payload: Mapping[str, Any],
    *,
    provider: str,
    collection_key: str,
) -> tuple[tuple[dict[str, Any], ...], Optional[int], Optional[str]]:
    rows = payload.get(collection_key)
    if not isinstance(rows, list):
        raise ProviderSearchError(
            f"{provider} response did not contain the expected {collection_key} list."
        )
    records: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            records.append(dict(row))
        else:
            raise ProviderSearchError(
                f"{provider} returned a malformed record in {collection_key}."
            )

    total = payload.get("total_entries")
    if type(total) is not int or total < 0:
        total = payload.get("total_count")
    if type(total) is not int or total < 0:
        total = None

    reference: Optional[str] = None
    for key in ("request_id", "request_reference", "correlation_id"):
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            reference = str(value)
            break
    response_context = payload.get("response_context")
    if reference is None and isinstance(response_context, Mapping):
        value = response_context.get("correlation_id")
        if isinstance(value, (str, int)) and str(value).strip():
            reference = str(value)
    return tuple(records), total, reference


def _read_apollo_meter(
    api_key: str,
    *,
    credit_pool: str,
    now: datetime,
    opener: Callable[..., Any],
    timeout: int,
) -> ProviderBalanceSnapshot:
    snapshot = read_apollo_balance(
        api_key,
        credit_pool=credit_pool,
        now=now,
        opener=opener,
        timeout=timeout,
    )
    if not snapshot.is_authoritative_for_paid_work(now=now, max_age_seconds=120):
        raise ProviderBudgetDenied(
            "Apollo paid search is blocked because its current credit pool could not be verified."
        )
    return snapshot


def _read_explorium_meter(
    api_key: str,
    *,
    now: datetime,
    opener: Callable[..., Any],
    timeout: int,
) -> ProviderBalanceSnapshot:
    snapshot = read_explorium_balance(
        api_key,
        now=now,
        opener=opener,
        timeout=timeout,
    )
    if not snapshot.is_authoritative_for_paid_work(now=now, max_age_seconds=120):
        raise ProviderBudgetDenied(
            "Explorium search is blocked because the shared credit balance could not be verified."
        )
    return snapshot


def search_apollo_organizations(
    *,
    filters: Mapping[str, Any],
    api_key: str,
    page: int = 1,
    per_page: int = 25,
    approved: bool = False,
    approval_reference: Optional[str] = None,
    approved_max_credits: Optional[int] = None,
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderSearchResult:
    """Search Apollo organizations. The documented price is one credit/page."""
    normalized_filters = _validate_filters(filters)
    _validate_paging(page, per_page, max_page_size=100)
    token = str(api_key or "").strip()
    if not token:
        raise ProviderBudgetDenied("Apollo API key is not configured.")
    if approved_max_credits is not None and (
        type(approved_max_credits) is not int or approved_max_credits < 1
    ):
        raise ValueError("approved_max_credits must be at least one for organization search")

    observed_at = _utc(now)
    balance = _read_apollo_meter(
        token,
        credit_pool="lead_credit",
        now=observed_at,
        opener=opener,
        timeout=timeout,
    )
    payload = {**normalized_filters, "page": page, "per_page": per_page}
    response: dict[str, Any] = {}

    def execute() -> Mapping[str, Any]:
        nonlocal response
        response = _read_json(
            url=APOLLO_ORGANIZATION_SEARCH_URL,
            method="POST",
            headers={
                "x-api-key": token,
                "accept": "application/json",
                "content-type": "application/json",
                "cache-control": "no-cache",
            },
            payload=payload,
            opener=opener,
            timeout=timeout,
            provider="Apollo organization search",
        )
        return response

    receipt = execute_provider_operation(
        provider="APOLLO",
        operation="company_search",
        estimated_credits=1,
        credits_available=balance.credits_remaining or 0,
        operation_callback=execute,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_max_credits,
        balance_verified=balance.is_authoritative_for_paid_work(now=observed_at),
        balance_observed_at=balance.observed_at,
    )
    records, total, reference = _require_records(
        receipt.result,
        provider="APOLLO",
        collection_key="organizations",
    )
    return ProviderSearchResult(
        provider="APOLLO",
        operation="organization_search",
        records=records,
        page=page,
        page_size=per_page,
        total_results=total,
        estimated_credits=1,
        approved_max_credits=approved_max_credits,
        observed_at=observed_at,
        source_endpoint=APOLLO_ORGANIZATION_SEARCH_URL,
        request_reference=reference,
    )


def search_apollo_people(
    *,
    filters: Mapping[str, Any],
    api_key: str,
    page: int = 1,
    per_page: int = 25,
    contact_data_approved: bool = False,
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderSearchResult:
    """Search people at zero credits; returned records still require contact-data approval.

    Apollo's people API search does not return email addresses or phone numbers.
    Any later contact enrichment is a separate, credit-bearing operation.
    """
    normalized_filters = _validate_filters(filters)
    _validate_paging(page, per_page, max_page_size=100)
    token = str(api_key or "").strip()
    if not token:
        raise ProviderBudgetDenied("Apollo API key is not configured.")

    observed_at = _utc(now)
    payload = {**normalized_filters, "page": page, "per_page": per_page}
    response: dict[str, Any] = {}

    def execute() -> Mapping[str, Any]:
        nonlocal response
        response = _read_json(
            url=APOLLO_PEOPLE_SEARCH_URL,
            method="POST",
            headers={
                "x-api-key": token,
                "accept": "application/json",
                "content-type": "application/json",
                "cache-control": "no-cache",
            },
            payload=payload,
            opener=opener,
            timeout=timeout,
            provider="Apollo people search",
        )
        return response

    receipt = execute_provider_operation(
        provider="APOLLO",
        operation="people_search",
        estimated_credits=0,
        credits_available=0,
        operation_callback=execute,
        personal_contact_access=True,
        contact_data_approved=contact_data_approved,
    )
    records, total, reference = _require_records(
        receipt.result,
        provider="APOLLO",
        collection_key="people",
    )
    return ProviderSearchResult(
        provider="APOLLO",
        operation="people_search",
        records=records,
        page=page,
        page_size=per_page,
        total_results=total,
        estimated_credits=0,
        approved_max_credits=0,
        observed_at=observed_at,
        source_endpoint=APOLLO_PEOPLE_SEARCH_URL,
        request_reference=reference,
    )


def _fetch_explorium(
    *,
    endpoint: str,
    collection_key: str,
    operation: str,
    filters: Mapping[str, Any],
    size: int,
    page_size: int,
    page: int,
    mode: str,
    api_key: str,
    approved: bool,
    approval_reference: Optional[str],
    approved_max_credits: Optional[int],
    contact_data_approved: bool,
    now: Optional[datetime],
    opener: Callable[..., Any],
    timeout: int,
) -> ProviderSearchResult:
    normalized_filters = _validate_filters(filters)
    if type(size) is not int or not 1 <= size <= 10000:
        raise ValueError("size must be between 1 and 10000")
    _validate_paging(page, page_size, max_page_size=100)
    if mode not in {"full", "preview"}:
        raise ValueError("mode must be 'full' or 'preview'")
    token = str(api_key or "").strip()
    if not token:
        raise ProviderBudgetDenied("Explorium API key is not configured.")
    if type(approved_max_credits) is not int or approved_max_credits < 1:
        raise ValueError("approved_max_credits must be a positive integer for Explorium fetch")

    observed_at = _utc(now)
    balance = _read_explorium_meter(
        token,
        now=observed_at,
        opener=opener,
        timeout=timeout,
    )
    body = {
        "mode": mode,
        "size": size,
        "page_size": page_size,
        "page": page,
        "filters": normalized_filters,
        "request_context": {},
    }
    response: dict[str, Any] = {}

    def execute() -> Mapping[str, Any]:
        nonlocal response
        response = _read_json(
            url=endpoint,
            method="POST",
            headers={
                "API_KEY": token,
                "accept": "application/json",
                "content-type": "application/json",
            },
            payload=body,
            opener=opener,
            timeout=timeout,
            provider=f"Explorium {operation}",
        )
        return response

    receipt = execute_provider_operation(
        provider="VIBE_PROSPECTING",
        operation=operation,
        estimated_credits=None,
        credits_available=balance.credits_remaining or 0,
        operation_callback=execute,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_max_credits,
        personal_contact_access=collection_key == "prospects",
        contact_data_approved=contact_data_approved,
        balance_verified=balance.is_authoritative_for_paid_work(now=observed_at),
        balance_observed_at=balance.observed_at,
    )
    records, total, reference = _require_records(
        receipt.result,
        provider="VIBE_PROSPECTING",
        collection_key=collection_key,
    )
    return ProviderSearchResult(
        provider="VIBE_PROSPECTING",
        operation=operation,
        records=records,
        page=page,
        page_size=page_size,
        total_results=total,
        estimated_credits=None,
        approved_max_credits=approved_max_credits,
        observed_at=observed_at,
        source_endpoint=endpoint,
        request_reference=reference,
    )


def fetch_explorium_businesses(
    *,
    filters: Mapping[str, Any],
    size: int,
    page_size: int,
    api_key: str,
    page: int = 1,
    mode: str = "full",
    approved: bool = False,
    approval_reference: Optional[str] = None,
    approved_max_credits: Optional[int] = None,
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderSearchResult:
    """Fetch Explorium businesses with a current balance and fixed approved cap."""
    return _fetch_explorium(
        endpoint=EXPLORIUM_BUSINESSES_URL,
        collection_key="businesses",
        operation="business_fetch",
        filters=filters,
        size=size,
        page_size=page_size,
        page=page,
        mode=mode,
        api_key=api_key,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_max_credits,
        contact_data_approved=False,
        now=now,
        opener=opener,
        timeout=timeout,
    )


def fetch_explorium_prospects(
    *,
    filters: Mapping[str, Any],
    size: int,
    page_size: int,
    api_key: str,
    approved: bool = False,
    approval_reference: Optional[str] = None,
    approved_max_credits: Optional[int] = None,
    contact_data_approved: bool = False,
    page: int = 1,
    mode: str = "full",
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderSearchResult:
    """Fetch Explorium professional prospects behind a separate data approval."""
    return _fetch_explorium(
        endpoint=EXPLORIUM_PROSPECTS_URL,
        collection_key="prospects",
        operation="prospect_fetch",
        filters=filters,
        size=size,
        page_size=page_size,
        page=page,
        mode=mode,
        api_key=api_key,
        approved=approved,
        approval_reference=approval_reference,
        approved_max_credits=approved_max_credits,
        contact_data_approved=contact_data_approved,
        now=now,
        opener=opener,
        timeout=timeout,
    )
