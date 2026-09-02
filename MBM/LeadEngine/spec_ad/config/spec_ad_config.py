"""
Spec-Ad Config — typed, env-aware, safe defaults (Phase 2 / Step 6).

Mirrors spec-ad-engine/src/config/specAdConfig.js behavior but in Python
conventions (frozen dataclass, like MBM/LeadEngine/intelligence/config.py).

- Never logs secrets.
- Deterministic.
- Safe when env vars are missing (falls back to defaults).
- Validates ranges; raises ValueError on invalid config (caller fails closed).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List


def _csv_to_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _parse_int(value: str | None, fallback: int) -> int:
    try:
        if value is None or str(value).strip() == "":
            return fallback
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return fallback


def _parse_float(value: str | None, fallback: float) -> float:
    try:
        if value is None or str(value).strip() == "":
            return fallback
        return float(str(value).strip())
    except (ValueError, TypeError):
        return fallback


@dataclass(frozen=True)
class SpecAdConfig:
    # ICP
    icp_industries: List[str] = field(default_factory=lambda: ["software", "saas", "software development"])
    excluded_industries: List[str] = field(default_factory=lambda: ["gambling", "adult", "crypto"])
    target_countries: List[str] = field(default_factory=lambda: ["US"])
    min_funding_usd: int = 0
    min_icp_score: int = 60
    min_creative_score: int = 0  # Phase 2 safeguard: not yet gated, default 0
    min_company_size: int = 0
    max_company_size: int = 0  # 0 = no max
    excluded_domains: List[str] = field(default_factory=list)
    excluded_accounts: List[str] = field(default_factory=list)

    # Creative
    creative_formats: List[str] = field(default_factory=lambda: ["9:16"])
    video_duration_sec: int = 15

    # Provider routing
    provider_priority: List[str] = field(default_factory=lambda: ["kling", "sora", "seedance", "veo", "higgsfield"])
    fallback_provider: str = "seedance"
    preferred_capability: str = "vertical_social"

    # Cost control (Phase 18)
    max_cost_per_spec_ad_usd: float = 5.0
    max_generation_attempts: int = 3
    daily_generation_budget_usd: float = 50.0
    monthly_generation_budget_usd: float = 500.0

    # Outreach cadence (modest)
    max_followups: int = 2
    followup_delays_minutes: List[int] = field(default_factory=lambda: [4320, 10080])
    daily_send_limit: int = 50

    # Suppression
    suppression_check_enabled: bool = True

    # Pricing tiers (config-driven, never hard-coded $10k)
    pricing_tiers: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            "entry": {"monthly_usd": 1500, "videos_per_month": 4, "revisions": 1, "turnaround_days": 5},
            "standard": {"monthly_usd": 3500, "videos_per_month": 10, "revisions": 2, "turnaround_days": 3},
            "premium": {"monthly_usd": 7500, "videos_per_month": 20, "revisions": 3, "turnaround_days": 2},
            "enterprise": {"monthly_usd": 15000, "videos_per_month": 50, "revisions": 5, "turnaround_days": 1},
        }
    )

    def __post_init__(self) -> None:
        if not 0 <= self.min_icp_score <= 100:
            raise ValueError(f"min_icp_score must be 0..100, got {self.min_icp_score}")
        if not 0 <= self.min_creative_score <= 100:
            raise ValueError(f"min_creative_score must be 0..100, got {self.min_creative_score}")
        if self.video_duration_sec < 5 or self.video_duration_sec > 60:
            raise ValueError(f"video_duration_sec must be 5..60, got {self.video_duration_sec}")
        if self.max_generation_attempts < 1 or self.max_generation_attempts > 5:
            raise ValueError(f"max_generation_attempts must be 1..5, got {self.max_generation_attempts}")
        if self.max_cost_per_spec_ad_usd < 0 or self.daily_generation_budget_usd < 0 or self.monthly_generation_budget_usd < 0:
            raise ValueError("cost budgets must be >= 0")
        if self.daily_send_limit < 1 or self.daily_send_limit > 1000:
            raise ValueError(f"daily_send_limit must be 1..1000, got {self.daily_send_limit}")
        allowed_formats = {"9:16", "1:1", "16:9"}
        for f in self.creative_formats:
            if f not in allowed_formats:
                raise ValueError(f"creative_formats must be subset of {allowed_formats}, got {f}")


def load_spec_ad_config(env: dict | None = None) -> SpecAdConfig:
    """Load from env dict (defaults to os.environ). Never logs secrets."""
    if env is None:
        env = os.environ

    def env_get(name: str, default: str | None = None) -> str | None:
        # Support both dict and os.environ
        try:
            val = env.get(name, default)  # type: ignore
        except Exception:
            val = os.environ.get(name, default)
        return val

    icp = _csv_to_list(env_get("SPEC_AD_ICP_INDUSTRIES", "software,saas,software development") or "")
    if not icp:
        icp = ["software", "saas", "software development"]
    excluded_ind = _csv_to_list(env_get("SPEC_AD_EXCLUDED_INDUSTRIES", "gambling,adult,crypto") or "")
    countries = _csv_to_list(env_get("SPEC_AD_TARGET_COUNTRIES", "US") or "")
    if not countries:
        countries = ["US"]
    creative_formats = _csv_to_list(env_get("SPEC_AD_CREATIVE_FORMATS", "9:16") or "")
    if not creative_formats:
        creative_formats = ["9:16"]

    provider_priority = _csv_to_list(env_get("SPEC_AD_PROVIDER_PRIORITY", "kling,sora,seedance,veo,higgsfield") or "")
    if not provider_priority:
        provider_priority = ["kling", "sora", "seedance", "veo", "higgsfield"]

    followup_raw = _csv_to_list(env_get("SPEC_AD_FOLLOWUP_DELAYS_MINUTES", "4320,10080") or "")
    followup_delays: List[int] = []
    for v in followup_raw:
        try:
            followup_delays.append(int(v))
        except ValueError:
            continue
    if not followup_delays:
        followup_delays = [4320, 10080]

    # JSON override for pricing tiers
    pricing_tiers = None
    tiers_json = env_get("SPEC_AD_PRICING_TIERS_JSON")
    if tiers_json:
        try:
            pricing_tiers = json.loads(tiers_json)  # type: ignore
        except Exception:
            pricing_tiers = None

    kwargs: dict = {
        "icp_industries": icp,
        "excluded_industries": excluded_ind,
        "target_countries": countries,
        "min_funding_usd": _parse_int(env_get("SPEC_AD_MIN_FUNDING_USD"), 0),
        "min_icp_score": _parse_int(env_get("SPEC_AD_MIN_ICP_SCORE"), 60),
        "min_creative_score": _parse_int(env_get("SPEC_AD_MIN_CREATIVE_SCORE"), 0),
        "min_company_size": _parse_int(env_get("SPEC_AD_MIN_COMPANY_SIZE"), 0),
        "max_company_size": _parse_int(env_get("SPEC_AD_MAX_COMPANY_SIZE"), 0),
        "excluded_domains": _csv_to_list(env_get("SPEC_AD_EXCLUDED_DOMAINS", "") or ""),
        "excluded_accounts": _csv_to_list(env_get("SPEC_AD_EXCLUDED_ACCOUNTS", "") or ""),
        "creative_formats": creative_formats,
        "video_duration_sec": _parse_int(env_get("SPEC_AD_VIDEO_DURATION_SEC"), 15),
        "provider_priority": [p.strip().lower() for p in provider_priority if p.strip()],
        "fallback_provider": (env_get("SPEC_AD_FALLBACK_PROVIDER", "seedance") or "seedance").strip().lower(),
        "preferred_capability": (env_get("SPEC_AD_PREFERRED_CAPABILITY", "vertical_social") or "vertical_social").strip(),
        "max_cost_per_spec_ad_usd": _parse_float(env_get("SPEC_AD_MAX_COST_PER_SPEC_AD_USD"), 5.0),
        "max_generation_attempts": _parse_int(env_get("SPEC_AD_MAX_GENERATION_ATTEMPTS"), 3),
        "daily_generation_budget_usd": _parse_float(env_get("SPEC_AD_DAILY_BUDGET_USD"), 50.0),
        "monthly_generation_budget_usd": _parse_float(env_get("SPEC_AD_MONTHLY_BUDGET_USD"), 500.0),
        "max_followups": _parse_int(env_get("SPEC_AD_MAX_FOLLOWUPS"), 2),
        "followup_delays_minutes": followup_delays,
        "daily_send_limit": _parse_int(env_get("SPEC_AD_DAILY_SEND_LIMIT"), 50),
        "suppression_check_enabled": (str(env_get("SPEC_AD_SUPPRESSION_CHECK_ENABLED", "true") or "true").strip().lower() not in ("0", "false", "no", "off")),
    }
    if pricing_tiers is not None:
        kwargs["pricing_tiers"] = pricing_tiers

    return SpecAdConfig(**kwargs)


# Singleton cache (like intelligence/config.py pattern)
_cached: SpecAdConfig | None = None


def get_spec_ad_config(env: dict | None = None) -> SpecAdConfig:
    global _cached
    if _cached is not None and env is None:
        return _cached
    cfg = load_spec_ad_config(env)
    if env is None:
        _cached = cfg
    return cfg


def clear_spec_ad_config_cache() -> None:
    global _cached
    _cached = None
