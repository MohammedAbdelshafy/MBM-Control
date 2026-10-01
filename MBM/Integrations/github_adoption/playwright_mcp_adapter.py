from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaywrightMcpConfig:
    version: str
    package: str = "@playwright/mcp"
    webmcp_enabled: bool = False
    file_paths: str = "absolute"

    @classmethod
    def from_env(cls) -> "PlaywrightMcpConfig":
        return cls(
            version=os.getenv("PLAYWRIGHT_MCP_VERSION", "0.0.82"),
            webmcp_enabled=os.getenv("PLAYWRIGHT_MCP_WEBMCP", "false").lower() == "true",
            file_paths=os.getenv("PLAYWRIGHT_MCP_FILE_PATHS", "absolute"),
        )

    def command(self) -> list[str]:
        """Return a pinned command; never silently use @latest."""
        command = ["npx", f"{self.package}@{self.version}"]
        if not self.webmcp_enabled:
            command.append("--no-webmcp")
        if self.file_paths == "absolute":
            command.extend(["--file-paths=absolute"])
        return command

    def risk_policy(self) -> dict[str, str]:
        return {
            "browser_action_policy": "READ_ONLY_BY_DEFAULT",
            "write_actions": "REQUIRE_JARVIS_APPROVAL",
            "destructive_actions": "HUMAN_APPROVAL_REQUIRED",
            "webmcp": "DISABLED_BY_DEFAULT",
            "credential_scope": "DEDICATED_BROWSER_PROFILE_ONLY",
        }
