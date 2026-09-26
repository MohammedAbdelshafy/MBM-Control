"""GLM Intelligence Team: safe multi-agent coordination layer.

The team turns the existing GLM registry into a role-aware execution fabric.
External agent frameworks are treated as optional research inputs, never as
authoritative writers. Jarvis remains the final authority for mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier, get_agent
from MBM.GLM.mission_router import EngineeringMission, MissionRouter, MissionCategory
from MBM.GLM.github_runtime_bridge import capability_status


@dataclass(frozen=True)
class IntelligenceTeamMember:
    role: GLMRole
    mission_types: tuple[str, ...]
    read_only: bool
    veto_on: tuple[str, ...] = ()


@dataclass
class TeamPlan:
    objective: str
    selected_roles: list[str] = field(default_factory=list)
    routing_tier: str = ModelRoutingTier.DEEP_GLM.value
    external_runtime_hints: dict[str, Any] = field(default_factory=dict)
    approval_required: bool = True
    authoritative_writes: bool = False
    parallel_safe: bool = False


TEAM: tuple[IntelligenceTeamMember, ...] = (
    IntelligenceTeamMember(
        GLMRole.ORCHESTRATOR,
        ("mission_planning", "cross_repo_coordination"),
        False,
        ("conflicting_missions", "authority_boundary"),
    ),
    IntelligenceTeamMember(
        GLMRole.ARCHITECT,
        ("architecture", "dependency_mapping", "repo_adoption"),
        True,
        ("unsafe_boundary_change",),
    ),
    IntelligenceTeamMember(
        GLMRole.RESEARCH_AGENT,
        ("github_intelligence", "market_research", "source_discovery"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.RELIABILITY_ENGINEER,
        ("locks", "concurrency", "state_integrity"),
        True,
        ("single_writer_violation", "dataset_shrinkage"),
    ),
    IntelligenceTeamMember(
        GLMRole.SECURITY_ENGINEER,
        ("secrets", "ssrf", "auth", "untrusted_content"),
        True,
        ("secret_exposure", "ssrf", "auth_bypass"),
    ),
    IntelligenceTeamMember(
        GLMRole.DATA_ENGINEER,
        ("schema", "dedupe", "provenance", "canonical_memory"),
        True,
        ("provenance_gap", "canonical_corruption"),
    ),
    IntelligenceTeamMember(
        GLMRole.GTM_ENGINEER,
        ("lead_generation", "buyer_pipeline", "outreach"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.MONETIZATION_ENGINEER,
        ("offers", "checkout", "revenue_attribution"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.SOCIAL_ENGINEER,
        ("content", "analytics", "social_gtm"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.DIALER_ENGINEER,
        ("dialer", "identity", "calling"),
        True,
        ("caller_identity_violation",),
    ),
    IntelligenceTeamMember(
        GLMRole.CODE_REVIEWER,
        ("diff_review", "regression_risk"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.TEST_ENGINEER,
        ("tests", "verification"),
        True,
    ),
    IntelligenceTeamMember(
        GLMRole.QA_AGENT,
        ("output_qa", "hallucination_checks", "compliance"),
        True,
    ),
)


def _member(role: GLMRole) -> IntelligenceTeamMember:
    for member in TEAM:
        if member.role == role:
            return member
    raise KeyError(role)


def select_roles(objective: str) -> list[GLMRole]:
    """Deterministically select a compact specialist squad."""
    text = objective.lower()
    roles: list[GLMRole] = [GLMRole.ORCHESTRATOR, GLMRole.ARCHITECT]
    if any(k in text for k in ("github", "repo", "framework", "agent")):
        roles.append(GLMRole.RESEARCH_AGENT)
        roles.append(GLMRole.INTEGRATION_ENGINEER)
    if any(k in text for k in ("lead", "sales", "gtm", "buyer", "revenue", "money")):
        roles.extend([GLMRole.GTM_ENGINEER, GLMRole.MONETIZATION_ENGINEER])
    if any(k in text for k in ("dialer", "call", "phone", "identity")):
        roles.append(GLMRole.DIALER_ENGINEER)
    if any(k in text for k in ("social", "video", "clip", "content")):
        roles.append(GLMRole.SOCIAL_ENGINEER)
    if any(k in text for k in ("data", "lead", "database", "dedupe")):
        roles.append(GLMRole.DATA_ENGINEER)
    roles.extend([
        GLMRole.SECURITY_ENGINEER,
        GLMRole.RELIABILITY_ENGINEER,
        GLMRole.CODE_REVIEWER,
        GLMRole.TEST_ENGINEER,
        GLMRole.QA_AGENT,
    ])
    seen: set[GLMRole] = set()
    return [role for role in roles if not (role in seen or seen.add(role))]


def build_team_plan(objective: str) -> TeamPlan:
    roles = select_roles(objective)
    caps = capability_status()
    external_hints = {
        "github_adoption": {
            "langgraph": {
                "role": "research_only",
                "reason": "state-machine patterns can inform orchestration without becoming canonical runtime",
            },
            "google_adk": caps["google_adk"],
            "playwright_mcp": caps["playwright_mcp"],
            "crawl4ai": caps["crawl4ai"],
            "trigger_dev": caps["trigger_dev"],
        },
        "superpowers": {
            "status": "skill_layer_available",
            "mode": "planning_testing_review",
            "note": "Use the installed Superpowers skills for brainstorming, TDD, parallel work, review, and verification.",
        },
    }
    return TeamPlan(
        objective=objective,
        selected_roles=[role.value for role in roles],
        routing_tier=ModelRoutingTier.DEEP_GLM.value,
        external_runtime_hints=external_hints,
        approval_required=True,
        authoritative_writes=False,
        parallel_safe=True,
    )


def create_revenue_mission(
    mission_id: str,
    title: str,
    target_repo: str,
    target_paths: Iterable[str],
    role: GLMRole,
    *,
    business_impact: float = 9.0,
    revenue_impact: float = 9.0,
    probability_of_success: float = 0.9,
    urgency: float = 4.5,
) -> EngineeringMission:
    """Create a revenue-aware mission with safe defaults."""
    return EngineeringMission(
        mission_id=mission_id,
        title=title,
        target_repo=target_repo,
        target_paths=list(target_paths),
        category=MissionCategory.GTM_REVENUE,
        assigned_role=role,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=business_impact,
        revenue_impact=revenue_impact,
        probability_of_success=probability_of_success,
        urgency=urgency,
        problem_statement=(
            "Use the existing verified MBM systems to shorten the path from "
            "qualified signal to measurable revenue without bypassing data gates."
        ),
        recommended_fix=(
            "Run specialist analysis in parallel, reconcile through the orchestrator, "
            "then require verification and Jarvis approval before authoritative writes."
        ),
    )


def rank_team_missions(missions: Iterable[EngineeringMission]) -> list[EngineeringMission]:
    return MissionRouter.rank_missions(list(missions))
