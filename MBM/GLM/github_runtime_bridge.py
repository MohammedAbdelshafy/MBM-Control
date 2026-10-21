"""Scoped GitHub-adopted runtime bridge for MBM subsystems.

This module is the single capability boundary for optional external runtimes.
Jarvis/GLM decides whether a capability is allowed; adapters execute only the
requested, non-authoritative work. No adapter may mutate canonical lead stores.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimePolicy:
    crawl4ai: bool
    playwright_mcp: bool
    google_adk: bool
    trigger_dev: bool

    @classmethod
    def from_env(cls) -> "RuntimePolicy":
        return cls(
            crawl4ai=os.getenv("MBM_CRAWL4AI_ENABLED", "false").lower() == "true",
            playwright_mcp=os.getenv("MBM_PLAYWRIGHT_MCP_ENABLED", "false").lower() == "true",
            google_adk=os.getenv("MBM_ADK_ENABLED", "false").lower() == "true",
            trigger_dev=os.getenv("MBM_TRIGGER_ENABLED", "false").lower() == "true",
        )


def policy() -> RuntimePolicy:
    return RuntimePolicy.from_env()


def capability_status() -> dict[str, Any]:
    p = policy()
    return {
        "crawl4ai": {"enabled": p.crawl4ai, "scope": "untrusted_web_ingestion"},
        "playwright_mcp": {"enabled": p.playwright_mcp, "scope": "browser_read_only_until_approval"},
        "google_adk": {"enabled": p.google_adk, "scope": "specialist_runtime"},
        "trigger_dev": {"enabled": p.trigger_dev, "scope": "durable_jobs_only"},
        "authoritative_writes": False,
        "jarvis_approval_required": True,
    }


def crawl_public_markdown(url: str):
    """Optional Crawl4AI adapter. Returns untrusted content only."""
    if not policy().crawl4ai:
        raise RuntimeError("Crawl4AI adapter is disabled; set MBM_CRAWL4AI_ENABLED=true in the sandbox.")
    from MBM.Integrations.github_adoption.crawl4ai_adapter import crawl_markdown
    return crawl_markdown(url)


def playwright_command() -> list[str]:
    """Return the pinned browser-MCP command without starting it."""
    from MBM.Integrations.github_adoption.playwright_mcp_adapter import PlaywrightMcpConfig
    return PlaywrightMcpConfig.from_env().command()
