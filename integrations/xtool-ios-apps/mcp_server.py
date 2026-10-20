#!/usr/bin/env python3
"""MCP stdio server exposing the xtool iOS-app-build orchestrator.

Stdlib only — no `mcp` package required. Speaks JSON-RPC 2.0 over stdio with
the MCP initialize / tools/list / tools/call surface.

Tools:
  xtool_probe          — detect xtool on PATH, report help banner + known subcommands
  xtool_devices        — list connected iOS devices (raw output, not parsed)
  xtool_project_new    — scaffold a new SwiftPM iOS project (`xtool new <name>`)
  xtool_project_dev    — build + install + launch a project on the connected phone
  xtool_app_install    — install a built .ipa on the connected device
  xtool_app_launch     — launch an installed app (passthrough args)
  xtool_setup_guide    — one-time setup recipe (Windows/WSL, Linux, macOS)

Every mutating tool takes dry_run=true for a pre-flight argv echo.
Subcommand surface is limited to the README-verified xtool CLI; anything else
is refused rather than passed through.

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"xtool-ios-apps": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"]}}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import xtool_client  # noqa: E402

SERVER_NAME = "xtool-ios-apps"
SERVER_VERSION = "1.0.0"

TOOL_SPECS = [
    {"name": "xtool_probe",
     "description": "Detect the xtool binary on PATH and report its help "
                    "banner plus the known (README-verified) subcommands. "
                    "No code runs; safe to call first.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "xtool_devices",
     "description": "List iOS devices visible to xtool (`xtool devices`). "
                    "Returns raw output; device fields are not parsed.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "dry_run": {"type": "boolean", "default": False}}}},
    {"name": "xtool_project_new",
     "description": "Scaffold a new xtool SwiftPM iOS project "
                    "(`xtool new <name>` run in dest_dir). Name must be a "
                    "safe identifier ([A-Za-z0-9._-], max 64 chars).",
     "inputSchema": {
         "type": "object",
         "properties": {
             "name": {"type": "string"},
             "dest_dir": {"type": "string"},
             "dry_run": {"type": "boolean", "default": False}},
         "required": ["name"]}},
    {"name": "xtool_project_dev",
     "description": "Build, sign, install and launch a project on the "
                    "USB-connected iPhone (`xtool dev`, run in project_dir). "
                    "Needs Swift toolchain + iOS SDK + trusted phone.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "project_dir": {"type": "string"},
             "timeout": {"type": "integer", "default": 1800},
             "dry_run": {"type": "boolean", "default": False}},
         "required": ["project_dir"]}},
    {"name": "xtool_app_install",
     "description": "Install a built .ipa file on the connected device "
                    "(`xtool install <ipa>`).",
     "inputSchema": {
         "type": "object",
         "properties": {
             "ipa_path": {"type": "string"},
             "dry_run": {"type": "boolean", "default": False}},
         "required": ["ipa_path"]}},
    {"name": "xtool_app_launch",
     "description": "Launch an installed app (`xtool launch ...`). Arguments "
                    "pass through verbatim — check `xtool launch --help` "
                    "for the flag shapes.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "args": {"type": "array", "items": {"type": "string"},
                      "default": []},
             "dry_run": {"type": "boolean", "default": False}}}},
    {"name": "xtool_setup_guide",
     "description": "Return the one-time xtool setup recipe "
                    "(prereqs, SDK extraction, auth, first-app steps, "
                    "licensing caution). Makes no host changes.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def call_tool(name: str, args: dict) -> dict:
    if name == "xtool_probe":
        return _text(xtool_client.probe())
    if name == "xtool_devices":
        return _text(xtool_client.list_devices(dry_run=args.get("dry_run", False)))
    if name == "xtool_project_new":
        return _text(xtool_client.project_new(
            args["name"], dest_dir=args.get("dest_dir"),
            dry_run=args.get("dry_run", False)))
    if name == "xtool_project_dev":
        return _text(xtool_client.project_dev(
            args["project_dir"], timeout=args.get("timeout", 1800),
            dry_run=args.get("dry_run", False)))
    if name == "xtool_app_install":
        return _text(xtool_client.install_ipa(
            args["ipa_path"], dry_run=args.get("dry_run", False)))
    if name == "xtool_app_launch":
        return _text(xtool_client.launch_app(
            *(args.get("args") or []), dry_run=args.get("dry_run", False)))
    if name == "xtool_setup_guide":
        return _text({"setup_guide": xtool_client.setup_guide()})
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
        return None  # true JSON-RPC notification: no response
    if method == "tools/list":
        return ok({"tools": TOOL_SPECS})
    if method == "tools/call":
        name = (params.get("name") or "")
        targs = params.get("arguments") or {}
        try:
            res = call_tool(name, targs)
        except Exception as exc:  # never break the stdio loop on one call
            res = {"isError": True,
                   "content": [{"type": "text",
                                "text": f"tool error: {type(exc).__name__}: "
                                        f"{exc}"}]}
        return ok(res)
    return err(-32601, f"unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
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
