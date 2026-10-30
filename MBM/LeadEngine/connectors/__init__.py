"""Reusable connector contracts for MBM integrations.

These contracts are intentionally provider-neutral. Connectors enrich, execute,
or observe; they do not override canonical Dialer safety decisions.
"""

from .evidence import Evidence, EvidenceEnvelope, build_evidence
from .events import RevenueEvent, normalize_event
from .provider_adapters import (
    BalanceStatus,
    ProviderBalanceSnapshot,
    apply_provider_balance,
    read_apollo_balance,
    read_explorium_balance,
    read_provider_balance,
    refresh_provider_candidates,
)
from .provider_router import (
    ProviderCandidate,
    ProviderRouteDecision,
    ProviderRouteStatus,
    execute_with_provider_fallback,
    route_provider,
)

__all__ = [
    "BalanceStatus",
    "Evidence",
    "EvidenceEnvelope",
    "ProviderBalanceSnapshot",
    "ProviderCandidate",
    "ProviderRouteDecision",
    "ProviderRouteStatus",
    "RevenueEvent",
    "apply_provider_balance",
    "build_evidence",
    "execute_with_provider_fallback",
    "normalize_event",
    "read_apollo_balance",
    "read_explorium_balance",
    "read_provider_balance",
    "refresh_provider_candidates",
    "route_provider",
]
