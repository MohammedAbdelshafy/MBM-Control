"""Thumbnail API — generate a thumbnail prompt (and image if ComfyUI wired)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/thumbnail", tags=["thumbnail"])


class ThumbnailRequest(BaseModel):
    angle: str
    hook: str = ""


@router.post("/")
async def generate_thumbnail(body: ThumbnailRequest, _: str = Depends(get_current_user)):
    from app.services.ai_service import AIService

    ai = AIService()
    prompt = (
        f"Design a high-CTR YouTube thumbnail for: {body.angle} (hook: {body.hook}). "
        f"Return ONLY JSON: {{'prompt':str,'text_overlay':str,'style':str,'colors':[str]}}"
    )
    raw = ai.complete(prompt, system="You are a YouTube thumbnail designer.")
    import json

    thumb = {"prompt": body.angle, "text_overlay": body.hook, "style": "high-contrast", "colors": ["#FF0000", "#FFFFFF"]}
    try:
        thumb.update(json.loads(raw or "{}"))
    except Exception:
        pass
    return {"thumbnail": thumb, "image_path": None, "note": "image generation optional (ComfyUI)"}
