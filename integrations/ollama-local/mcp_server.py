#!/usr/bin/env python3
"""MCP stdio server exposing the Ollama local-LLM router (power #7).

Stdlib only — no `mcp` package required. JSON-RPC 2.0 over stdio:
initialize / tools/list / tools/call.

Tools:
  ollama_status          — health check: reachable, models, default config
  ollama_models          — model tags pulled on the local Ollama host
  ollama_generate        — one local completion (never a paid endpoint)
  ollama_route           — apply the routing policy AND run the task:
                           local kinds run on Ollama; anything else returns
                           a frontier-required decision (never auto-called)
  ollama_route_decision  — pure planner: where would this task kind run?
                           No network, no cost.

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"ollama-local": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"]}}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ollama_router  # noqa: E402

SERVER_NAME = "ollama-local"
SERVER_VERSION = "1.0.0"

TOOL_SPECS = [
    {"name": "ollama_status",
     "description": "Health check for the local Ollama host: reachable, "
                    "pulled models, default model config. No generation.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ollama_models",
     "description": "List model tags currently pulled on the Ollama host "
                    "(e.g. qwen3:8b). Use before ollama_generate to pick a "
                    "real tag — never guess one.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ollama_generate",
     "description": "One completion on the LOCAL Ollama host ($0 marginal "
                    "cost). For internal drafts only — not client-facing "
                    "copy. Fails cleanly if Ollama is down or the model "
                    "isn't pulled.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "prompt": {"type": "string"},
             "model": {"type": "string",
                       "description": "tag from ollama_models; "
                                      "default = OLLAMA_MODEL"},
             "system": {"type": "string"}},
         "required": ["prompt"]}},
    {"name": "ollama_route",
     "description": "Apply the routing policy and run the task. Local-safe "
                    "kinds (reply-triage, intel-summary, digest-draft, "
                    "research-note, dedupe-preview, prompt-rewrite, "
                    "translate-draft) run on Ollama. Anything else returns "
                    "a frontier-required decision — it is NEVER auto-routed "
                    "to a paid API.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "kind": {"type": "string",
                      "description": "task kind, e.g. 'digest-draft'"},
             "prompt": {"type": "string"},
             "model": {"type": "string"}},
         "required": ["kind", "prompt"]}},
    {"name": "ollama_route_decision",
     "description": "Pure planner: report where a task kind would run "
                    "(local vs frontier) and why. No network, no cost.",
     "inputSchema": {
         "type": "object",
         "properties": {"kind": {"type": "string"}},
         "required": ["kind"]}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def call_tool(name: str, args: dict) -> dict:
    if name == "ollama_status":
        return _text(ollama_router.status())
    if name == "ollama_models":
        return _text({"host": ollama_router.OLLAMA_HOST,
                      "models": ollama_router.list_local_models()})
    if name == "ollama_generate":
        msgs = []
        if args.get("system"):
            msgs.append({"role": "system", "content": args["system"]})
        msgs.append({"role": "user", "content": args["prompt"]})
        return _text({"target": "local",
                      "model": args.get("model") or ollama_router.DEFAULT_MODEL,
                      "text": ollama_router.generate(
                          args["prompt"],
                          model=args.get("model"))})
    if name == "ollama_route":
        try:
            return _text(ollama_router.route_task(
                args["kind"],
                [{"role": "user", "content": args["prompt"]}],
                model=args.get("model")))
        except ollama_router.FrontierRequired as exc:
            return _text({"target": "frontier", "kind": exc.kind,
                          "why": exc.reason,
                          "note": "not executed — route to a frontier "
                                  "model explicitly"})
    if name == "ollama_route_decision":
        return _text(ollama_router.route_decision(args["kind"]))
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
