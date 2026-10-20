#!/usr/bin/env python3
"""Hermetic smoke test for xtool-ios-apps. No network, no real xtool,
no Swift toolchain, no iPhone.

1. xtool_client.self_check() — mock xtool on a temp PATH: probe, project
   new/dev, device list, install argv echo, launch, bad-subcommand refuse,
   unsafe-name refuse, nonzero-exit path, dry_run.
2. MCP protocol test — spawn mcp_server.py over stdio with mock PATH:
   initialize -> tools/list -> tools/call (probe, devices, project_new,
   project_dev dry_run, app_install dry_run, app_launch dry_run,
   setup_guide) + one unknown tool (expect isError).
3. setup_guide() contains the key recipe steps.

Exit 0 = all pass; prints PASS/FAIL per step.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import xtool_client  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, str(detail)))
        print(f"PASS {name} — {detail}")
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        print(f"FAIL {name} — {type(exc).__name__}: {exc}")


TMP = tempfile.mkdtemp(prefix="xtool_smoke_")
xtool_client.make_mock_xtool(TMP)
ENV = dict(os.environ)
ENV["PATH"] = TMP + os.pathsep + ENV.get("PATH", "")
os.environ["PATH"] = ENV["PATH"]  # visible to shutil.which in this process


def t_selfcheck():
    r = xtool_client.self_check()
    assert r["self_check"] == "PASS", r
    return f"steps: {', '.join(r['steps'])}"


def t_probe_banner():
    r = xtool_client.probe()
    assert r["installed"] is True
    assert any("Cross-platform Xcode replacement" in ln
               for ln in r["help_banner"]), r["help_banner"]
    assert "devices" in r["known_subcommands"]
    return f"banner ok, {len(r['known_subcommands'])} known subcommands"


def t_devices_raw():
    r = xtool_client.list_devices()
    assert r["ok"] is True
    assert r["device_line_count"] == 2
    assert "mock-iphone-1" in r["device_lines"][0]
    return "2 mock device lines returned raw"


def t_project_new_argv():
    r = xtool_client.project_new("MyApp", dest_dir="/tmp", dry_run=True)
    assert r["dry_run"] is True
    assert r["argv"][-2:] == ["new", "MyApp"], r["argv"]
    return f"argv={r['argv']}"


def t_unsafe_name_refused():
    for bad in ("../../evil", "a b", "", "x" * 65, "-lead"):
        r = xtool_client.project_new(bad, dry_run=True)
        assert r["ok"] is False, bad
    return "5 unsafe names refused"


def t_unknown_subcommand_refused():
    r = xtool_client.run_xtool("pwn")
    assert r["ok"] is False and "refusing" in r["error"]
    return "refused as designed"


def t_missing_ipa_refused():
    r = xtool_client.install_ipa("/tmp/does-not-exist-xyz.ipa")
    assert r["ok"] is False and "ipa not found" in r["error"]
    return "missing ipa refused before any subprocess"


def t_setup_guide_content():
    g = xtool_client.setup_guide()
    for needle in ("xtool setup", "Xcode.xip", "$99", "WSL"):
        assert needle in g, needle
    return "guide covers setup, SDK, fee, WSL"


def mcp_call(proc, mid, method, params=None):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def t_mcp_roundtrip():
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=ENV)
    try:
        init = mcp_call(proc, 1, "initialize", {})
        assert init["result"]["serverInfo"]["name"] == "xtool-ios-apps"
        # true notification: no id -> server must NOT reply; send a tools/list
        # right after and confirm the response matches tools/list, not the
        # notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                     "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        tools = mcp_call(proc, 2, "tools/list")
        names = [t["name"] for t in tools["result"]["tools"]]
        assert "xtool_probe" in names and len(names) == 7, names

        def call(mid, tool, args):
            r = mcp_call(proc, mid, "tools/call",
                         {"name": tool, "arguments": args})
            return json.loads(r["result"]["content"][0]["text"])

        assert call(3, "xtool_probe", {})["installed"] is True
        assert call(4, "xtool_devices", {})["device_line_count"] == 2
        assert call(5, "xtool_project_new",
                    {"name": "McpApp", "dry_run": True})["dry_run"] is True
        assert call(6, "xtool_project_dev",
                    {"project_dir": "/tmp", "dry_run": True})["argv"][-1] == "dev"
        assert call(7, "xtool_app_install",
                    {"ipa_path": "/tmp/a.ipa",
                     "dry_run": True})["argv"][2] == "/tmp/a.ipa"
        assert call(8, "xtool_app_launch",
                    {"args": ["com.example.a"],
                     "dry_run": True})["argv"][-1] == "com.example.a"
        assert "xtool setup" in call(9, "xtool_setup_guide", {})["setup_guide"]
        bad = mcp_call(proc, 10, "tools/call",
                       {"name": "nope", "arguments": {}})
        assert bad["result"]["isError"] is True
        return "init/list/7 tool calls + unknown-tool error, no notification hang"
    finally:
        proc.stdin.close()
        proc.wait(timeout=15)


if __name__ == "__main__":
    check("client_self_check", t_selfcheck)
    check("probe_banner", t_probe_banner)
    check("devices_raw", t_devices_raw)
    check("project_new_argv", t_project_new_argv)
    check("unsafe_name_refused", t_unsafe_name_refused)
    check("unknown_subcommand_refused", t_unknown_subcommand_refused)
    check("missing_ipa_refused", t_missing_ipa_refused)
    check("setup_guide_content", t_setup_guide_content)
    check("mcp_roundtrip", t_mcp_roundtrip)

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    sys.exit(1 if failed else 0)
