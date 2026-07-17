"""
Model registry + local LLM routing for MBM-Social.

Routes every task to the strongest *available* local model. No task is
hardcoded to a single model — routing is data-driven and falls back if a
model is missing. All inference is local (Ollama); nothing leaves the machine.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Optional

OLLAMA_BASE = "http://localhost:11434"


# Task -> preferred model. Resolution checks availability and falls back.
# NOTE: gemma4:latest currently returns HTTP 500 locally; qwen2.5-coder:7b is
# the verified-working local generator. Keep gemma4 only as a last resort.
TASK_MODELS = {
    "topic_classification": ["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
    "hook_scoring": ["qwen2.5-coder:7b"],
    "title_generation": ["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
    "caption_generation": ["qwen2.5-coder:7b"],
    "hashtag_generation": ["qwen2.5-coder:7b"],
    "brand_fit_scoring": ["qwen2.5-coder:7b"],
    "channel_selection": ["qwen2.5-coder:7b"],
    "analytics_summary": ["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
    "experiment_recommendations": ["qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "quality_review": ["qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "thumbnail_text": ["qwen2.5-coder:7b"],
    "vision_thumbnail": ["llava:7b"],
    # Strongest local reasoning for campaign / cross-channel / strategy decisions.
    "strategy": ["qwen2.5-coder:14b", "qwen2.5-coder:7b"],
}

EMBED_MODEL = "nomic-embed-text:latest"
VISION_MODEL = "llava:7b"
STRONGEST_REASONING = "qwen2.5-coder:14b"


@dataclass
class ModelInfo:
    name: str
    available: bool


def list_models() -> list[ModelInfo]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as r:
            data = json.load(r)
        names = {m["name"] for m in data.get("models", [])}
        # normalise: "gemma4:latest" matches requested "gemma4:latest"
        return [ModelInfo(n, True) for n in names]
    except Exception:
        return []


_AVAIL: Optional[set[str]] = None


def _available() -> set[str]:
    global _AVAIL
    if _AVAIL is None:
        _AVAIL = {m.name for m in list_models()}
    return _AVAIL


def resolve(task: str) -> str:
    """Return the best available model for a task, or raise if none."""
    for cand in TASK_MODELS.get(task, [STRONGEST_REASONING]):
        if cand in _available():
            return cand
    # last resort: any reasoning-capable model
    for cand in [STRONGEST_REASONING, "qwen2.5-coder:14b", "qwen2.5-coder:7b"]:
        if cand in _available():
            return cand
    raise RuntimeError(f"No local model available for task '{task}'. Is Ollama running?")


def generate(
    prompt: str,
    task: str = "strategy",
    system: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> str:
    model = resolve(task)
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
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return data.get("response", "").strip()


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
