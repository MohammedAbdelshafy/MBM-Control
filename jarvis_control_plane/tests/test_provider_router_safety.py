"""Regression tests for provider router execution truth and fail-closed safety."""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_control_plane import provider_router


def test_provider_router_unconfigured_when_registry_absent(monkeypatch):
    # When registry data files do not exist or are empty
    monkeypatch.setattr(provider_router, "load_registry", lambda: [])
    result = provider_router.resolve("Test mission", ["terminal_agent"])
    assert result["status"] == "UNCONFIGURED"
    assert "absent" in result["reason"].lower() or "unconfigured" in result["reason"].lower()


def test_provider_router_does_not_claim_verified_on_match(monkeypatch):
    mock_providers = [
        {
            "provider_id": "test_provider",
            "status": "ADOPT",
            "capabilities": ["test_cap"],
            "approval_required": False,
            "revenue_leverage": "HIGH",
            "integration_cost": "LOW",
            "maintenance_confidence": "HIGH",
        }
    ]
    monkeypatch.setattr(provider_router, "load_registry", lambda: mock_providers)
    result = provider_router.resolve("Test mission", ["test_cap"])
    assert result["status"] == "RESOLVED"
    assert result["status"] != "VERIFIED"
    assert result["best_provider"]["provider_id"] == "test_provider"


def test_provider_router_fails_on_missing_capabilities(monkeypatch):
    mock_providers = [
        {
            "provider_id": "test_provider",
            "status": "ADOPT",
            "capabilities": ["test_cap"],
            "approval_required": False,
        }
    ]
    monkeypatch.setattr(provider_router, "load_registry", lambda: mock_providers)
    result = provider_router.resolve("Test mission", ["nonexistent_cap"])
    assert result["status"] == "FAILED"
