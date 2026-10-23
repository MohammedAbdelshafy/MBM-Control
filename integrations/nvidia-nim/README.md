# nvidia-free-models — Night-Shift Build (Power 1 of 3)

Call 80+ frontier models free through one API key: NVIDIA NIM's
OpenAI-compatible endpoint at `https://integrate.api.nvidia.com/v1`.
Verified live 2026-10-04: `GET /v1/models` returns HTTP 200 **without a key**,
listing 81 models.

## What it does

- `nvidia_router.py` — working OpenAI-compatible client wrapper (stdlib only).
  `chat(model, messages, **kw)` sends a chat completion; `list_models()`
  reads the real saved catalog (refreshable live via `--refresh`);
  `pick_model(task_type)` returns the best catalog-verified id for
  `coding` / `chat` / `vision` / `reasoning`.
- `models.json` — 36 curated model ids with `role` tags
  (chat/coding/vision/reasoning), every id verified against the real saved
  response.
- `bin/nvidia_chat.py` — one-shot CLI: `python3 bin/nvidia_chat.py --model <id> "prompt"`.
- `mbm-control/nvidia-nim/` — drop-in for the MBM-Control repo:
  `PROVIDER.md` (endpoint/auth/model table), `swarm.models.yaml`
  (task_type → model id routing), `test_provider.py` (keyless wiring check).
- `SKILL.md` — workspace skill so the main agent can invoke all of this.

## Configure

Two lanes, same endpoint:

**A. Vault-keyed live lane (this VM, no key in env)** — the founder's free
NVIDIA key is registered in the vault (`custom.nvidia-nim` connector). Use
`bin/nvidia_live.py`; the helper swaps the real key in only for
`integrate.api.nvidia.com`. Nothing to export, nothing to commit.

**B. Env-key lane (swarm hosts / machines without the vault)** — one thing
is needed for real inference: a **free** key:

```bash
# 1. Get a free key: sign in at https://build.nvidia.com and generate one.
# 2. Export it (never hardcode, never commit):
export NVIDIA_API_KEY='nvapi-YOUR_KEY_HERE'
```

The key slot is `NVIDIA_API_KEY`. Nothing is bundled; nothing is invented.

## Run

```bash
cd ~/workspace/night-shift/nvidia-free-models

# list all 81 models (no key needed)
python3 nvidia_router.py --list

# recommended model per task (no key needed)
python3 nvidia_router.py --pick coding

# one chat completion (needs NVIDIA_API_KEY)
python3 bin/nvidia_chat.py --model mistralai/codestral-22b-instruct-v0.1 "write a python dedupe function"

# LIVE LANE (vault key, this VM — no env key needed)
python3 bin/nvidia_live.py --models        # live model count via vault lane
python3 bin/nvidia_live.py --probe         # first healthy chat model
python3 bin/nvidia_live.py --chat z-ai/glm-5.3-flash "say hi in 5 words"

# activation test: 4 hermetic + 4 live checks
python3 test_activation.py

# verify provider wiring for MBM-Control (no key needed)
python3 mbm-control/nvidia-nim/test_provider.py
```

## How MBM-Control uses it

Copy `mbm-control/nvidia-nim/` into the repo (repo-relative path
`mbm-control/nvidia-nim/`), set the swarm's provider to
`base_url: https://integrate.api.nvidia.com/v1` with
`api_key_env: NVIDIA_API_KEY` (see `PROVIDER.md`), and route task types via
`swarm.models.yaml`. Any OpenAI-compatible agent config or SDK works — just
swap base URL + key.

Failure semantics are explicit: **401** = missing/invalid/revoked key
(re-issue at build.nvidia.com, not a code bug); **429** = free-tier rate
limit, back off. Paid fallback engages **only** when both `OPENAI_API_KEY`
and `OPENAI_BASE_URL` are explicitly set — the router never silently spends
paid credits.

## Status

**ACTIVATED 2026-10-23** — the founder's free NVIDIA API key is live in the
vault (registered 2026-10-22; `custom.nvidia-nim` connector). This build no
longer needs `NVIDIA_API_KEY` in the environment on this VM: `bin/nvidia_live.py`
routes through the vault-keyed connector helper, with `probe()` trying chat
candidates in order until one answers the exact sentinel.

Live-lane facts observed 2026-10-23 (see TEST_EVIDENCE.md addendum):
- `GET /v1/models` → 83 models; saved catalog refreshed (`nvidia_models_2026-10-23.json`).
- End-to-end chat proven live: `z-ai/glm-5.3-flash` answered exactly "lane live".
- `moonshotai/kimi-k3` removed from the curated catalog (410 on live endpoint).
- Catalog-presence ≠ chat-availability tonight: `deepseek-ai/deepseek-v4.1-flash`
  (timed out twice, incl. a 180s window) and `moonshotai/kimi-k2.6` /
  `google/gemma-3-4b-it` (HTTP 404 on /chat/completions) were unusable even
  though listed in /v1/models. **Always probe before routing** — that is why
  `nvidia_live.probe()` exists.
- On other hosts (swarm machines), the env-key lane (`NVIDIA_API_KEY` +
  `nvidia_router.chat()`) still applies — see below.

Built and tested 2026-10-04; activated and re-tested 2026-10-23. See
`TEST_EVIDENCE.md` for the literal test output.
