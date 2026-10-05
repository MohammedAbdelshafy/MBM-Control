#!/usr/bin/env python3
"""MCP stdio server exposing the Higgsfield video/image API to agents.

Stdlib only — no `mcp` package required. Speaks JSON-RPC 2.0 over stdio with
the MCP initialize / tools/list / tools/call surface.

Tools:
  higgsfield_submit   — validate + submit a generation (dry-run default)
  higgsfield_status   — poll one status snapshot for a request_id
  higgsfield_poll     — wait for completion (live only)
  higgsfield_catalog  — list known models + snapshot pricing
  higgsfield_estimate — pre-flight USD estimate (no network)
  higgsfield_download — fetch a completed media URL to disk

Env: HF_API_KEY_ID + HF_API_KEY_SECRET, or HIGGSFIELD_API_KEY (single token).

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"higgsfield-video": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"],
      "env": {"HF_API_KEY_ID": "...", "HF_API_KEY_SECRET": "..."}}}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hf_client  # noqa: E402

SERVER_NAME = "higgsfield-video"
SERVER_VERSION = "1.0.0"

TOOL_SPECS = [
    {"name": "higgsfield_submit",
     "description": "Submit a Higgsfield generation (Seedance/Kling/Soul). "
                    "dry_run=true validates + simulates, costs nothing. "
                    "dry_run=false charges your Higgsfield balance.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "model_id": {"type": "string",
                          "description": "e.g. bytedance/seedance-2.5/text-to-video"},
             "input": {"type": "object",
                       "description": "prompt, duration, aspect_ratio, image_url, ..."},
             "dry_run": {"type": "boolean", "default": True}},
         "required": ["model_id", "input"]}},
    {"name": "higgsfield_status",
     "description": "One status snapshot for a request_id.",
     "inputSchema": {"type": "object",
                     "properties": {"request_id": {"type": "string"}},
                     "required": ["request_id"]}},
    {"name": "higgsfield_poll",
     "description": "Poll until the job completes (live only), then return "
                    "final payload + media URLs.",
     "inputSchema": {"type": "object",
                     "properties": {"request_id": {"type": "string"},
                                    "max_wait": {"type": "integer", "default": 900}},
                     "required": ["request_id"]}},
    {"name": "higgsfield_catalog",
     "description": "List known models, tasks, and snapshot USD pricing.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "higgsfield_estimate",
     "description": "Pre-flight USD cost estimate. No network, never charged.",
     "inputSchema": {"type": "object",
                     "properties": {"model_id": {"type": "string"},
                                    "seconds": {"type": "number", "default": 5.0}},
                     "required": ["model_id"]}},
    {"name": "higgsfield_download",
     "description": "Download a completed media URL into outputs/.",
     "inputSchema": {"type": "object",
                     "properties": {"url": {"type": "string"},
                                    "filename": {"type": "string"}},
                     "required": ["url", "filename"]}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def call_tool(name: str, args: dict) -> dict:
    if name == "higgsfield_submit":
        return _text(hf_client.submit(
            args["model_id"], args.get("input", {}),
            dry_run=args.get("dry_run", True)))
    if name == "higgsfield_status":
        return _text(hf_client.job_status(args["request_id"]))
    if name == "higgsfield_poll":
        final = hf_client.wait(args["request_id"],
                               max_wait=args.get("max_wait", 900))
        return _text({"final_status": final,
                      "media": hf_client.extract_media_urls(final)})
    if name == "higgsfield_catalog":
        return _text(hf_client.load_catalog())
    if name == "higgsfield_estimate":
        return _text(hf_client.estimate_cost(
            args["model_id"], args.get("seconds", 5.0)))
    if name == "higgsfield_download":
        dest = Path(__file__).with_name("outputs") / args["filename"]
        saved = hf_client.download(args["url"], dest)
        return _text({"saved_to": str(saved), "bytes": saved.stat().st_size})
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
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": SERVER_NAME,
                                  "version": SERVER_VERSION}})
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return ok({"tools": TOOL_SPECS})
    if method == "tools/call":
        try:
            return ok(call_tool(params.get("name", ""),
                                params.get("arguments", {}) or {}))
        except hf_client.HiggsfieldError as e:
            return ok({"isError": True,
                       "content": [{"type": "text",
                                    "text": f"{type(e).__name__}: {e}"}]})
    if method and method.startswith("notifications/"):
        return None
    return err(-32601, f"method not found: {method}")


def main() -> None:
    inp, out = sys.stdin, sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            out.write(json.dumps(resp) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
