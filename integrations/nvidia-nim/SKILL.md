---
name: nvidia-free-models
description: Route LLM inference through NVIDIA NIM's free tier (80+ frontier models, OpenAI-compatible API at https://integrate.api.nvidia.com/v1) instead of paid credits. Use when the user wants free model access, wants to point the MBM-Control agent swarm (or any OpenAI-compatible agent) at a free inference provider, needs a model recommendation per task type (coding/chat/vision/reasoning), or needs to verify NVIDIA provider wiring. Requires NVIDIA_API_KEY from build.nvidia.com for actual chat calls.
---

# nvidia-free-models

## Purpose

NVIDIA's NIM API exposes 80+ frontier models (Llama, Mistral, DeepSeek,
Kimi, GLM, Nemotron, ...) through one OpenAI-compatible endpoint with a
**free** API key. This skill wraps it so the MBM-Control agent swarm (or any
agent) can route inference through the free tier instead of spending paid
credits.

Build home: `~/workspace/night-shift/nvidia-free-models/`
MBM-Control drop-in: `~/workspace/night-shift/nvidia-free-models/mbm-control/nvidia-nim/`

## Tooling

All scripts are stdlib-only (no pip installs).

| Script | Command | What it does |
|---|---|---|
| `nvidia_router.py` | `python3 nvidia_router.py --list` | Print all 81 catalog model ids |
| `nvidia_router.py` | `python3 nvidia_router.py --pick coding` | Recommended model id for `coding\|chat\|vision\|reasoning` |
| `nvidia_router.py` | `python3 nvidia_router.py --refresh` | Re-fetch live catalog, overwrite saved copy |
| `bin/nvidia_chat.py` | `python3 bin/nvidia_chat.py --model <id> "prompt"` | One chat completion |
| `bin/nvidia_chat.py` | `python3 bin/nvidia_chat.py "prompt"` | One chat completion (auto-picks chat model) |
| `mbm-control/nvidia-nim/test_provider.py` | `python3 mbm-control/nvidia-nim/test_provider.py` | Verify wiring without a key |

Python API:

```python
import sys
sys.path.insert(0, "/home/hatch/workspace/night-shift/nvidia-free-models")
from nvidia_router import chat, pick_model, list_models

model = pick_model("coding")          # e.g. mistralai/codestral-22b-instruct-v0.1
resp = chat(model, [{"role": "user", "content": "write a dedupe function"}])
print(resp["choices"][0]["message"]["content"])
```

Model reference: `models.json` (36 curated ids with `role` tags:
chat/coding/vision/reasoning, `free_tier: true`). Full 81-model live list:
`~/workspace/night-shift/nvidia_models_2026-10-04.json`.
MBM-Control integration docs: `mbm-control/nvidia-nim/PROVIDER.md`;
routing table: `mbm-control/nvidia-nim/swarm.models.yaml`.

## Auth

- Actual chat calls need `NVIDIA_API_KEY` in the environment.
- The free key comes from **https://build.nvidia.com** (sign in → generate).
- **Never invent a key, never hardcode one, never commit one.**
- Without the key, `bin/nvidia_chat.py` prints the exact `export` command and
  exits 2; `test_provider.py` still verifies everything else.

## Operating Rules

1. **Never hardcode API keys** — env vars only (`NVIDIA_API_KEY`).
2. **Verify model ids against the catalog** — use exact `id` strings from
   `models.json` or `nvidia_router.py --list`. Never guess an id.
3. **401 means bad/missing key, not a code bug** — re-issue the key at
   build.nvidia.com; do not "fix" working code.
4. **No silent paid fallback** — the router only touches a paid endpoint when
   BOTH `OPENAI_API_KEY` and `OPENAI_BASE_URL` are explicitly set; otherwise
   it raises a clear error naming the key problem.
5. `pick_model("embeddings")` intentionally raises — this build routes no
   embedding model on the free tier; configure a dedicated embeddings provider.
6. `GET /v1/models` needs no key and is the canary: if it stops returning 200,
   the endpoint or network is the problem, not auth.
