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
    ]


def skill_names() -> list[str]:
    return [s.skill for s in build_skill_registry()]
