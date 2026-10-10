#!/usr/bin/env python3
"""MCP stdio server exposing AI voice calling to agents.

Stdlib only — no `mcp` package required. Speaks JSON-RPC 2.0 over stdio with
the MCP initialize / tools/list / tools/call surface.

Tools:
  voice_config_check      — which config slots are set (no secrets shown)
  voice_assistant_create  — create a Vapi assistant (dry-run default)
  voice_call_start        — start one outbound call (dry-run default)
  voice_call_status       — one status snapshot for a call_id
  voice_call_list         — list recent calls
  voice_campaign_run      — CSV leads -> calls (dry-run default; DNC + disclosure enforced)
  voice_cost_estimate     — pre-flight USD estimate (no network)
  voice_dnc_check         — check numbers against a DNC CSV

Env: VAPI_API_KEY (required for live), VAPI_ASSISTANT_ID,
     VAPI_PHONE_NUMBER_ID, VAPI_BASE_URL.

Every mutating tool takes dry_run=true by default: validation, DNC and
disclosure checks run, no network call is made, nothing is charged.

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"ai-voice-calls": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"],
      "env": {"VAPI_API_KEY": "..."}}}}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import voice_calls as vc  # noqa: E402

SERVER_NAME = "ai-voice-calls"
SERVER_VERSION = "1.0.0"


def _client():
    return vc.VapiClient(vc.Config.from_env())


TOOL_SPECS = [
    {"name": "voice_config_check",
     "description": "Report which voice-call config slots are set. "
                    "No secrets are ever echoed.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "voice_assistant_create",
     "description": "Create a Vapi assistant. dry_run=true validates the "
                    "config (incl. AI-disclosure check) without calling the API.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "assistant": {"type": "object",
                           "description": "assistant config (model, firstMessage, ...)"},
             "dry_run": {"type": "boolean", "default": True}},
         "required": ["assistant"]}},
    {"name": "voice_call_start",
     "description": "Start one outbound AI call. dry_run=true validates "
                    "(E.164, DNC, disclosure) and estimates cost; no call placed.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "number": {"type": "string",
                        "description": "E.164 phone number, e.g. +14155551234"},
             "assistant_id": {"type": "string"},
             "phone_number_id": {"type": "string"},
             "dnc_csv": {"type": "string",
                         "description": "path to DNC suppression CSV"},
             "dry_run": {"type": "boolean", "default": True}},
         "required": ["number"]}},
    {"name": "voice_call_status",
     "description": "One status snapshot for a call_id (live only).",
     "inputSchema": {"type": "object",
                     "properties": {"call_id": {"type": "string"}},
                     "required": ["call_id"]}},
    {"name": "voice_call_list",
     "description": "List recent calls (live only).",
     "inputSchema": {"type": "object",
                     "properties": {"limit": {"type": "integer", "default": 20}}}},
    {"name": "voice_campaign_run",
     "description": "Run an outbound campaign over a leads CSV "
                    "(number,name,consent[, ...]). dry_run=true simulates; "
                    "DNC suppression and AI-disclosure checks always enforced.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "leads_csv": {"type": "string"},
             "assistant_id": {"type": "string"},
             "phone_number_id": {"type": "string"},
             "dnc_csv": {"type": "string"},
             "interval_s": {"type": "number", "default": 10.0},
             "dry_run": {"type": "boolean", "default": True}},
         "required": ["leads_csv"]}},
    {"name": "voice_cost_estimate",
     "description": "Pre-flight USD estimate for a campaign. No network, "
                    "never charged.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "num_calls": {"type": "integer"},
             "avg_minutes": {"type": "number", "default": 2.0}},
         "required": ["num_calls"]}},
    {"name": "voice_dnc_check",
     "description": "Check phone numbers against a DNC CSV.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "numbers": {"type": "array", "items": {"type": "string"}},
             "dnc_csv": {"type": "string"}},
         "required": ["numbers"]}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def _dry_disclosure_ok(args: dict) -> None:
    ov = args.get("assistant_overrides") or {}
    fm = ov.get("firstMessage") or ""
    if fm:
        vc.ensure_ai_disclosure(fm)


def call_tool(name: str, args: dict) -> dict:
    if name == "voice_config_check":
        cfg = vc.Config.from_env(require_key=False)
        return _text({
            "VAPI_API_KEY": "set" if cfg.key_set() else "MISSING",
            "VAPI_ASSISTANT_ID": "set" if cfg.assistant_id else "not set",
            "VAPI_PHONE_NUMBER_ID": "set" if cfg.phone_number_id else "not set",
            "VAPI_BASE_URL": cfg.base_url,
            "blocked_on_key": not cfg.key_set(),
        })
    if name == "voice_assistant_create":
        assistant = args["assistant"]
        if not isinstance(assistant, dict) or not assistant.get("model"):
            raise vc.ValidationError(
                "assistant must be a dict with at least a 'model' key")
        fm = assistant.get("firstMessage") or ""
        vc.ensure_ai_disclosure(fm)  # enforced even in dry-run
        if args.get("dry_run", True):
            return _text({"dry_run": True,
                          "valid": True,
                          "name": assistant.get("name"),
                          "disclosure_ok": True,
                          "note": "no assistant created; re-run with dry_run=false"})
        return _text(_client().create_assistant(assistant))
    if name == "voice_call_start":
        number = vc.validate_e164(args["number"])
        dnc = vc.DncList.from_csv(args["dnc_csv"]) if args.get("dnc_csv") else vc.DncList()
        if dnc.is_suppressed(number):
            raise vc.ValidationError(f"{number} is on the DNC suppression list")
        _dry_disclosure_ok(args)
        if args.get("dry_run", True):
            return _text({
                "dry_run": True, "number": number, "valid": True,
                "cost_estimate": vc.estimate_cost(1),
                "note": "no call placed; re-run with dry_run=false"})
        return _text(_client().start_call(
            number,
            assistant_id=args.get("assistant_id"),
            phone_number_id=args.get("phone_number_id")))
    if name == "voice_call_status":
        return _text(_client().get_call(args["call_id"]))
    if name == "voice_call_list":
        return _text(_client().list_calls(limit=args.get("limit", 20)))
    if name == "voice_campaign_run":
        leads, warnings = vc.load_leads_csv(args["leads_csv"])
        dnc = vc.DncList.from_csv(args["dnc_csv"]) if args.get("dnc_csv") else vc.DncList()
        runner = vc.CampaignRunner(
            client=None if args.get("dry_run", True) else _client(),
            dnc=dnc, dry_run=args.get("dry_run", True))
        results = runner.run(
            leads,
            assistant_id=args.get("assistant_id"),
            phone_number_id=args.get("phone_number_id"),
            interval_s=args.get("interval_s", 10.0))
        return _text({"dry_run": args.get("dry_run", True),
                      "warnings": warnings,
                      "cost_estimate": vc.estimate_cost(len(leads)),
                      "results": results})
    if name == "voice_cost_estimate":
        return _text(vc.estimate_cost(args["num_calls"],
                                      args.get("avg_minutes", 2.0)))
    if name == "voice_dnc_check":
        dnc = vc.DncList.from_csv(args["dnc_csv"]) if args.get("dnc_csv") else vc.DncList()
        return _text({n: ("suppressed" if dnc.is_suppressed(n) else "clear")
                      for n in args["numbers"]})
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
        except vc.VoiceCallsError as e:
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
