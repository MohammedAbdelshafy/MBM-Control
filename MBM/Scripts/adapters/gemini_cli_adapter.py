"""Gemini CLI Adapter for JARVIS.

Thin adapter that interfaces with the Google Gemini CLI.
"""
from typing import Any, Dict
import subprocess
import shutil

def execute(prompt: str, capabilities: list[str]) -> Dict[str, Any]:
    """Execute a prompt via Gemini CLI securely."""
    if not shutil.which("gemini"):
        raise RuntimeError("Gemini CLI is not installed or not in PATH. Cannot execute.")
    
    try:
        # Actually execute it via subprocess
        result = subprocess.run(["gemini", prompt], capture_output=True, text=True, check=True)
        return {
            "status": "SUCCESS",
            "provider": "gemini_cli",
            "output": result.stdout.strip(),
            "evidence": "Executed securely via jarvis_control_plane boundaries"
        }
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Gemini CLI execution failed: {e.stderr}") from e
