# ollama-local — $0 marginal inference for MBM-Control's background work

**VibeFounder power #7:** *"Run LLMs locally on Mac at 112 tok/s for $0/month"*
([Ollama field guide](https://www.instagram.com/p/Da3CSRKjqtN/)) → **MBM-Control**.

Every MBM-Control agent run currently burns paid API credits — including for
work nobody pays to see: reply-triage drafts, intel summaries, digest drafts,
research notes. This integration routes those non-critical task kinds to a
local Ollama instance (stdlib-only client, OpenAI-compatible endpoint) and
keeps client-facing work on frontier models. No paid endpoint is ever called
silently: frontier-routed tasks return a decision, never an API call.

## Layout

| File | What |
|---|---|
| `ollama_router.py` | stdlib client + routing policy + CLI |
| `mcp_server.py` | stdlib MCP stdio server (5 tools) |
| `test_smoke.py` | hermetic tests — fake Ollama server on localhost; no network, no keys |
| `SKILL.md` | reusable skill doc |
| `WIRING.md` | where this plugs into MBM-Control (swarm runners, Reporting Digest) |
| `TEST_EVIDENCE.md` | test results |

## Quickstart

```bash
# 1. Ollama must be running somewhere reachable (founder's Mac, a local box):
ollama serve
ollama pull qwen3:8b        # any tag from `ollama list` works

# 2. Point the router at it (defaults shown):
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="qwen3:8b"
export OLLAMA_TIMEOUT="120"

# 3. Check + generate:
python3 ollama_router.py --status
python3 ollama_router.py --route digest-draft "draft today's digest"
```

## Routing policy

**Local (runs on Ollama, $0):** `reply-triage`, `intel-summary`,
`digest-draft`, `research-note`, `dedupe-preview`, `prompt-rewrite`,
`translate-draft` (aliases: `triage`, `summary`, `digest`, `note`).

**Frontier (never auto-called):** everything else. `route_task()` raises
`FrontierRequired`; the CLI exits 3 with a JSON decision on stderr; the MCP
`ollama_route` tool returns the decision payload. A paid provider is wired
only when the caller explicitly takes the decision and calls their own
frontier client.

## MCP tools

`ollama_status`, `ollama_models`, `ollama_generate`, `ollama_route`,
`ollama_route_decision` (pure planner — no network).

Wire-up (Claude Code / Cursor):

```json
{"mcpServers": {"ollama-local": {
  "command": "python3",
  "args": ["/abs/path/to/mcp_server.py"]}}}
```

## Honest limits

- **No Ollama here.** This VM has no `ollama` binary, no GPU, and no local
  server (verified 2026-10-08) — live generation is untested on this machine.
  All behavior is proven hermetically against a fake Ollama server in
  `test_smoke.py` (8/8 pass). Activation = install Ollama on the host that
  runs the swarm, `ollama pull <model>`, set `OLLAMA_HOST`.
- Model quality: local 4–8B models draft internal material well; they are
  **not** a substitute for frontier models on client-facing copy — the
  routing policy enforces that by construction.
- The reel's "112 tok/s" is the creator's Mac hardware claim, not a number
  this integration promises. Local throughput depends on the host.
