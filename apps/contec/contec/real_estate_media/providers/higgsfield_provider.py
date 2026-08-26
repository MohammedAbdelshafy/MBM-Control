"""Higgsfield adapter - the currently preferred AI video engine.

Uses the local `higgsfield` CLI when present. If the binary/key is missing,
available()=False and callers skip generation gracefully (never simulate).
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List

from .base import VideoProvider


class HiggsfieldProvider(VideoProvider):
    code = "higgsfield"
    model = "seedance-2.0"

    def __init__(self, binary: str = "higgsfield", timeout_s: int = 900):
        self._binary = binary
        self._timeout_s = timeout_s

    def available(self) -> bool:
        return shutil.which(self._binary) is not None

    def render(self, *, prompt: str, images: List[Dict[str, Any]],
               aspects: List[Dict[str, str]], timeout_s: int = 900) -> Dict[str, Any]:
        if not self.available():
            return {"status": "SKIPPED_UNAVAILABLE", "outputs": [],
                    "provider": self.code, "model": self.model,
                    "error": "higgsfield_cli_not_found"}
        outputs: List[Dict[str, Any]] = []
        try:
            for aspect in aspects:
                ratio = aspect["ratio"]
                proc = subprocess.run(
                    [self._binary, "generate", "video",
                     "--prompt", prompt, "--aspect", ratio, "--json"],
                    capture_output=True, text=True, timeout=timeout_s or self._timeout_s)
                if proc.returncode != 0:
                    return {"status": "FAILED", "outputs": outputs,
                            "provider": self.code, "model": self.model,
                            "error": (proc.stderr or proc.stdout)[-400:]}
                url = _extract_url(proc.stdout)
                if not url:
                    return {"status": "FAILED", "outputs": outputs,
                            "provider": self.code, "model": self.model,
                            "error": "no_url_in_cli_output"}
                outputs.append({"ratio": ratio, "url": url})
            return {"status": "SUCCEEDED", "outputs": outputs,
                    "provider": self.code, "model": self.model}
        except subprocess.TimeoutExpired:
            return {"status": "FAILED", "outputs": outputs, "provider": self.code,
                    "error": f"timeout_after_{timeout_s}s"}
        except OSError as exc:
            return {"status": "FAILED", "outputs": outputs, "provider": self.code,
                    "error": str(exc)[:200]}


def _extract_url(stdout: str) -> str:
    import json as _json
    import re
    m = re.search(r"https?://\S+", stdout)
    if not m:
        return ""
    candidate = m.group(0).rstrip('",')
    try:  # prefer structured json field when present
        data = _json.loads(stdout)
        candidate = (data.get("url") or data.get("video_url")
                     or data.get("output_url") or candidate)
    except Exception:
        pass
    return candidate
