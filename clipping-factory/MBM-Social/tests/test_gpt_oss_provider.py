"""Hermetic tests for GPT-OSS local provider routing."""
from __future__ import annotations

from mbm_social import model_registry as mr

def test_gpt_oss_is_selected_when_configured(monkeypatch):
    monkeypatch.setattr(mr, "GPT_OSS_BASE", "http://127.0.0.1:11434")
    monkeypatch.setattr(mr, "GPT_OSS_MODEL", "gpt-oss:20b")
    monkeypatch.setattr(mr, "STRONGEST_REASONING", "gpt-oss:20b")
    monkeypatch.setattr(mr, "TASK_MODELS", {"strategy": ["gpt-oss:20b", "qwen2.5-coder:7b"]})
    monkeypatch.setattr(mr, "_AVAIL", set())
    captured = {}
    def transport(**kwargs):
        captured.update(kwargs)
        return "verified-response"
    result = mr.generate("test", task="strategy", transport=transport)
    assert result == "verified-response"
    assert captured["model"] == "gpt-oss:20b"

def test_gpt_oss_is_not_selected_without_endpoint(monkeypatch):
    monkeypatch.setattr(mr, "GPT_OSS_BASE", "")
    monkeypatch.setattr(mr, "GPT_OSS_MODEL", "gpt-oss:20b")
    monkeypatch.setattr(mr, "TASK_MODELS", {"strategy": ["gpt-oss:20b", "qwen2.5-coder:7b"]})
    monkeypatch.setattr(mr, "_AVAIL", {"qwen2.5-coder:7b"})
    assert mr.resolve("strategy") == "qwen2.5-coder:7b"

def test_gpt_oss_response_parser_is_empty_on_missing_choices(monkeypatch):
    monkeypatch.setattr(mr, "GPT_OSS_BASE", "http://127.0.0.1:9")
    import json
    from unittest.mock import patch
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({'choices': []}).encode()
    with patch('urllib.request.urlopen', return_value=FakeResponse()):
        assert mr._gpt_oss_generate("gpt-oss:20b", "x") is None