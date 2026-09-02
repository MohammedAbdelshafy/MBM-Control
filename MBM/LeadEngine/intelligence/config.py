"""
Feature flags + env config for the intelligence layer.
All new behaviour is OFF by default. Production lead pipeline
is unaffected unless flags are explicitly enabled.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: str = "false") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class IntelligenceFlags:
    enabled: bool = False
    world_monitor_enabled: bool = False
    anderro_enabled: bool = False
    topview_enabled: bool = False
    skysnail_enabled: bool = False
    voxcpm_enabled: bool = False
    # allow blocked providers only in hermetic tests when this is true
    allow_blocked_in_tests: bool = False


def load_flags() -> IntelligenceFlags:
    master = _bool_env("INTELLIGENCE_ENABLED", "false")
    return IntelligenceFlags(
        enabled=master,
        world_monitor_enabled=master and _bool_env("WORLDMONITOR_ENABLED", "false"),
        anderro_enabled=master and _bool_env("ANDERRO_ENABLED", "false"),
        topview_enabled=master and _bool_env("TOPVIEW_ENABLED", "false"),
        skysnail_enabled=master and _bool_env("SKYSNAIL_ENABLED", "false"),
        voxcpm_enabled=master and _bool_env("VOXCPM_ENABLED", "false"),
        allow_blocked_in_tests=_bool_env("INTELLIGENCE_ALLOW_BLOCKED_IN_TESTS", "false"),
    )


# Provider credentials (env-only, never committed)
@dataclass(frozen=True)
class ProviderCredentials:
    worldmonitor_api_key: str = ""
    worldmonitor_base_url: str = ""
    worldmonitor_mcp_url: str = ""
    anderro_api_key: str = ""
    topview_api_key: str = ""
    skysnail_api_key: str = ""

    @classmethod
    def from_env(cls) -> "ProviderCredentials":
        return cls(
            worldmonitor_api_key=os.environ.get("WORLDMONITOR_API_KEY", "") or os.environ.get("WORLD_MONITOR_API_KEY", ""),
            worldmonitor_base_url=os.environ.get("WORLDMONITOR_BASE_URL", "") or os.environ.get("WORLD_MONITOR_BASE_URL", "") or "https://worldmonitor.app",
            worldmonitor_mcp_url=os.environ.get("WORLDMONITOR_MCP_URL", "") or os.environ.get("WORLD_MONITOR_MCP_URL", ""),
            anderro_api_key=os.environ.get("ANDERRO_API_KEY", ""),
            topview_api_key=os.environ.get("TOPVIEW_API_KEY", "") or os.environ.get("TOPVIEW_API_TOKEN", ""),
            skysnail_api_key=os.environ.get("SKYSNAIL_API_KEY", "") or os.environ.get("SKYSNAIL_API_TOKEN", ""),
        )

    def has(self, provider: str) -> bool:
        p = provider.lower()
        if p == "worldmonitor":
            return bool(self.worldmonitor_api_key or self.worldmonitor_mcp_url)
        if p == "anderro":
            return bool(self.anderro_api_key)
        if p == "topview":
            return bool(self.topview_api_key)
        if p == "skysnail":
            return bool(self.skysnail_api_key)
        return False
