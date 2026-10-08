# TEST EVIDENCE — ollama-local (VibeFounder power #7)

**Date:** 2026-10-08 | **Run:** `vibefounder-night-shift` | **Command:** `python3 test_smoke.py`
**Result: 8/8 PASS** — hermetic (fake Ollama HTTP server on 127.0.0.1; no
external network, no Ollama install, no keys).

```
PASS status_and_models — models=['qwen3:8b', 'gemma3:4b']
PASS generate_and_chat — chat+generate OK
PASS route_policy_local_and_frontier — 7 local kinds; frontier kinds raise, never call paid API
PASS unreachable_host — OllamaNotRunning + status ok=false
PASS model_not_pulled — ModelNotPulled names the pull command
PASS validation — 6 bad inputs rejected
PASS mcp_protocol — 5 tools over stdio; error path OK
PASS cli — --kinds/--route CLI paths OK
```

What each test proves:

| # | Test | Proves |
|---|---|---|
| 1 | status_and_models | `/api/tags` parsed; default model presence detected; local kinds listed |
| 2 | generate_and_chat | `/v1/chat/completions` shape handled; `generate()` returns text |
| 3 | route_policy_local_and_frontier | 7 local kinds execute; aliases resolve; frontier kinds raise `FrontierRequired` with zero network calls |
| 4 | unreachable_host | down server → `OllamaNotRunning` with the `ollama serve` hint; `status()` reports `ok: false` |
| 5 | model_not_pulled | 404 → `ModelNotPulled` naming the exact `ollama pull <tag>` command |
| 6 | validation | empty/bad message lists, bad roles, blank prompts rejected before any I/O |
| 7 | mcp_protocol | stdio JSON-RPC: initialize → tools/list (5 tools) → route decision (local), route (frontier decision, not executed), route (local, executed), unknown-tool error path |
| 8 | cli | `--kinds` lists 7 kinds; `--route outreach-copy` exits 3 with frontier JSON; `--route intel-summary` runs and returns text |

**Not tested here (documented, not claimed):** a real Ollama server and real
model tags — this VM has no `ollama` binary, no GPU, and no server on
localhost:11434 (verified 2026-10-08). `WIRING.md` states the activation
checklist plainly. Also untested: real tok/s throughput (the reel's
"112 tok/s" is the creator's hardware claim, not this integration's).
