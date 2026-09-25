"""Tests for the Jarvis-managed multi-tool fabric."""
from MBM.GLM.capability_router import jarvis_capability_snapshot, route_capabilities, route_for_intent
from MBM.GLM.tool_fabric import (
    TOOL_FABRIC,
    provider_contract,
    safe_capability,
    tool_fabric_snapshot,
)


def test_all_requested_providers_present():
    providers = {item.provider for item in TOOL_FABRIC}
    expected = {
        "GitHub",
        "Firecrawl",
        "Higgsfield",
        "Creative_Claw",
        "Vercel",
        "AI_Vibe_Prospecting",
        "Clay",
        "Clipform",
        "Business_Helper",
        "OpenArt",
        "Microsoft_Outlook_Email",
        "Ace_Knowledge_Graph",
        "Atlassian_Rovo_Legacy",
    }
    assert expected <= providers


def test_no_connector_is_canonical_writer():
    assert all(not item.canonical_writer for item in TOOL_FABRIC)
    assert tool_fabric_snapshot()["canonical_writer_provider"] is None


def test_firecrawl_is_safe_read_only():
    assert safe_capability("Firecrawl", "search", mutation=False)
    assert not safe_capability("Firecrawl", "search", mutation=True)


def test_provider_contract_rejects_unknown_provider():
    try:
        provider_contract("UnknownProvider")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown provider should fail closed")


def test_outlook_is_approval_gated():
    contract = provider_contract("Microsoft_Outlook_Email")
    assert contract.requires_human_approval


def test_jarvis_routes_seo_to_semrush_and_firecrawl():
    route = route_for_intent("SEO")
    assert route.providers == ("Semrush", "Firecrawl")
    selected = route_capabilities("seo_market_intelligence")
    assert selected[0]["provider"] == "Semrush"
    assert selected[0]["allowed"] is True


def test_mutation_is_not_allowed_on_semrush():
    selected = route_capabilities("seo_market_intelligence", mutation=True)
    assert selected[0]["allowed"] is False


def test_snapshot_is_actionable():
    snapshot = jarvis_capability_snapshot()
    assert snapshot["controller"] == "Jarvis_GLM_orchestrator"
    assert snapshot["route_count"] >= 8
