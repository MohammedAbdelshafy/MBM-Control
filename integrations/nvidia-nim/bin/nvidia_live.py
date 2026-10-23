#!/usr/bin/env python3
"""nvidia_live.py — live lane for the nvidia-free-models integration.

Routes chat calls through the founder's *vault-registered* NVIDIA NIM
credential via the custom connector helper, instead of an NVIDIA_API_KEY
in the environment. The key is never handled directly: the helper attaches
a surrogate and the runtime swaps in the real key only for the registered
host (integrate.api.nvidia.com).

Stdlib only.

    python3 bin/nvidia_live.py --models            # live model count + ids
    python3 bin/nvidia_live.py --chat MODEL "prompt"
    python3 bin/nvidia_live.py --probe             # first healthy chat lane

probe() is the routing primitive: try the candidate chat models in order,
return the first that answers with the exact sentinel. Lane health is a
live fact — probe before routing, never assume yesterday's pick still works.

The helper path can be overridden for tests with NVIDIA_LIVE_HELPER.
"""

import json
import os
import subprocess
import sys

HELPER = os.environ.get(
    "NVIDIA_LIVE_HELPER",
    os.path.expanduser(
        "~/workspace/custom-connectors/custom.nvidia-nim/bin/nvidia_chat.py"
    ),
)
SENTINEL = "lane live"
SENTINEL_PROMPT = "Reply with exactly: lane live"

# Candidates in preference order. z-ai/glm-5.3-flash proved live end-to-end
# 2026-10-23; deepseek-ai/deepseek-v4.1-flash answered at connector setup
# (2026-10-22) but was timing out on the free tier later that night — so it
# stays a candidate, behind the proven one, and probe order is a live fact.
PROBE_CANDIDATES = [
    "z-ai/glm-5.3-flash",
    "deepseek-ai/deepseek-v4.1-flash",
    "mistralai/mistral-large-2-instruct",
    "moonshotai/kimi-k2.6",
    "google/gemma-3-12b-it",
]


class LiveLaneError(Exception):
    """The live vault-keyed lane failed (helper error, no healthy model)."""


def _run_helper(*args):
    """Run the connector helper; return parsed JSON. Raises LiveLaneError."""
    try:
        proc = subprocess.run(
            [sys.executable, HELPER, *args],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError as e:
        raise LiveLaneError(f"helper not found at {HELPER}: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise LiveLaneError(f"helper timed out: {e}") from e
    if proc.returncode != 0:
        raise LiveLaneError(
            f"helper exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise LiveLaneError(
            f"helper returned non-JSON: {proc.stdout[:200]!r}"
        ) from e


def live_models():
    """Return the live model-id list via the vault-keyed lane."""
    result = _run_helper("models")
    # Helper prints {"count": N, "models": [...first 20...]}; for a full list
    # we need the router's refresh path. Count + sample is the health signal.
    return result


def live_chat(model, prompt, max_tokens=64):
    """One chat completion via the vault-keyed lane. Returns reply text."""
    result = _run_helper("chat", prompt, model)
    try:
        return result["reply"]
    except (KeyError, TypeError) as e:
        raise LiveLaneError(f"unexpected chat payload: {result!r}") from e


def probe(candidates=None, sentinel=SENTINEL):
    """Return (model_id, reply) for the first candidate that answers exactly.

    Raises LiveLaneError if none answer. Each attempt is independent: a
    timeout or 4xx on one model moves to the next — that is the point.
    """
    tried = []
    for model in candidates or PROBE_CANDIDATES:
        try:
            reply = live_chat(model, SENTINEL_PROMPT)
        except LiveLaneError as e:
            tried.append((model, f"error: {e}"))
            continue
        if not reply or not reply.strip():
            tried.append((model, "empty reply"))
            continue
        if reply.strip() == sentinel:
            return model, reply, tried
        tried.append((model, f"wrong reply: {reply[:80]!r}"))
    detail = "; ".join(f"{m}: {why}" for m, why in tried)
    raise LiveLaneError(f"no healthy chat lane; tried: {detail}")


def _main(argv):
    if "--models" in argv:
        print(json.dumps(live_models(), indent=1))
        return 0
    if "--chat" in argv:
        i = argv.index("--chat")
        try:
            model, prompt = argv[i + 1], argv[i + 2]
        except IndexError:
            print('usage: nvidia_live.py --chat MODEL "prompt"', file=sys.stderr)
            return 2
        print(live_chat(model, prompt))
        return 0
    if "--probe" in argv:
        model, reply, tried = probe()
        print(json.dumps({"healthy_model": model, "reply": reply,
                          "tried": tried}, indent=1))
        return 0
    print(__doc__.strip().splitlines()[0])
    print("usage: nvidia_live.py [--models | --chat MODEL PROMPT | --probe]")
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
