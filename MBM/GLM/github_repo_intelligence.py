"""Curated GitHub intelligence memory for the MBM GLM team.

External projects are pattern references or guarded adapters, never authorities.
Each entry records what to learn, how to use it, and the safety boundary.
"""

from __future__ import annotations
from typing import Any

REPO_PATTERNS: dict[str, dict[str, Any]] = {
    "langchain-ai/langgraph": {
        "adopt_as": "pattern_reference",
        "pattern": "stateful graph orchestration, checkpoints, durable state, deterministic routing, interrupt/resume",
        "boundary": "do_not_replace_glm_authority",
        "current_use": "mission graph/checkpoint design and human approval pauses",
        "enhancements": ["durable_mission_state", "resume_after_approval", "checkpoint_before_external_call"],
    },
    "google/adk-python": {
        "adopt_as": "optional_secondary_runtime",
        "pattern": "code-first agents, evaluation, sessions/state/memory/artifacts, callbacks, multi-agent collaboration",
        "boundary": "specialists_only; no canonical writes",
        "current_use": "sandboxed specialist runtime behind github_runtime_bridge",
        "enhancements": ["agent_eval_harness", "session_context", "pre_post_callbacks", "artifact_contracts"],
    },
    "microsoft/playwright-mcp": {
        "adopt_as": "approved_browser_adapter",
        "pattern": "structured browser control, isolated profiles, explicit permissions, configurable toolsets",
        "boundary": "read_only_until_explicit_approval",
        "current_use": "research/verification browser worker",
        "enhancements": ["isolated_profile", "browser_capability_allowlist", "screenshot_evidence", "action_audit"],
    },
    "unclecode/crawl4ai": {
        "adopt_as": "approved_web_ingestion_adapter",
        "pattern": "clean Markdown, structured extraction, deep crawl, adaptive crawl, hooks, caching, batch crawling",
        "boundary": "untrusted_content_only",
        "current_use": "source discovery metadata",
        "enhancements": ["adaptive_source_discovery", "schema_extractors", "cache_policy", "crawl_resume_state"],
    },
    "triggerdotdev/trigger.dev": {
        "adopt_as": "durable_job_pattern",
        "pattern": "durable AI workflows, retries, checkpoints, long-running jobs, orchestration",
        "boundary": "lab_only_until_evaluated",
        "current_use": "future durable worker experiments",
        "enhancements": ["idempotency_keys", "retry_policy", "concurrency_keys", "checkpointed_workers"],
    },
    "github/github-mcp-server": {
        "adopt_as": "github_control_plane_reference",
        "pattern": "toolsets, per-tool allowlists, exclusions, read-only mode, lockdown, scope filtering",
        "boundary": "never bypass repository authority or Jarvis approvals",
        "current_use": "design the MBM GitHub capability profile",
        "enhancements": ["read_only_profile", "tool_allowlist", "write_tool_exclusions", "lockdown_content_filter"],
    },
    "github/awesome-copilot": {
        "adopt_as": "agent_definition_pattern_reference",
        "pattern": "file-based custom agents, skills, instructions, hooks and workflows",
        "boundary": "copy patterns, inspect third-party content before adoption",
        "current_use": "shape reusable GLM role packs and project instructions",
        "enhancements": ["agent_role_manifests", "skill_bundles", "repo_local_instructions", "qa_agent_pack"],
    },
    "obra/superpowers": {
        "adopt_as": "engineering_skill_layer",
        "pattern": "brainstorming, plans, TDD, parallel work, review and verification",
        "boundary": "process_guidance_not_data_authority",
        "current_use": "planning/testing/review discipline",
        "enhancements": ["tdd_gate", "parallel_task_gate", "review_gate", "verification_before_completion"],
    },
    "langchain-ai/open_deep_research": {
        "adopt_as": "research_pattern_reference",
        "pattern": "deep research planning, source gathering and evidence synthesis",
        "boundary": "research_outputs_advisory",
        "current_use": "research-agent design",
        "enhancements": ["source_plan", "evidence_bundle", "claim_provenance", "research_stop_conditions"],
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
        "version": 2,
        "count": len(REPO_PATTERNS),
        "repos": sorted(REPO_PATTERNS),
        "authority": "Jarvis_GLM_orchestrator",
        "canonical_writes_allowed": False,
    }
