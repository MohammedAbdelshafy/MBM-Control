"""
Channel Profile Loader — single source of truth for brand-specific production recipes.
Each channel defines its own: content type, voice, captions, sound, visual style,
quality thresholds, and publishing rules.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PROFILES_DIR = Path(__file__).parent.parent
PROFILES_FILE = PROFILES_DIR / "channel_profiles.json"


@dataclass
class VoiceConfig:
    provider: str = "none"
    voice_id: str = ""
    rate: str = "+0%"
    pitch: str = "+0Hz"
    style: str = ""
    fallback_voices: List[str] = field(default_factory=list)


@dataclass
class CaptionConfig:
    style: str = "default"
    max_words_per_beat: int = 4
    font: str = "Arial"
    font_size: int = 36
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    position: str = "center"
    safe_area_margin: float = 0.1
    emphasis_words: bool = False


@dataclass
class SoundDesign:
    tension_music: bool = False
    reveal_hits: bool = False
    ambience: bool = False
    ducking_db: int = -6
    music_volume_db: int = -18
    master_loudness_lufs: float = -14.0


@dataclass
class PublishingConfig:
    platforms: List[str] = field(default_factory=lambda: ["youtube"])
    youtube_privacy: str = "unlisted"
    test_before_live: bool = True
    require_video_id_verification: bool = True
    prefer_publish_time_utc: List[int] = field(default_factory=lambda: [14, 18, 22])


@dataclass
class ChannelProfile:
    slug: str
    display_name: str
    channel_type: str
    genres: List[str]
    format: str
    aspect_ratio: str
    resolution: str
    fps: int
    narration: str
    tone: str
    visual_style: str
    target_duration_min: int
    target_duration_max: int
    daily_target: int
    quality_tier: str
    min_creative_score: float
    premium_creative_score: float = 8.5
    source_policy: List[str] = field(default_factory=list)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    captions: CaptionConfig = field(default_factory=CaptionConfig)
    sound: SoundDesign = field(default_factory=SoundDesign)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)
    hook_requirements: Dict[str, Any] = field(default_factory=dict)
    story_structure: List[str] = field(default_factory=list)
    visual_requirements: Dict[str, Any] = field(default_factory=dict)
    content_safety: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, slug: str, data: dict) -> "ChannelProfile":
        voice_data = data.get("voice_config", {})
        caption_data = data.get("caption_config", {})
        sound_data = data.get("sound_design", {})
        publish_data = data.get("publishing", {})

        return cls(
            slug=slug,
            display_name=data.get("display_name", slug),
            channel_type=data.get("channel_type", "generic"),
            genres=data.get("genres", []),
            format=data.get("format", "short_vertical"),
            aspect_ratio=data.get("aspect_ratio", "9:16"),
            resolution=data.get("resolution", "1080x1920"),
            fps=data.get("fps", 30),
            narration=data.get("narration", "none"),
            tone=data.get("tone", "neutral"),
            visual_style=data.get("visual_style", "default"),
            target_duration_min=data.get("target_duration_min", 30),
            target_duration_max=data.get("target_duration_max", 60),
            daily_target=data.get("daily_target", 2),
            quality_tier=data.get("quality_tier", "PUBLISH"),
            min_creative_score=data.get("min_creative_score", 7.0),
            premium_creative_score=data.get("premium_creative_score", 8.5),
            source_policy=data.get("source_policy", []),
            voice=VoiceConfig(
                provider=voice_data.get("provider", "none"),
                voice_id=voice_data.get("voice_id", ""),
                rate=voice_data.get("rate", "+0%"),
                pitch=voice_data.get("pitch", "+0Hz"),
                style=voice_data.get("style", ""),
                fallback_voices=voice_data.get("fallback_voices", []),
            ),
            captions=CaptionConfig(
                style=caption_data.get("style", "default"),
                max_words_per_beat=caption_data.get("max_words_per_beat", 4),
                font=caption_data.get("font", "Arial"),
                font_size=caption_data.get("font_size", 36),
                color=caption_data.get("color", "#FFFFFF"),
                outline_color=caption_data.get("outline_color", "#000000"),
                outline_width=caption_data.get("outline_width", 2),
                position=caption_data.get("position", "center"),
                safe_area_margin=caption_data.get("safe_area_margin", 0.1),
                emphasis_words=caption_data.get("emphasis_words", False),
            ),
            sound=SoundDesign(
                tension_music=sound_data.get("tension_music", False),
                reveal_hits=sound_data.get("reveal_hits", False),
                ambience=sound_data.get("ambience", False),
                ducking_db=sound_data.get("ducking_db", -6),
                music_volume_db=sound_data.get("music_volume_db", -18),
                master_loudness_lufs=sound_data.get("master_loudness_lufs", -14.0),
            ),
            publishing=PublishingConfig(
                platforms=publish_data.get("platforms", ["youtube"]),
                youtube_privacy=publish_data.get("youtube_privacy", "unlisted"),
                test_before_live=publish_data.get("test_before_live", True),
                require_video_id_verification=publish_data.get("require_video_id_verification", True),
                prefer_publish_time_utc=publish_data.get("prefer_publish_time_utc", [14, 18, 22]),
            ),
            hook_requirements=data.get("hook_requirements", {}),
            story_structure=data.get("story_structure", []),
            visual_requirements=data.get("visual_requirements", {}),
            content_safety=data.get("content_safety", {}),
        )


def load_all_profiles() -> Dict[str, ChannelProfile]:
    """Load all channel profiles from channel_profiles.json."""
    if not PROFILES_FILE.exists():
        raise FileNotFoundError(f"Channel profiles not found: {PROFILES_FILE}")
    raw = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    profiles = {}
    for slug, data in raw.get("channels", {}).items():
        profiles[slug] = ChannelProfile.from_dict(slug, data)
    return profiles


def get_profile(slug: str) -> ChannelProfile:
    """Get a single channel profile by slug."""
    profiles = load_all_profiles()
    if slug not in profiles:
        raise KeyError(f"No channel profile for '{slug}'. Available: {list(profiles.keys())}")
    return profiles[slug]
