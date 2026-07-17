"""
Central configuration — all values read from environment variables.
No hardcoded secrets or paths. Add new settings here; import Settings everywhere.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],  # load parent dir first (project root), then local override
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "production", "test"] = "development"
    app_secret_key: str = "change-me"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://clipuser:clippass@localhost:5432/clipping_factory"
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_statement_timeout: int = 30000
    database_pool_timeout: int = 10

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Storage (S3/MinIO with local filesystem fallback)
    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket_source: str = "source-content"
    storage_bucket_clips: str = "clips"
    storage_bucket_deliverables: str = "deliverables"
    storage_region: str = "us-east-1"
    storage_use_ssl: bool = False
    storage_local_path: str = "data/storage"

    # AI
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    runware_api_key: str = ""
    ai_primary_model: str = "claude-fable-5"
    ai_fast_model: str = "claude-opus-4-8"
    ai_max_tokens: int = 16000
    ai_temperature: float = 0.3
    ai_cost_cap_per_campaign: float = 2.00
    # Prompt caching — marks system prompts with cache_control for ~90% token savings
    ai_cache_system_prompt: bool = True
    # Extended thinking:
    #   Fable 5 — always on; AI_EFFORT_LEVEL controls depth (budget_tokens is rejected).
    #   Opus 4.8 — uses thinking: {type: "adaptive"} when this is True.
    ai_extended_thinking: bool = True
    ai_thinking_budget: int = 16000   # Opus 4.8 only; ignored for Fable 5
    # Fable 5 reasoning depth: low | medium | high | xhigh | max
    ai_effort_level: str = "high"

    # Gemini free tier (aistudio.google.com → Get API key — FREE)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.0-flash"   # best free model: 1M ctx, fast

    # Ollama local (completely free — no key, no internet, already pulled qwen2.5:7b)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5-coder:7b"

    # Whisper
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Video
    ffmpeg_path: str = ""  # empty = auto-resolved via imageio_ffmpeg at runtime
    max_video_duration_seconds: int = 7200
    max_clip_duration_seconds: int = 180
    min_clip_duration_seconds: int = 15
    video_temp_dir: str = "C:/temp/clips"

    # Clipping.com
    clipping_base_url: str = "https://clipping.com"
    clipping_email: str = ""
    clipping_password: str = ""
    clipping_auth_method: str = "email"   # email | discord | google
    clipping_scan_interval_seconds: int = 300
    clipping_max_campaigns_per_scan: int = 20
    clipping_session_refresh_hours: int = 12

    # Demo mode: seed fake campaigns instead of real scraping. Auto-on when no credentials.
    clipping_demo_mode: bool = False

    # ---- Social publishing (browser automation via Playwright) --------------
    # Comma-separated platforms to auto-publish to, e.g. "tiktok,instagram,youtube".
    publish_platforms: str = "tiktok,instagram,youtube"
    publish_headless: bool = True
    publish_slow_mo_ms: int = 0          # add delay between actions to dodge anti-bot
    publish_timeout_ms: int = 45000
    # Publish a clip to socials automatically after it passes QC (mirrors auto_submit).
    auto_publish: bool = False
    # Per-platform session state as JSON (Playwright storage_state or cookie array).
    # Paste an exported logged-in session here; empty => simulated (mock) publish.
    tiktok_session_state: str = ""
    instagram_session_state: str = ""
    youtube_session_state: str = ""
    whop_session_state: str = ""
    clippingnet_session_state: str = ""

    # ---- Clipping-platform sessions (creator-account logins) --------------
    # Per-platform Playwright storage_state JSON (exported via
    # scripts/export_clipping_sessions.py after you manually log in).
    # Empty => delivery to that platform is simulated (mock submit).
    vyro_session_state: str = ""
    reachcat_session_state: str = ""
    clipaffiliates_session_state: str = ""
    clippingcom_session_state: str = ""

    @property
    def publish_platform_list(self) -> list[str]:
        from app.models.social_post import SocialPlatform
        raw = [p.strip().lower() for p in self.publish_platforms.split(",") if p.strip()]
        return SocialPlatform.resolve(raw)

    def social_session_state(self, platform: str) -> str:
        return {
            "tiktok": self.tiktok_session_state,
            "instagram": self.instagram_session_state,
            "youtube": self.youtube_session_state,
        }.get(platform, "")

    def clipping_session_state(self, platform: str) -> str:
        """Return exported session JSON for a clipping platform key.

        Checks the env var first, then falls back to the JSON file written
        by scripts/export_clipping_sessions.py at backend/sessions/<id>.json
        (so you only need to run that script — no .env editing required).
        """
        env_val = {
            "whop": self.whop_session_state,
            "clipping_com": self.clippingcom_session_state,
            "clipping_net": self.clippingnet_session_state,
            "vyro": self.vyro_session_state,
            "reach_cat": self.reachcat_session_state,
            "clip_affiliates": self.clipaffiliates_session_state,
            "clipping_com": self.clippingcom_session_state,
        }.get(platform, "")
        if env_val:
            return env_val
        # Fallback: read the saved session file produced by the export script.
        session_file = (
            Path(__file__).parent.parent / "sessions" / f"{platform}.json"
        )
        if session_file.exists():
            try:
                return session_file.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    @property
    def demo_mode(self) -> bool:
        _placeholders = {"", "your@email.com", "your_password", "change-me"}
        no_creds = (
            self.clipping_email in _placeholders
            or self.clipping_password in _placeholders
        )
        return self.clipping_demo_mode or no_creds

    # Voice-over / TTS
    voiceover_default_voice: str = "en-US-JennyNeural"
    voiceover_default_rate: str = "+0%"
    voiceover_default_pitch: str = "+0Hz"

    # Monetization Agent
    monetization_enabled: bool = False
    monetization_check_interval_seconds: int = 600
    monetization_min_viable_revenue: float = 50.0
    monetization_alert_email: str = ""
    monetization_webhook_url: str = ""
    monetization_max_offer_age_hours: int = 48
    # Good-news-only mode: the agent NEVER sends security / storage / pipeline
    # health / low-revenue ("no money") alerts. It only reports positive events
    # (winnings, new accepted clips, completed campaigns, recovered earnings).
    monetization_good_news_only: bool = True

    # Telegram alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Notification verbosity: error (only errors), important (delivery + earnings + errors), all (every event)
    telegram_notification_level: str = "important"

    # Enhancement (FFmpeg filter pipeline) — pro clipper quality
    enhancement_enabled: bool = True
    enhancement_sharpen: bool = True
    enhancement_sharpen_luma_strength: float = 8.0      # was 5.0 — crisper details
    enhancement_sharpen_luma_radius: float = 5.0
    enhancement_sharpen_luma_threshold: float = 0.6     # was 0.8 — catches more softness
    enhancement_sharpen_chroma_strength: float = 5.0    # was 3.0 — richer colors
    enhancement_sharpen_chroma_radius: float = 4.0      # was 3.0
    enhancement_sharpen_chroma_threshold: float = 0.3   # was 0.4
    enhancement_color_grade: bool = True
    enhancement_contrast: float = 1.08                  # was 1.05 — punchier
    enhancement_brightness: float = 0.03                # was 0.02 — slightly brighter
    enhancement_saturation: float = 1.15                # was 1.1 — more vibrant
    enhancement_denoise: bool = True
    enhancement_denoise_spatial_luma: float = 2.0       # was 1.5 — cleaner
    enhancement_denoise_spatial_chroma: float = 2.0     # was 1.5
    enhancement_denoise_temp_luma: float = 4.0          # was 3.0 — smoother motion
    enhancement_denoise_temp_chroma: float = 4.0        # was 3.0
    enhancement_upscale: bool = True                    # was False — auto-upscale low-res
    enhancement_upscale_model: str = "realesrgan-x4plus"
    enhancement_upscale_scale: int = 2
    enhancement_crf: int = 16                           # was 18 — near-lossless
    enhancement_preset: str = "veryslow"                # was slow — best compression

    # Real-ESRGAN path (empty = auto-resolve)
    real_esrgan_path: str = "realesrgan-ncnn-vulkan"

    # Processing
    max_concurrent_campaigns: int = 3
    max_clips_per_campaign: int = 30
    clip_score_threshold: float = 0.65
    auto_submit: bool = False
    min_payout_per_1k_views: float = 4.0

    # Alerts
    alert_webhook_url: str = ""
    alert_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    # Admin
    admin_username: str = "admin"
    admin_password: str = "change-me-admin-password"

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        if v == "change-me-admin-password":
            import warnings
            warnings.warn(
                "SECURITY: admin_password is set to the default value. "
                "Set ADMIN_PASSWORD env var before deploying to production.",
                stacklevel=2,
            )
        if len(v) < 8:
            raise ValueError("admin_password must be at least 8 characters")
        return v

    @field_validator("ffmpeg_path")
    @classmethod
    def resolve_ffmpeg_path(cls, v: str) -> str:
        if v:
            return v
        try:
            import shutil
            sys_ffmpeg = shutil.which("ffmpeg")
            if sys_ffmpeg:
                return sys_ffmpeg
        except Exception:
            pass
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return "ffmpeg"

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if "postgresql://" in v and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def storage_public_url(self) -> str:
        return self.storage_endpoint

    # ------------------------------------------------------------------
    # jarvis-mbm integrated services (reachable on the jm-net / host)
    # All bound to 127.0.0.1 by default (Tailscale-only exposure).
    # ------------------------------------------------------------------
    # Langflow — visual LLM workflows exposed as REST APIs (:7860)
    langflow_base_url: str = "http://localhost:7860"
    langflow_api_key: str = ""
    langflow_verify_ssl: bool = False

    # Browser-Use API — web automation (:8001)
    browser_use_api_url: str = "http://localhost:8001"
    browser_use_api_key: str = ""

    # Maxun — no-code scraping, server :8000
    maxun_api_url: str = "http://localhost:8000"
    maxun_api_key: str = ""

    # Open WebUI — chat UI over local models (:3000 -> container 8080)
    open_webui_url: str = "http://localhost:3000"

    # Qdrant — vector store (memory / RAG)
    qdrant_url: str = "http://localhost:6333"

    # ------------------------------------------------------------------
    # YouTube pipeline (OAuth — secrets NEVER stored in code)
    # ------------------------------------------------------------------
    youtube_oauth_enabled: bool = False
    # Path to client_secret_*.json obtained from Google Cloud Console.
    # The actual token file (youtube_tokens.json) is created by
    # scripts/youtube_oauth_setup.py and is git-ignored.
    youtube_client_secrets_path: str = "youtube_client_secret.json"
    youtube_tokens_path: str = "youtube_tokens.json"
    youtube_default_privacy: str = "unlisted"   # public | unlisted | private
    youtube_default_category_id: str = "28"     # 28 = Science & Technology

    # Pipeline artifact directories (created on demand)
    pipeline_data_dir: str = "data/pipeline"
    uploads_dir: str = "data/uploads"
    transcripts_dir: str = "data/transcripts"
    thumbnails_dir: str = "data/thumbnails"

    @property
    def pipeline_dirs(self) -> dict[str, Path]:
        """Resolve and ensure the pipeline artifact directories exist."""
        base = Path(self.pipeline_data_dir)
        dirs = {
            "pipeline": base,
            "uploads": Path(self.uploads_dir),
            "transcripts": Path(self.transcripts_dir),
            "thumbnails": Path(self.thumbnails_dir),
        }
        for p in dirs.values():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        return dirs

    def youtube_tokens_file(self) -> Path:
        return Path(self.youtube_tokens_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
