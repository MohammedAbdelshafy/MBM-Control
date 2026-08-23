"""
Visual Provider Architecture — Higgsfield as an OPTIONAL enhancement provider.

Provider contract (no fake jobs, no fake media URLs, no fake outputs):
  * health_check()      -> real provider state
  * generate_scene()    -> only ever returns evidence-backed output paths;
                           on ANY non-AVAILABLE state it returns ok=False with
                           the provider state — the caller MUST continue with
                           the local pipeline.
  * generate_scenes()   -> batch form of generate_scene()
  * capability_status() -> static capability description

States: AVAILABLE | AUTH_REQUIRED | PLAN_REQUIRED | UNAVAILABLE |
        RATE_LIMITED | NETWORK_ERROR | TEMPORARY_FAILURE

Routing: HIGGSFIELD -> (secondary providers) -> LOCAL FFMPEG VISUAL PIPELINE.
A PLAN_REQUIRED or UNAVAILABLE Higgsfield NEVER blocks a campaign.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProviderState(str, Enum):
    AVAILABLE = "AVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PLAN_REQUIRED = "PLAN_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"


# HTTP status -> provider state mapping for real API responses
_STATUS_MAP = {
    401: ProviderState.AUTH_REQUIRED,
    403: ProviderState.AUTH_REQUIRED,
    402: ProviderState.PLAN_REQUIRED,
    429: ProviderState.RATE_LIMITED,
}


class HiggsfieldProvider:
    """Optional cinematic-scene provider. Disabled unless HF_API_KEY is set."""

    name = "higgsfield"

    def __init__(self, api_key: Optional[str] = None,
                 endpoint: Optional[str] = None):
        self.api_key = api_key or os.environ.get("HF_API_KEY", "")
        self.endpoint = endpoint or os.environ.get(
            "HF_ENDPOINT", "https://api.higgsfield.ai/v1")

    # ── contract ────────────────────────────────────────────────────
    def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"provider": self.name, "state": ProviderState.UNAVAILABLE.value,
                    "detail": "HF_API_KEY not configured — local visual pipeline will be used"}
        try:
            import requests
            r = requests.get(f"{self.endpoint}/plans",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=15)
            state = _STATUS_MAP.get(r.status_code,
                                    ProviderState.AVAILABLE if r.status_code < 400
                                    else ProviderState.TEMPORARY_FAILURE)
            return {"provider": self.name, "state": state.value,
                    "http_status": r.status_code}
        except Exception as exc:
            return {"provider": self.name,
                    "state": ProviderState.NETWORK_ERROR.value,
                    "detail": str(exc)[:200]}

    def capability_status(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "modes": ["image_to_video", "text_to_image"],
            "max_clip_seconds": 10,
            "recommended_recipe": {
                "style": "cinematic thriller",
                "look": "photorealistic, low-key lighting, subtle film grain",
                "camera": "controlled slow push-in / handheld drift",
                "avoid": ["text overlays in scene", "logos", "celebrity likenesses"],
            },
            "visual_beats_target": "6-12 meaningful beats per 35-75s Short",
        }

    def generate_scene(self, prompt: str, out_path: Path,
                       seconds: float = 5.0) -> Dict[str, Any]:
        health = self.health_check()
        if health["state"] != ProviderState.AVAILABLE.value:
            return {"ok": False, "provider": self.name,
                    "state": health["state"], "output": "",
                    "reason": f"provider not available ({health['state']})"}
        try:
            import requests
            r = requests.post(
                f"{self.endpoint}/generations",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"prompt": prompt, "duration_seconds": seconds},
                timeout=120,
            )
            state = _STATUS_MAP.get(r.status_code,
                                    ProviderState.AVAILABLE if r.status_code < 300
                                    else ProviderState.TEMPORARY_FAILURE)
            if state != ProviderState.AVAILABLE.value or not r.ok:
                return {"ok": False, "provider": self.name, "state": state.value,
                        "output": "", "reason": f"generation refused ({r.status_code})"}
            media_url = (r.json() or {}).get("output_url", "")
            if not media_url:
                return {"ok": False, "provider": self.name,
                        "state": ProviderState.TEMPORARY_FAILURE.value,
                        "output": "", "reason": "no output_url in provider response"}
            return {"ok": True, "provider": self.name,
                    "state": ProviderState.AVAILABLE.value,
                    "output": media_url}
        except Exception as exc:
            return {"ok": False, "provider": self.name,
                    "state": ProviderState.NETWORK_ERROR.value, "output": "",
                    "reason": str(exc)[:200]}

    def generate_scenes(self, prompts: List[str], work_dir: Path,
                        seconds_per_scene: float = 5.0) -> Dict[str, Any]:
        results = []
        for i, p in enumerate(prompts):
            out = work_dir / f"hf_scene_{i:02d}.mp4"
            results.append(self.generate_scene(p, out, seconds_per_scene))
            if results[-1]["state"] in (ProviderState.PLAN_REQUIRED.value,
                                        ProviderState.UNAVAILABLE.value):
                break  # do not hammer a provider that cannot serve us
        ok = [r for r in results if r.get("ok")]
        return {"ok": bool(ok) and len(ok) == len(results),
                "provider": self.name,
                "state": (ok[0]["state"] if ok else
                          (results[0]["state"] if results else
                           ProviderState.UNAVAILABLE.value)),
                "outputs": [r["output"] for r in ok],
                "attempts": results}


class VisualProviderRouter:
    """HIGGSFIELD -> secondary providers (none yet) -> LOCAL visual pipeline."""

    def __init__(self, higgsfield: Optional[HiggsfieldProvider] = None):
        self.providers: List[HiggsfieldProvider] = []
        if higgsfield is not None:
            self.providers.append(higgsfield)

    def route(self) -> Dict[str, Any]:
        """Pick the first AVAILABLE provider; otherwise fall back to LOCAL.
        Never raises, never fabricates availability."""
        for p in self.providers:
            h = p.health_check()
            if h["state"] == ProviderState.AVAILABLE.value:
                return {"provider": p.name, "state": h["state"]}
        return {"provider": "local_ffmpeg", "state": ProviderState.UNAVAILABLE.value,
                "detail": (self.providers[0].health_check().get("detail",
                            "no provider available") if self.providers else
                           "local visual pipeline")}


def get_router() -> VisualProviderRouter:
    """Router wired from env. Higgsfield participates ONLY when configured."""
    return VisualProviderRouter(higgsfield=HiggsfieldProvider())
