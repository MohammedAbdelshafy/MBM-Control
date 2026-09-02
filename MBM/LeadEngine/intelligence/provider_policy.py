"""
Quarantine / allowlist enforcement — code-enforced, not docs-only.

Every external integration MUST call `assert_allowed(provider)` before
any network I/O. Unknown providers default to BLOCKED.

Statuses:
  allow                      -> production allowed
  allow_pending_verification -> allowed but flagged for verification
  gated                      -> OFF unless explicit flag + authz
  research_only              -> never called from production path
  blocked                    -> hard blocked, always raises
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Literal

ProviderStatus = Literal["allow", "allow_pending_verification", "gated", "research_only", "blocked"]

@dataclass(frozen=True)
class ProviderRule:
    provider: str
    status: ProviderStatus
    reason: str
    requires_flag: str | None = None  # env flag name if gated
    allow_test_bypass: bool = False


# Canonical policy — single source of truth.
# Mirrors master prompt §11.
_POLICY: Dict[str, ProviderRule] = {
    "worldmonitor": ProviderRule("worldmonitor", "allow", "Primary intelligence provider (koala73/worldmonitor)"),
    "topview": ProviderRule("topview", "allow_pending_verification", "Video production engine — verify API surface before prod"),
    "skysnail": ProviderRule("skysnail", "allow_pending_verification", "Thumbnail/creative optimizer — verify API surface"),
    "anderro": ProviderRule("anderro", "allow_pending_verification", "Affiliate marketplace — live rates only"),
    "voxcpm_official": ProviderRule("voxcpm_official", "gated", "Self-hosted voice clone — consent + kill-switch required", requires_flag="VOXCPM_ENABLED"),
    "famelack": ProviderRule("famelack", "research_only", "Links to public streams — copyright status not guaranteed"),
    "vidbox_dev": ProviderRule("vidbox_dev", "blocked", "High-risk streaming clone — do not integrate"),
    "ankergames": ProviderRule("ankergames", "blocked", "Markets pre-installed commercial games — do not integrate"),
    "voxcpm_net": ProviderRule("voxcpm_net", "blocked", "Unverified voxcpm.net domain — not canonical VoxCPM"),
}

# Aliases so callers can use natural names
_ALIASES: Dict[str, str] = {
    "world_monitor": "worldmonitor",
    "world-monitor": "worldmonitor",
    "worldmonitor.app": "worldmonitor",
    "topview.ai": "topview",
    "skysnail": "skysnail",
    "sky_snail": "skysnail",
    "anderro": "anderro",
    "voxcpm": "voxcpm_official",
    "voxcpm_official": "voxcpm_official",
    "voxcpn": "voxcpm_official",
    "famelack": "famelack",
    "vidbox": "vidbox_dev",
    "vidbox.dev": "vidbox_dev",
    "anker_games": "ankergames",
    "ankergames": "ankergames",
    "voxcpm.net": "voxcpm_net",
    "voxcpm_net": "voxcpm_net",
}


class ProviderBlocked(RuntimeError):
    pass


class ProviderGated(RuntimeError):
    pass


class ProviderResearchOnly(RuntimeError):
    pass


def _normalize(name: str) -> str:
    key = (name or "").strip().lower()
    return _ALIASES.get(key, key)


def get_rule(provider: str) -> ProviderRule | None:
    return _POLICY.get(_normalize(provider))


def is_blocked(provider: str) -> bool:
    r = get_rule(provider)
    if r is None:
        return True  # unknown -> blocked
    return r.status == "blocked"


def assert_allowed(provider: str, *, purpose: str = "production") -> ProviderRule:
    """
    Enforce policy in code. Raises on blocked/gated/research_only.
    Call before any external I/O.
    """
    norm = _normalize(provider)
    rule = _POLICY.get(norm)
    if rule is None:
        raise ProviderBlocked(f"Unknown provider '{provider}' defaulted to BLOCKED (no policy entry). Refusing.")

    if rule.status == "blocked":
        # Test bypass only when explicitly allowed (hermetic contract tests with mocked provider)
        allow_bypass = os.environ.get("INTELLIGENCE_ALLOW_BLOCKED_IN_TESTS", "").lower() in ("1", "true", "yes", "on")
        if allow_bypass:
            return rule
        raise ProviderBlocked(f"Provider '{provider}' is BLOCKED: {rule.reason}")

    if rule.status == "research_only" and purpose == "production":
        raise ProviderResearchOnly(f"Provider '{provider}' is RESEARCH_ONLY: {rule.reason}. Not callable from production.")

    if rule.status == "gated":
        flag = rule.requires_flag or "VOXCPM_ENABLED"
        enabled = (os.environ.get(flag, "") or "").strip().lower() in ("1", "true", "yes", "on")
        if not enabled:
            raise ProviderGated(f"Provider '{provider}' is GATED behind {flag}=true (currently off). Refusing. Reason: {rule.reason}")

    return rule


def list_policy() -> Dict[str, Dict[str, str]]:
    return {k: {"status": v.status, "reason": v.reason, "requires_flag": v.requires_flag or ""} for k, v in _POLICY.items()}
