"""Models API — list installed Ollama models and availability."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.clients.ollama import OllamaClient
from app.core.clients import ClientUnavailable
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/models", tags=["models"])


@router.get("/")
async def list_models(_: str = Depends(get_current_user)):
    client = OllamaClient()
    if not await client.is_available():
        return {
            "available": False,
            "models": [],
            "note": f"Ollama not reachable at {settings.ollama_base_url}. Start `ollama serve`.",
        }
    try:
        models = await client.list_models()
        return {"available": True, "models": models, "default": settings.ollama_model}
    except ClientUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"Ollama unavailable: {exc}")
