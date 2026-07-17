"""Ollama client — list local models and check availability."""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.clients import BaseClient, ClientUnavailable
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("clients.ollama")


class OllamaClient(BaseClient):
    def __init__(self):
        # Ollama base URL points at /v1 (OpenAI-compatible). The native admin
        # API lives at the root, so strip the /v1 suffix for tag listing.
        root = settings.ollama_base_url.replace("/v1", "").rstrip("/")
        super().__init__(root, timeout=15.0)

    async def list_models(self) -> list[dict]:
        """Return installed Ollama models as a list of {name, size, modified}."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "name": m.get("name"),
                        "size": m.get("size"),
                        "modified_at": m.get("modified_at"),
                        "digest": m.get("digest"),
                    }
                    for m in data.get("models", [])
                ]
        except httpx.HTTPError as exc:
            logger.warning(f"Ollama list_models failed: {exc}")
            raise ClientUnavailable(str(exc)) from exc

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
