"""Curated GitHub intelligence memory for the MBM GLM team.

External projects are pattern references or guarded adapters, never authorities.
Each entry has an explicit adoption boundary so GLM can learn without creating
an uncontrolled framework pile-up.
"""

from __future__ import annotations
from typing import Any

REPO_PATTERNS: dict[str, dict[str, Any]] = {
    "langchain-ai/langgraph": {
        "adopt_as": "pattern_reference",
        "pattern": "stateful graph orchestration, checkpoints, durable state, deterministic routing",
        "boundary": "do_not_replace_glm_authority",
        "current_use": "inform mission graph/checkpoint design only",
    },
    "google/adk-python": {
        "adopt_as": "optional_secondary_runtime",
        "pattern": "code-first agents, evaluation, deployment and multi-agent collaboration",
        "boundary": "specialists_only; no canonical writes",
        "current_use": "sandboxed specialist runtime behind github_runtime_bridge",
    },
    "microsoft/playwright": {
        "adopt_as": "approved_browser_adapter",
        "pattern": "structured accessibility-tree browser control",
        "boundary": "read_only_until_explicit_approval",
        "current_use": "research/verification browser worker",
    },
    "unclecode/crawl4ai": {
        "adopt_as": "approved_web_ingestion_adapter",
        "pattern": "LLM-friendly web crawling and extraction",
        "boundary": "untrusted_content_only",
        "current_use": "source discovery metadata",
    },
    "triggerdotdev/trigger.dev": {
        "adopt_as": "durable_job_pattern",
        "pattern": "retries, long-running jobs, checkpoints and durable execution",
        "boundary": "lab_only_until_evaluated",
        "current_use": "future durable worker experiments",
    },
    "obra/superpowers": {
        "adopt_as": "engineering_skill_layer",
        "pattern": "brainstorming, plans, TDD, parallel work, review and verification",
        "boundary": "process_guidance_not_data_authority",
        "current_use": "planning/testing/review discipline",
    },
    "langchain-ai/open_deep_research": {
        "adopt_as": "research_pattern_reference",
        "pattern": "deep research planning, source gathering and evidence synthesis",
        "boundary": "research_outputs_advisory",
        "current_use": "research-agent design",
    },
    "crewAIInc/crewAI": {
        "adopt_as": "pattern_reference",
        "pattern": "role-based crews, task delegation and agent tooling",
        "boundary": "do_not_duplicate_glm_registry",
        "current_use": "compare delegation patterns before implementation",
    },
    "mastra-ai/mastra": {
        "adopt_as": "pattern_reference",
        "pattern": "agent workflows, memory, tools and evaluation",
        "boundary": "do_not_duplicate_canonical_runtime",
        "current_use": "evaluate workflow and memory patterns",
    },
    "browserbase/stagehand": {
        "adopt_as": "browser_pattern_reference",
        "pattern": "AI-driven browser actions with reusable abstractions",
        "boundary": "must sit behind approved browser capability boundary",
        "current_use": "compare browser-agent design against Playwright MCP",
    },
}


def get_repo_pattern(repo: str) -> dict[str, Any] | None:
    return REPO_PATTERNS.get(repo)


def repo_intelligence_snapshot() -> dict[str, Any]:
    return {
        "version": 1,
        "count": len(REPO_PATTERNS),
        "repos": sorted(REPO_PATTERNS),
        "authority": "Jarvis_GLM_orchestrator",
        "canonical_writes_allowed": False,
    }
