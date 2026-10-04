# NVIDIA NIM provider for MBM-Control swarm

Point any OpenAI-compatible agent config at NVIDIA's free model tier instead
of paid credits.

## Endpoint

| Field | Value |
|---|---|
| Base URL | `https://integrate.api.nvidia.com/v1` |
| Chat completions | `POST https://integrate.api.nvidia.com/v1/chat/completions` |
| Model list (public, no key) | `GET https://integrate.api.nvidia.com/v1/models` |
| Auth header | `Authorization: Bearer $NVIDIA_API_KEY` |
| Protocol | OpenAI-compatible (`/v1/chat/completions`, same request/response schema) |

## Configuration

1. Get a **free** API key at https://build.nvidia.com (sign in → generate key).
   Never hardcode it; never commit it.
2. Export it where the swarm runs:

   ```bash
   export NVIDIA_API_KEY='nvapi-YOUR_KEY_HERE'
   ```

3. In any OpenAI-compatible client/library config, set:

   ```yaml
   provider:
     base_url: https://integrate.api.nvidia.com/v1
     api_key_env: NVIDIA_API_KEY
   ```

   Python example (OpenAI SDK):

   ```python
   import os
   from openai import OpenAI
   client = OpenAI(
       base_url="https://integrate.api.nvidia.com/v1",
       api_key=os.environ["NVIDIA_API_KEY"],
   )
   ```

   Or use the bundled router (zero dependencies, stdlib only):

   ```python
   from nvidia_router import chat, pick_model
   resp = chat(pick_model("coding"),
               [{"role": "user", "content": "write a dedupe function"}])
   ```

## Recommended model ids (verified live 2026-10-04)

| Task | Model id |
|---|---|
| coding | `mistralai/codestral-22b-instruct-v0.1` |
| chat | `mistralai/mistral-large-2-instruct` |
| vision | `meta/llama-3.2-11b-vision-instruct` |
| reasoning | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| embeddings | _not routed on the free tier in this build_ |

Full list: 81 models, see `models.json` (curated, role-tagged) and the saved
live response. `swarm.models.yaml` in this directory is the routing table to
drop into the swarm config.

## Failure modes

- **HTTP 401** → the key is missing/invalid/revoked. Not a code bug; re-issue
  the key at build.nvidia.com.
- **HTTP 429** → free-tier rate limit; back off and retry.
- Paid fallback is **off by default**. It only engages when BOTH
  `OPENAI_API_KEY` and `OPENAI_BASE_URL` are explicitly set — the router will
  never silently spend paid credits.

## Verify the wiring (no key needed)

```bash
python3 mbm-control/nvidia-nim/test_provider.py
```

Asserts: base URL reachable (live `/v1/models` → 200), catalog loads,
routing table parses, every routed id exists in the catalog.
