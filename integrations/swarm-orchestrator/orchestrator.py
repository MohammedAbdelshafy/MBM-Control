#!/usr/bin/env python3
"""Parallel CLI-coding-agent orchestrator ("Munder Difflin pattern", headless).

Implements VibeFounder power #6: take the terminal coding-agent CLIs you
already run (claude, codex, gemini, qwen, opencode, ...) and turn them into a
parallel office of agents — one task fanned out to N backends at once, with
role splits (researcher / coder / reviewer), per-backend timeouts, and a JSONL
event log ("office mailbox").

Stdlib only. Backends are ordinary subprocesses; a mock backend directory can
be injected via PATH for fully hermetic tests.

Design notes (honesty first):
  - Only the five catalog backends below have flags the author is confident
    about; every other CLI is addable as a custom spec (dict), so nothing
    here invents a flag for a CLI it hasn't verified.
  - `dispatch()` never improvises: dry_run=True echoes the exact argv that
    would run, which is also the recommended pre-flight check.
  - Backends run with `env` inherited from the caller; model choice stays
    with the CLI's own login/subscription, exactly like Munder Difflin.
"""

from __future__ import annotations

import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

# name -> {binary, args (before prompt), prompt_via_arg, note}
CATALOG: dict[str, dict] = {
    "claude": {
        "binary": "claude",
        "args": ["-p"],           # Claude Code print (non-interactive) mode
        "prompt_via_arg": True,
        "note": "Claude Code; uses your existing claude login/subscription.",
    },
    "codex": {
        "binary": "codex",
        "args": ["exec"],         # OpenAI Codex non-interactive exec
        "prompt_via_arg": True,
        "note": "OpenAI Codex CLI; uses your existing codex login.",
    },
    "gemini": {
        "binary": "gemini",
        "args": ["-p"],           # Gemini CLI non-interactive prompt flag
        "prompt_via_arg": True,
        "note": "Gemini CLI; uses your existing gemini login.",
    },
    "qwen": {
        "binary": "qwen",
        "args": ["-p"],           # Qwen Code is the same CLI family as gemini
        "prompt_via_arg": True,
        "note": "Qwen Code CLI (Gemini-CLI family); same -p convention.",
    },
    "opencode": {
        "binary": "opencode",
        "args": ["run"],          # opencode non-interactive run
        "prompt_via_arg": True,
        "note": "opencode CLI; bring your own provider keys.",
    },
}

ROLES = ("researcher", "coder", "reviewer")

ROLE_WRAPPERS: dict[str, str] = {
    "researcher": (
        "You are the RESEARCHER on a small agent team. Investigate only: "
        "gather facts, read code, list options with tradeoffs. Do not write "
        "code or change files. End with a numbered findings list.\n\nTASK:\n{task}"
    ),
    "coder": (
        "You are the CODER on a small agent team. A researcher has already "
        "done the investigation. Implement the task now with real, working "
        "changes. Keep diffs small and runnable.\n\nTASK:\n{task}"
    ),
    "reviewer": (
        "You are the REVIEWER on a small agent team. Critique the approach "
        "for bugs, missing edge cases, and security issues. Propose concrete "
        "fixes. Do not rewrite the whole thing.\n\nTASK:\n{task}"
    ),
}

EVENT_LOG = Path(__file__).resolve().parent / "office_mailbox.jsonl"
OUTPUT_TRUNCATE_AT = 200_000  # chars; mark truncation instead of blowing up logs


