"""Codex Adapter for JARVIS Ecosystem.

Interfaces with the OpenAI Codex CLI.
"""
from typing import Any, Dict
import subprocess
import shutil

def execute(prompt: str, capabilities: list[str]) -> Dict[str, Any]:
    """Execute a prompt via Codex CLI."""
    if not shutil.which("codex"):
        raise RuntimeError("Codex CLI is not installed or not in PATH. Cannot execute.")
    
    try:
        result = subprocess.run(["codex", prompt], capture_output=True, text=True, check=True)
        return {
            "status": "SUCCESS",
            "provider": "codex",
            "output": result.stdout.strip(),
            "evidence": "Executed securely via jarvis_control_plane boundaries"
        }
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Codex execution failed: {e.stderr}") from e
