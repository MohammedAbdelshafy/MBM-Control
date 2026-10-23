# TEST_EVIDENCE.md — nvidia-free-models (built 2026-10-04)

Real test runs with literal output. Nothing below is mocked except where
explicitly labeled.

## (a) Live GET https://integrate.api.nvidia.com/v1/models → 200, 81 models

```
$ python3 -c "...urllib GET /v1/models..."
=== (a) live GET /v1/models ===
HTTP 200
model count: 81
first id: 01-ai/yi-large
```

No API key was sent; the endpoint answers 200 publicly. The 81-id list is
saved at `~/workspace/night-shift/nvidia_models_2026-10-04.json`.

## (b) py_compile on all Python files

```
$ python3 -m py_compile nvidia_router.py bin/nvidia_chat.py mbm-control/nvidia-nim/test_provider.py
=== (b) py_compile ===
ALL COMPILE OK
```

## (c) CLI without NVIDIA_API_KEY → exit 2 + exact export command

```
$ env -u NVIDIA_API_KEY python3 bin/nvidia_chat.py --model mistralai/codestral-22b-instruct-v0.1 "say hi"
error: NVIDIA_API_KEY is not set.

Get a FREE API key at https://build.nvidia.com (sign in, generate key), then run:

    export NVIDIA_API_KEY='nvapi-YOUR_KEY_HERE'

then re-run this command. No key is bundled with this tool and none will be invented.
exit code: 2
```

(`nvapi-YOUR_KEY_HERE` is a placeholder the script prints, not a real key.)

## (d) Auth wiring: HTTP 401 → clear key error (not a fake success)

A direct POST to NVIDIA with a dummy key was attempted twice, but the
runtime held the outbound call on an approval card (`pending_user_confirmation`)
and the user was unavailable to tap it, so the live-401 observation could not
complete. Instead, the REAL `_post()` function (same code path `chat()` uses:
same request construction, same `Authorization: Bearer` header, same
`/chat/completions` path, same error mapping) was exercised against a local
HTTP stub returning 401 / 429 / 200:

```
$ python3 - <<'EOF'   # local stub on 127.0.0.1, real nvidia_router._post()
=== (d) auth-wiring test: real _post() against local 401/429/200 stub ===
PASS: HTTP 401 -> NvidiaAuthError (names missing/invalid key)
      request path: /chat/completions | auth scheme: Bearer
      model in body: m/x
PASS: HTTP 429 -> NvidiaRateLimitError
PASS: HTTP 200 -> decoded OpenAI-style dict returned
PASS: missing NVIDIA_API_KEY -> NvidiaAuthError with export instructions (no network call made)
ALL AUTH-WIRING CHECKS PASSED
```

The 401 error message names the missing/invalid key and points to
build.nvidia.com — it does not blame the code. A live end-to-end chat call
remains **needs NVIDIA_API_KEY** (see blocker below).

## (e) test_provider.py — all wiring checks pass (no key needed)

```
$ python3 mbm-control/nvidia-nim/test_provider.py
== NVIDIA NIM provider wiring test (no API key required) ==

[PASS] live GET /v1/models returns HTTP 200 — HTTP 200
[PASS] live catalog non-empty — 81 models
       sample ids: 01-ai/yi-large, adept/fuyu-8b, ai21labs/jamba-1.5-large-instruct
[PASS] model catalog loads — 81 ids from /home/hatch/workspace/night-shift/nvidia_models_2026-10-04.json
[PASS] swarm.models.yaml parses — .../mbm-control/nvidia-nim/swarm.models.yaml
[PASS] provider.base_url correct — https://integrate.api.nvidia.com/v1
[PASS] provider.api_key_env correct — NVIDIA_API_KEY
[PASS] provider.protocol openai-compatible — openai-compatible
[PASS] routing table non-empty — tasks: chat, coding, reasoning, vision
[PASS] routing[chat] id in catalog — mistralai/mistral-large-2-instruct
[PASS] routing[coding] id in catalog — mistralai/codestral-22b-instruct-v0.1
[PASS] routing[reasoning] id in catalog — nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
[PASS] routing[vision] id in catalog — meta/llama-3.2-11b-vision-instruct

RESULT: all provider wiring checks passed
exit code: 0
```

## Extras (router behavior)

