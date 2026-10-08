# swarm-orchestrator — Munder Difflin pattern as a headless MCP power

**VibeFounder power #6** — *"Orchestrate 10 parallel CLI coding agents from one
task"* ([Munder Difflin reel](https://www.instagram.com/reel/DcbJE6Tj4vY/)) —
implemented as a working MCP server + Python library + reusable skill.

## What it does

Turns the terminal coding-agent CLIs you already run (`claude`, `codex`,
`gemini`, `qwen`, `opencode`) into a parallel office of agents:

- **`swarm_detect`** — scan PATH for installed agent CLIs (+ `--version` probe).
- **`swarm_plan`** — pure pre-flight: role → backend assignments, nothing spawns.
- **`swarm_dispatch`** — fan one task prompt out to N backends in parallel;
  per-backend exit code, output, timing. `dry_run` echoes the exact argv.
- **`swarm_dispatch_roles`** — role-split a task (researcher / coder /
  reviewer), one backend per role, merged team report.
- **`swarm_events`** — read the office mailbox (`office_mailbox.jsonl` event log).

Everything runs headless over stdio — the same swarm power as Munder
Difflin's 2D office floor, minus the Electron GUI.

## Quick start

```bash
python3 test_smoke.py          # 8/8 hermetic tests, no network, no real CLIs
python3 orchestrator.py        # built-in self-check
```

MCP wire-up (Claude Code / Cursor):

```json
{"mcpServers": {"swarm-orchestrator": {
    "command": "python3",
    "args": ["<abs path>/mcp_server.py"]}}}
```

Then from an agent: `swarm_detect` → `swarm_plan(task)` → `swarm_dispatch`
or `swarm_dispatch_roles(task)`. Pre-flight with `dry_run=true` first.

## Files

| File | What |
|---|---|
| `orchestrator.py` | core: catalog, `detect_backends`, `dispatch`, `dispatch_roles`, event log |
| `mcp_server.py` | stdio MCP server (stdlib only), 5 tools |
| `test_smoke.py` | 8 hermetic smoke tests (mock backends on temp PATH) |
| `SKILL.md` | reusable skill: when/how to use this power |
| `WIRING.md` | mapping into MBM-Control + honest Munder Difflin evaluation |
| `TEST_EVIDENCE.md` | test evidence for this integration |

## Backend catalog (honest flags)

Only `claude -p`, `codex exec`, `gemini -p`, `qwen -p`, `opencode run` are in
the catalog — flags the author trusts. Other CLIs (grok, kimi, crush,
copilot, ...) plug in as custom specs: `dispatch(..., catalog={...})`.
Nothing here invents a flag for a CLI it hasn't verified.

## Safety

- Runs run in parallel threads with a per-backend `timeout` (default 600s);
  timeouts and crashes are captured as structured results, never exceptions.
- Outputs are truncated at 200K chars with a flag; prompts stay on your
  machine; model cost stays with each CLI's own login/subscription.
- The event log (`office_mailbox.jsonl`) is append-only audit history of
  every detection and dispatch.
