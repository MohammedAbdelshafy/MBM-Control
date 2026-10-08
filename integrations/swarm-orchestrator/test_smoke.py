#!/usr/bin/env python3
"""Hermetic smoke test for swarm-orchestrator. No network, no real CLIs.

1. orchestrator.self_check() — mock backends on a temp PATH.
2. MCP protocol test — spawn mcp_server.py over stdio with mock PATH:
   initialize -> tools/list -> tools/call (swarm_detect, swarm_plan,
   swarm_dispatch dry_run, swarm_dispatch_roles dry_run, swarm_events).
3. Role wrapper sanity — every role formats without KeyError.
4. Event log append/read round-trip.

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

import orchestrator  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, str(detail)))
        print(f"PASS {name} — {detail}")
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        print(f"FAIL {name} — {type(exc).__name__}: {exc}")


def make_mocks():
    tmp = tempfile.mkdtemp(prefix="swarm_smoke_")
    for n in ("smoke-a", "smoke-b", "smoke-c"):
        orchestrator.make_mock_backend(tmp, n, "smoke output")
    catalog = {n: {"binary": n, "args": ["-p"], "prompt_via_arg": True,
                   "note": "smoke mock"} for n in ("smoke-a", "smoke-b", "smoke-c")}
    env = dict(os.environ)
    env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
    return tmp, catalog, env


TMP, CATALOG, ENV = make_mocks()
# mocks must be visible to shutil.which in THIS process too
os.environ["PATH"] = TMP + os.pathsep + os.environ.get("PATH", "")


def mcp_call(proc, mid, method, params=None):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def t_selfcheck():
    r = orchestrator.self_check()
    assert r["self_check"] == "PASS", r
    return f'{r["dispatch_results"]} mock results, roles {r["roles"]}'


def t_detect_mocks():
    found = {b["name"]: b for b in orchestrator.detect_backends(CATALOG)}
    assert all(found[n]["installed"] for n in CATALOG), found
    return f'{len(found)} mock backends detected on PATH'


def t_dispatch_parallel():
    import time
    start = time.monotonic()
    out = orchestrator.dispatch("smoke task", catalog=CATALOG, timeout=30)
    dt = time.monotonic() - start
    assert len(out["results"]) == 3, out
    assert all(r.get("exit_code") == 0 for r in out["results"]), out
    assert all("smoke output" in r.get("output", "")
               for r in out["results"]), out
    # parallel: 3 instant mocks must finish well under 3x any serial bound
    assert dt < 20, f"took {dt:.1f}s"
    return f'3 results in {dt:.2f}s, all exit 0'


def t_dispatch_subset_and_dryrun():
    out = orchestrator.dispatch("x", backends=["smoke-a"], catalog=CATALOG,
                                timeout=30)
    assert len(out["results"]) == 1 and out["results"][0]["backend"] == "smoke-a"
    dry = orchestrator.dispatch("x", backends=["smoke-b"], catalog=CATALOG,
                                dry_run=True)
    assert dry["results"][0].get("dry_run") is True
    assert dry["results"][0]["argv"][0] == "smoke-b"
    return "subset + dry_run argv echo OK"


def t_roles():
    out = orchestrator.dispatch_roles("smoke roles",
                                      roles=["researcher", "coder", "reviewer"],
                                      catalog=CATALOG, timeout=30)
    roles = [p["role"] for p in out["roles"]]
    assert roles == ["researcher", "coder", "reviewer"], roles
    backends = {a["backend"] for a in out["assignments"]}
    assert backends <= set(CATALOG), backends
    return f'roles in order on {sorted(backends)}'


def t_role_wrappers():
    for role, tpl in orchestrator.ROLE_WRAPPERS.items():
        s = tpl.format(task="demo")
        assert "demo" in s and len(s) > 50, role
    return f'{len(orchestrator.ROLE_WRAPPERS)} wrappers format cleanly'


def t_events_roundtrip():
    orchestrator.log_event("smoke_note", {"msg": "hello-memo"})
    events = orchestrator.read_events(limit=5)
    assert any(e.get("kind") == "smoke_note" for e in events), events
    return f'{len(events)} recent events readable'


def t_mcp_protocol():
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=ENV)
    try:
        init = mcp_call(proc, 1, "initialize", {"protocolVersion": "2024-11-05"})
        assert init["result"]["serverInfo"]["name"] == "swarm-orchestrator", init
        tools = mcp_call(proc, 2, "tools/list")
        names = {t["name"] for t in tools["result"]["tools"]}
        assert names == {"swarm_detect", "swarm_plan", "swarm_dispatch",
                         "swarm_dispatch_roles", "swarm_events"}, names
        det = mcp_call(proc, 3, "tools/call",
                       {"name": "swarm_detect", "arguments": {}})
        det_b = json.loads(det["result"]["content"][0]["text"])["backends"]
        det_names = {b["name"] for b in det_b}
        # real catalog: mocks aren't in it, so assert shape, not content
        assert all("installed" in b for b in det_b), det_b
        plan = mcp_call(proc, 4, "tools/call",
                        {"name": "swarm_plan",
                         "arguments": {"task": "t", "roles": ["coder"]}})
        plan_p = json.loads(plan["result"]["content"][0]["text"])
        assert plan_p["plan"][0]["role"] == "coder", plan_p
        disp = mcp_call(proc, 5, "tools/call",
                        {"name": "swarm_dispatch",
                         "arguments": {"task": "t", "dry_run": True}})
        disp_r = json.loads(disp["result"]["content"][0]["text"])
        assert isinstance(disp_r["results"], list), disp_r
        roles = mcp_call(proc, 6, "tools/call",
                         {"name": "swarm_dispatch_roles",
                          "arguments": {"task": "t", "roles": ["coder"],
                                        "dry_run": True}})
        roles_r = json.loads(roles["result"]["content"][0]["text"])
        assert roles_r["roles"][0]["role"] == "coder", roles_r
        ev = mcp_call(proc, 7, "tools/call",
                      {"name": "swarm_events", "arguments": {"limit": 3}})
        ev_r = json.loads(ev["result"]["content"][0]["text"])
        assert "events" in ev_r, ev_r
        bad = mcp_call(proc, 8, "tools/call",
                       {"name": "nope", "arguments": {}})
        assert bad["result"].get("isError") is True, bad
        return f'{len(names)} tools over stdio; error path OK'
    finally:
        proc.kill()


for name, fn in [
    ("self_check", t_selfcheck),
    ("detect_mocks", t_detect_mocks),
    ("dispatch_parallel", t_dispatch_parallel),
    ("dispatch_subset_and_dryrun", t_dispatch_subset_and_dryrun),
    ("roles", t_roles),
    ("role_wrappers", t_role_wrappers),
    ("events_roundtrip", t_events_roundtrip),
    ("mcp_protocol", t_mcp_protocol),
]:
    check(name, fn)

failed = [n for n, ok, _ in RESULTS if not ok]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} smoke tests passed")
sys.exit(1 if failed else 0)
