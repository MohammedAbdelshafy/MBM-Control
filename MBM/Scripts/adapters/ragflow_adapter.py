"""RagFlow Adapter for JARVIS Ecosystem.

Exposes RAG_ENGINE pointing to containerized REST APIs with fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional


class RagFlowAdapter:
    """
    Adapter for infiniflow/ragflow.
    Exposes RAG_ENGINE pointing to containerized REST APIs.
    """
    def __init__(self, api_url: str, api_key: str):
        if not api_url or not api_key:
            raise ValueError("RagFlowAdapter requires non-empty api_url and api_key.")
        self.api_url = api_url
        self.api_key = api_key

    def retrieve_context(self, query: str, approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._verify_mcp_approval(approval=approval)
        raise NotImplementedError(
            "RAGFlow transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            "retrieve context from ragflow",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied RagFlow retrieval: {decision.reason}")
