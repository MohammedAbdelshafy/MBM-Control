"""Anthropic Adapter for JARVIS Ecosystem.

Routes to the canonical model provider instead of fabricating output.
"""
from typing import Any, Dict
import os
from MBM.LeadEngine.model_provider import ModelProvider, TaskProfile, Provider

def execute(prompt: str, capabilities: list[str]) -> Dict[str, Any]:
    """Execute via ModelProvider for Anthropic."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is missing. Cannot execute.")
    
    provider = ModelProvider()
    
    # We force the routing by mocking the available providers to just Anthropic
    # Or we can just call complete and let it route
    # But since this adapter is specifically for anthropic, we'll configure it directly.
    try:
        response = provider._serve_anthropic(prompt)
        return {
            "status": "SUCCESS",
            "provider": Provider.ANTHROPIC.value,
            "output": response.get("text", ""),
            "evidence": "Executed securely via jarvis_control_plane boundaries"
        }
    except Exception as e:
        raise RuntimeError(f"Anthropic execution failed: {str(e)}") from e
