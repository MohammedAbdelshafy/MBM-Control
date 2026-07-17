"""Workflows API — proxy to Langflow flows (list + trigger)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.clients.langflow import LangflowClient
from app.core.clients import ClientUnavailable

router = APIRouter(prefix="/workflows", tags=["workflows"])


class RunFlowRequest(BaseModel):
    flow_id: str
    inputs: dict = {}


@router.get("/")
async def list_workflows(_: str = Depends(get_current_user)):
    client = LangflowClient()
    try:
        flows = await client.list_flows()
        return {"count": len(flows), "flows": flows}
    except ClientUnavailable as exc:
        return {"count": 0, "flows": [], "note": f"Langflow unavailable: {exc}"}


@router.post("/run")
async def run_workflow(body: RunFlowRequest, _: str = Depends(get_current_user)):
    client = LangflowClient()
    try:
        result = await client.run_flow(body.flow_id, body.inputs)
        return {"flow_id": body.flow_id, "result": result}
    except ClientUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"Langflow unavailable: {exc}")
