from MBM.GLM.agent_registry import GLMRole
from MBM.GLM.intelligence_team import build_team_plan, rank_team_missions, create_revenue_mission


def test_team_plan_is_fail_closed():
    plan = build_team_plan("build a smarter GitHub revenue and lead team")
    assert plan.approval_required is True
    assert plan.authoritative_writes is False
    assert plan.parallel_safe is True
    assert GLMRole.ORCHESTRATOR.value in plan.selected_roles
    assert GLMRole.RESEARCH_AGENT.value in plan.selected_roles
    assert GLMRole.GTM_ENGINEER.value in plan.selected_roles
    assert GLMRole.SECURITY_ENGINEER.value in plan.selected_roles


def test_revenue_mission_uses_deep_route():
    mission = create_revenue_mission(
        "TEAM-001",
        "Qualify new revenue signals",
        "MBM/LeadEngine",
        ["MBM/LeadEngine"],
        GLMRole.GTM_ENGINEER,
    )
    assert mission.routing_tier.value == "DEEP_GLM"
    assert mission.category == "GTM_REVENUE"


def test_team_ranking_is_deterministic():
    missions = [
        create_revenue_mission(
            "TEAM-LOW",
            "Lower impact",
            "MBM/LeadEngine",
            ["MBM/LeadEngine"],
            GLMRole.DATA_ENGINEER,
            business_impact=7.0,
            revenue_impact=7.0,
            probability_of_success=0.9,
            urgency=3.0,
        ),
        create_revenue_mission(
            "TEAM-HIGH",
            "Higher impact",
            "MBM/LeadEngine",
            ["MBM/LeadEngine"],
            GLMRole.GTM_ENGINEER,
            business_impact=10.0,
            revenue_impact=10.0,
            probability_of_success=0.95,
            urgency=5.0,
        ),
    ]
    ranked = rank_team_missions(missions)
    assert [m.mission_id for m in ranked] == ["TEAM-HIGH", "TEAM-LOW"]
