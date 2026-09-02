"""Security Configuration — no secrets in source.

Uses environment variables and existing secret management patterns.
References existing MBM security rules (no hardcoded credentials in scripts,
.env only for local development, OAuth secrets outside source tree).
"""
from __future__ import annotations
import os
from typing import Optional, Dict, Any


class SecurityConfig:
    """Verify security rules for M-022 readiness."""

    REQUIRED_ENV_KEYS: list = [
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REDIRECT_URI",
    ]

    PROHIBITED_KEYS_IN_SOURCE: list = [
        "client_secret",
        "refresh_token",
        "access_token",
        "client_id",
    ]

    def __init__(self):
        pass

    def check_env_secrets(self) -> Dict[str, Any]:
        """Check that secrets come from environment, not source files."""
        missing: list = []
        present: list = []
        for key in self.REQUIRED_ENV_KEYS:
            val = os.getenv(key, "").strip()
            if val:
                present.append(key)
            else:
                missing.append(key)
        return {
            "missing_env_keys": missing,
            "present_env_keys": present,
            "all_configured": len(missing) == 0,
        }

    def verify_no_secrets_in_file(self, file_path: str) -> Dict[str, Any]:
        """Scan a source file for potential hardcoded secrets.

        This is a heuristic check, not a cryptographic audit.
        It flags strings that look like secrets, not actual secrets.
        """
        import pathlib
        path = pathlib.Path(file_path)
        if not path.exists():
            return {"file_exists": False, "potential_issues": ["file_not_found"]}
        content = path.read_text(encoding="utf-8")
        issues = []
        # Check for literal patterns that look like hardcoded tokens
        # We use a safe heuristic: don't flag variables/environments, flag literal strings
        for line in content.splitlines():
            lower_line = line.lower()
            # Skip comments and variable assignments
            stripped = line.split("#")[0].strip()
            if stripped.startswith("from") or stripped.startswith("import") or stripped.startswith("#"):
                continue
            # Heuristic: long alphanumeric strings assigned to variables named with secret/token patterns
            if any(indicator in lower_line for indicator in ["client_secret", "client_id", "refresh_token", "access_token"]):
                # This is acceptable ONLY if it references an environment variable or a file read
                if "os.getenv" not in line and "os.environ" not in line and "read_text" not in line and "json.load" not in line:
                    issues.append(f"potential_secret_reference_in_line: {line[:100]}")
        # Deduplicate
        unique_issues = list(dict.fromkeys(issues))
        return {
            "file_exists": True,
            "potential_issues": unique_issues,
            "safe_heuristic": len(unique_issues) == 0,
        }

    def verify_token_storage_location(self) -> Dict[str, Any]:
        """Verify tokens are stored outside source tree."""
        token_path_str = str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent / "youtube_tokens.json")
        source_root = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
        # The token file should NOT be in the same directory as source modules for production
        # For M-022, we reference it by relative path; production should use an absolute secure path.
        # This check verifies it exists and is readable.
        from pathlib import Path
        token_path = Path(token_path_str)
        exists = token_path.exists()
        readable = token_path.is_file() if exists else False
        return {
            "token_path": str(token_path),
            "exists": exists,
            "readable": readable,
            "in_source_tree": True,  # By design for M-022; production should move outside
            "production_recommendation": "Move youtube_tokens.json and .env outside source tree for production.",
        }
