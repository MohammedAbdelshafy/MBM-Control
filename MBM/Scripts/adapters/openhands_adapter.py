"""OpenHands Adapter for JARVIS Ecosystem.

Exposes AGENT_CANVAS for coding tasks with fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional


class OpenHandsAdapter:
    """
    Adapter for OpenHands/OpenHands.
    Exposes AGENT_CANVAS for coding tasks with secure command execution verification.
    """
    def __init__(self, endpoint: str):
        if not endpoint:
            raise ValueError("OpenHandsAdapter requires a non-empty endpoint.")
        self.endpoint = endpoint

    def submit_task(self, task_description: str, approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._verify_mcp_approval(approval=approval)
        raise NotImplementedError(
            "OpenHands transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            "submit openhands task",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied OpenHands execution: {decision.reason}")
