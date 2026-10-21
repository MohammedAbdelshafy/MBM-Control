from MBM.GLM.github_runtime_bridge import capability_status, playwright_command


def test_github_runtime_defaults_are_fail_closed():
    status = capability_status()
    assert all(not value["enabled"] for key, value in status.items() if isinstance(value, dict) and "enabled" in value)
    assert status["authoritative_writes"] is False
    assert status["jarvis_approval_required"] is True


def test_playwright_command_is_pinned():
    command = playwright_command()
    assert command[:2] == ["npx", "@playwright/mcp@0.0.82"]
    assert "--no-webmcp" in command
