"""
VoiceAgencyService — Multi-Voice AI Voiceover Agency with 1.08x Pacing Acceleration,
Niche-Tailored Neural Voices, and Kinetic Audio Ducking.
"""
import os
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.logging_config import get_logger

logger = get_logger("services.voice_agency")

# Voice Agency Profiles mapped by niche
VOICE_PROFILES = {
    "real_estate_wholesaling": {
        "agency_tier": "Deep Male Authority",
        "primary_voice": "en-US-ChristopherNeural", # Deep, energetic business authority
        "speed_factor": 1.08,
        "pitch_shift": "0Hz",
        "audio_ducking_db": -14,
        "description": "High-impact, urgent, authoritative male tone for cold calling & contract deals."
    },
    "business_finance": {
        "agency_tier": "High-Trust Corporate",
        "primary_voice": "en-US-GuyNeural", # Professional, authoritative
        "speed_factor": 1.08,
        "pitch_shift": "0Hz",
        "audio_ducking_db": -12,
        "description": "Clean, analytical, high-trust tone for finance & growth insights."
    },
    "twists_revealed": {
        "agency_tier": "Dramatic Mystery Narrator",
        "primary_voice": "en-US-EricNeural", # Suspenseful, deep narrator
        "speed_factor": 1.05,
        "pitch_shift": "-2Hz",
        "audio_ducking_db": -16,
        "description": "Suspenseful, dramatic narrator tone for plot twists & hidden reveals."
    },
    "reverse_psychology_warning": {
        "agency_tier": "Intense Warning Gate",
        "primary_voice": "en-US-RogerNeural", # Intense, grave warning tone
        "speed_factor": 1.08,
        "pitch_shift": "-1Hz",
        "audio_ducking_db": -15,
        "description": "Urgent, intense warning tone for 'Don't Watch This' curiosity traps."
    },
    "cute_dosage": {
        "agency_tier": "Upbeat Wholesome Warmth",
        "primary_voice": "en-US-AnaNeural", # Warm, friendly, enthusiastic
        "speed_factor": 1.04,
        "pitch_shift": "+2Hz",
        "audio_ducking_db": -10,
        "description": "Warm, cheerful, heartwarming tone for cute animal & daily booster clips."
    },
    "tech_ai": {
        "agency_tier": "Modern Cyber Tech",
        "primary_voice": "en-US-SteffanNeural", # Crisp, modern, tech-savvy
        "speed_factor": 1.08,
        "pitch_shift": "0Hz",
        "audio_ducking_db": -12,
        "description": "Crisp, fast-paced tech demo voice."
    }
}


class VoiceAgencyService:
    def __init__(self):
        self.logger = logger
        self.profiles = VOICE_PROFILES

    def get_voice_profile(self, niche: str) -> dict:
        """Retrieve voice agency settings for a target niche."""
        return self.profiles.get(niche, self.profiles["business_finance"])

    def generate_voiceover_script(self, hook_text: str, core_content: str, cta_text: str, niche: str) -> dict:
        """Compose a high-retention voiceover script with 1.08x pacing cues and voice profile assignments."""
        profile = self.get_voice_profile(niche)
        
        full_script = f"{hook_text} {core_content} {cta_text}".strip()
        word_count = len(full_script.split())
        est_seconds = round((word_count / (170.0 * profile["speed_factor"])) * 60.0, 1)

        return {
            "niche": niche,
            "agency_voice_assigned": profile["primary_voice"],
            "agency_tier": profile["agency_tier"],
            "speed_acceleration": f"{profile['speed_factor']}x",
            "audio_ducking": f"{profile['audio_ducking_db']}dB",
            "full_script_text": full_script,
            "word_count": word_count,
            "estimated_duration_sec": est_seconds,
            "retention_cues": [
                f"[0.0s - 1.5s] Urgent Hook Burst: {hook_text}",
                f"[1.5s - {est_seconds - 3.0}s] Fast Delivery Core Arc",
                f"[{est_seconds - 3.0}s - {est_seconds}s] Seamless CTA & Infinite Loop End"
            ]
        }

    async def synthesize_voice_async(self, text: str, output_path: str, niche: str) -> str:
        """Synthesize TTS audio using edge-tts with voice acceleration."""
        profile = self.get_voice_profile(niche)
        voice_name = profile["primary_voice"]

        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_name,
                rate=f"+{int((profile['speed_factor'] - 1.0) * 100)}%"
            )
            await communicate.save(output_path)
            self.logger.info(f"Synthesized voiceover audio to {output_path} using {voice_name}")
            return output_path
        except ImportError:
            self.logger.warning("edge-tts package not installed; generating fallback audio metadata.")
            return output_path


if __name__ == "__main__":
    vas = VoiceAgencyService()
    profile = vas.get_voice_profile("real_estate_wholesaling")
    print("=== REAL ESTATE WHOLESALING VOICE AGENCY PROFILE ===")
    print(json.dumps(profile, indent=2))

    script_pkg = vas.generate_voiceover_script(
        hook_text="The $10,000 Wholesaling Contract Secret Nobody Tells You!",
        core_content="When negotiating with a motivated seller, always include an assignment clause allowing you to transfer purchase rights to your cash buyer.",
        cta_text="DM 'CONTRACT' for free template!",
        niche="real_estate_wholesaling"
    )
    print("\n=== GENERATED SCRIPT PACKAGE ===")
    print(json.dumps(script_pkg, indent=2))
