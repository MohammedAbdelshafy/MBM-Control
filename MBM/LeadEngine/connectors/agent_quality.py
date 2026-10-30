"""Deterministic quality gates for autonomous provider operations.

These checks replace routine human approval prompts for bounded agent work.
They do not replace legal/provider terms, suppression obligations, or external
connectors' mandatory consent requirements.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence


DEFAULT_REQUIRED_CHECKS = (
    "capability_match",
    "evidence_provenance",
    "identity_confidence",
    "duplicate_check",
    "suppression_check",
    "privacy_scope_check",
)
CONTACT_REQUIRED_CHECKS = (
    "contact_scope_check",
    "lawful_basis_check",
    "business_channel_verification",
)


@dataclass(frozen=True)
class AgentQualityAssessment:
    passed: bool
    score: float
    required_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]
    missing_checks: tuple[str, ...]


def assess_agent_operation(
    checks: Mapping[str, bool],
    *,
    require_contact_scope: bool = False,
    required_checks: Optional[Sequence[str]] = None,
) -> AgentQualityAssessment:
    """Require every applicable deterministic check to pass.

    Missing, non-boolean, or false checks fail closed. A numerical score is
    reported for diagnostics; it never overrides a failed mandatory check.
    """
    if not isinstance(checks, Mapping):
        raise TypeError("checks must be a mapping")

    required = tuple(required_checks or DEFAULT_REQUIRED_CHECKS)
    if require_contact_scope:
        required = tuple(dict.fromkeys((*required, *CONTACT_REQUIRED_CHECKS)))
    if not required:
        raise ValueError("at least one required quality check is needed")

    missing = tuple(
        name for name in required
        if name not in checks or type(checks[name]) is not bool
    )
    failed = tuple(
        name for name in required
        if name in checks and type(checks[name]) is bool and checks[name] is False
    )
    passed_count = sum(
        1 for name in required
        if name in checks and type(checks[name]) is bool and checks[name] is True
    )
    score = passed_count / len(required)
    return AgentQualityAssessment(
        passed=not missing and not failed,
        score=score,
        required_checks=required,
        failed_checks=failed,
        missing_checks=missing,
    )
