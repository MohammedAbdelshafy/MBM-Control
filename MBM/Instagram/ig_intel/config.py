"""Config loader for the MBM Instagram Intelligence system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    browser_mode: str = "chrome-devtools-mcp"
    devtools_url: str = "http://127.0.0.1:9222"
    playwright_profile: str = ""
    headless: bool = False
    rate_limit_seconds: float = 2.0
    max_reels_per_run: int = 200

    sources_saved: bool = True
    sources_liked: bool = True
    sources_collections: bool = True
    sources_following: bool = False
    sources_explore: bool = False
    sources_bookmarks: bool = True
    creators: list[str] = field(default_factory=list)
    collection_names: list[str] = field(default_factory=list)

    speech_engine: str = "whisper"
    ocr_engine: str = "paddleocr"
    vision_model: str = "qwen2.5-vl"
    llm_model: str = "qwen3"
    ffmpeg_path: str = "ffmpeg"
    sample_frames_every_sec: int = 2
    whisper_model: str = "base"

    base_dir: str = "."
    media_dir: str = "data/media"
    knowledge_dir: str = "Knowledge/Instagram"
    db_dir: str = "data/db"
    cache_dir: str = "data/cache"

    git_auto_commit: bool = True
    git_auto_push: bool = False
    git_commit_prefix: str = "instagram"

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        data: dict[str, Any] = {}
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        c = cls()
        # flatten nested config
        browser = data.get("browser", {})
        for k in ("mode", "devtools_url", "playwright_profile", "headless",
                  "rate_limit_seconds", "max_reels_per_run"):
            if k in browser:
                setattr(c, f"browser_{k}" if k == "mode" else k, browser[k])
        c.browser_mode = browser.get("mode", c.browser_mode)
        c.devtools_url = browser.get("devtools_url", c.devtools_url)
        c.playwright_profile = browser.get("playwright_profile", c.playwright_profile)
        c.headless = browser.get("headless", c.headless)
        c.rate_limit_seconds = browser.get("rate_limit_seconds", c.rate_limit_seconds)
        c.max_reels_per_run = browser.get("max_reels_per_run", c.max_reels_per_run)

        sources = data.get("sources", {})
        c.sources_saved = sources.get("saved", c.sources_saved)
        c.sources_liked = sources.get("liked", c.sources_liked)
        c.sources_collections = sources.get("collections", c.sources_collections)
        c.sources_following = sources.get("following", c.sources_following)
        c.sources_explore = sources.get("explore", c.sources_explore)
        c.sources_bookmarks = sources.get("bookmarks", c.sources_bookmarks)
        c.creators = sources.get("creators", c.creators)
        c.collection_names = sources.get("collection_names", c.collection_names)

        analysis = data.get("analysis", {})
        c.speech_engine = analysis.get("speech_engine", c.speech_engine)
        c.ocr_engine = analysis.get("ocr_engine", c.ocr_engine)
        c.vision_model = analysis.get("vision_model", c.vision_model)
        c.llm_model = analysis.get("llm_model", c.llm_model)
        c.ffmpeg_path = analysis.get("ffmpeg_path", c.ffmpeg_path)
        c.sample_frames_every_sec = analysis.get("sample_frames_every_sec", c.sample_frames_every_sec)
        c.whisper_model = analysis.get("whisper_model", c.whisper_model)

        storage = data.get("storage", {})
        c.base_dir = storage.get("base_dir", c.base_dir)
        c.media_dir = storage.get("media_dir", c.media_dir)
        c.knowledge_dir = storage.get("knowledge_dir", c.knowledge_dir)
        c.db_dir = storage.get("db_dir", c.db_dir)
        c.cache_dir = storage.get("cache_dir", c.cache_dir)

        git = data.get("git", {})
        c.git_auto_commit = git.get("auto_commit", c.git_auto_commit)
        c.git_auto_push = git.get("auto_push", c.git_auto_push)
        c.git_commit_prefix = git.get("commit_prefix", c.git_commit_prefix)

        # env overrides
        if os.getenv("IG_DEVTOOLS_URL"):
            c.devtools_url = os.environ["IG_DEVTOOLS_URL"]
        return c

    def resolve(self) -> "Config":
        """Resolve relative dirs against base_dir."""
        base = Path(self.base_dir).resolve()
        self.base_dir = str(base)
        self.media_dir = str((base / self.media_dir).resolve())
        self.knowledge_dir = str((base / self.knowledge_dir).resolve())
        self.db_dir = str((base / self.db_dir).resolve())
        self.cache_dir = str((base / self.cache_dir).resolve())
        return self
