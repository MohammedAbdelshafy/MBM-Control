"""Authoritative provider credit meters for MBM acquisition routing.

Meter reads are low-cost/read-only provider operations. They never perform
search, enrichment, export, or contact-data access. Unknown, malformed, or
stale balances remain non-authoritative and cannot authorize paid work.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APOLLO_CREDIT_POOLS = frozenset({
    "lead_credit",
    "direct_dial_credit",
    "export_credit",
    "conversation_credit",
    "ai_credit",
    "power_up_credit",
    "inbound_website_visitor_credit",
    "dialer",
    "web_search_record_credit",
    "contact_website_visitor_credit",
    "broadcast_credit",
})

APOLLO_CREDIT_USAGE_URL = (
    "https://api.apollo.io/api/v1/usage_stats/credit_usage_stats"
)
EXPLORIUM_CREDITS_URL = "https://api.explorium.ai/v1/credits"
DEFAULT_TIMEOUT_SECONDS = 10


class BalanceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    UNCONFIGURED = "UNCONFIGURED"


@dataclass(frozen=True)
class ProviderBalanceSnapshot:
    provider: str
    status: BalanceStatus
    credits_allocated: Optional[int] = None
    credits_remaining: Optional[int] = None
    credit_pool: Optional[str] = None
    observed_at: Optional[datetime] = None
    cycle_start: Optional[datetime] = None
    cycle_end: Optional[datetime] = None
    account_type: Optional[str] = None
    detail: str = ""

    def is_authoritative_for_paid_work(
        self,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: int = 120,
    ) -> bool:
        """Return true only for a recent, valid balance snapshot."""
        current = _utc(now or _utc_now())
        observed = _utc(self.observed_at) if self.observed_at else None
        if (
            self.status is not BalanceStatus.VERIFIED
            or self.credits_remaining is None
            or observed is None
            or max_age_seconds < 0
        ):
            return False
        age_seconds = (current - observed).total_seconds()
        if age_seconds < 0 or age_seconds > max_age_seconds:
            return False
        if self.cycle_start is not None and current < _utc(self.cycle_start):
            return False
        if self.cycle_end is not None and current >= _utc(self.cycle_end):
            return False
        return True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return _utc(parsed)


def _non_negative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _unknown(
    provider: str,
    detail: str,
    *,
    observed_at: Optional[datetime] = None,
    credit_pool: Optional[str] = None,
) -> ProviderBalanceSnapshot:
    return ProviderBalanceSnapshot(
        provider=provider,
        status=BalanceStatus.UNKNOWN,
        observed_at=observed_at,
        credit_pool=credit_pool,
        detail=detail,
    )


def _read_json(
    request: Request,
    *,
    opener: Callable[..., Any],
    timeout: int,
) -> Mapping[str, Any]:
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("provider meter response must be a JSON object")
    return payload


def read_apollo_balance(
    api_key: Optional[str],
    *,
    credit_pool: str = "lead_credit",
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderBalanceSnapshot:
    """Read one Apollo credit pool and validate its current billing window."""
    provider = "APOLLO"
    pool = str(credit_pool or "").strip()
    if pool not in APOLLO_CREDIT_POOLS:
        return _unknown(provider, "Requested Apollo credit pool is unsupported.")
    token = str(api_key or "").strip()
    if not token:
        return ProviderBalanceSnapshot(
            provider=provider,
            status=BalanceStatus.UNCONFIGURED,
            credit_pool=pool,
            detail="APOLLO_API_KEY is not configured.",
        )

    observed_at = _utc(now or _utc_now())
    request = Request(
        APOLLO_CREDIT_USAGE_URL,
        headers={
            "x-api-key": token,
            "accept": "application/json",
            "content-type": "application/json",
            "cache-control": "no-cache",
        },
        method="POST",
    )
    try:
        payload = _read_json(request, opener=opener, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return _unknown(
            provider,
            "Apollo credit meter request failed or returned invalid JSON.",
            observed_at=observed_at,
            credit_pool=pool,
        )
    except Exception:
        return _unknown(
            provider,
            "Apollo credit meter request failed.",
            observed_at=observed_at,
            credit_pool=pool,
        )

    usage = payload.get("credit_usage_stats")
    if not isinstance(usage, Mapping):
        return _unknown(
            provider,
            "Apollo response did not contain credit_usage_stats.",
            observed_at=observed_at,
            credit_pool=pool,
        )
    pool_data = usage.get(pool)
    if not isinstance(pool_data, Mapping):
        return _unknown(
            provider,
            "Apollo response did not contain the requested credit pool.",
            observed_at=observed_at,
            credit_pool=pool,
        )

    allocated = pool_data.get("limit")
    consumed = pool_data.get("consumed")
    remaining = pool_data.get("left_over")
    if not all(_non_negative_int(v) for v in (allocated, consumed, remaining)):
        return _unknown(
            provider,
            "Apollo credit pool returned missing or invalid integer balances.",
            observed_at=observed_at,
            credit_pool=pool,
        )
    if consumed + remaining != allocated:
        return _unknown(
            provider,
            "Apollo credit pool totals are internally inconsistent.",
            observed_at=observed_at,
            credit_pool=pool,
        )

    cycle = payload.get("current_credit_cycle")
    if not isinstance(cycle, Mapping):
        return _unknown(
            provider,
            "Apollo response did not contain a current billing cycle.",
            observed_at=observed_at,
            credit_pool=pool,
        )
    cycle_start = _parse_datetime(cycle.get("start_date"))
    cycle_end = _parse_datetime(cycle.get("end_date"))
    if cycle_start is None or cycle_end is None or cycle_end <= cycle_start:
        return _unknown(
            provider,
            "Apollo billing-cycle dates are missing or invalid.",
            observed_at=observed_at,
            credit_pool=pool,
        )

    status = (
        BalanceStatus.VERIFIED
        if cycle_start <= observed_at < cycle_end
        else BalanceStatus.STALE
    )
    detail = (
        "Apollo credit balance verified for the active billing cycle."
        if status is BalanceStatus.VERIFIED
        else "Apollo credit balance belongs to an expired or not-yet-active billing cycle."
    )
    return ProviderBalanceSnapshot(
        provider=provider,
        status=status,
        credits_allocated=allocated,
        credits_remaining=remaining,
        credit_pool=pool,
        observed_at=observed_at,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        detail=detail,
    )


def read_explorium_balance(
    api_key: Optional[str],
    *,
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderBalanceSnapshot:
    """Read Explorium's active shared credit balance."""
    provider = "VIBE_PROSPECTING"
    token = str(api_key or "").strip()
    if not token:
        return ProviderBalanceSnapshot(
            provider=provider,
            status=BalanceStatus.UNCONFIGURED,
            detail="EXPLORIUM_API_KEY is not configured.",
        )

    observed_at = _utc(now or _utc_now())
    request = Request(
        EXPLORIUM_CREDITS_URL,
        headers={
            "api_key": token,
            "accept": "application/json",
            "content-type": "application/json",
            "cache-control": "no-cache",
        },
        method="GET",
    )
    try:
        payload = _read_json(request, opener=opener, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return _unknown(
            provider,
            "Explorium credit meter request failed or returned invalid JSON.",
            observed_at=observed_at,
        )
    except Exception:
        return _unknown(
            provider,
            "Explorium credit meter request failed.",
            observed_at=observed_at,
        )

    allocated = payload.get("allocated_credits")
    remaining = payload.get("remaining_credits")
    if (
        not _non_negative_int(allocated)
        or not _non_negative_int(remaining)
        or remaining > allocated
    ):
        return _unknown(
            provider,
            "Explorium credit meter returned missing or invalid integer balances.",
            observed_at=observed_at,
        )

    account_type = payload.get("account_type")
    if account_type is not None and account_type not in {"trial", "paid"}:
        account_type = None
    return ProviderBalanceSnapshot(
        provider=provider,
        status=BalanceStatus.VERIFIED,
        credits_allocated=allocated,
        credits_remaining=remaining,
        observed_at=observed_at,
        account_type=account_type,
        detail="Explorium active credit balance verified.",
    )


def read_provider_balance(
    provider: str,
    *,
    api_key: Optional[str] = None,
    credit_pool: str = "lead_credit",
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProviderBalanceSnapshot:
    """Resolve the supported live meter, or fail closed when none is exposed."""
    name = str(provider or "").strip().upper()
    if name == "APOLLO":
        token = api_key if api_key is not None else os.getenv("APOLLO_API_KEY")
        return read_apollo_balance(
            token,
            credit_pool=credit_pool,
            now=now,
            opener=opener,
            timeout=timeout,
        )
    if name in {"VIBE_PROSPECTING", "EXPLORIUM"}:
        token = api_key if api_key is not None else os.getenv("EXPLORIUM_API_KEY")
        return read_explorium_balance(
            token,
            now=now,
            opener=opener,
            timeout=timeout,
        )
    if name == "CLAY":
        return ProviderBalanceSnapshot(
            provider="CLAY",
            status=BalanceStatus.UNKNOWN,
            detail=(
                "Clay data-credit and action balances are visible in its workspace "
                "usage dashboard; no authoritative balance endpoint is configured."
            ),
        )
    return _unknown(name or "UNKNOWN", "No authoritative meter adapter is registered.")


def apply_provider_balance(
    candidate: Any,
    snapshot: ProviderBalanceSnapshot,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: int = 120,
) -> Any:
    """Return a candidate carrying a fresh balance, or zero paid-work capacity."""
    provider = str(candidate.provider or "").strip().upper()
    snapshot_provider = str(snapshot.provider or "").strip().upper()
    expected = "VIBE_PROSPECTING" if snapshot_provider == "EXPLORIUM" else snapshot_provider
    if provider != expected:
        raise ValueError("provider balance snapshot does not match candidate provider")

    if snapshot.is_authoritative_for_paid_work(
        now=now,
        max_age_seconds=max_age_seconds,
    ):
        return replace(
            candidate,
            credits_available=snapshot.credits_remaining,
            balance_verified=True,
            balance_observed_at=_utc(snapshot.observed_at),
            balance_source=snapshot.provider,
            balance_detail=snapshot.detail,
        )

    return replace(
        candidate,
        credits_available=0,
        balance_verified=False,
        balance_observed_at=_utc(snapshot.observed_at) if snapshot.observed_at else None,
        balance_source=snapshot.provider,
        balance_detail=snapshot.detail or "Provider balance is not verified.",
    )


def refresh_provider_candidates(
    candidates: Any,
    *,
    required_capability: str,
    api_keys: Optional[Mapping[str, str]] = None,
    now: Optional[datetime] = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_age_seconds: int = 120,
) -> list[Any]:
    """Attach a fresh vendor meter to paid/unknown-cost routing candidates.

    Zero-credit operations are left untouched because their documented
    operation cost, not a guessed vendor balance, is the spend control. Paid
    and unknown-cost operations get a just-in-time balance read; any missing,
    stale, malformed, or unavailable meter makes the candidate non-routable.
    """
    capability = str(required_capability or "").strip().lower()
    if not capability:
        raise ValueError("required_capability is required")

    keys = {
        str(name).strip().upper(): str(value).strip()
        for name, value in (api_keys or {}).items()
        if value is not None and str(value).strip()
    }
    direct_dial_capabilities = {
        "direct_dial_enrichment",
        "phone_enrichment",
        "mobile_enrichment",
    }
    credit_pool = (
        "direct_dial_credit"
        if capability in direct_dial_capabilities
        else "lead_credit"
    )
    refreshed = []
    for candidate in candidates:
        if candidate.estimated_credits == 0:
            refreshed.append(candidate)
            continue

        provider = str(candidate.provider or "").strip().upper()
        snapshot = read_provider_balance(
            provider,
            api_key=keys.get(provider),
            credit_pool=credit_pool,
            now=now,
            opener=opener,
            timeout=timeout,
        )
        refreshed.append(apply_provider_balance(
            candidate,
            snapshot,
            now=now,
            max_age_seconds=max_age_seconds,
        ))
    return refreshed
