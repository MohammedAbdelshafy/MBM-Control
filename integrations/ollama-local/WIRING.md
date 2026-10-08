# WIRING — ollama-local into MBM-Control

Where this integration plugs into the founder's stack. All wiring points
are code-ready patterns, not live edits to MBM-Control (the branch copy
lives at `integrations/ollama-local/` on `night-shift/vibefounder-powers`).

## 1. Swarm runners (mbm-agent / jarvis_control_plane)

Pattern — wrap the existing model call with the routing decision:

```python
import sys
sys.path.insert(0, "<mbm-control>/integrations/ollama-local")
from ollama_router import route_decision, generate, FrontierRequired

decision = route_decision(task_kind)          # pure, no network
if decision["target"] == "local":
    draft = generate(prompt, model=decision["model"])   # $0
else:
    draft = frontier_client.chat(prompt)      # existing paid path, explicit
```

Task kinds already classified as local-safe:
`reply-triage`, `intel-summary`, `digest-draft`, `research-note`,
`dedupe-preview`, `prompt-rewrite`, `translate-draft`.

**Guardrail:** `route_decision()` defaults unknown kinds to frontier, so a
new task kind can never silently downgrade to a local model.

## 2. Reporting Digest (scheduled)

The digest cron currently drafts on paid credits. Rewire:

1. Draft body via `ollama_route(kind="digest-draft", prompt=...)`
   (MCP tool) or the CLI `--route digest-draft`.
2. Human (or a frontier reviewer agent) approves/edits before send.
3. Send path unchanged.

Expected saving: the entire draft stage moves to $0 marginal cost; only
the optional frontier review pass costs credits.

## 3. Reply triage

`route_task("reply-triage", ...)` classifies an inbound reply and drafts a
suggested response. The draft is returned, never sent — the existing
approval/send flow stays the human (or gate) checkpoint.

## 4. Complements, doesn't replace

- **nvidia-free-models (power #1):** free *frontier-class* models via one key
  — for client-facing work once `NVIDIA_API_KEY` exists.
- **ollama-local (power #7):** $0 *local* models — for internal drafts, no
  key, no network dependency, works offline.

Use both: local drafts → frontier polish on the paid/free-tier frontier key.

## Activation checklist (founder or whoever owns the swarm host)

- [ ] Install Ollama on the swarm host (`https://ollama.com`)
- [ ] `ollama pull qwen3:8b` (or `gemma3:4b` for smaller boxes)
- [ ] `export OLLAMA_HOST=http://<host>:11434` where the swarm runs
- [ ] `python3 ollama_router.py --status` → `ok: true`
- [ ] Point one non-critical cron (digest draft) at `--route digest-draft`
