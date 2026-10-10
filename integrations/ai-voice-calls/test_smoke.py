#!/usr/bin/env python3
"""Hermetic smoke tests for ai-voice-calls.

Everything runs against an in-process fake Vapi HTTP server on localhost:
no network beyond loopback, no API key, no charge, no real calls.
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import voice_calls as vc  # noqa: E402

PASSES, FAILS = [], []


def check(name, fn):
    try:
        fn()
        PASSES.append(name)
        print(f"  PASS {name}")
    except Exception as e:  # noqa: BLE001
        FAILS.append((name, e))
        print(f"  FAIL {name}: {type(e).__name__}: {e}")


# --- fake Vapi server ---------------------------------------------------------

STORE = {"assistants": {}, "calls": {}, "seen": []}


class FakeVapi(BaseHTTPRequestHandler):
    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n).decode() or "{}") if n else {}

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass

    def _auth_ok(self):
        return self.headers.get("Authorization") == "Bearer test-key"

    def do_POST(self):
        STORE["seen"].append(("POST", self.path, self.headers.get("Authorization")))
        if not self._auth_ok():
            return self._send(401, {"message": "unauthorized"})
        body = self._body()
        if self.path == "/assistant":
            aid = f"asst_{len(STORE['assistants']) + 1:03d}"
            STORE["assistants"][aid] = {"id": aid, **body}
            return self._send(201, {"id": aid, **body})
        if self.path == "/call":
            cid = f"call_{len(STORE['calls']) + 1:03d}"
            call = {"id": cid, "status": "queued", **body,
                    "polls": 0}
            STORE["calls"][cid] = call
            return self._send(201, call)
        return self._send(404, {"message": "not found"})

    def do_GET(self):
        STORE["seen"].append(("GET", self.path, None))
        if not self._auth_ok():
            return self._send(401, {"message": "unauthorized"})
        path = self.path.split("?")[0]  # strip query string
        if path == "/call":
            return self._send(200, list(STORE["calls"].values()))
        parts = path.split("/")
        if len(parts) == 3 and parts[1] == "call":
            call = STORE["calls"].get(parts[2])
            if call is None:
                return self._send(404, {"message": "call not found"})
            call["polls"] += 1
            # advance lifecycle on each poll: queued -> in-progress -> ended
            if call["polls"] >= 3:
                call["status"] = "ended"
            elif call["polls"] >= 2:
                call["status"] = "in-progress"
            return self._send(200, call)
        if len(parts) == 3 and parts[1] == "assistant":
            a = STORE["assistants"].get(parts[2])
            if a is None:
                return self._send(404, {"message": "assistant not found"})
            return self._send(200, a)
        return self._send(404, {"message": "not found"})

    def do_PATCH(self):
        STORE["seen"].append(("PATCH", self.path, None))
        if not self._auth_ok():
            return self._send(401, {"message": "unauthorized"})
        parts = self.path.split("/")
        if len(parts) == 3 and parts[1] == "call":
            call = STORE["calls"].get(parts[2])
            if call is None:
                return self._send(404, {"message": "call not found"})
            body = self._body()
            call.update(body)
            return self._send(200, call)
        return self._send(404, {"message": "not found"})


def start_fake():
    srv = HTTPServer(("127.0.0.1", 0), FakeVapi)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def client(srv):
    cfg = vc.Config(api_key="test-key",
                    base_url=f"http://127.0.0.1:{srv.server_port}")
    return vc.VapiClient(cfg)


# --- tests --------------------------------------------------------------------

def t_missing_key():
    cfg = vc.Config(api_key="")
    try:
        vc.VapiClient(cfg)
        raise AssertionError("expected ConfigError")
    except vc.ConfigError:
        pass


def t_bad_e164():
    for bad in ["12345", "+1", "++14155551234", "14155551234", "", "+abcdef"]:
        try:
            vc.validate_e164(bad)
            raise AssertionError(f"expected ValidationError for {bad!r}")
        except vc.ValidationError:
            pass
    assert vc.validate_e164("+14155551234") == "+14155551234"


def t_create_assistant(srv):
    c = client(srv)
    a = c.create_assistant({
        "name": "test",
        "model": {"provider": "openai", "model": "gpt-4o-mini"},
        "firstMessage": "Hi, I'm an AI assistant calling about your property.",
    })
    assert a["id"].startswith("asst_")
    got = c.get_assistant(a["id"])
    assert got["id"] == a["id"]


def t_create_assistant_requires_model(srv):
    c = client(srv)
    try:
        c.create_assistant({"name": "no-model"})
        raise AssertionError("expected ValidationError")
    except vc.ValidationError:
        pass


def t_start_call(srv):
    c = client(srv)
    call = c.start_call("+14155551234", assistant_id="asst_x",
                        phone_number_id="pn_y")
    assert call["id"].startswith("call_")
    assert call["customer"]["number"] == "+14155551234"
    # Authorization header was a Bearer token (not leaked in error paths)
    method, path, auth = STORE["seen"][-1]
    assert auth == "Bearer test-key"


def t_start_call_needs_ids(srv):
    cfg = vc.Config(api_key="test-key",
                    base_url=f"http://127.0.0.1:{srv.server_port}")
    c = vc.VapiClient(cfg)
    try:
        c.start_call("+14155551234")
        raise AssertionError("expected ValidationError")
    except vc.ValidationError as e:
        assert "assistant_id" in str(e)


def t_wait_call(srv):
    c = client(srv)
    call = c.start_call("+14155559999", assistant_id="asst_x",
                        phone_number_id="pn_y")
    final = c.wait_call(call["id"], timeout_s=30, poll_s=0.05)
    assert final["status"] == "ended"


def t_end_call(srv):
    c = client(srv)
    call = c.start_call("+14155558888", assistant_id="asst_x",
                        phone_number_id="pn_y")
    ended = c.end_call(call["id"])
    assert ended["status"] == "ended"


def t_list_calls(srv):
    c = client(srv)
    calls = c.list_calls(limit=5)
    assert isinstance(calls, list) and len(calls) >= 1


def t_api_error(srv):
    cfg = vc.Config(api_key="wrong-key",
                    base_url=f"http://127.0.0.1:{srv.server_port}")
    c = vc.VapiClient(cfg)
    try:
        c.list_calls()
        raise AssertionError("expected ApiError")
    except vc.ApiError as e:
        assert e.status == 401


def t_disclosure_enforced():
    try:
        vc.ensure_ai_disclosure("Hi, this is John from Acme Realty.")
        raise AssertionError("expected ValidationError")
    except vc.ValidationError:
        pass
    vc.ensure_ai_disclosure(
        "Hi, I'm an AI assistant calling on behalf of Acme Realty.")  # ok
    vc.ensure_ai_disclosure("whatever", enforce=False)  # waiver ok


def t_dnc():
    dnc = vc.DncList(numbers={"+14155551234"})
    assert dnc.is_suppressed("+14155551234")
    assert not dnc.is_suppressed("+14155559999")
    assert dnc.is_suppressed("garbage")  # unparseable -> never dialed


def t_load_leads_csv():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        w = csv.writer(f)
        w.writerow(["number", "name", "consent", "source"])
        w.writerow(["+14155550001", "Alice", "true", "call-now-list"])
        w.writerow(["+14155550002", "Bob", "false", "call-now-list"])
        w.writerow(["not-a-number", "Zed", "true", "x"])
        w.writerow(["+14155550001", "Alice dup", "true", "x"])
        path = f.name
    leads, warnings = vc.load_leads_csv(path)
    assert len(leads) == 1 and leads[0].name == "Alice"
    assert leads[0].metadata["source"] == "call-now-list"
    assert len(warnings) == 3  # no-consent, bad number, duplicate


def t_campaign_dry_run():
    STORE["seen"].clear()
    dnc = vc.DncList(numbers={"+14155550002"})
    runner = vc.CampaignRunner(dnc=dnc, dry_run=True)
    log = Path(tempfile.mkdtemp()) / "calls.jsonl"
    runner.log_path = log
    leads = [vc.Lead("+14155550001", "Alice"),
             vc.Lead("+14155550002", "Bob"),
             vc.Lead("+14155550003", "Cara")]
    res = runner.run(leads, interval_s=0)
    statuses = [r["status"] for r in res]
    assert statuses == ["dry-run-ok", "suppressed", "dry-run-ok"], statuses
    assert not STORE["seen"], "dry-run must make zero HTTP calls"
    lines = log.read_text().strip().split("\n")
    assert len(lines) == 3 and all(json.loads(l)["number"] for l in lines)


def t_estimate_cost():
    est = vc.estimate_cost(100, 2.0)
    assert est["platform_fee_usd"] == round(100 * 2.0 * 1.2 * 0.05, 2)
    assert est["all_in_low_usd"] < est["all_in_high_usd"]
    est2 = vc.estimate_cost(10, 3.0, rates={"platform_per_min": 0.10})
    assert est2["platform_fee_usd"] == round(10 * 3.0 * 1.2 * 0.10, 2)


def _mcp_call(payloads):
    proc = subprocess.run(
        [sys.executable, str(HERE / "mcp_server.py")],
        input="\n".join(json.dumps(p) for p in payloads) + "\n",
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return [json.loads(l) for l in proc.stdout.strip().split("\n") if l.strip()]


def t_mcp_initialize_and_list():
    resps = _mcp_call([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ])
    assert resps[0]["result"]["serverInfo"]["name"] == "ai-voice-calls"
    names = {t["name"] for t in resps[1]["result"]["tools"]}
    assert {"voice_config_check", "voice_call_start", "voice_campaign_run",
            "voice_cost_estimate", "voice_dnc_check",
            "voice_assistant_create"} <= names


def t_mcp_config_check():
    env = dict(os.environ)
    env.pop("VAPI_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, str(HERE / "mcp_server.py")],
        input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "voice_config_check",
                                     "arguments": {}}}) + "\n",
        capture_output=True, text=True, timeout=60, env=env)
    resp = json.loads(proc.stdout.strip())
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["VAPI_API_KEY"] == "MISSING"
    assert payload["blocked_on_key"] is True
    assert "sk-" not in json.dumps(payload)  # no secrets echoed


def t_mcp_call_start_dry_run_validation():
    # bad number -> isError; good number -> dry-run payload, no network
    resps = _mcp_call([
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "voice_call_start",
                    "arguments": {"number": "bad", "dry_run": True}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "voice_call_start",
                    "arguments": {"number": "+14155551234", "dry_run": True}}},
    ])
    assert resps[0]["result"]["isError"] is True
    payload = json.loads(resps[1]["result"]["content"][0]["text"])
    assert payload["dry_run"] is True and payload["valid"] is True
    assert "cost_estimate" in payload


def t_mcp_assistant_disclosure_gate():
    resps = _mcp_call([
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "voice_assistant_create",
                    "arguments": {"assistant": {
                        "model": {"provider": "openai", "model": "gpt-4o-mini"},
                        "firstMessage": "Hi, this is John from Acme."},
                        "dry_run": True}}},
    ])
    assert resps[0]["result"]["isError"] is True
    assert "disclose" in resps[0]["result"]["content"][0]["text"].lower()


def t_mcp_cost_estimate():
    resps = _mcp_call([
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "voice_cost_estimate",
                    "arguments": {"num_calls": 50, "avg_minutes": 3.0}}},
    ])
    payload = json.loads(resps[0]["result"]["content"][0]["text"])
    assert payload["billable_minutes"] == round(50 * 3.0 * 1.2, 1)


def t_cli_estimate():
    proc = subprocess.run(
        [sys.executable, str(HERE / "voice_calls.py"),
         "--estimate", "25", "--avg-minutes", "2.5"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["num_calls"] == 25


def main():
    print("== ai-voice-calls smoke tests (hermetic) ==")
    srv = start_fake()
    try:
        check("missing key raises ConfigError", t_missing_key)
        check("E.164 validation", t_bad_e164)
        check("create/get assistant", lambda: t_create_assistant(srv))
        check("assistant requires model", lambda: t_create_assistant_requires_model(srv))
        check("start call posts correct payload", lambda: t_start_call(srv))
        check("start call needs assistant+number ids", lambda: t_start_call_needs_ids(srv))
        check("wait_call polls to ended", lambda: t_wait_call(srv))
        check("end_call PATCH", lambda: t_end_call(srv))
        check("list calls", lambda: t_list_calls(srv))
        check("401 raises ApiError", lambda: t_api_error(srv))
        check("AI disclosure enforced", t_disclosure_enforced)
        check("DNC suppression", t_dnc)
        check("leads CSV loading", t_load_leads_csv)
        check("campaign dry-run (zero HTTP)", t_campaign_dry_run)
        check("cost estimation", t_estimate_cost)
        check("MCP initialize + tools/list", t_mcp_initialize_and_list)
        check("MCP config check (no secrets)", t_mcp_config_check)
        check("MCP call start dry-run validation", t_mcp_call_start_dry_run_validation)
        check("MCP assistant disclosure gate", t_mcp_assistant_disclosure_gate)
        check("MCP cost estimate", t_mcp_cost_estimate)
        check("CLI --estimate", t_cli_estimate)
    finally:
        srv.shutdown()
    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
