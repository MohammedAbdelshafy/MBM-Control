#!/usr/bin/env python3
"""MCP stdio server exposing the interactive pitch-deck builder (power #8).

Stdlib only — no `mcp` package required. JSON-RPC 2.0 over stdio:
initialize / tools/list / tools/call.

Tools:
  deck_create       — start a deck (title, theme, subtitle, author)
  deck_add_slide    — append a slide: cover | bullets | statement |
                      widget | chart | pricing | cta
  deck_get          — deck JSON (slide spec)
  deck_list         — all decks in this server process
  deck_export_html  — render to a single self-contained HTML file
  deck_render_html  — render to an HTML string (no file write)

Decks live in memory, keyed by deck_id, for the life of the server
process. Use deck_export_html for anything you want to keep.

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"bolt-slides": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"]}}}
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deck_builder  # noqa: E402
from deck_builder import Deck  # noqa: E402

SERVER_NAME = "bolt-slides"
SERVER_VERSION = deck_builder.VERSION

_DECKS: dict[str, Deck] = {}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


TOOL_SPECS = [
    {"name": "deck_create",
     "description": "Start a new interactive pitch deck. Returns a deck_id "
                    "for the other tools.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "title": {"type": "string"},
             "subtitle": {"type": "string"},
             "theme": {"type": "string",
                       "description": "midnight (default) or paper"},
             "author": {"type": "string"}},
         "required": ["title"]}},
    {"name": "deck_add_slide",
     "description": "Append one slide to a deck. kind: cover | bullets | "
                    "statement | widget | chart | pricing | cta. payload "
                    "fields per kind — see SKILL.md for the full spec.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "deck_id": {"type": "string"},
             "kind": {"type": "string"},
             "payload": {"type": "object"},
             "notes": {"type": "string",
                       "description": "presenter notes (press N while "
                                      "presenting)"}},
         "required": ["deck_id", "kind", "payload"]}},
    {"name": "deck_get",
     "description": "Return a deck's full JSON slide spec.",
     "inputSchema": {
         "type": "object",
         "properties": {"deck_id": {"type": "string"}},
         "required": ["deck_id"]}},
    {"name": "deck_list",
     "description": "List decks in this server process "
                    "(id, title, slide count).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "deck_export_html",
     "description": "Render a deck to ONE self-contained HTML file "
                    "(no CDN, no network needed to present). Returns the "
                    "absolute path written.",
     "inputSchema": {
         "type": "object",
         "properties": {
             "deck_id": {"type": "string"},
             "path": {"type": "string",
                      "description": "output .html path"}},
         "required": ["deck_id", "path"]}},
    {"name": "deck_render_html",
     "description": "Render a deck to an HTML string without writing a "
                    "file. For inspection / piping, not for presenting.",
     "inputSchema": {
         "type": "object",
         "properties": {"deck_id": {"type": "string"}},
         "required": ["deck_id"]}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}]}


def _deck(deck_id: str) -> Deck:
    try:
        return _DECKS[deck_id]
    except KeyError:
        raise ValueError(f"unknown deck_id: {deck_id!r}") from None


_BUILDERS = {
    "cover": lambda d, p: d.add_cover(
        p.get("kicker", ""), p.get("title", ""), p.get("subtitle", ""),
        p.get("cta", "")),
    "bullets": lambda d, p: d.add_bullets(p.get("title", ""),
                                          p.get("items", [])),
    "statement": lambda d, p: d.add_statement(p.get("text", ""),
                                              p.get("sub", "")),
    "widget": lambda d, p: d.add_widget(p.get("widget", ""),
                                        p.get("title", ""),
                                        p.get("config")),
    "chart": lambda d, p: d.add_chart(p.get("title", ""),
                                      [tuple(s) for s in p.get("series", [])]),
    "pricing": lambda d, p: d.add_pricing(p.get("title", ""),
                                         p.get("tiers", [])),
    "cta": lambda d, p: d.add_cta(p.get("title", ""),
                                  p.get("lines", []),
                                  p.get("button_text", "Start →"),
                                  p.get("button_url", "")),
}


def call_tool(name: str, args: dict) -> dict:
    if name == "deck_create":
        deck_id = _new_id()
        _DECKS[deck_id] = Deck(
            args["title"],
            subtitle=args.get("subtitle", ""),
            theme=args.get("theme", "midnight"),
            author=args.get("author", ""))
        return _text({"deck_id": deck_id,
                      "title": args["title"], "slides": 0})
    if name == "deck_add_slide":
        deck = _deck(args["deck_id"])
        kind = args["kind"]
        if kind not in _BUILDERS:
            raise ValueError(
                f"unknown slide kind: {kind!r} "
                f"(expected one of {sorted(_BUILDERS)})")
        idx = _BUILDERS[kind](deck, args.get("payload") or {})
        notes = args.get("notes", "")
        if notes:
            deck.slides[idx]["notes"] = notes
        return _text({"deck_id": args["deck_id"], "slide_index": idx,
                      "kind": kind, "total_slides": len(deck.slides)})
    if name == "deck_get":
        return _text(_deck(args["deck_id"]).to_dict())
    if name == "deck_list":
        return _text([{"deck_id": did, "title": d.title,
                       "slides": len(d.slides)}
                      for did, d in _DECKS.items()])
    if name == "deck_export_html":
        deck = _deck(args["deck_id"])
        out = deck.save(args["path"])
        return _text({"deck_id": args["deck_id"],
                      "path": str(out.resolve()),
                      "slides": len(deck.slides),
                      "bytes": out.stat().st_size})
    if name == "deck_render_html":
        return _text({"deck_id": args["deck_id"],
                      "html": _deck(args["deck_id"]).render_html()})
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
