"""Curated intelligence memory for external GitHub agent frameworks.

This is a design-memory layer, not a vendoring mechanism. It records which
external projects can teach MBM patterns and what boundary each project must
respect.
"""

from __future__ import annotations

from typing import Any


REPO_PATTERNS: dict[str, dict[str, Any]] = {
    "langchain-ai/langgraph": {
        "adopt_as": "pattern_reference",
        "pattern": "stateful graph orchestration, checkpoints, deterministic routing",
        "boundary": "do_not_replace_glm_authority",
    },
    "google/adk-python": {
        "adopt_as": "optional_secondary_runtime",
        "pattern": "code-first agents, evaluation and deployment primitives",
        "boundary": "specialists_only; no canonical writes",
    },
    "microsoft/playwright": {
        "adopt_as": "approved_browser_adapter",
        "pattern": "structured accessibility-tree browser control",
        "boundary": "read_only_until_explicit_approval",
    },
    "unclecode/crawl4ai": {
        "adopt_as": "approved_web_ingestion_adapter",
        "pattern": "LLM-friendly web crawling/extraction",
        "boundary": "untrusted_content_only",
    },
    "triggerdotdev/trigger.dev": {
        "adopt_as": "durable_job_pattern",
        "pattern": "retries, long-running jobs, checkpoints",
        "boundary": "lab_only_until_evaluated",
    },
    "obra/superpowers": {
        "adopt_as": "engineering_skill_layer",
        "pattern": "brainstorming, plans, TDD, parallel agents, review, verification",
        "boundary": "process guidance, not data authority",
    },
    "langchain-ai/open_deep_research": {
        "adopt_as": "research_pattern_reference",
        "pattern": "deep research planning and evidence gathering",
        "boundary": "research outputs remain advisory",
    },
}


def get_repo_pattern(repo: str) -> dict[str, Any] | None:
    return REPO_PATTERNS.get(repo)
