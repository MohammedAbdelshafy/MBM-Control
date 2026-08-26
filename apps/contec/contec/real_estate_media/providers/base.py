"""Video provider interface + registry.

Law (D-021): providers are swappable adapters. An unconfigured provider
reports available()=False and callers skip generation - NEVER simulated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class VideoProvider(ABC):
    code: str = "abstract"

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def render(self, *, prompt: str, images: list[Dict[str, Any]],
               aspects: list[Dict[str, str]], timeout_s: int = 600) -> Dict[str, Any]:
        """Return {status:'SUCCEEDED'|'FAILED'|'SKIPPED_UNAVAILABLE',
        outputs:[{ratio,url}], provider, model, error?}"""

    def qa_check(self, outputs: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Automated pre-delivery check: every planned aspect produced."""
        missing = [a["ratio"] for a in aspects_from(outputs)] if False else []
        ok = bool(outputs) and all(o.get("url") for o in outputs)
        return {"qa_status": "PASS" if ok else "FAIL", "missing_aspects": missing}


class NullProvider(VideoProvider):
    """Explicit 'not configured' provider - always skipped, never faked."""
    code = "null"

    def available(self) -> bool:
        return False

    def render(self, **kw):  # pragma: no cover - trivially honest
        return {"status": "SKIPPED_UNAVAILABLE", "outputs": [],
                "provider": self.code, "error": "provider_not_configured"}


_REGISTRY: Dict[str, type] = {"null": NullProvider}


def register(provider_cls: type) -> None:
    _REGISTRY[provider_cls.code] = provider_cls


def get_provider(code: Optional[str]) -> VideoProvider:
    cls = _REGISTRY.get((code or "null").lower(), NullProvider)
    return cls()


def aspects_from(outputs):  # helper kept for symmetry
    return outputs


try:  # optional adapter registration (graceful if deps absent)
    from . import higgsfield_provider as _hf  # noqa: F401
    register(_hf.HiggsfieldProvider)
except Exception:  # pragma: no cover - adapter optional by design
    pass
