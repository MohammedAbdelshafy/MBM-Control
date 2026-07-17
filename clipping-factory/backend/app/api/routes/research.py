"""Research API — trend-aware research for a topic (Ollama-backed)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    topic: str
    niche: str = "general"
    angle: str | None = None


@router.post("/")
async def research(body: ResearchRequest, _: str = Depends(get_current_user)):
    from app.services.ai_service import AIService

    ai = AIService()
    prompt = (
        f"Research the YouTube angle '{body.angle or body.topic}' in the "
        f"'{body.niche}' niche. Return 3-5 factual bullet points a creator "
        f"can use on-screen, as a JSON list of strings under key 'facts'."
    )
    raw = ai.complete(prompt, system="You are a meticulous researcher.")
    import json

    facts: list[str] = []
    try:
        facts = json.loads(raw or "{}").get("facts", [])
    except Exception:
        facts = [body.topic]
    return {"topic": body.topic, "niche": body.niche, "facts": facts}
