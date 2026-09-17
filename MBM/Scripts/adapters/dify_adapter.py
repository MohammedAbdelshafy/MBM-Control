"""Dify Adapter for JARVIS Ecosystem.

Exposes AGENT_WORKFLOWS connecting to Dify's APIs with fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional


class DifyAdapter:
    """
    Adapter for langgenius/dify.
    Exposes AGENT_WORKFLOWS connecting to Dify's APIs.
    """
    def __init__(self, api_url: str, api_key: str):
        if not api_url or not api_key:
            raise ValueError("DifyAdapter requires non-empty api_url and api_key.")
        self.api_url = api_url
        self.api_key = api_key

    def run_workflow(self, workflow_id: str, inputs: Dict[str, Any], approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._verify_mcp_approval(workflow_id=workflow_id, approval=approval)
        raise NotImplementedError(
            "Dify transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, workflow_id: str, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            f"run dify workflow {workflow_id}",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied Dify workflow: {decision.reason}")
