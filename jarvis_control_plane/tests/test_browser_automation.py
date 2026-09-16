"""BROWSER_AUTOMATION proofs (Slice 1: Playwright).

Hermetic: injected stub fetchers only — no network, no browser, no creds.
Proves: exact/suffix allowlist, suffix-spoof rejection, unlisted rejection,
non-http rejection, READ classification (no approval needed), truncation,
timeout error_kind for bus retries, adapter/bus allowlist parity.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_control_plane import build_capability_bus
from jarvis_control_plane import policy as P
from jarvis_control_plane.capabilities import (
    BROWSER_ALLOWED_DOMAINS,
    browser_navigate_extract,
)

ADAPTER_PATH = (
    ROOT / "MBM" / "Scripts" / "adapters" / "playwright_adapter.py"
)


def _load_adapter_module():
    spec = importlib.util.spec_from_file_location(
        "playwright_adapter_under_test", ADAPTER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_bus(monkeypatch=None):
    return build_capability_bus(
        browser_fetcher=lambda url: f"page-text for {url}"
    )


# -- allowlist ------------------------------------------------------------
def test_adapter_allows_exact_and_subdomain():
    mod = _load_adapter_module()
    adapter = mod.PlaywrightAdapter(fetcher=lambda url: "hello")
    out = adapter.extract("https://example.com/some/page")
    assert out["status"] == "success" and out["host"] == "example.com"
    sub = adapter.extract("https://sub.github.com/org/repo")
    assert sub["status"] == "success" and sub["host"] == "sub.github.com"


def test_adapter_rejects_suffix_spoof():
    mod = _load_adapter_module()
    adapter = mod.PlaywrightAdapter(fetcher=lambda url: "x")
    with pytest.raises(PermissionError):
        adapter.extract("https://example.com.evil.com/phish")
    with pytest.raises(PermissionError):
        adapter.extract("https://notgithub.com/")


def test_adapter_rejects_unlisted_domain():
    mod = _load_adapter_module()
    adapter = mod.PlaywrightAdapter(fetcher=lambda url: "x")
    with pytest.raises(PermissionError):
        adapter.extract("https://unlisted-bank.example.net/login")


def test_adapter_rejects_bad_shapes():
    mod = _load_adapter_module()
    adapter = mod.PlaywrightAdapter(fetcher=lambda url: "x")
    with pytest.raises(ValueError):
        adapter.extract("ftp://example.com/file")
    with pytest.raises(ValueError):
        adapter.extract("https://example.com/has space")
    with pytest.raises(ValueError):
        adapter.extract("")
    with pytest.raises(ValueError):
        adapter.extract("https://" + "a" * 3000 + ".example.com/")


def test_allowlist_parity_adapter_vs_bus():
    mod = _load_adapter_module()
    assert sorted(m.lower() for m in mod.PlaywrightAdapter.ALLOWED_DOMAINS) == sorted(
        d.lower() for d in BROWSER_ALLOWED_DOMAINS
    )


# -- bus wiring -----------------------------------------------------------
def test_bus_exposes_browser_tool_as_read_without_approval():
    bus = _stub_bus()
    assert "browser_navigate_extract" in bus.exposed_tools()
    tool = bus._tools["browser_navigate_extract"]
    assert tool.effective_class is P.ActionClass.READ
    out = bus.call("browser_navigate_extract", {"url": "https://example.com/"})
    assert out["status"] == "success"
    assert out["host"] == "example.com"
    assert "page-text" in out["content"]


def test_bus_rejects_off_allowlist_and_malformed():
    bus = _stub_bus()
    with pytest.raises(PermissionError):
        bus.call("browser_navigate_extract", {"url": "https://evil.example.com.evil.com/"})
    with pytest.raises(PermissionError):
        bus.call("browser_navigate_extract", {"url": "https://random-site.test/"})
    with pytest.raises(ValueError):
        bus.call("browser_navigate_extract", {})
    with pytest.raises(ValueError):
        bus.call("browser_navigate_extract", {"url": "javascript:alert(1)"})


def test_bus_denial_never_runs_fetcher():
    fired = []
    bus = build_capability_bus(
        browser_fetcher=lambda url: fired.append(url) or "must not run"
    )
    with pytest.raises(PermissionError):
        bus.call("browser_navigate_extract", {"url": "https://blocked.example.org/"})
    assert fired == []


def test_truncation_bounds_content():
    big = "x" * 25000
    out = browser_navigate_extract(
        {"url": "https://example.com/long"}, browser_fetcher=lambda url: big
    )
    assert out["truncated"] is True
    assert len(out["content"]) == 20000
    assert out["content_length"] == 25000


def test_timeout_maps_to_retryable_error_kind():
    def slow(url):
        raise TimeoutError("navigation timed out after 30000ms")

    mod = _load_adapter_module()
    adapter = mod.PlaywrightAdapter(fetcher=slow)
    with pytest.raises(RuntimeError) as excinfo:
        adapter.extract("https://example.com/slow")
    assert getattr(excinfo.value, "error_kind", None) == "timeout"
