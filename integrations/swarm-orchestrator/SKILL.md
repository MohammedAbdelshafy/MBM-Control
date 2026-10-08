# Skill: swarm-orchestrator

Parallelize any coding task across every CLI coding agent installed on the
machine — the headless "Munder Difflin" power for MBM-Control's GLM workforce.

## When to use

- A task that benefits from **parallel attempts**: bug hunts, refactors,
  research sweeps, test generation across backends.
- You want **role-split teamwork**: one backend researches, a different one
  codes, a third reviews.
- You need a **pre-flight plan** before spending model time: `swarm_plan`
  shows role→backend assignments without spawning anything.

## How (MCP tools)

1. `swarm_detect` — see which agent CLIs exist here (claude/codex/gemini/qwen/opencode).
2. `swarm_plan(task, roles=["researcher","coder","reviewer"])` — dry assignment map.
3. Execute:
   - `swarm_dispatch(task, backends=[...], timeout=600, dry_run=false)` — same prompt everywhere.
   - `swarm_dispatch_roles(task, roles=[...], timeout=900, dry_run=false)` — role-split team run.
4. `swarm_events(limit=50)` — audit what ran.

## Rules

- **Always `dry_run=true` first** when backends are unfamiliar — it echoes the
  exact argv that would run.
- Prefer `swarm_dispatch_roles` for build tasks (research → code → review),
  `swarm_dispatch` for "give me 3 independent takes" tasks.
- Cap `timeout` to the task: 300s for research, 900s for builds.
- If `swarm_detect` finds no backends, install at least one CLI
  (`claude`, `codex`, `gemini`, `qwen`, or `opencode`) or supply a custom
  catalog spec via `orchestrator.dispatch(catalog={...})`.
- Never paste secrets into task prompts — they go to subprocess CLIs.

## Wire-up

```json
{"mcpServers": {"swarm-orchestrator": {
    "command": "python3",
    "args": ["<abs path>/mcp_server.py"]}}}
```

See `WIRING.md` for the MBM-Control / GLM-workforce integration map.
