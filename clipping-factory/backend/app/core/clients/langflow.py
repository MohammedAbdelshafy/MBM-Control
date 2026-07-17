"""Langflow client — list and trigger flows exposed as REST APIs."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.clients import BaseClient, ClientUnavailable
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("clients.langflow")


class LangflowClient(BaseClient):
    def __init__(self):
        super().__init__(
            settings.langflow_base_url,
            api_key=settings.langflow_api_key,
            timeout=30.0,
        )

    async def list_flows(self) -> list[dict]:
        """Return Langflow flows (id, name)."""
        try:
            data = await self._get("/api/v1/flows/")
            flows = data.get("flows", []) if isinstance(data, dict) else data
            return [
                {"id": f.get("id"), "name": f.get("name")}
                for f in flows
            ]
        except ClientUnavailable:
            raise

    async def run_flow(self, flow_id: str, inputs: dict | None = None) -> dict:
        """Trigger a flow by id and return its result."""
        payload = {"input_value": inputs or {}, "output_type": "chat", "input_type": "chat"}
        return await self._post(f"/api/v1/run/{flow_id}", json=payload)
