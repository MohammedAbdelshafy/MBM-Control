"""
Model registry + local LLM routing for MBM-Social.

Routes tasks to the strongest *available* local model. Ollama remains the
default transport. GPT-OSS can be exposed through an OpenAI-compatible local
endpoint (for example Ollama or vLLM) and selected per task with environment
configuration. No provider is granted mutation authority by this registry.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GPT_OSS_BASE = os.getenv("GPT_OSS_BASE_URL", "")
GPT_OSS_MODEL = os.getenv("GPT_OSS_MODEL", "gpt-oss:20b")


# Task -> preferred models. Resolution checks availability and falls back.
TASK_MODELS = {
    "topic_classification": ["qwen2.5-coder:7b", GPT_OSS_MODEL, "qwen2.5-coder:14b"],
    "hook_scoring": [GPT_OSS_MODEL, "qwen2.5-coder:7b"],
    "title_generation": ["qwen2.5-coder:7b", GPT_OSS_MODEL, "qwen2.5-coder:14b"],
    "caption_generation": ["qwen2.5-coder:7b", GPT_OSS_MODEL],
    "hashtag_generation": ["qwen2.5-coder:7b", GPT_OSS_MODEL],
    "brand_fit_scoring": [GPT_OSS_MODEL, "qwen2.5-coder:7b"],
    "channel_selection": [GPT_OSS_MODEL, "qwen2.5-coder:7b"],
    "analytics_summary": [GPT_OSS_MODEL, "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "experiment_recommendations": [GPT_OSS_MODEL, "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "quality_review": [GPT_OSS_MODEL, "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "thumbnail_text": ["qwen2.5-coder:7b", GPT_OSS_MODEL],
    "vision_thumbnail": ["llava:7b"],
    "strategy": [GPT_OSS_MODEL, "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
}

EMBED_MODEL = "nomic-embed-text:latest"
VISION_MODEL = "llava:7b"
STRONGEST_REASONING = GPT_OSS_MODEL


@dataclass
class ModelInfo:
    name: str
    available: bool


def list_models() -> list[ModelInfo]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as r:
            data = json.load(r)
        names = {m["name"] for m in data.get("models", [])}
        return [ModelInfo(n, True) for n in names]
    except Exception:
        return []


_AVAIL: Optional[set[str]] = None


def _available() -> set[str]:
    global _AVAIL
    if _AVAIL is None:
        _AVAIL = {m.name for m in list_models()}
    return _AVAIL


def _gpt_oss_configured() -> bool:
    return bool(GPT_OSS_BASE.strip())


def resolve(task: str) -> str:
    """Return the best available local model for a task, or raise."""
    candidates = TASK_MODELS.get(task, [STRONGEST_REASONING])
    available = _available()
    for cand in candidates:
        if cand == GPT_OSS_MODEL and not _gpt_oss_configured():
            continue
        if cand in available or (cand == GPT_OSS_MODEL and _gpt_oss_configured()):
            return cand
    for cand in ["qwen2.5-coder:14b", "qwen2.5-coder:7b"]:
        if cand in available:
            return cand
    raise RuntimeError(f"No local model available for task '{task}'. Is Ollama running?")


def _ollama_generate(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> Optional[str]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return (data.get("response") or "").strip() or None


def _gpt_oss_generate(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> Optional[str]:
    """Call an OpenAI-compatible local GPT-OSS endpoint.

    This intentionally supports only the local endpoint configured by
    GPT_OSS_BASE_URL. Authentication is optional and read from env.
    """
    base = GPT_OSS_BASE.rstrip("/")
    if not base:
        return None
    body = {
        "model": model,
        "messages": [
            *([{"role": "system", "content": system}] if system else []),
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {os.environ['GPT_OSS_API_KEY']}"}
               if os.getenv("GPT_OSS_API_KEY") else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    choices = data.get("choices") or []
    if not choices:
        return None
    content = (choices[0].get("message") or {}).get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def generate(
    prompt: str,
    task: str = "strategy",
    system: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
    transport=None,
) -> str:
    """Generate text using configured local inference only.

    Provider fallback is deterministic and never fabricates a response.
    The transport hook is retained for hermetic tests.
    """
    model = resolve(task)
    try:
        if transport:
            resp = transport(
                model=model,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        elif model == GPT_OSS_MODEL and _gpt_oss_configured():
            resp = _gpt_oss_generate(
                model=model,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            resp = _ollama_generate(
                model=model,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if resp:
            return resp
    except Exception as e:
        print(f"[model_registry] local generation failed for task '{task}': {e}")
    raise RuntimeError(f"Generation failed for task '{task}' with model '{model}'.")


def embed(text: str) -> list[float]:
    if EMBED_MODEL not in _available():
        raise RuntimeError(f"Embedding model {EMBED_MODEL} not available in Ollama.")
    payload = {"model": EMBED_MODEL, "input": text}
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/embed",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data.get("embeddings", [[]])[0]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
