"""Regression tests for adapter fail-closed execution truth invariants.

Proves:
1. Unimplemented adapters refuse execution with explicit NotImplementedError (never fake success or mock data).
2. Unapproved operations fail closed with PermissionError.
3. Missing credentials or unconfigured parameters fail closed (ValueError or PermissionError).
4. Firecrawl URL validation uses parsed hostname; substring spoofing, path/query bypasses,
   and unlisted domains are strictly rejected.
"""

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.Scripts.adapters.firecrawl_adapter import FirecrawlAdapter
from MBM.Scripts.adapters.daytona_adapter import DaytonaAdapter
from MBM.Scripts.adapters.dify_adapter import DifyAdapter
from MBM.Scripts.adapters.fastmcp_adapter import FastMCPAdapter
from MBM.Scripts.adapters.ragflow_adapter import RagFlowAdapter
from MBM.Scripts.adapters.langchain_adapter import LangChainAdapter
from MBM.Scripts.adapters.openhands_adapter import OpenHandsAdapter
from MBM.Scripts.adapters.scrapy_adapter import ScrapyAdapter
from MBM.Scripts.adapters import playwright_mcp_adapter


VALID_APPROVAL = {"approved": True, "approver": "security_officer"}


# ---------------------------------------------------------------------------
# Firecrawl Allowlist & Security Tests
# ---------------------------------------------------------------------------

def test_firecrawl_allows_exact_allowed_domain():
    adapter = FirecrawlAdapter(api_key="test-api-key")
    # _enforce_whitelist returns the parsed hostname
    host = adapter._enforce_whitelist("https://example.com/api/data")
    assert host == "example.com"
    host2 = adapter._enforce_whitelist("https://github.com/repo/test")
    assert host2 == "github.com"
    host3 = adapter._enforce_whitelist("https://zillow.com/homes")
    assert host3 == "zillow.com"


def test_firecrawl_allows_subdomain():
    adapter = FirecrawlAdapter(api_key="test-api-key")
    host = adapter._enforce_whitelist("https://api.github.com/v1/resource")
    assert host == "api.github.com"
    host2 = adapter._enforce_whitelist("https://www.zillow.com/homes")
    assert host2 == "www.zillow.com"
    host3 = adapter._enforce_whitelist("https://sub.example.com/page")
    assert host3 == "sub.example.com"


def test_firecrawl_rejects_substring_spoofing():
    adapter = FirecrawlAdapter(api_key="test-api-key")
    # Substring in path
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://malicious.com/example.com")
    # Substring in domain suffix
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://example.com.malicious.com/data")
    # Substring prefix
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://notexample.com/")
    # Substring in query param
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://evil.org/search?q=github.com")
    # Substring in fragment
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://attacker.io/#zillow.com")


def test_firecrawl_rejects_unlisted_domain():
    adapter = FirecrawlAdapter(api_key="test-api-key")
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://google.com")
    with pytest.raises(PermissionError):
        adapter._enforce_whitelist("https://bing.com/search")


def test_firecrawl_rejects_malformed_urls():
    adapter = FirecrawlAdapter(api_key="test-api-key")
    with pytest.raises(ValueError):
        adapter._enforce_whitelist("")
    with pytest.raises(ValueError):
        adapter._enforce_whitelist(None)
    with pytest.raises(ValueError):
        adapter._enforce_whitelist("ftp://example.com/file")
    with pytest.raises(ValueError):
        adapter._enforce_whitelist("https://example.com/with space")
    with pytest.raises(ValueError):
        adapter._enforce_whitelist("http:///empty-host")


def test_firecrawl_scrape_fails_without_credentials():
    adapter = FirecrawlAdapter(api_key=None)
    with pytest.raises(PermissionError) as exc:
        adapter.scrape_url("https://example.com", approval=VALID_APPROVAL)
    assert "API key" in str(exc.value)


def test_firecrawl_scrape_fails_without_approval():
    adapter = FirecrawlAdapter(api_key="valid-test-key")
    with pytest.raises(PermissionError) as exc:
        adapter.scrape_url("https://example.com", approval=None)
    assert "denied" in str(exc.value).lower() or "approval" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Unimplemented Provider Adapters Fail-Closed Tests
# ---------------------------------------------------------------------------

def test_daytona_fails_unconfigured():
    with pytest.raises(ValueError):
        DaytonaAdapter(workspace_id="")


