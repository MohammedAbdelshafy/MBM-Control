"""
Security helpers — input sanitization, SSRF guards, prompt-injection defense (§12).

External content is UNTRUSTED DATA, never instructions.
"""
from __future__ import annotations

import re
from typing import Any

# Patterns that look like prompt injection — flagged as DATA, never executed
INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disable\s+safety",
    r"expose\s+api\s+keys?",
    r"bypass\s+policy",
    r"write\s+this\s+directly\s+into\s+the\s+lead\s+database",
    r"publish\s+this\s+immediately",
    r"system\s*:\s*you\s+are",
    r"\[INST\]",
    r"disable\s+kill\s+switch",
    r"exfiltrate",
]

_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

def contains_injection(text: str) -> bool:
    if not text:
        return False
    return bool(_INJECTION_RE.search(text))

def sanitize_external_text(text: str, *, max_len: int = 4000) -> str:
    """
    Treat external text as DATA: truncate, strip control chars, never interpret.
    Returns sanitized string; caller must store original rawReference separately.
    """
    if not isinstance(text, str):
        text = str(text)
    # Remove control chars except newline/tab
    text = "".join(c for c in text if c == "\n" or c == "\t" or ord(c) >= 32)
    if len(text) > max_len:
        text = text[:max_len] + "…[truncated]"
    return text

def assert_no_instruction_override(payload: dict) -> None:
    """
    Regression helper: verify that no external payload can set internal flags.
    Raises if payload tries to inject feature flag / secret / command.
    """
    forbidden_keys = {"INTELLIGENCE_ENABLED", "VOXCPM_ENABLED", "API_KEY", "SECRET", "exec", "eval", "__import__"}
    for key in payload:
        if key in forbidden_keys or key.startswith("__"):
            raise ValueError(f"External payload attempted to set forbidden key: {key}")