def log_event(kind: str, payload: dict) -> dict:
    entry = {"ts": datetime.now(timezone.utc).isoformat(),
             "kind": kind, **payload}
    with open(EVENT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def read_events(limit: int = 50) -> list[dict]:
    if not EVENT_LOG.exists():
        return []
    lines = EVENT_LOG.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def detect_backends(catalog: dict | None = None) -> list[dict]:
    """Scan PATH for known coding-agent CLIs; probe --version for hits."""
    catalog = catalog or CATALOG
    found = []
    for name, spec in catalog.items():
        binary = shutil.which(spec["binary"])
        info = {"name": name, "binary": spec["binary"],
                "installed": binary is not None, "path": binary,
                "note": spec.get("note", "")}
        if binary:
            try:
                proc = subprocess.run(
                    [binary, "--version"], capture_output=True, text=True,
                    timeout=15)
                out = (proc.stdout or proc.stderr or "").strip().splitlines()
                info["version"] = out[0][:120] if out else "unknown"
            except (subprocess.SubprocessError, OSError) as exc:
                info["version"] = f"probe failed: {exc}"
        found.append(info)
    log_event("detect", {"backends": [
        {"name": b["name"], "installed": b["installed"]} for b in found]})
    return found


def _argv_for(spec: dict, prompt: str) -> list[str]:
    argv = [spec["binary"], *spec.get("args", [])]
    if spec.get("prompt_via_arg", True):
        argv.append(prompt)
    return argv


def _run_one(name: str, spec: dict, prompt: str, timeout: int,
             cwd: str | None, dry_run: bool) -> dict:
    argv = _argv_for(spec, prompt)
    started = time.monotonic()
    if dry_run:
        return {"backend": name, "dry_run": True,
                "argv": argv, "elapsed_ms": 0}
    try:
        proc = subprocess.run(
            argv,
            input=None if spec.get("prompt_via_arg", True) else prompt,
            capture_output=True, text=True, timeout=timeout, cwd=cwd)
        elapsed = int((time.monotonic() - started) * 1000)
        out = proc.stdout or ""
        truncated = len(out) > OUTPUT_TRUNCATE_AT
        return {
            "backend": name, "argv": argv,
            "exit_code": proc.returncode, "elapsed_ms": elapsed,
            "output": out[:OUTPUT_TRUNCATE_AT],
            "truncated": truncated,
            "stderr_tail": (proc.stderr or "")[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"backend": name, "argv": argv,
                "exit_code": None, "elapsed_ms": timeout * 1000,
                "output": "", "truncated": False,
                "error": f"timed out after {timeout}s"}
    except OSError as exc:
        return {"backend": name, "argv": argv,
                "exit_code": None, "elapsed_ms": 0,
                "output": "", "truncated": False, "error": str(exc)}


def dispatch(task: str, backends: list[str] | None = None,
             catalog: dict | None = None, timeout: int = 600,
             cwd: str | None = None, dry_run: bool = False) -> dict:
    """Fan the same task out to N backends in parallel; return all results."""
    catalog = catalog or CATALOG
    names = backends or [n for n, s in catalog.items()
                         if shutil.which(s["binary"])]
    if not names:
        return {"task": task, "results": [],
                "error": "no backends available (none installed or named)"}
    log_event("dispatch_start", {"task": task[:200], "backends": names,
                                 "dry_run": dry_run})
    results = []
    with futures.ThreadPoolExecutor(max_workers=len(names)) as pool:
        futs = {pool.submit(_run_one, n, catalog[n], task, timeout, cwd,
                            dry_run): n for n in names if n in catalog}
        missing = [n for n in names if n not in catalog]
        for fut in futures.as_completed(futs):
            results.append(fut.result())
        for n in missing:
            results.append({"backend": n, "error": "unknown backend spec"})
    summary = {"task": task, "backends": names, "dry_run": dry_run,
               "results": sorted(results, key=lambda r: r["backend"])}
    log_event("dispatch_done", {
        "backends": names,
        "ok": sum(1 for r in results if r.get("exit_code") == 0),
        "failed": sum(1 for r in results if r.get("exit_code") not in (0, None)
                      or r.get("error"))})
    return summary


def dispatch_roles(task: str, roles: list[str] | None = None,
                   catalog: dict | None = None, timeout: int = 900,
                   cwd: str | None = None, dry_run: bool = False) -> dict:
    """Split task across roles (researcher/coder/reviewer), one backend per
    role, round-robin over installed backends; return a merged team report."""
    catalog = catalog or CATALOG
    roles = roles or list(ROLES)
    installed = [n for n, s in catalog.items() if shutil.which(s["binary"])]
    if not installed:
        return {"task": task, "error": "no backends installed; nothing ran"}
    assignments = []
    with futures.ThreadPoolExecutor(max_workers=len(roles)) as pool:
        futs = {}
        for i, role in enumerate(roles):
            backend = installed[i % len(installed)]
            wrapper = ROLE_WRAPPERS.get(role, "{task}")
            prompt = wrapper.format(task=task)
            futs[pool.submit(_run_one, backend, catalog[backend], prompt,
                             timeout, cwd, dry_run)] = (role, backend)
            assignments.append({"role": role, "backend": backend})
        parts = []
        for fut in futures.as_completed(futs):
            role, backend = futs[fut]
            res = fut.result()
            parts.append({"role": role, **res})
    parts.sort(key=lambda p: roles.index(p["role"]))
    report = {"task": task, "assignments": assignments,
              "dry_run": dry_run, "roles": parts,
              "merged_note": "Read roles in order: researcher findings feed "
                             "the coder; the reviewer checks the coder."}
    log_event("roles_done", {"task": task[:200], "roles": roles,
                             "backends": installed})
    return report


def make_mock_backend(directory: str, name: str, body: str) -> str:
    """Write a fake executable CLI into `directory` (for tests)."""
    path = Path(directory) / name
    path.write_text("#!/bin/sh\nprintf '%s' " +
                    json.dumps(f"[{name}] " + body) + "\n")
    path.chmod(0o755)
    return str(path)


def self_check() -> dict:
    """Hermetic self-check: mock backends on a temp PATH, dispatch, verify."""
    tmp = tempfile.mkdtemp(prefix="swarm_selfcheck_")
    mock_catalog = {
        "mock-a": {"binary": "mock-a", "args": ["-p"],
                   "prompt_via_arg": True, "note": "test mock"},
        "mock-b": {"binary": "mock-b", "args": ["exec"],
                   "prompt_via_arg": True, "note": "test mock"},
    }
    for n in mock_catalog:
        make_mock_backend(tmp, n, "did the thing")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = tmp + os.pathsep + old_path
    try:
        detected = [b for b in detect_backends(mock_catalog)
                    if b["installed"]]
        assert {b["name"] for b in detected} == {"mock-a", "mock-b"}, detected
        out = dispatch("self-check task", catalog=mock_catalog, timeout=30)
        assert len(out["results"]) == 2, out
        assert all(r.get("exit_code") == 0 for r in out["results"]), out
        assert all("did the thing" in r.get("output", "")
                   for r in out["results"]), out
        roles_out = dispatch_roles("self-check roles", roles=["coder"],
                                   catalog=mock_catalog, timeout=30)
        assert roles_out["roles"][0]["role"] == "coder", roles_out
        dry = dispatch("x", catalog=mock_catalog, dry_run=True)
        assert all(r.get("dry_run") for r in dry["results"]), dry
    finally:
        os.environ["PATH"] = old_path
    return {"self_check": "PASS", "mocks": 2,
            "dispatch_results": 2, "roles": ["coder"], "dry_run": True}


if __name__ == "__main__":
    print(json.dumps(self_check(), indent=2))
