"""Factory skills/workflows registry (reusable engineering workflows).

Each skill is a deterministic checklist routed to Factory stages.
Skills propose; deterministic code still owns policy/state/scoring/
validation/evidence/gates. Skills never grant authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FactorySkill:
    skill: str
    factory_use: str
    trigger: str
    verification: str
    stages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_skill_registry() -> list[FactorySkill]:
    return [
        FactorySkill(
            skill="brainstorming_design_gate",
            factory_use="Classify work, establish intent, define design; require approval before architectural implementation.",
            trigger="new opportunity / ambiguous scope",
            verification="design doc + approval record before BUILD",
            stages=["DISCOVER", "RESEARCH", "STRATEGY"],
        ),
        FactorySkill(
            skill="test_driven_development",
            factory_use="Tests before implementation for new functionality; deterministic fixtures; regression protection.",
            trigger="new validator/gate/capability",
            verification="failing test first, then passing suite + hermetic fixtures",
            stages=["BUILD", "QA"],
        ),
        FactorySkill(
            skill="systematic_debugging",
            factory_use="Reproduce, isolate, identify root cause, verify fix, prevent recurrence.",
            trigger="test or gate failure",
            verification="repro script + root-cause note + regression test",
            stages=["QA"],
        ),
        FactorySkill(
            skill="writing_plans",
            factory_use="Convert approved designs into executable implementation plans with dependencies and checkpoints.",
            trigger="approved design",
            verification="plan with explicit deps/checkpoints; no scope creep",
            stages=["STRATEGY", "BUILD"],
        ),
        FactorySkill(
            skill="parallel_execution",
            factory_use="Split genuinely independent work; avoid shared-state collisions; aggregate evidence before merge.",
            trigger="independent workstreams",
            verification="no shared-state writes; combined evidence reviewed",
            stages=["BUILD", "QA"],
        ),
        FactorySkill(
            skill="code_review",
            factory_use="Security, correctness, architecture, policy, regression review before integration.",
            trigger="pre-merge diff",
            verification="diff review + policy check + affected suite green",
            stages=["QA", "PACKAGE"],
        ),
        FactorySkill(
            skill="verification_before_completion",
            factory_use="Never claim completion without actual evidence: tests, CI, artifacts, Git state, release gates.",
            trigger="pre-completion",
            verification="executed test results + CI status + git evidence + gate results",
            stages=["QA", "RELEASE", "MEASURE"],
        ),
        FactorySkill(
            skill="worktree_branch_isolation",
            factory_use="Isolate risky or parallel work; preserve branch integrity.",
            trigger="risky/parallel change",
            verification="worktree/branch ancestry clean; no destructive reset",
            stages=["BUILD", "QA"],
        ),
        FactorySkill(
            skill="finishing_integration_workflow",
            factory_use="Ensure completed work has a clean merge/integration path; no abandoned partial branches.",
            trigger="ready to integrate",
            verification="focused commits + reviewable diff + PR linkage",
            stages=["PACKAGE", "RELEASE"],
        ),
        # GTM skills (separate entries, same canonical registry; no second registry).
        FactorySkill(
            skill="icp_definition",
            factory_use="Define ICP from market evidence with explicit criteria; never invent qualification data.",
            trigger="new vertical or offer",
            verification="criteria doc + scored sample against it",
            stages=["DISCOVER", "STRATEGY"],
        ),
        FactorySkill(
            skill="account_research",
            factory_use="Build evidence-backed company profiles with per-field provenance.",
            trigger="qualified account without profile",
            verification="profile fields each carry source + timestamp",
            stages=["RESEARCH"],
        ),
        FactorySkill(
            skill="prospect_qualification",
            factory_use="Apply deterministic qualification (production gate + verification + suppression).",
            trigger="new prospect batch",
            verification="QUALIFIED/DISQUALIFIED/NEEDS_REVIEW with reasons + evidence",
            stages=["SCORE"],
        ),
        FactorySkill(
            skill="lead_cleaning",
            factory_use="Normalize, verify, classify, dedupe, suppress via the canonical gate.",
            trigger="raw lead list",
            verification="cleaned.csv + summary.json + reason breakdown",
            stages=["SCORE"],
        ),
        FactorySkill(
            skill="evidence_verification",
            factory_use="Require source + timestamp + confidence before any claim travels downstream.",
            trigger="new claim or enrichment",
            verification="GtmEvidence records; empty claims rejected",
            stages=["RESEARCH", "QA"],
        ),
        FactorySkill(
            skill="offer_matching",
            factory_use="Map prospect problem to verified capability + offer + evidence via the revenue router.",
            trigger="qualified prospect without offer",
            verification="rail + reason + required assets recorded",
            stages=["STRATEGY"],
        ),
        FactorySkill(
            skill="outreach_writing",
            factory_use="Draft from verified fields only; banned claims fail closed; drafts stay pending review.",
            trigger="qualified prospect with matched offer",
            verification="draft + claims_used + evidence_ids; no banned patterns",
            stages=["STRATEGY", "BUILD"],
        ),
        FactorySkill(
            skill="objection_handling",
            factory_use="Answer objections only from attached evidence; say 'I don't know' otherwise.",
            trigger="OBJECTION response label",
            verification="reply cites evidence_ids or declines",
            stages=["MEASURE"],
        ),
        FactorySkill(
            skill="proposal_preparation",
            factory_use="Shape CRM/send proposals for approval; never execute consequential actions.",
            trigger="engaged prospect",
            verification="proposal artifact with executed:false + approval requirement",
            stages=["PACKAGE"],
        ),
        FactorySkill(
            skill="crm_hygiene",
            factory_use="Overlay proposals, dedupe, stage discipline; never mutate production CRM directly.",
            trigger="pipeline review or new activity",
            verification="overlay diff + approval record; production untouched",
            stages=["MEASURE", "LEARN"],
        ),
        FactorySkill(
            skill="pipeline_review",
            factory_use="Walk GtmState transitions; illegal moves fail closed; terminal moves need approval.",
            trigger="weekly review or stalled deal",
            verification="transition log with reasons + actors",
            stages=["MEASURE"],
        ),
        FactorySkill(
            skill="gtm_analytics",
            factory_use="Measure discovery→win from recorded events only; zero-fabrication dashboards.",
            trigger="measurement window close",
            verification="metrics traceable to event records",
            stages=["MEASURE", "LEARN"],
        ),
        FactorySkill(
            skill="competitive_research",
            factory_use="Collect competitor facts with provenance; no unsupported comparisons.",
            trigger="new competitor signal",
            verification="fact table with sources; comparisons evidence-backed",
            stages=["RESEARCH"],
        ),
        FactorySkill(
            skill="market_research",
            factory_use="Offline signal discovery → ranked opportunities with exclusions preserved.",
            trigger="new market question",
            verification="slice_a result + exclusions_preserved list",
            stages=["DISCOVER", "RESEARCH"],
        ),
    ]


def skill_names() -> list[str]:
    return [s.skill for s in build_skill_registry()]
