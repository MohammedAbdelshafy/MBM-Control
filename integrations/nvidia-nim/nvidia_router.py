#!/usr/bin/env python3
"""nvidia_router.py — OpenAI-compatible client for NVIDIA NIM's free model tier.

Routes inference through https://integrate.api.nvidia.com/v1 using a free
NVIDIA_API_KEY (get one at https://build.nvidia.com — never invent one).

Stdlib only: no third-party dependencies.

Public API:
    chat(model, messages, **kw)  -> dict  (OpenAI chat.completions response)
    list_models(refresh=False)   -> list of {"id": ...} model dicts
    pick_model(task_type)        -> str   (best model id for the task)

CLI:
    python3 nvidia_router.py --list            # print all model ids
    python3 nvidia_router.py --refresh        # re-fetch live catalog, save it
    python3 nvidia_router.py --pick coding    # print recommended model id
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://integrate.api.nvidia.com/v1"
API_KEY_ENV = "NVIDIA_API_KEY"

# Real saved copy of GET /v1/models (fetched 2026-10-23, 83 models).
# Resolution order: NVIDIA_MODELS_CATALOG env > repo-local copy beside this
# file (what the branch carries) > legacy workspace path > curated models.json.
_REPO_CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "nvidia_models_2026-10-23.json")
_SAVED_CATALOG = os.path.expanduser(
    "~/workspace/night-shift/nvidia_models_2026-10-23.json"
)
# Curated role-tagged subset shipped with this build.
_CURATED_CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "models.json")


class NvidiaRouterError(Exception):
    """Base error for NVIDIA NIM router failures."""


class NvidiaAuthError(NvidiaRouterError):
    """401 / missing key: the NVIDIA_API_KEY is absent, invalid, or revoked."""


class NvidiaRateLimitError(NvidiaRouterError):
    """429: the free-tier rate limit was hit."""


def _load_saved_catalog():
    """Load model ids from the real saved catalog file (or curated fallback)."""
    path = os.environ.get("NVIDIA_MODELS_CATALOG")
    if not path or not os.path.exists(path):
        path = _REPO_CATALOG
    if not os.path.exists(path):
        path = _SAVED_CATALOG
    if not os.path.exists(path):
        path = _CURATED_CATALOG
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "data" in data:
        return [m["id"] for m in data["data"] if m.get("id")]
    if isinstance(data, list):
        return [m["id"] if isinstance(m, dict) else m for m in data]
    raise NvidiaRouterError(f"unrecognized catalog format in {path}")


def list_models(refresh=False):
    """Return the model catalog as a list of {"id": ...} dicts.

    Default: read the real saved response (no network, no key needed).
    refresh=True: hit the live public GET /v1/models endpoint (no key needed)
    and return the fresh list.
    """
    if not refresh:
        return [{"id": mid} for mid in _load_saved_catalog()]
    req = urllib.request.Request(
        BASE_URL + "/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise NvidiaRouterError(f"live catalog fetch failed: HTTP {e.code}") from e
    except OSError as e:
        raise NvidiaRouterError(f"live catalog fetch failed: {e}") from e
    return [{"id": m["id"]} for m in data.get("data", []) if m.get("id")]


def refresh_catalog(dest=None):
    """Fetch the live catalog and save it over the saved-catalog path.

    Returns (dest_path, model_count).
    """
    models = list_models(refresh=True)
    dest = dest or os.environ.get("NVIDIA_MODELS_CATALOG", _SAVED_CATALOG)
    payload = {"object": "list", "data": models}
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return dest, len(models)


# Preferred ids per task type. First id present in the live catalog wins,
# so this stays correct even as NVIDIA adds/removes models.
#
# 2026-10-21 (ai-dev-updates): deepseek-v4.1-flash promoted to first coding
# pick on the Oct 17 1017 checkpoint — DeepSeek-reported Terminal-Bench 4.0
# 31.2→42.3, DeepSWE 77.0, shorter outputs/faster completion, API name
# unchanged (`deepseek-flash`), direct pricing $0.30/$1.20 peak
# ($0.15/$0.60 off-peak) per M tokens. Verified present in the live
# GET /v1/models catalog on 2026-10-21 (83 models); free tier = $0.
_PICKS = {
    "coding": [
        "deepseek-ai/deepseek-v4.1-flash",
        "mistralai/codestral-22b-instruct-v0.1",
        "deepseek-ai/deepseek-coder-6.7b-instruct",
        "ibm/granite-34b-code-instruct",
        "ibm/granite-8b-code-instruct",
        "meta/codellama-70b",
        "bigcode/starcoder2-15b",
        "google/codegemma-1.1-7b",
    ],
    "chat": [
        "mistralai/mistral-large-2-instruct",
        "mistralai/mistral-large",
        "moonshotai/kimi-k2.6",
        "z-ai/glm-5.3",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "nvidia/nemotron-3-super-120b-a12b",
        "openai/gpt-oss-20b",
    ],
    "vision": [
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
        "microsoft/phi-3-vision-128k-instruct",
        "nvidia/vila",
        "adept/fuyu-8b",
    ],
    "reasoning": [
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "nvidia/cosmos-reason2-8b",
        "deepseek-ai/deepseek-v4.1-flash",
    ],
}


def pick_model(task_type):
    """Return the best available model id for a task type.

    task_type: one of coding | chat | vision | reasoning.
    Raises ValueError for unknown types, NotImplementedError for embeddings
    (this build routes no embedding model on the free tier).
    """
    if task_type == "embeddings":
        raise NotImplementedError(
            "no embedding model is routed on the NVIDIA free tier in this "
            "build — configure a dedicated embeddings provider instead"
        )
    if task_type not in _PICKS:
        raise ValueError(
            f"unknown task_type {task_type!r}; expected one of "
            f"{sorted(list(_PICKS) + ['embeddings'])}"
        )
    available = set(_load_saved_catalog())
    for mid in _PICKS[task_type]:
        if mid in available:
            return mid
    raise NvidiaRouterError(
        f"none of the preferred {task_type} models are in the current catalog"
    )


def _paid_fallback_config():
    """Return (api_key, base_url) for the paid fallback, or None.

    Paid fallback is OFF by default. It activates only when BOTH
    OPENAI_API_KEY and OPENAI_BASE_URL are explicitly set in the environment.
    """
    key = os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL")
    if key and base:
        return key, base.rstrip("/")
    return None


def _post(base_url, api_key, model, messages, kw):
    body = {
        "model": model,
        "messages": messages,
    }
    body.update(kw)
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code == 401:
            raise NvidiaAuthError(
                "NVIDIA API returned HTTP 401: the NVIDIA_API_KEY is missing, "
                "invalid, or revoked. It is NOT a code bug. Get a free key at "
                "https://build.nvidia.com and set it with:\n"
                f"  export NVIDIA_API_KEY='nvapi-...'\n"
                f"Upstream detail: {detail}"
            ) from e
        if e.code == 429:
            raise NvidiaRateLimitError(
                "NVIDIA API returned HTTP 429: free-tier rate limit hit. "
                "Back off and retry, or pick a smaller model. "
                f"Upstream detail: {detail}"
            ) from e
        raise NvidiaRouterError(
            f"NVIDIA API returned HTTP {e.code}: {detail}"
        ) from e
    except OSError as e:
        raise NvidiaRouterError(f"network error calling NVIDIA API: {e}") from e


def chat(model, messages, **kw):
    """Send one chat completion via NVIDIA NIM.

    model: exact model id from the catalog (see list_models()).
    messages: OpenAI-style list of {"role": ..., "content": ...} dicts.
    **kw: extra body fields (temperature, max_tokens, ...).

    Returns the decoded OpenAI chat.completions JSON dict.
    """
    available = set(_load_saved_catalog())
    if model not in available:
        raise ValueError(
            f"model {model!r} is not in the NVIDIA catalog; "
            "run list_models() to see valid ids"
        )
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise NvidiaAuthError(
            f"{API_KEY_ENV} is not set. Get a free key at "
            "https://build.nvidia.com and export it:\n"
            f"  export {API_KEY_ENV}='nvapi-...'"
        )
    try:
        return _post(BASE_URL, key, model, messages, kw)
    except (NvidiaAuthError, NvidiaRateLimitError):
        paid = _paid_fallback_config()
        if paid is None:
            raise
        paid_key, paid_base = paid
        print(
            f"[nvidia_router] NVIDIA call failed; paid fallback explicitly "
            f"configured via OPENAI_API_KEY/OPENAI_BASE_URL — retrying at "
            f"{paid_base}",
            file=sys.stderr,
        )
        return _post(paid_base, paid_key, model, messages, kw)


def _main(argv):
    if "--refresh" in argv:
        dest, count = refresh_catalog()
        print(f"saved {count} models to {dest}")
        return 0
    if "--list" in argv:
        for m in list_models():
            print(m["id"])
        return 0
    if "--pick" in argv:
        idx = argv.index("--pick")
        try:
            task = argv[idx + 1]
        except IndexError:
            print("usage: nvidia_router.py --pick <coding|chat|vision|reasoning>",
                  file=sys.stderr)
            return 2
        print(pick_model(task))
        return 0
    print(__doc__.strip().splitlines()[0])
    print("usage: nvidia_router.py [--list | --refresh | --pick <task>]")
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
