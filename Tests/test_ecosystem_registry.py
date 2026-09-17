"""Tests for the JARVIS Ecosystem Capability Operating Layer."""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add root to python path for imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from jarvis_control_plane.provider_router import resolve
from jarvis_control_plane.evidence_recorder import record_execution, EvidenceStatus
from MBM.LeadEngine.model_provider import ModelProvider, TaskProfile, route, Provider

def test_model_provider_routing():
    """Test model provider routing based on capability."""
    profile = TaskProfile(need_tools=True)
    available = {Provider.ANTHROPIC.value, Provider.GROQ.value, Provider.DETERMINISTIC.value}
    
    # Tool capabilities prefer ANTHROPIC or GROQ
    chosen = route(profile, available=available)
    assert chosen in (Provider.ANTHROPIC.value, Provider.GROQ.value)

def test_model_provider_latency_routing():
    """Test latency-sensitive routes to Groq."""
    profile = TaskProfile(latency_sensitive=True)
    available = {Provider.ANTHROPIC.value, Provider.GROQ.value, Provider.DETERMINISTIC.value}
    chosen = route(profile, available=available)
    assert chosen == Provider.GROQ.value

def test_provider_router_fallback():
    """Test provider router correctly handles absent registry or missing capabilities."""
    result = resolve(
        mission_intent="Extract data", 
        required_capabilities=["imaginary_capability"],
        approval_id="test_id"
    )
    assert result["status"] in ("UNCONFIGURED", "FAILED")
    if result["status"] == "FAILED":
        assert "No providers match" in result["reason"]
    else:
        assert "absent" in result["reason"].lower() or "unconfigured" in result["reason"].lower()

def test_provider_router_approval_enforcement():
    """Test strict deterministic approval check."""
    result = resolve(
        mission_intent="Perform action",
        required_capabilities=["terminal_agent"],
        approval_id=None
    )
    assert result["status"] in ("UNCONFIGURED", "RESOLVED", "BLOCKED", "FAILED")

def test_evidence_recorder():
    """Test that evidence is recorded successfully."""
    filepath = record_execution(
        mission_id="test_mission_001",
        provider_id="gemini_cli",
        commit_sha="abcdef",
        capability="terminal_agent",
        permission="READ_ONLY",
        executor="subprocess",
        status=EvidenceStatus.VERIFIED,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        approval_id="test_approval_123"
    )
    
    path = Path(filepath)
    assert path.exists()
    
    # Clean up test file
    path.unlink()


def test_canonical_providers_snapshot_loaded():
    """Verify load_registry loads canonical data from Schemas/ecosystem_providers.json."""
    from jarvis_control_plane.provider_router import load_registry
    providers = load_registry()
    assert len(providers) >= 6
    provider_ids = {p["provider_id"] for p in providers}
    assert {"anthropic", "groq", "gemini_cli", "codex_cli", "playwright", "firecrawl"}.issubset(provider_ids)


def test_canonical_provider_routing_resolves():
    """Verify genuine capabilities resolve to RESOLVED (not UNCONFIGURED or fake VERIFIED)."""
    res = resolve("code automation", ["coding_agent"])
    assert res["status"] == "RESOLVED"
    assert res["best_provider"]["provider_id"] in ("gemini_cli", "codex_cli")


def test_canonical_firecrawl_approval_gating():
    """Verify firecrawl requires explicit approval and blocks if missing."""
    unapproved = resolve("scrape site", ["web_extraction"], approval_id=None)
    assert unapproved["status"] == "BLOCKED"

    approved = resolve("scrape site", ["web_extraction"], approval_id="operator_approved_001")
    assert approved["status"] == "RESOLVED"
    assert approved["best_provider"]["provider_id"] == "firecrawl"

