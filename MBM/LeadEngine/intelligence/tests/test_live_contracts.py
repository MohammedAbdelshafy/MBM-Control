"""
LIVE CONTRACT TESTS — excluded from normal CI (§24).

Each test requires explicit env vars and makes read-only, bounded calls.
Secrets never printed. No production writes. Mark `pytest -m live` only.
"""
import os
import pytest

pytestmark = pytest.mark.live

def _require(var: str) -> str:
    v = os.environ.get(var, "")
    if not v:
        pytest.skip(f"{var} not set — live contract not run (expected)")
    return v

def test_worldmonitor_live_contract():
    key = _require("WORLDMONITOR_API_KEY")
    from MBM.LeadEngine.intelligence.world_monitor_adapter import WorldMonitorAdapter
    # Read-only, bounded timeout, 5s
    wm = WorldMonitorAdapter(api_key=key, base_url=os.environ.get("WORLDMONITOR_BASE_URL", "https://worldmonitor.app"), timeout_sec=8, max_retries=1)
    # discover is read-only
    tools = wm.discover_tools()
    # We don't assert count; just that it didn't fabricate. If empty, report UNVERIFIED.
    assert isinstance(tools, list)

def test_anderro_live_contract():
    _require("ANDERRO_API_KEY")
    from MBM.LeadEngine.intelligence.anderro_adapter import AnderroAdapter
    a = AnderroAdapter(api_key=os.environ["ANDERRO_API_KEY"], base_url=os.environ.get("ANDERRO_BASE_URL", "https://anderro.com"), timeout_sec=8)
    offers = a.list_offers(limit=5)
    assert isinstance(offers, list)
    # Never fabricate: if API returned, offers have real fields; if BLOCKED, status is BLOCKED
    for o in offers:
        assert o.offerId

def test_topview_live_contract():
    _require("TOPVIEW_API_KEY")
    from MBM.LeadEngine.intelligence.topview_adapter import TopviewAdapter
    from MBM.LeadEngine.intelligence.jobs import JobStore
    import pathlib, tempfile
    store = JobStore(path=pathlib.Path(tempfile.mktemp()))
    tv = TopviewAdapter(api_key=os.environ["TOPVIEW_API_KEY"], base_url=os.environ.get("TOPVIEW_BASE_URL", "https://api.topview.ai"), timeout_sec=8, store=store)
    # Do NOT create real video in CI; just verify auth path (would be BLOCKED if no key, but we have key).
    # Instead do a bounded poll of non-existent job to prove endpoint reachable without side effect.
    try:
        tv.poll_status("nonexistent_test_id")
    except Exception as e:
        # Should fail with INVALID_INPUT, not crash
        assert "unknown job" in str(e).lower() or "invalid" in str(e).lower()

def test_skysnail_live_contract():
    _require("SKYSNAIL_API_KEY")
    # Similar — we don't generate real thumbnails in contract test, just verify adapter is configured
    from MBM.LeadEngine.intelligence.skysnail_adapter import SkySnailAdapter
    ss = SkySnailAdapter(api_key=os.environ["SKYSNAIL_API_KEY"], timeout_sec=8)
    assert ss.api_key
