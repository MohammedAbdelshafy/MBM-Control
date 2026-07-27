"""Analysis pipeline: speech -> OCR -> vision -> LLM classification.

All heavy lifting prefers local inference:
  - speech: whisper (local) or Ollama ASR
  - OCR: PaddleOCR (local) or Ollama vision
  - vision: Ollama VLM (qwen2.5-vl)
  - classification/prompts: Ollama LLM (qwen3 / deepseek)

Each stage degrades gracefully: if a local engine is unavailable the stage is
skipped and the field is left for later / manual fill, rather than failing the run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .config import Config
from .media import extract_audio, sample_frames
from .schema import (
    Reel, HOOK_TYPES, PSYCHOLOGY_TRIGGERS, BUSINESS_MODELS, MBM_SCORE_KEYS,
)


class Analyzer:
    def __init__(self, config: Config, log: Callable[[str], None] = print):
        self.config = config
        self.log = log

    # --- speech --------------------------------------------------------
    def transcribe(self, video: Path) -> dict:
        audio = extract_audio(video, self.config.ffmpeg_path)
        if not audio:
            return {"transcript": "", "summary": "", "key_quotes": []}
        if self.config.speech_engine == "whisper":
            return self._whisper(audio)
        return self._ollama_asr(audio)

    def _whisper(self, audio: Path) -> dict:
        try:
            import whisper

            model = whisper.load_model(self.config.whisper_model)
            res = model.transcribe(str(audio))
            text = res.get("text", "").strip()
            return {"transcript": text, "summary": text[:500], "key_quotes": []}
        except Exception as e:  # noqa: BLE001
            self.log(f"[speech] whisper failed: {e}")
            return {"transcript": "", "summary": "", "key_quotes": []}

    def _ollama_asr(self, audio: Path) -> dict:
        # Placeholder for Ollama-based ASR (e.g. whisper.cpp served via Ollama).
        self.log("[speech] ollama ASR not wired; returning empty")
        return {"transcript": "", "summary": "", "key_quotes": []}

    # --- OCR -----------------------------------------------------------
    def ocr_frames(self, frames: list[Path]) -> dict:
        if self.config.ocr_engine == "paddleocr":
            return self._paddleocr(frames)
        return self._ollama_ocr(frames)

    def _paddleocr(self, frames: list[Path]) -> dict:
        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="en")
            texts: list[str] = []
            numbers: list[str] = []
            contacts: list[str] = []
            for fr in frames:
                result = ocr.predict(str(fr))
                for line in result:
                    txt = " ".join(line) if isinstance(line, (list, tuple)) else str(line)
                    texts.append(txt)
                    numbers += __import__("re").findall(r"\b\d[\d,.]*\b", txt)
                    contacts += __import__("re").findall(
                        r"(?:https?://\S+|[\w.]+@[\w.]+\.\w+|\+?\d[\d\s()-]{7,}\d)", txt
                    )
            return {
                "subtitles": "\n".join(texts),
                "numbers": ", ".join(sorted(set(numbers))),
                "contacts": ", ".join(sorted(set(contacts))),
            }
        except Exception as e:  # noqa: BLE001
            self.log(f"[ocr] paddleocr failed: {e}")
            return {"subtitles": "", "numbers": "", "contacts": ""}

    def _ollama_ocr(self, frames: list[Path]) -> dict:
        self.log("[ocr] ollama vision OCR not wired; returning empty")
        return {"subtitles": "", "numbers": "", "contacts": ""}

    # --- vision --------------------------------------------------------
    def vision(self, frames: list[Path], transcript: str) -> dict:
        prompt = (
            "You are a video editing analyst. Given sampled frames from an Instagram "
            "Reel and its transcript, return strict JSON with keys: editing_style, "
            "visual_breakdown, scene_timeline, transitions, cuts_per_minute, "
            "average_shot_length, subtitle_style, font, color_palette, hook_timing, "
            "cta_timing, music_timing. Be concise and numeric where possible."
        )
        out = self._ollama_vision(prompt, frames)
        try:
            return json.loads(out)
        except Exception:
            self.log("[vision] could not parse VLM output")
            return {}

    def _ollama_vision(self, prompt: str, frames: list[Path]) -> str:
        try:
            import ollama

            imgs = [str(f) for f in frames[:8]]
            res = ollama.chat(
                model=self.config.vision_model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": imgs,
                }],
            )
            return res["message"]["content"]
        except Exception as e:  # noqa: BLE001
            self.log(f"[vision] ollama failed: {e}")
            return ""

    # --- classification / prompts -------------------------------------
    def classify(self, reel: Reel) -> Reel:
        prompt = self._build_classify_prompt(reel)
        out = self._ollama_llm(prompt)
        data = self._safe_json(out)
        if data:
            self._apply_classification(reel, data)
        return reel

    def _build_classify_prompt(self, reel: Reel) -> str:
        return (
            "You are the MBM Instagram intelligence classifier. Given a Reel's "
            "caption and transcript, return strict JSON with these keys:\n"
            "title, category, niche, business_model (one of "
            f"{BUSINESS_MODELS}), primary_hook, hook_type (one of {HOOK_TYPES}), "
            "hook_score (1-10 int), retention_score (1-10 int), cta, "
            "psychology_used (comma list from "
            f"{PSYCHOLOGY_TRIGGERS}), marketing_strategy, sales_funnel, "
            "monetization_method, offer, pain_points, dream_outcome, audience, "
            "keywords, hashtags, music, framework, how_to_clone,\n"
            "ai_recreation_prompt, capcut_prompt, invideo_prompt, canva_prompt, "
            "midjourney_prompt, flux_prompt, chatgpt_prompt, claude_prompt, "
            "gemini_prompt, thumbnail_prompt, improvements,\n"
            "mbm_scores (object with keys "
            f"{MBM_SCORE_KEYS} each 1-100 int), potential_revenue, notes.\n\n"
            f"CAPTION:\n{reel.caption}\n\nTRANSCRIPT:\n{reel.transcript}\n"
        )

    def _ollama_llm(self, prompt: str) -> str:
        try:
            import ollama

            res = ollama.chat(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return res["message"]["content"]
        except Exception as e:  # noqa: BLE001
            self.log(f"[llm] ollama failed: {e}")
            return ""

    @staticmethod
    def _safe_json(text: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception:
            return {}
        return {}

    @staticmethod
    def _apply_classification(reel: Reel, data: dict):
        for k, v in data.items():
            if k == "mbm_scores":
                reel.mbm_scores = v
                try:
                    reel.mbm_relevance_score = int(v.get("moneybeast", 0))
                except Exception:
                    pass
            elif hasattr(reel, k):
                setattr(reel, k, v)
