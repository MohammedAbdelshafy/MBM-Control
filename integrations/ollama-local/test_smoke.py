#!/usr/bin/env python3
"""Hermetic smoke tests for ollama-local (VibeFounder power #7).

No network beyond localhost, no Ollama install, no keys. A fake Ollama
HTTP server (threaded stdlib http.server) answers:
  GET  /api/tags
  POST /v1/chat/completions
  POST /api/generate          (unused here, present for shape)

Run: python3 test_smoke.py
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, detail or "ok"))
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))


# ---------------------------------------------------------------------------
# Fake Ollama server
# ---------------------------------------------------------------------------

class _FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json(200, {"models": [
                {"name": "qwen3:8b"}, {"name": "gemma3:4b"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        if self.path == "/v1/chat/completions":
            if payload.get("model") == "missing:tag":
                self._json(404, {"error": 'model "missing:tag" not found, '
                                         'try pulling it first'})
                return
            msgs = payload.get("messages", [])
            last = msgs[-1]["content"] if msgs else ""
            self._json(200, {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "model": payload.get("model"),
                "choices": [{"index": 0,
                             "message": {"role": "assistant",
                                         "content": f"FAKE-REPLY: {last[:40]}"},
                             "finish_reason": "stop"}],
            })
        else:
            self._json(404, {"error": "not found"})


def _start_fake() -> tuple[HTTPServer, int]:
    srv = HTTPServer(("127.0.0.1", 0), _FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _import_router(host: str):
    os.environ["OLLAMA_HOST"] = host
    os.environ["OLLAMA_MODEL"] = "qwen3:8b"
    for mod in ("ollama_router",):
        sys.modules.pop(mod, None)
    import ollama_router
    importlib.reload(ollama_router)
    return ollama_router


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t_status_and_models():
    srv, port = _start_fake()
    try:
        r = _import_router(f"http://127.0.0.1:{port}")
        st = r.status()
        assert st["ok"] is True, st
        assert st["models"] == ["qwen3:8b", "gemma3:4b"], st["models"]
        assert st["default_model_present"] is True, st
        assert "digest-draft" in st["local_kinds"], st["local_kinds"]
        return f"models={st['models']}"
    finally:
        srv.shutdown()


def t_generate_and_chat():
    srv, port = _start_fake()
    try:
        r = _import_router(f"http://127.0.0.1:{port}")
        text = r.generate("summarize this", model="qwen3:8b")
        assert text.startswith("FAKE-REPLY:"), text
        resp = r.chat([{"role": "user", "content": "hi"}])
        assert resp["choices"][0]["message"]["content"].startswith("FAKE-REPLY:")
        return "chat+generate OK"
    finally:
        srv.shutdown()


def t_route_policy_local_and_frontier():
    srv, port = _start_fake()
    try:
        r = _import_router(f"http://127.0.0.1:{port}")
        # local kind runs against the fake server
        out = r.route_task("digest-draft",
                           [{"role": "user", "content": "draft digest"}])
        assert out["target"] == "local", out
        assert out["text"].startswith("FAKE-REPLY:"), out
        # alias resolves too
        assert r.route_decision("triage")["target"] == "local"
        # unknown / client-facing kind -> FrontierRequired, NO network call
        for kind in ("outreach-copy", "sales-email", "whatever-new"):
            d = r.route_decision(kind)
            assert d["target"] == "frontier", d
            try:
                r.route_task(kind, [{"role": "user", "content": "x"}])
            except r.FrontierRequired:
                pass
            else:
                raise AssertionError(f"{kind} did not raise FrontierRequired")
        return "7 local kinds; frontier kinds raise, never call paid API"
    finally:
        srv.shutdown()


def t_unreachable_host():
    r = _import_router("http://127.0.0.1:1")  # nothing listens here
    try:
        r.generate("hi")
    except r.OllamaNotRunning as exc:
        assert "ollama serve" in str(exc), exc
        st = r.status()
        assert st["ok"] is False, st
        return "OllamaNotRunning + status ok=false"
    raise AssertionError("expected OllamaNotRunning")


def t_model_not_pulled():
    srv, port = _start_fake()
    try:
        r = _import_router(f"http://127.0.0.1:{port}")
        try:
            r.generate("hi", model="missing:tag")
        except r.ModelNotPulled as exc:
            assert "ollama pull missing:tag" in str(exc), exc
            return "ModelNotPulled names the pull command"
        raise AssertionError("expected ModelNotPulled")
    finally:
        srv.shutdown()


def t_validation():
    r = _import_router("http://127.0.0.1:1")  # no network needed here
    bad = [
        [],
        [{"role": "user"}],                       # missing content
        [{"role": "user", "content": "  "}],       # empty content
        [{"role": "bogus", "content": "x"}],       # bad role
        "not-a-list",
    ]
    for b in bad:
        try:
            r.validate_messages(b)
        except ValueError:
            pass
        else:
            raise AssertionError(f"validate_messages accepted {b!r}")
    try:
        r.generate("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("generate accepted blank prompt")
    return "6 bad inputs rejected"


def t_mcp_protocol():
    srv, port = _start_fake()
    env = dict(os.environ, OLLAMA_HOST=f"http://127.0.0.1:{port}",
               OLLAMA_MODEL="qwen3:8b")
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env)
    try:
        def rpc(mid, method, params=None):
            proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "id": mid, "method": method,
                 "params": params or {}}) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        init = rpc(1, "initialize")
        assert init["result"]["serverInfo"]["name"] == "ollama-local", init
        tools = rpc(2, "tools/list")["result"]["tools"]
        names = [t["name"] for t in tools]
        assert names == ["ollama_status", "ollama_models", "ollama_generate",
                         "ollama_route", "ollama_route_decision"], names
        # decision tool (pure)
        d = rpc(3, "tools/call",
                {"name": "ollama_route_decision",
                 "arguments": {"kind": "intel-summary"}})
        assert '"target": "local"' in d["result"]["content"][0]["text"], d
        # route tool, frontier kind -> decision, not executed
        f = rpc(4, "tools/call",
                {"name": "ollama_route",
                 "arguments": {"kind": "outreach-copy",
                               "prompt": "write the pitch"}})
        assert '"target": "frontier"' in f["result"]["content"][0]["text"], f
        # route tool, local kind -> runs on fake server
        g = rpc(5, "tools/call",
                {"name": "ollama_route",
                 "arguments": {"kind": "digest-draft",
                               "prompt": "draft the digest"}})
        assert "FAKE-REPLY" in g["result"]["content"][0]["text"], g
        # error path
        e = rpc(6, "tools/call",
                {"name": "nope", "arguments": {}})
        assert e["result"]["isError"] is True, e
        return "5 tools over stdio; local/frontier/error paths OK"
    finally:
        proc.kill()
        srv.shutdown()


def t_cli():
    srv, port = _start_fake()
    env = dict(os.environ, OLLAMA_HOST=f"http://127.0.0.1:{port}",
               OLLAMA_MODEL="qwen3:8b")
    try:
        out = subprocess.run(
            [sys.executable, str(HERE / "ollama_router.py"), "--kinds"],
            capture_output=True, text=True, env=env, timeout=30)
        assert out.returncode == 0, out.stderr
        kinds = json.loads(out.stdout)
        assert len(kinds) == 7, kinds
        out = subprocess.run(
            [sys.executable, str(HERE / "ollama_router.py"),
             "--route", "outreach-copy", "write it"],
            capture_output=True, text=True, env=env, timeout=30)
        assert out.returncode == 3, (out.returncode, out.stderr)
        assert '"target": "frontier"' in out.stderr, out.stderr
        out = subprocess.run(
            [sys.executable, str(HERE / "ollama_router.py"),
             "--route", "intel-summary", "summarize"],
            capture_output=True, text=True, env=env, timeout=30)
        assert out.returncode == 0 and "FAKE-REPLY" in out.stdout, out.stderr
        return "--kinds/--route CLI paths OK"
    finally:
        srv.shutdown()


TESTS = [
    ("status_and_models", t_status_and_models),
    ("generate_and_chat", t_generate_and_chat),
    ("route_policy_local_and_frontier", t_route_policy_local_and_frontier),
    ("unreachable_host", t_unreachable_host),
    ("model_not_pulled", t_model_not_pulled),
    ("validation", t_validation),
    ("mcp_protocol", t_mcp_protocol),
    ("cli", t_cli),
]


def main() -> int:
    for name, fn in TESTS:
        check(name, fn)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'} {name} — {detail}")
    print(f"\n{passed}/{len(RESULTS)} passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
