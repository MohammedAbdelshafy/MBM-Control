"""Transcribe API — convert speech to text using local Whisper."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


class TranscribeRequest(BaseModel):
    # Path to a media file accessible to the backend (local-first).
    media_path: str
    model: str | None = None


@router.post("/")
async def transcribe(body: TranscribeRequest, _: str = Depends(get_current_user)):
    from pathlib import Path

    path = Path(body.media_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {body.media_path}")

    try:
        from app.services.video_processor import VideoProcessor

        result = VideoProcessor.transcribe(str(path), model=body.model)
        return {
            "text": result.get("text", ""),
            "language": result.get("language"),
            "segments": result.get("segments", []),
        }
    except Exception as exc:
        # Fall back to noting the need for whisper deps.
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
