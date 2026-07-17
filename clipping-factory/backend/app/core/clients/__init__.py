"""
HTTP clients for the integrated jarvis-mbm services.

Each client degrades gracefully: if the service is unreachable it raises a
ClientUnavailable error that callers can catch and report, instead of
crashing the pipeline. No secrets are logged.
"""
from __future__ import annotations

import httpx
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("clients.base")

DEFAULT_TIMEOUT = 30.0


class ClientUnavailable(Exception):
    """Raised when an integrated service cannot be reached."""


class BaseClient:
    """Minimal async HTTP client with JSON helpers."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            headers.update(extra)
        return headers

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(
                    f"{self.base_url}{path}", params=params, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            logger.warning(f"{self.__class__.__name__} GET {path} failed: {exc}")
            raise ClientUnavailable(str(exc)) from exc

    async def _post(self, path: str, json: dict | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.post(
                    f"{self.base_url}{path}", json=json, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            logger.warning(f"{self.__class__.__name__} POST {path} failed: {exc}")
            raise ClientUnavailable(str(exc)) from exc
