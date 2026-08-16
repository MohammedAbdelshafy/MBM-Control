#!/usr/bin/env python3
"""
GLM Swarm Agent Registry
========================
Defines the 16 specialized GLM agents, their capabilities, and model routing tiers.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ModelRoutingTier(str, Enum):
    LIGHT = "LIGHT"          # Groq Llama-3.3-70B / Fast Classification / Formatting / Tagging
    MEDIUM = "MEDIUM"        # Gemini 2.5 Flash / Standard Code Edits / Tests / Refactoring
    DEEP_GLM = "DEEP_GLM"    # GLM-5.2 / Deep Reasoning / Architecture / Cross-Repo / Concurrency Races


class GLMRole(str, Enum):
    ARCHITECT = "GLM_ARCHITECT"
    CODE_REVIEWER = "GLM_CODE_REVIEWER"
    TEST_ENGINEER = "GLM_TEST_ENGINEER"
    RELIABILITY_ENGINEER = "GLM_RELIABILITY_ENGINEER"
    SECURITY_ENGINEER = "GLM_SECURITY_ENGINEER"
    PERFORMANCE_ENGINEER = "GLM_PERFORMANCE_ENGINEER"
    GTM_ENGINEER = "GLM_GTM_ENGINEER"
    SOCIAL_ENGINEER = "GLM_SOCIAL_ENGINEER"
    DIALER_ENGINEER = "GLM_DIALER_ENGINEER"
    MONETIZATION_ENGINEER = "GLM_MONETIZATION_ENGINEER"
    CONSTRUCTION_ENGINEER = "GLM_CONSTRUCTION_ENGINEER"
    DATA_ENGINEER = "GLM_DATA_ENGINEER"
    DEVOPS_ENGINEER = "GLM_DEVOPS_ENGINEER"
    DOCUMENTATION_ENGINEER = "GLM_DOCUMENTATION_ENGINEER"
    INTEGRATION_ENGINEER = "GLM_INTEGRATION_ENGINEER"
    REVENUE_ANALYST = "GLM_REVENUE_ANALYST"
    ORCHESTRATOR = "GLM_ORCHESTRATOR"


class AgentSpec(BaseModel):
    role: GLMRole
    name: str
    description: str
    preferred_tier: ModelRoutingTier
    capabilities: List[str]
    read_only_by_default: bool = False


AGENT_REGISTRY: Dict[GLMRole, AgentSpec] = {
    GLMRole.ARCHITECT: AgentSpec(
        role=GLMRole.ARCHITECT,
        name="GLM Master Architect",
        description="Analyzes cross-repo system architecture, maps dependencies, detects duplicates and structural bottlenecks.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["dependency_mapping", "duplication_detection", "architectural_refactoring", "boundary_enforcement"],
    ),
    GLMRole.CODE_REVIEWER: AgentSpec(
        role=GLMRole.CODE_REVIEWER,
        name="GLM Code Reviewer",
        description="Performs rigorous diff reviews, detects bugs, race conditions, brittle logic, and dead code.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["diff_analysis", "bug_detection", "race_condition_check", "dead_code_audit"],
    ),
    GLMRole.TEST_ENGINEER: AgentSpec(
        role=GLMRole.TEST_ENGINEER,
        name="GLM Test Engineer",
        description="Expands unit & integration coverage, fixes flaky tests, validates production runtime contracts.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["test_generation", "flaky_test_repair", "regression_verification", "contract_testing"],
    ),
    GLMRole.RELIABILITY_ENGINEER: AgentSpec(
        role=GLMRole.RELIABILITY_ENGINEER,
        name="GLM Reliability Engineer",
        description="Detects concurrency races, process collisions, data corruption, stale caches, and background conflicts.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["race_detection", "single_writer_enforcement", "lock_auditing", "cache_invalidation"],
    ),
    GLMRole.SECURITY_ENGINEER: AgentSpec(
        role=GLMRole.SECURITY_ENGINEER,
        name="GLM Security Engineer",
        description="Audits .env leaks, API credentials, auth bypass, injection risks, and private data protection.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["secret_detection", "auth_audit", "injection_prevention", "hipaa_compliance_check"],
    ),
    GLMRole.PERFORMANCE_ENGINEER: AgentSpec(
        role=GLMRole.PERFORMANCE_ENGINEER,
        name="GLM Performance Engineer",
        description="Identifies slow code, duplicate API calls, expensive workflows, DB indexing issues, and token waste.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["latency_optimization", "model_call_caching", "payload_reduction", "database_query_tuning"],
    ),
    GLMRole.GTM_ENGINEER: AgentSpec(
        role=GLMRole.GTM_ENGINEER,
        name="GLM GTM Revenue Engineer",
        description="Manages 100+ daily lead factory, buyer hunting, outreach campaigns, and revenue attribution.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["lead_discovery", "intent_ranking", "outreach_generation", "meeting_attribution"],
    ),
    GLMRole.SOCIAL_ENGINEER: AgentSpec(
        role=GLMRole.SOCIAL_ENGINEER,
        name="GLM Social Content Engineer",
        description="Integrates MBM-Social, content DNA, viral hook extraction, auto-publishing, and social-to-GTM handoff.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["content_dna_extraction", "viral_hook_generation", "engagement_analysis", "social_gtm_bridge"],
    ),
    GLMRole.DIALER_ENGINEER: AgentSpec(
        role=GLMRole.DIALER_ENGINEER,
        name="GLM Dialer Engineer",
        description="Maintains MBM Dialer, dual-lane calling (Sellers + AI Buyers), identity verification, and runtime sync.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["dialer_lane_routing", "script_optimization", "identity_gate_enforcement", "single_writer_sync"],
    ),
    GLMRole.MONETIZATION_ENGINEER: AgentSpec(
        role=GLMRole.MONETIZATION_ENGINEER,
        name="GLM Monetization Engineer",
        description="Packages high-converting AI offers, validates Neteller checkout rails, and optimizes pricing.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["offer_architecture", "neteller_rail_validation", "pricing_tiering", "conversion_optimization"],
    ),
    GLMRole.CONSTRUCTION_ENGINEER: AgentSpec(
        role=GLMRole.CONSTRUCTION_ENGINEER,
        name="GLM ConTech Engineer",
        description="Maintains BOQ estimator, DXF/CAD takeoff parsers, and construction AI agency retainers.",
        preferred_tier=ModelRoutingTier.MEDIUM,
        capabilities=["boq_estimation", "cad_takeoff", "masterformat_cost_matrix", "construction_retainers"],
    ),
    GLMRole.DATA_ENGINEER: AgentSpec(
        role=GLMRole.DATA_ENGINEER,
        name="GLM Data Engineer",
        description="Ensures canonical deal memory, schema migrations, entity deduplication, and historical exclusion ledgers.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["canonical_memory_sync", "schema_validation", "global_dedupe", "ledger_reconciliation"],
    ),
    GLMRole.DEVOPS_ENGINEER: AgentSpec(
        role=GLMRole.DEVOPS_ENGINEER,
        name="GLM DevOps Engineer",
        description="Manages Docker stacks, background daemons, git sync, environment integrity, and runtime health.",
        preferred_tier=ModelRoutingTier.LIGHT,
        capabilities=["docker_management", "process_monitoring", "git_synchronization", "daemon_scheduling"],
    ),
    GLMRole.DOCUMENTATION_ENGINEER: AgentSpec(
        role=GLMRole.DOCUMENTATION_ENGINEER,
        name="GLM Documentation Engineer",
        description="Generates executive briefings, API specs, runbooks, architecture diagrams, and onboarding guides.",
        preferred_tier=ModelRoutingTier.LIGHT,
        capabilities=["markdown_generation", "api_doc_sync", "runbook_maintenance", "briefing_formatting"],
    ),
    GLMRole.INTEGRATION_ENGINEER: AgentSpec(
        role=GLMRole.INTEGRATION_ENGINEER,
        name="GLM Integration Engineer",
        description="Enforces cross-repo contracts, event buses, shared schema adapters, and webhook routing.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["contract_verification", "event_bus_wiring", "schema_adapters", "cross_repo_sync"],
    ),
    GLMRole.REVENUE_ANALYST: AgentSpec(
        role=GLMRole.REVENUE_ANALYST,
        name="GLM Revenue Analyst",
        description="Reconciles pipeline vs expected value vs confirmed revenue with 100% evidence-backed integrity.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["revenue_reconciliation", "deal_tracking", "pipeline_forecasting", "attribution_audit"],
    ),
    GLMRole.ORCHESTRATOR: AgentSpec(
        role=GLMRole.ORCHESTRATOR,
        name="GLM Master Orchestrator",
        description="Coordinates swarm execution, selects high-value missions, enforces file locks, and manages regression gates.",
        preferred_tier=ModelRoutingTier.DEEP_GLM,
        capabilities=["mission_planning", "concurrency_locking", "verification_gating", "executive_reporting"],
    ),
}


def get_agent(role: GLMRole) -> AgentSpec:
    return AGENT_REGISTRY[role]
