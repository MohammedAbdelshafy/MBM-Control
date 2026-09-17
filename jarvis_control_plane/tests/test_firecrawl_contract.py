"""Hermetic contract tests for FirecrawlAdapter (P0 Real Transport).

Validates:
- Uncredentialed access denied (fail-closed)
- Hostname and scheme enforcement (no spoofing/traversal)
- Approval gate enforcement via JARVIS policy layer
- Mocked HTTP 200 payload deserialization
- Upstream HTTP errors and connection timeouts
"""

import pytest
import requests
from unittest.mock import Mock, patch
from MBM.Scripts.adapters.firecrawl_adapter import FirecrawlAdapter


def test_firecrawl_missing_api_key_fails_closed():
    adapter = FirecrawlAdapter(api_key=None)
    with pytest.raises(PermissionError, match="Firecrawl API key is required"):
        adapter.scrape_url("https://example.com", approval={"approved": True, "approver": "test_operator"})


@pytest.mark.parametrize("invalid_url, expected_err", [
    ("", ValueError),
    ("   ", ValueError),
    ("http://example.com/ bad whitespace", ValueError),
    ("ftp://example.com/file", ValueError),
    ("https://evil.com/page", PermissionError),
    ("https://example.com.evil.com/page", PermissionError),
    ("https://evil-example.com/page", PermissionError),
])
def test_firecrawl_whitelist_enforcement(invalid_url, expected_err):
    adapter = FirecrawlAdapter(api_key="fc_test_mock_token")
    with pytest.raises(expected_err):
        adapter.scrape_url(invalid_url, approval={"approved": True, "approver": "test_operator"})


def test_firecrawl_missing_approval_fails_closed():
    adapter = FirecrawlAdapter(api_key="fc_test_mock_token")
    with pytest.raises(PermissionError, match="Policy denied"):
        adapter.scrape_url("https://example.com", approval=None)


def test_firecrawl_successful_scrape_hermetic(monkeypatch):
    adapter = FirecrawlAdapter(api_key="fc_test_mock_token")
    mock_payload = {
        "success": True,
        "data": {
            "markdown": "# Example Domain\nThis domain is for illustrative examples in documents.",
            "metadata": {"title": "Example Domain", "statusCode": 200}
        }
    }

    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp)

    result = adapter.scrape_url(
        "https://example.com/page",
        approval={"approved": True, "approver": "test_operator"}
    )
    assert result == mock_payload
    assert result["data"]["metadata"]["statusCode"] == 200


def test_firecrawl_http_error_fails_closed(monkeypatch):
    adapter = FirecrawlAdapter(api_key="fc_test_mock_token")
    mock_resp = Mock()
    mock_resp.ok = False
    mock_resp.status_code = 502

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp)

    with pytest.raises(RuntimeError, match="Firecrawl scrape failed with HTTP 502"):
        adapter.scrape_url(
            "https://example.com",
            approval={"approved": True, "approver": "test_operator"}
        )


def test_firecrawl_timeout_fails_closed(monkeypatch):
    adapter = FirecrawlAdapter(api_key="fc_test_mock_token", timeout=5.0)

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "post", raise_timeout)

    with pytest.raises(RuntimeError, match="Firecrawl scrape timed out after 5.0s"):
        adapter.scrape_url(
            "https://example.com",
            approval={"approved": True, "approver": "test_operator"}
        )
