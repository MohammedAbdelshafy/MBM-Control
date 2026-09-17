"""FastMCP Adapter for JARVIS Ecosystem.

Exposes MCP_SERVER mapping JARVIS capabilities to FastMCP endpoints with fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional


class FastMCPAdapter:
    """
    Adapter for PrefectHQ/fastmcp.
    Exposes MCP_SERVER mapping JARVIS capabilities to FastMCP endpoints.
    """
    def __init__(self, server_url: str):
        if not server_url:
            raise ValueError("FastMCPAdapter requires a non-empty server_url.")
        self.server_url = server_url

    def call_tool(self, tool_name: str, args: Dict[str, Any], approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._verify_mcp_approval(tool_name=tool_name, approval=approval)
        raise NotImplementedError(
            "FastMCP transport is not implemented without active provider transport. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _verify_mcp_approval(self, tool_name: str, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            f"call fastmcp tool {tool_name}",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied FastMCP tool call: {decision.reason}")
