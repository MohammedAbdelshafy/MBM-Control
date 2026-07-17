def __getattr__(name):
    if name == "VideoProcessor":
        from app.services.video_processor import VideoProcessor
        return VideoProcessor
    elif name == "AIService":
        from app.services.ai_service import AIService
        return AIService
    elif name == "AIVideoService":
        from app.services.ai_video_service import AIVideoService
        return AIVideoService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["VideoProcessor", "AIService", "AIVideoService"]
