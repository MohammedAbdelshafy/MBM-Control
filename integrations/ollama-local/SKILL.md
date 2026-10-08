---
name: ollama-local
description: Route non-critical MBM-Control work (reply-triage drafts, intel summaries, digest drafts, research notes) to a local Ollama instance at $0 marginal cost; client-facing kinds always return a frontier-required decision and are never auto-routed to a paid API. Use when the user wants zero-cost local inference, an offline-capable draft stage, or to verify Ollama wiring. Requires Ollama installed + a pulled model on the swarm host for actual generation.
---

# ollama-local

## Purpose

Local LLMs for the 80% of agent work nobody pays to see. MBM-Control's
background tasks — triage drafts, intel summaries, digest drafts, research
notes — run on a local Ollama instance ($0 marginal cost, works offline).
Client-facing or revenue-adjacent work stays on frontier models by
construction: the router defaults unknown kinds to frontier and never makes
a paid call silently.

Build home: `~/workspace/night-shift/ollama-local/`
MBM-Control drop-in: `integrations/ollama-local/` on branch
`night-shift/vibefounder-powers`

## Tooling

All scripts are stdlib-only (no pip installs).

| Script | Command | What it does |
|---|---|---|
| `ollama_router.py` | `python3 ollama_router.py --status` | Health check: reachable, models, config |
| `ollama_router.py` | `python3 ollama_router.py --models` | Tags pulled on the host |
| `ollama_router.py` | `python3 ollama_router.py --kinds` | Routing table (7 local kinds) |
| `ollama_router.py` | `python3 ollama_router.py --route <kind> "<prompt>"` | Route + run; exit 3 = frontier-required |
| `ollama_router.py` | `python3 ollama_router.py --generate "<prompt>"` | One local completion |
| `mcp_server.py` | stdio | 5 MCP tools (see below) |
| `test_smoke.py` | `python3 test_smoke.py` | 8/8 hermetic tests (fake Ollama server) |

Python API:

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/ollama-local")
from ollama_router import route_decision, route_task, generate, FrontierRequired

d = route_decision("digest-draft")   # pure, no network
# {"target": "local", "model": "qwen3:8b", ...}

try:
    out = route_task("digest-draft", [{"role": "user", "content": "draft it"}])
except FrontierRequired as e:
    out = frontier_client.chat(prompt)   # explicit paid path, your call
```

MCP tools: `ollama_status`, `ollama_models`, `ollama_generate`,
`ollama_route`, `ollama_route_decision` (pure planner, no network).

## Auth / config

- No API keys. Ever.
- `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL`
  (default `qwen3:8b`), `OLLAMA_TIMEOUT` (default `120`).
- Actual generation needs Ollama installed on the swarm host and a pulled
  model: `ollama pull qwen3:8b`. Missing model → error names the pull
  command. Server down → error says how to start it.

## Operating Rules

1. **Local kinds are internal drafts only** — reply-triage, intel-summary,
   digest-draft, research-note, dedupe-preview, prompt-rewrite,
   translate-draft. Anything else is frontier by default.
2. **Never bypass the routing policy for client-facing copy** — if
   `route_decision()` says frontier, the frontier call is made explicitly
   by the caller, never by this router.
3. **Verify model tags with `ollama_models`** — never guess a tag; a
   404 names the exact `ollama pull` command.
4. **Down server ≠ code bug** — `OllamaNotRunning` means start Ollama;
   do not "fix" the router.
5. Local models draft; humans or frontier models approve. Triage drafts are
   returned, never sent, by this integration.