def test_daytona_fails_without_approval():
    adapter = DaytonaAdapter(workspace_id="ws-123")
    with pytest.raises(PermissionError):
        adapter.execute_code("print(1)", approval=None)


def test_daytona_approved_raises_not_implemented():
    adapter = DaytonaAdapter(workspace_id="ws-123")
    with pytest.raises(NotImplementedError) as exc:
        adapter.execute_code("print(1)", approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_dify_fails_unconfigured():
    with pytest.raises(ValueError):
        DifyAdapter(api_url="", api_key="")


def test_dify_fails_without_approval():
    adapter = DifyAdapter(api_url="https://api.dify.ai", api_key="dify_mock_key_untrusted")
    with pytest.raises(PermissionError):
        adapter.run_workflow(workflow_id="wf-123", inputs={}, approval=None)


def test_dify_approved_raises_not_implemented():
    adapter = DifyAdapter(api_url="https://api.dify.ai", api_key="dify_mock_key_untrusted")
    with pytest.raises(NotImplementedError) as exc:
        adapter.run_workflow(workflow_id="wf-123", inputs={}, approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_fastmcp_fails_unconfigured():
    with pytest.raises(ValueError):
        FastMCPAdapter(server_url="")


def test_fastmcp_fails_without_approval():
    adapter = FastMCPAdapter(server_url="http://localhost:8000")
    with pytest.raises(PermissionError):
        adapter.call_tool(tool_name="test_tool", args={}, approval=None)


def test_fastmcp_approved_raises_not_implemented():
    adapter = FastMCPAdapter(server_url="http://localhost:8000")
    with pytest.raises(NotImplementedError) as exc:
        adapter.call_tool(tool_name="test_tool", args={}, approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_ragflow_fails_unconfigured():
    with pytest.raises(ValueError):
        RagFlowAdapter(api_url="", api_key="")


def test_ragflow_fails_without_approval():
    adapter = RagFlowAdapter(api_url="https://ragflow.example.com", api_key="test-key")
    with pytest.raises(PermissionError):
        adapter.retrieve_context(query="test query", approval=None)


def test_ragflow_approved_raises_not_implemented():
    adapter = RagFlowAdapter(api_url="https://ragflow.example.com", api_key="test-key")
    with pytest.raises(NotImplementedError) as exc:
        adapter.retrieve_context(query="test query", approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_langchain_fails_without_approval():
    adapter = LangChainAdapter()
    with pytest.raises(PermissionError):
        adapter.invoke_chain(prompt="test prompt", approval=None)


def test_langchain_approved_raises_not_implemented():
    adapter = LangChainAdapter()
    with pytest.raises(NotImplementedError) as exc:
        adapter.invoke_chain(prompt="test prompt", approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_openhands_fails_unconfigured():
    with pytest.raises(ValueError):
        OpenHandsAdapter(endpoint="")


def test_openhands_fails_without_approval():
    adapter = OpenHandsAdapter(endpoint="http://localhost:3000")
    with pytest.raises(PermissionError):
        adapter.submit_task(task_description="do work", approval=None)


def test_openhands_approved_raises_not_implemented():
    adapter = OpenHandsAdapter(endpoint="http://localhost:3000")
    with pytest.raises(NotImplementedError) as exc:
        adapter.submit_task(task_description="do work", approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_scrapy_fails_disallowed_domain():
    adapter = ScrapyAdapter(allowed_domains=["example.com"])
    with pytest.raises(PermissionError):
        adapter.run_spider("https://evil.com/example.com", dry_run=True, approval=VALID_APPROVAL)


def test_scrapy_fails_without_approval():
    adapter = ScrapyAdapter(allowed_domains=["example.com"])
    with pytest.raises(PermissionError):
        adapter.run_spider("https://example.com/items", dry_run=True, approval=None)


def test_scrapy_approved_raises_not_implemented():
    adapter = ScrapyAdapter(allowed_domains=["example.com"])
    with pytest.raises(NotImplementedError) as exc:
        adapter.run_spider("https://example.com/items", dry_run=True, approval=VALID_APPROVAL)
    assert "not implemented" in str(exc.value).lower()


def test_playwright_mcp_raises_not_implemented():
    with pytest.raises((NotImplementedError, RuntimeError)):
        playwright_mcp_adapter.execute("test", capabilities=["browser"])
