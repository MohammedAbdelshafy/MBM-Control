"""LangChain Adapter for JARVIS Ecosystem.

Wraps LLM wrappers and prevents arbitrary subprocess execution with fail-closed policy enforcement.
"""
from typing import List, Optional, Dict, Any


class LangChainAdapter:
    """
    Adapter for langchain-ai/langchain.
    Wraps LLM wrappers and prevents arbitrary subprocess execution.
    """
    def __init__(self, safe_tools: Optional[List[str]] = None):
        self.safe_tools = safe_tools or ["calculator", "search"]

    def invoke_chain(self, prompt: str, approval: Optional[Dict[str, Any]] = None) -> str:
        self._verify_mcp_approval(approval=approval)
        raise NotImplementedError(
            "LangChain transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            "invoke langchain chain",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied LangChain execution: {decision.reason}")