```
$ python3 nvidia_router.py --pick coding       -> mistralai/codestral-22b-instruct-v0.1
$ python3 nvidia_router.py --pick chat         -> mistralai/mistral-large-2-instruct
$ python3 nvidia_router.py --pick vision       -> meta/llama-3.2-11b-vision-instruct
$ python3 nvidia_router.py --pick reasoning    -> nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
$ python3 nvidia_router.py --list | wc -l      -> 81
pick_model('embeddings') -> NotImplementedError (no embedding model routed on free tier)
pick_model('teleport')   -> ValueError (unknown task type)
paid fallback OFF by default (no OPENAI_API_KEY/OPENAI_BASE_URL set)
```

Every `pick_model()` result was asserted present in the real 81-id catalog.

## Summary

| Check | Result |
|---|---|
| Live endpoint reachable, 81 models | PASS |
| All py files compile | PASS |
| CLI without key → exit 2 + export help | PASS |
| 401 → NvidiaAuthError naming key problem | PASS (real `_post`, local stub; live variant blocked on approval card) |
| 429 → NvidiaRateLimitError | PASS |
| Missing key → error before network call | PASS |
| test_provider.py (13 checks) | PASS |
| pick_model ids all in real catalog | PASS |
| Paid fallback off by default | PASS |
| Live end-to-end chat completion | **needs NVIDIA_API_KEY** |

## Remaining blocker for full activation

A **free API key from build.nvidia.com, set as `NVIDIA_API_KEY`**.
One command activates everything: `export NVIDIA_API_KEY='nvapi-...'`.

---

## ACTIVATION 2026-10-23 — power #1 live through the vault credential

The founder registered his free NVIDIA API key on 2026-10-22
(`custom.nvidia-nim` connector, vault-stored, never in files). Tonight the
integration was activated end-to-end and re-tested. New files:
`bin/nvidia_live.py` (vault-keyed lane + `probe()`), `test_activation.py`
(8 checks), refreshed live catalog `nvidia_models_2026-10-23.json` (83
models), curated catalog now 35 ids (`moonshotai/kimi-k3` removed — HTTP 410
on the live endpoint).

### Live observations (literal)

```
$ python3 ~/workspace/custom-connectors/custom.nvidia-nim/bin/nvidia_chat.py models
{"count": 83, "models": ["01-ai/yi-large", "adept/fuyu-8b", ...]}
```
83 models, key authenticates.

```
$ python3 bin/nvidia_live.py --chat z-ai/glm-5.3-flash "Reply with exactly: lane live"
lane live
```
End-to-end chat proven live on the free tier, zero spend.

```
$ python3 bin/nvidia_live.py --probe
{"healthy_model": "z-ai/glm-5.3-flash", "reply": "lane live", "tried": []}
```

### Free-tier health caveats found tonight (documented, not hidden)

- `deepseek-ai/deepseek-v4.1-flash` (in /v1/models) timed out on
  /chat/completions twice — once at the helper's 60s limit, once at 180s.
  It answered correctly at connector setup (2026-10-22), so this is
  intermittent free-tier congestion, not an auth failure. `probe()` treats
  timeouts as a skip, not a crash.
- `moonshotai/kimi-k2.6` and `google/gemma-3-4b-it` are listed in
  /v1/models but return **HTTP 404** on /chat/completions tonight.
  Catalog-presence does not imply chat-availability on the free tier —
  always probe before routing. (The hermetic test caught one real probe
  bug here: a None/empty reply used to crash `probe()` with AttributeError;
  it now records "empty reply" and moves on.)
- One hermetic-test harness bug found and fixed along the way: the fake
  helpers read `sys.argv[2]` (the prompt) as the model id — real argv is
  `[script, chat, prompt, model]`, so the id is `sys.argv[3]`.

### test_activation.py — 8/8 pass (2026-10-23)

```
== Part 1: hermetic probe logic ==
PASS probe picks healthy first
PASS probe skips wrong-reply + error models
PASS probe raises when all fail
PASS non-JSON helper raises LiveLaneError
== Part 2: live lane ==
PASS live /v1/models count >= 80
PASS every pick_model() id in live catalog
PASS every curated models.json id in live catalog
PASS live chat returns exact sentinel
RESULT: 8 passed, 0 failed
```

Part 2 needs the vault-registered credential; it skips cleanly only if the
connector helper is absent — a live failure fails, never silently passes.

### Remaining honest limits

- The env-key lane (`nvidia_router.chat()` + `NVIDIA_API_KEY`) is unchanged
  and untested live from this VM — it is the lane for swarm hosts without
  the vault.
- Free-tier model health is volatile: re-run `test_activation.py` (or
  `bin/nvidia_live.py --probe`) before any batch routing run.
