#!/usr/bin/env python3
"""MCP stdio server for the ECC skill-intake hub (power #9).

Stdlib only — no `mcp` package required. JSON-RPC 2.0 over stdio:
initialize / tools/list / tools/call.

Tools:
  skill_list      — the 9 vetted picks (slug, product, role, verdict)
  skill_get       — full SKILL.md text of one pick (+ its bundled agents)
  skill_search    — match picks by keyword against slug/role/why/product
  pick_install    — copy a pick into a target dir (dry_run default)
  audit_run       — run the safety/inventory auditor on any repo path

Wire-up example (Claude Code / Cursor):
  {"mcpServers": {"ecc-skill-hub": {
      "command": "python3",
      "args": ["<abs path>/mcp_server.py"]}}}
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit as audit_mod  # noqa: E402
import library  # noqa: E402

SERVER_NAME = "ecc-skill-hub"
SERVER_VERSION = "1.0.0"


def _pick_dict(p: library.Pick) -> dict:
    return {
        "slug": p.slug,
        "product": p.product,
        "role": p.role,
        "verdict": p.verdict,
        "needs": p.needs,
        "note": p.note,
    }


TOOL_SPECS = [
    {"name": "skill_list",
     "description": "List the 9 vetted ECC cherry-picks with product "
                    "mapping, role, and safety verdict.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "skill_get",
     "description": "Return the full SKILL.md of one pick (plus names of "
                    "any bundled sub-agent files).",
     "inputSchema": {"type": "object",
                     "properties": {"slug": {"type": "string"}},
                     "required": ["slug"]}},
    {"name": "skill_search",
     "description": "Keyword search over the 9 picks (slug, role, why, "
                    "product).",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"}},
                     "required": ["query"]}},
    {"name": "pick_install",
     "description": "Copy a pick's vendored files into target_dir. "
                    "dry_run=true (default) only reports what would copy. "
                    "Copies are pinned to the vendored commit; the hub never "
                    "pulls from the network.",
     "inputSchema": {"type": "object",
                     "properties": {
                         "slug": {"type": "string"},
                         "target_dir": {"type": "string"},
                         "dry_run": {"type": "boolean", "default": True}},
                     "required": ["slug", "target_dir"]}},
    {"name": "audit_run",
     "description": "Run the safety/inventory auditor against a local repo "
                    "path (read-only, hermetic). Returns agent/skill/command "
                    "counts and HIGH/MEDIUM/INFO findings.",
     "inputSchema": {"type": "object",
                     "properties": {
                         "repo_path": {"type": "string"},
                         "scan_dir": {"type": "string",
                                      "description": "optional subdir to "
                                                     "limit the scan"}}}},
]


def _handle(name: str, args: dict) -> dict:
    if name == "skill_list":
        return {"picks": [_pick_dict(p) for p in library.PICKS],
                "source": library.SOURCE_REPO,
                "pinned_commit": library.PINNED_COMMIT}

    if name == "skill_get":
        p = library.get(args["slug"])
        files = sorted(f.name for f in p.path.rglob("*") if f.is_file())
        return {"slug": p.slug, "meta": _pick_dict(p),
                "files": files, "skill_md": p.read_skill()}

    if name == "skill_search":
        hits = library.search(args["query"])
        return {"query": args["query"],
                "hits": [_pick_dict(p) for p in hits]}

    if name == "pick_install":
        p = library.get(args["slug"])
        if not p.has_skill():
            return {"ok": False, "error": f"pick missing: {p.slug}"}
        src, dst = p.path, Path(args["target_dir"]).expanduser().resolve()
        files = sorted(str(f.relative_to(src)) for f in src.rglob("*")
                       if f.is_file())
        if args.get("dry_run", True):
            return {"ok": True, "dry_run": True, "slug": p.slug,
                    "target": str(dst), "files": files}
        if dst.exists():
            return {"ok": False,
                    "error": f"target exists, refusing to overwrite: {dst}"}
        shutil.copytree(src, dst)
        return {"ok": True, "dry_run": False, "slug": p.slug,
                "target": str(dst), "files": files,
                "pinned_commit": library.PINNED_COMMIT}

    if name == "audit_run":
        repo = Path(args["repo_path"]).expanduser()
        report = audit_mod.scan_repo(repo, args.get("scan_dir"))
        return report.to_dict()

    return {"ok": False, "error": f"unknown tool: {name}"}


def _read_message() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        rid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        def respond(result=None, error=None):
            msg = {"jsonrpc": "2.0", "id": rid}
            if error is not None:
                msg["error"] = error
            else:
                msg["result"] = result
            sys.stdout.write(json.dumps(msg) + "\n")
            sys.stdout.flush()

        # notifications (no id) get no response
        is_notification = rid is None

        if method == "initialize":
            respond({"protocolVersion": "2024-11-05",
                     "serverInfo": {"name": SERVER_NAME,
                                   "version": SERVER_VERSION},
                     "capabilities": {"tools": {}}})
        elif method == "tools/list":
            respond({"tools": TOOL_SPECS})
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            try:
                out = _handle(name, args)
            except (KeyError, FileNotFoundError, OSError) as exc:
                respond(error={"code": -32000, "message": str(exc)})
                continue
            respond({"content": [{"type": "text",
                                  "text": json.dumps(out, indent=2)}]})
        elif method in ("notifications/initialized", "notifications/cancelled"):
            pass  # true JSON-RPC notifications: no response
        elif not is_notification:
            respond(error={"code": -32601,
                           "message": f"unknown method: {method}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
