"""Maxun client — run no-code scraping templates, export CSV/JSON/Excel."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.clients import BaseClient, ClientUnavailable
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("clients.maxun")


class MaxunClient(BaseClient):
    def __init__(self):
        super().__init__(
            settings.maxun_api_url,
            api_key=settings.maxun_api_key,
            timeout=60.0,
        )

    async def list_templates(self) -> list[dict]:
        try:
            data = await self._get("/api/workflows")
            return data.get("workflows", data) if isinstance(data, dict) else data
        except ClientUnavailable:
            raise

    async def run_template(self, workflow_id: str) -> dict:
        """Trigger a saved scraping workflow and return the run handle."""
        return await self._post(f"/api/workflows/{workflow_id}/run", json={})

    async def get_run_result(self, run_id: str) -> dict:
        return await self._get(f"/api/runs/{run_id}")
