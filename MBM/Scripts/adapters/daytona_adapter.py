"""Daytona Adapter for JARVIS Ecosystem.

Exposes CODE_EXECUTION sandbox environment with fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional


class DaytonaAdapter:
    """
    Adapter for daytonaio/daytona.
    Exposes CODE_EXECUTION sandbox environment via API/SDK.
    """
    def __init__(self, workspace_id: str):
        if not workspace_id:
            raise ValueError("DaytonaAdapter requires a non-empty workspace_id.")
        self.workspace_id = workspace_id

    def execute_code(self, code: str, language: str = "python", approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._verify_mcp_approval(approval=approval)
        raise NotImplementedError(
            "Daytona transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            f"execute daytona code in workspace {self.workspace_id}",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied Daytona execution: {decision.reason}")
