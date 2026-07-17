"""Script API — generate a YouTube script + hook (Ollama-backed)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/script", tags=["script"])


class ScriptRequest(BaseModel):
    angle: str
    facts: list[str] = []
    format: str = "short"   # short | long
    length_seconds: int = 45


@router.post("/")
async def generate_script(body: ScriptRequest, _: str = Depends(get_current_user)):
    from app.services.ai_service import AIService

    ai = AIService()
    prompt = (
        f"Write a YouTube {body.format} script for: {body.angle}. Include a "
        f"1-sentence hook, body, and CTA. Facts:\n"
        f"{chr(10).join('- ' + f for f in body.facts)}\n"
        f"Respond ONLY with JSON: {{'hook':str,'body':str,'cta':str,'est_seconds':int}}"
    )
    raw = ai.complete(prompt, system="You are a viral YouTube scriptwriter.")
    import json

    script = {"hook": "", "body": body.angle, "cta": "Follow for more!", "est_seconds": body.length_seconds}
    try:
        script.update(json.loads(raw or "{}"))
    except Exception:
        pass
    return {"script": script}
