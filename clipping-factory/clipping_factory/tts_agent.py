"""
TTS Agent — provider-independent voiceover generation.

Order:
  1. edge-tts   (neural, online)
  2. Windows SAPI via PowerShell System.Speech  (offline fallback)

Both produce REAL audio files validated by ffprobe.
No silent placeholder output is ever returned as success.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).parent.parent


def probe_audio_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _tts_edge(text: str, out_path: Path, voice_id: str, rate: str, pitch: str) -> bool:
    try:
        import asyncio
        import edge_tts

        async def _gen():
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
            await communicate.save(str(out_path))

        asyncio.run(_gen())
        return out_path.exists() and out_path.stat().st_size > 1000
    except Exception:
        return False


def _tts_sapi(text: str, out_path: Path, rate: int = -1) -> bool:
    """Offline Windows voice via System.Speech. Text passed through a temp file (no quoting issues)."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(text)
            text_file = tf.name

        ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.SetOutputToWaveFile("{str(out_path)}")
$text = Get-Content -Raw -Encoding UTF8 "{text_file}"
$synth.Speak($text)
$synth.Dispose()
"""
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, timeout=600,
        )
        Path(text_file).unlink(missing_ok=True)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000
    except Exception:
        return False


def generate_voiceover(
    narration: str,
    output_path: Path,
    voice_config: Optional[Dict] = None,
    estimated_duration_sec: float = 0.0,
) -> Dict:
    """
    Generate the voiceover. Returns an evidence record:
      provider used, file path, probed duration, validation result.
    """
    cfg = voice_config or {}
    provider_pref = (cfg.get("provider") or "edge_tts").lower()
    voice_id = cfg.get("voice_id") or "en-US-GuyNeural"
    rate = cfg.get("rate") or "-5%"
    pitch = cfg.get("pitch") or "-2Hz"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = []

    if provider_pref == "edge_tts":
        ok = _tts_edge(narration, output_path, voice_id, rate, pitch)
        attempts.append({"provider": f"edge_tts:{voice_id}", "ok": ok})
        if not ok:
            for fb in (cfg.get("fallback_voices") or [])[:2]:
                ok = _tts_edge(narration, output_path, fb, rate, pitch)
                attempts.append({"provider": f"edge_tts:{fb}", "ok": ok})
                if ok:
                    break

    provider = ""
    if output_path.exists() and output_path.stat().st_size > 1000:
        provider = "edge_tts"
    else:
        wav_path = output_path.with_suffix(".wav")
        ok = _tts_sapi(narration, wav_path)
        attempts.append({"provider": "windows_sapi", "ok": ok})
        if ok:
            provider = "windows_sapi"

            # normalize SAPI wav into the same container as primary path
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", "-b:a", "192k",
                     str(output_path)],
                    capture_output=True, timeout=300,
                )
                wav_path.unlink(missing_ok=True)
                if not output_path.exists():
                    provider = ""
                    output_path.rename(wav_path)  # keep the wav as evidence
                    output_path = wav_path
            except Exception:
                if wav_path.exists():
                    output_path.unlink(missing_ok=True)
                    wav_path.rename(output_path)

    duration = probe_audio_duration(output_path) if provider else 0.0
    valid = bool(provider) and duration >= 3.0
    pace_ok = True
    if valid and estimated_duration_sec > 0:
        ratio = duration / estimated_duration_sec
        pace_ok = 0.5 <= ratio <= 2.0

    return {
        "provider": provider,
        "path": str(output_path) if valid else "",
        "duration_sec": round(duration, 2),
        "estimated_duration_sec": round(estimated_duration_sec, 1),
        "pace_ratio": round(duration / estimated_duration_sec, 2) if estimated_duration_sec else None,
        "valid": valid,
        "pace_ok": pace_ok,
        "attempts": attempts,
        "error": "" if valid else "TTS_FAILED: no provider produced a valid audio file",
    }
