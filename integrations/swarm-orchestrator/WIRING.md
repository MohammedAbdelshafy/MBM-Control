# WIRING — swarm-orchestrator → MBM-Control / GLM workforce

## Where this power lives

**Product mapping:** MBM-Control — specifically the GLM workforce / swarm
control layer (revenue-first swarm runs, triage, digest, research).

**Workspace build:** `~/workspace/night-shift/swarm-orchestrator/`
**Branch copy:** `integrations/swarm-orchestrator/` on `night-shift/vibefounder-powers`
(MohammedAbdelshafy/MBM-Control)

## How it slots in

| Today (hand-rolled) | With this power |
|---|---|
| One agent run per task; serial fan-out code per job | `swarm_dispatch` fans one task to N CLI backends in parallel |
| GLM workforce = manual coordination of subagents | `swarm_dispatch_roles` gives researcher/coder/reviewer splits with zero coordination code |
| No audit of what ran where | `office_mailbox.jsonl` logs every detection/dispatch |
| New runner needed = new code | custom `catalog` spec plugs any CLI in without touching the library |

**Suggested wiring point:** `mbm-agent` / `jarvis_control_plane` swarm
runners — replace hand-rolled fan-out with `orchestrator.dispatch()` for the
parallel lanes (triage drafts, intel summaries, multi-backend code attempts),
keeping the existing task decomposition and approval flow untouched.
"What changes" is only the runner, exactly as the backlog prescribed.

**Cost note:** model spend stays with each CLI's own login/subscription —
the same economics Munder Difflin relies on. The free-tier NVIDIA NIM
integration (power #1) remains the cheapest backend lane where API-key
invocation fits.

## Honest Munder Difflin evaluation (2026-10-06)

- **Real:** canonical repo is `HarnessMD/munder-difflin` — 8,483 stars, MIT
  license, updated 2026-10-05. (Search-index forks like `chaitanyagiri/…`
  are stale/low-star copies.)
- **What it is:** an Electron GUI (React/Pixi/xterm) that wraps your existing
  CLI agent logins into a visual "office floor" — mailbox, memory, routing by
  your "clone". Powerful for a human watching; not scriptable headless.
- **Recommendation:** keep this repo's headless MCP server as the
  automation/programmatic layer (CI, cron, swarm jobs); use the actual
  Munder Difflin desktop app as the *visual* layer for the founder when he
  wants to watch agents work. They solve different halves of the same power.

## Activation

No API key needed. Needs at least one coding-agent CLI installed
(`claude`, `codex`, `gemini`, `qwen`, or `opencode` with a logged-in
session). On this VM `swarm_detect` currently finds none — mock-backed
tests pass; a live run needs a login on the host machine.
