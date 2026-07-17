"""Browser-Use API client — web automation tasks (Google, YouTube Studio, etc.)."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.clients import BaseClient, ClientUnavailable
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("clients.browser_use")


class BrowserUseClient(BaseClient):
    def __init__(self):
        super().__init__(
            settings.browser_use_api_url,
            api_key=settings.browser_use_api_key,
            timeout=60.0,
        )

    async def list_tasks(self) -> list[dict]:
        try:
            data = await self._get("/tasks/")
            return data.get("tasks", data) if isinstance(data, dict) else data
        except ClientUnavailable:
            raise

    async def run_task(self, task: str, llm_model: str | None = None) -> dict:
        """Submit a natural-language browser task and return the run handle."""
        payload = {"task": task, "llm_model": llm_model or settings.ollama_model}
        return await self._post("/tasks/", json=payload)

    async def get_task_result(self, task_id: str) -> dict:
        return await self._get(f"/tasks/{task_id}")
