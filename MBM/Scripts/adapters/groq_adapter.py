"""Groq Adapter for JARVIS Ecosystem.

Routes to the canonical model provider instead of fabricating output.
"""
from typing import Any, Dict
import os
from MBM.LeadEngine.model_provider import ModelProvider, Provider

def execute(prompt: str, capabilities: list[str]) -> Dict[str, Any]:
    """Execute via ModelProvider for Groq."""
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is missing. Cannot execute.")
    
    provider = ModelProvider()
    
    try:
        response = provider._serve_groq(prompt)
        return {
            "status": "SUCCESS",
            "provider": Provider.GROQ.value,
            "output": response.get("text", ""),
            "evidence": "Executed securely via jarvis_control_plane boundaries"
        }
    except Exception as e:
        raise RuntimeError(f"Groq execution failed: {str(e)}") from e
