#!/usr/bin/env python3
"""Ollama local-LLM router for MBM-Control (VibeFounder power #7).

Stdlib-only. Routes non-critical swarm work (triage drafts, intel summaries,
digest drafts, research notes) to a local Ollama instance ($0 marginal cost)
and keeps client-facing work on frontier models. Never calls a paid endpoint
silently: frontier-routed tasks return a decision dict, never an API call.

Config (env vars):
    OLLAMA_HOST   Ollama base URL. Default: http://localhost:11434
    OLLAMA_MODEL  Default model for local tasks. Default: qwen3:8b
                  (any tag from `ollama list`, e.g. gemma3:4b, llama3.1:8b)
    OLLAMA_TIMEOUT Seconds per request. Default: 120
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class OllamaError(Exception):
    """Base error for Ollama routing failures."""


class OllamaNotRunning(OllamaError):
    """No Ollama server reachable at OLLAMA_HOST."""


class ModelNotPulled(OllamaError):
    """Requested model tag is not present locally; needs `ollama pull`."""


class FrontierRequired(Exception):
    """Task kind must stay on a frontier model; returned, never auto-called."""
    def __init__(self, kind: str, reason: str):
        super().__init__(f"task kind {kind!r} requires a frontier model: {reason}")
        self.kind = kind
        self.reason = reason


# ---------------------------------------------------------------------------
# Routing policy
# ---------------------------------------------------------------------------

# Task kinds that are safe to draft locally: internal, non-client-facing,
# human-reviewed-before-send. Anything not listed here defaults to frontier.
LOCAL_KINDS = {
    "reply-triage": "draft a reply classification + suggested response (human sends)",
    "intel-summary": "summarize scraped intel into bullet notes",
    "digest-draft": "draft the scheduled reporting-digest body",
    "research-note": "condense research into structured notes",
    "dedupe-preview": "suggest dedupe/merge candidates for a lead list",
    "prompt-rewrite": "rewrite an internal prompt for clarity",
    "translate-draft": "draft translation of internal copy",
}

FRONTIER_REASON = (
    "client-facing or revenue-adjacent work stays on frontier models; "
    "local models draft only internal material."
)

_KIND_ALIASES = {
    "triage": "reply-triage",
    "summary": "intel-summary",
    "digest": "digest-draft",
    "note": "research-note",
}

def normalize_kind(kind: str) -> str:
    """Lowercase + alias-resolve a task kind."""
    k = (kind or "").strip().lower()
    return _KIND_ALIASES.get(k, k)


def route_decision(kind: str) -> Dict[str, Any]:
    """Decide where a task kind runs. Pure function, no network."""
    k = normalize_kind(kind)
    if k in LOCAL_KINDS:
        return {
            "kind": k,
            "target": "local",
            "model": DEFAULT_MODEL,
            "host": OLLAMA_HOST,
            "why": LOCAL_KINDS[k],
        }
    return {
        "kind": k,
        "target": "frontier",
        "model": None,
        "host": None,
        "why": FRONTIER_REASON,
    }


# ---------------------------------------------------------------------------
# HTTP layer (stdlib)
# ---------------------------------------------------------------------------

def _post(path: str, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
    url = OLLAMA_HOST + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise  # callers translate status codes (e.g. 404 -> ModelNotPulled)
    except urllib.error.URLError as exc:
        raise OllamaNotRunning(
            f"no Ollama server at {OLLAMA_HOST} ({exc}). "
            f"Start it with `ollama serve` (or install from https://ollama.com)."
        ) from exc


def _get(path: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    url = OLLAMA_HOST + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise OllamaNotRunning(
            f"no Ollama server at {OLLAMA_HOST} ({exc}). "
            f"Start it with `ollama serve` (or install from https://ollama.com)."
        ) from exc


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def validate_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Validate a chat message list; raises ValueError on bad input."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    for m in messages:
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            raise ValueError(f"each message needs 'role' and 'content': {m!r}")
        if m["role"] not in ("system", "user", "assistant"):
            raise ValueError(f"bad role {m['role']!r}: use system|user|assistant")
        if not isinstance(m["content"], str) or not m["content"].strip():
            raise ValueError("message content must be a non-empty string")
    return messages


def chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """One chat completion via Ollama's OpenAI-compatible endpoint.

    Raises OllamaNotRunning if the server is down, ModelNotPulled (as
    OllamaError) if the tag is missing.
    """
    messages = validate_messages(messages)
    model = model or DEFAULT_MODEL
    try:
        return _post("/v1/chat/completions", {
            "model": model,
            "messages": messages,
            "stream": False,
        }, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        if exc.code == 404 and "not found" in body.lower():
            raise ModelNotPulled(
                f"model {model!r} is not pulled on {OLLAMA_HOST}. "
                f"Run: ollama pull {model}"
            ) from exc
        raise OllamaError(f"Ollama chat failed HTTP {exc.code}: {body}") from exc


def generate(prompt: str, model: Optional[str] = None,
             timeout: Optional[float] = None) -> str:
    """Single-prompt completion; returns the text."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    resp = chat([{"role": "user", "content": prompt}], model=model, timeout=timeout)
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OllamaError(f"unexpected Ollama response shape: {resp!r}") from exc


