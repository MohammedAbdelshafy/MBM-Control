from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class ProductQualityContract:
    outcome_statement: str = ""
    proof_inventory: list[str] = field(default_factory=list)
    buyer_preview: str = ""
    usage_path: list[str] = field(default_factory=list)
    objection_map: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    qa_checks: list[str] = field(default_factory=list)
    claim_evidence_level: Literal[
        "hypothesis",
        "single_signal",
        "repeated_signal",
        "explicit_request",
        "observed_purchase",
        "repeat_purchase",
    ] = "hypothesis"


MINIMUM_LAUNCH_EVIDENCE = {
    "hypothesis": 9,
    "single_signal": 8,
    "repeated_signal": 7,
    "explicit_request": 6,
    "observed_purchase": 5,
    "repeat_purchase": 4,
}


def validate_quality_contract(contract: ProductQualityContract) -> list[str]:
    failures: list[str] = []
    if not contract.outcome_statement.strip():
        failures.append("missing_outcome_statement")
    if not contract.proof_inventory:
        failures.append("missing_proof_inventory")
    if not contract.buyer_preview.strip():
        failures.append("missing_buyer_preview")
    if not contract.usage_path:
        failures.append("missing_usage_path")
    if not contract.objection_map:
        failures.append("missing_objection_map")
    if not contract.limitations:
        failures.append("missing_limitations")
    if not contract.qa_checks:
        failures.append("missing_qa_checks")
    if MINIMUM_LAUNCH_EVIDENCE[contract.claim_evidence_level] > 6:
        failures.append("proof_evidence_below_launch_threshold")
    return failures
