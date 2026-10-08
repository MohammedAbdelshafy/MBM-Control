#!/usr/bin/env python3
"""MCP stdio server exposing the parallel coding-agent orchestrator.

Stdlib only — no `mcp` package required. Speaks JSON-RPC 2.0 over stdio with
the MCP initialize / tools/list / tools/call surface.

Tools:
  swarm_detect        — scan PATH for installed coding-agent CLIs
  swarm_plan          — pure planner: roles -> backend assignments (no spawn)
  swarm_dispatch      — fan one task out to N backends in parallel
  swarm_dispatch_roles — role-split (researcher/coder/reviewer) team run
  swarm_events        — read the office mailbox (JSONL event log)

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"swarm-orchestrator": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"]}}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import orchestrator  # noqa: E402

SERVER_NAME = "swarm-orchestrator"
SERVER_VERSION = "1.0.0"

TOOL_SPECS = [
    {"name": "swarm_detect",
     "description": "Detect installed coding-agent CLIs (claude, codex, "
                    "gemini, qwen, opencode) on PATH, with version probes. "
                    "No code runs.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "swarm_plan",
     "description": "Pure planner: given a task and roles, return the "
                    "role->backend assignments that would run (no spawn). "
                    "Use this as a pre-flight check.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "task": {"type": "string"},
             "roles": {"type": "array", "items": {"type": "string"},
                       "default": ["researcher", "coder", "reviewer"]}},
         "required": ["task"]}},
    {"name": "swarm_dispatch",
     "description": "Run one task prompt on N backends in parallel; return "
                    "per-backend exit code, output, and timing. dry_run=true "
                    "only echoes the exact argv (no execution).",
     "inputSchema": {
         "type": "object",
         "properties": {
             "task": {"type": "string"},
             "backends": {"type": "array", "items": {"type": "string"},
                          "description": "backend names; default = all installed"},
             "timeout": {"type": "integer", "default": 600},
             "dry_run": {"type": "boolean", "default": False}},
         "required": ["task"]}},
    {"name": "swarm_dispatch_roles",
     "description": "Split the task across roles (researcher/coder/reviewer), "
                    "one installed backend per role, run in parallel, return "
                    "a merged team report. dry_run=true echoes argv only.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "task": {"type": "string"},
             "roles": {"type": "array", "items": {"type": "string"},
                       "default": ["researcher", "coder", "reviewer"]},
             "timeout": {"type": "integer", "default": 900},
             "dry_run": {"type": "boolean", "default": False}},
         "required": ["task"]}},
    {"name": "swarm_events",
     "description": "Read the office mailbox: the JSONL event log of "
                    "detections, dispatches, and role runs.",
     "inputSchema": {
         "type": "object",
         "properties": {"limit": {"type": "integer", "default": 50}}}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def call_tool(name: str, args: dict) -> dict:
    if name == "swarm_detect":
        return _text({"backends": orchestrator.detect_backends()})
    if name == "swarm_plan":
        task, roles = args["task"], args.get("roles",
                                             list(orchestrator.ROLES))
        detected = orchestrator.detect_backends()
        installed = [b["name"] for b in detected if b["installed"]]
        plan = [{"role": r, "backend": installed[i % len(installed)]
                 if installed else None} for i, r in enumerate(roles)]
        return _text({"task": task, "roles": roles, "plan": plan,
                      "note": "no backends installed — nothing would run"
                      if not installed else "dry plan; use "
                      "swarm_dispatch_roles to execute"})
    if name == "swarm_dispatch":
        return _text(orchestrator.dispatch(
            args["task"], backends=args.get("backends"),
            timeout=args.get("timeout", 600),
            dry_run=args.get("dry_run", False)))
    if name == "swarm_dispatch_roles":
        return _text(orchestrator.dispatch_roles(
            args["task"], roles=args.get("roles"),
            timeout=args.get("timeout", 900),
            dry_run=args.get("dry_run", False)))
    if name == "swarm_events":
        return _text({"events": orchestrator.read_events(
            args.get("limit", 50))})
    return {"isError": True,
            "content": [{"type": "text", "text": f"unknown tool: {name}"}]}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({"protocolVersion": "2024-11-05",
                   "serverInfo": {"name": SERVER_NAME,
                                  "version": SERVER_VERSION},
                   "capabilities": {"tools": {}}})
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return ok({"tools": TOOL_SPECS})
    if method == "tools/call":
        name = (params.get("name") or "")
        args = params.get("arguments") or {}
        try:
            res = call_tool(name, args)
        except Exception as exc:  # never break the stdio loop on one call
            res = {"isError": True,
                   "content": [{"type": "text",
                                "text": f"tool error: {type(exc).__name__}: "
                                        f"{exc}"}]}
        return ok(res)
    return err(-32601, f"unknown method: {method}")


def main() -> None:
    stdin = sys.stdin
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
