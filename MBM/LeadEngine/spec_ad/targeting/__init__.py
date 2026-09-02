"""spec_ad targeting package — Phase 2 foundation."""
from .dedup import canonicalize_domain, extract_canonical_domain, dedup_key, is_duplicate, dedup_accounts
from .scoring import (
    HIGH_VALUE_WEIGHTS,
    NEGATIVE_SIGNALS,
    score_icp,
    score_creative_opportunity,
    qualify_account,
    build_target_account,
)
from .repository import TargetAccountRepository

__all__ = [
    "canonicalize_domain",
    "extract_canonical_domain",
    "dedup_key",
    "is_duplicate",
    "dedup_accounts",
    "HIGH_VALUE_WEIGHTS",
    "NEGATIVE_SIGNALS",
    "score_icp",
    "score_creative_opportunity",
    "qualify_account",
    "build_target_account",
    "TargetAccountRepository",
]