def list_local_models(timeout: Optional[float] = None) -> List[str]:
    """Model tags currently pulled on this Ollama host."""
    data = _get("/api/tags", timeout=timeout)
    return [m["name"] for m in data.get("models", []) if "name" in m]


def status(timeout: Optional[float] = None) -> Dict[str, Any]:
    """Health check: reachable, models available, default configured."""
    try:
        models = list_local_models(timeout=timeout)
    except OllamaNotRunning as exc:
        return {"ok": False, "host": OLLAMA_HOST, "error": str(exc)}
    return {
        "ok": True,
        "host": OLLAMA_HOST,
        "models": models,
        "default_model": DEFAULT_MODEL,
        "default_model_present": DEFAULT_MODEL in models,
        "local_kinds": sorted(LOCAL_KINDS),
    }


def route_task(kind: str, messages: List[Dict[str, str]],
               model: Optional[str] = None,
               timeout: Optional[float] = None) -> Dict[str, Any]:
    """Apply the routing policy, then run the task.

    LOCAL_KINDS  -> runs on Ollama, returns {"target": "local", "text": ...}
    anything else -> raises FrontierRequired (no paid call is ever made)
    """
    decision = route_decision(kind)
    if decision["target"] != "local":
        raise FrontierRequired(decision["kind"], decision["why"])
    text = generate(
        "\n\n".join(f"{m['role']}: {m['content']}" for m in validate_messages(messages)),
        model=model or decision["model"],
        timeout=timeout,
    )
    return {"target": "local", "kind": decision["kind"],
            "model": model or decision["model"], "text": text}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("commands: --status | --models | --kinds | --route <kind> <prompt> | --generate <prompt> [--model tag]")
        return 0
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "--status":
            print(json.dumps(status(), indent=2))
        elif cmd == "--models":
            print(json.dumps(list_local_models(), indent=2))
        elif cmd == "--kinds":
            print(json.dumps({k: route_decision(k) for k in sorted(LOCAL_KINDS)}, indent=2))
        elif cmd == "--route":
            if len(rest) < 2:
                print("usage: --route <kind> <prompt> [--model tag]", file=sys.stderr)
                return 2
            kind, prompt = rest[0], rest[1]
            model = rest[3] if len(rest) > 3 and rest[2] == "--model" else None
            out = route_task(kind, [{"role": "user", "content": prompt}], model=model)
            print(json.dumps(out, indent=2))
        elif cmd == "--generate":
            if not rest:
                print("usage: --generate <prompt> [--model tag]", file=sys.stderr)
                return 2
            model = rest[2] if len(rest) > 2 and rest[1] == "--model" else None
            print(generate(rest[0], model=model))
        else:
            print(f"unknown command {cmd!r}", file=sys.stderr)
            return 2
    except FrontierRequired as exc:
        print(json.dumps({"target": "frontier", "kind": exc.kind,
                          "why": exc.reason}), file=sys.stderr)
        return 3
    except (OllamaError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
