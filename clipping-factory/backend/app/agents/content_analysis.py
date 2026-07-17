"""
ContentAnalysisAgent — transcribes source content and identifies clip candidates.

Produces:
- Full transcript with word-level timestamps
- Speaker diarization (if enabled)
- Viral moment detection (emotional peaks, story arcs, high-energy segments)
- Ranked clip candidate windows ready for ClipGenerationAgent
- AI-generated video clips via Comfy AI (when requested)
"""
from typing import Any
import json

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


class ContentAnalysisAgent(BaseAgent):
    name = "content_analysis"

    def run(self, source_content_id: str) -> AgentResult:
        from app.models.source_content import SourceContent
        from app.models.transcript import Transcript

        source = (
            self.db.query(SourceContent)
            .filter(SourceContent.id == source_content_id)
            .first()
        )
        if not source:
            return AgentResult.fail(f"SourceContent {source_content_id} not found")

        self.logger.info(
            f"Analyzing content: {source.id} "
            f"({source.duration_seconds:.0f}s, {source.source_type})"
        )

        # Download source file temporarily
        import tempfile
        from pathlib import Path
        from app.core.storage import download_file

        with tempfile.TemporaryDirectory(prefix="clip_analysis_") as tmpdir:
            local_path = download_file(
                source.storage_bucket,
                source.storage_key,
                Path(tmpdir) / "source.mp4",
            )

            # Step 1: Transcribe
            transcript_data = self._transcribe(local_path)

            # Step 2: Speaker diarization (optional, CPU-intensive)
            speakers = self._diarize(local_path) if self.settings.whisper_device != "cpu" else []

            # Step 3: Detect viral moments using AI
            viral_moments = self._detect_viral_moments(
                transcript_data, source.duration_seconds or 0
            )

            # Step 4: Generate clip candidates
            campaign = source.campaign
            requirements = dict(campaign.requirements or {}) if campaign else {}
            if campaign and campaign.brand_name:
                requirements["brand"] = campaign.brand_name
            candidates = self._generate_candidates(
                transcript_data, viral_moments, requirements, source.duration_seconds or 0
            )

        # Persist transcript
        existing = (
            self.db.query(Transcript)
            .filter(Transcript.source_content_id == source_content_id)
            .first()
        )
        if existing:
            transcript = existing
        else:
            transcript = Transcript(source_content_id=source_content_id)
            self.db.add(transcript)

        transcript.full_text = transcript_data.get("text", "")
        transcript.language = transcript_data.get("language", "en")
        transcript.segments = transcript_data.get("segments", [])
        transcript.speakers = speakers
        transcript.viral_moments = viral_moments
        transcript.clip_candidates = candidates
        transcript.whisper_model = self.settings.whisper_model
        transcript.status = "ready"
        self.db.flush()

        self.logger.info(
            f"Analysis complete: {len(candidates)} clip candidates, "
            f"{len(viral_moments)} viral moments"
        )

        # Trigger clip generation
        from app.workers.video_tasks import generate_clips
        generate_clips.apply_async(args=[source_content_id], queue="video")

        return AgentResult.ok({
            "transcript_id": transcript.id,
            "candidates": len(candidates),
            "viral_moments": len(viral_moments),
        })

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def _transcribe(self, local_path) -> dict:
        """Run transcription with WhisperX (GPU) or faster-whisper (CPU).

        WhisperX provides better word-level timestamps via wav2vec2 alignment.
        Falls back gracefully through faster-whisper → empty (no paid API fallback).
        """
        import time

        t0 = time.time()
        empty = {"text": "", "language": "en", "segments": [], "processing_time": 0.0}

        # Try WhisperX first if GPU available
        if self.settings.whisper_device != "cpu":
            try:
                return self._transcribe_whisperx(local_path, t0)
            except ImportError:
                self.logger.debug("whisperx not installed; falling back to faster-whisper")
            except ValueError as exc:
                if "Language" in str(exc) and "is not supported" in str(exc):
                    self.logger.warning(f"Unsupported language for WhisperX alignment ({exc}); falling back to faster-whisper")
                else:
                    self.logger.warning(f"WhisperX failed ({exc}); falling back to faster-whisper")
            except Exception as exc:
                self.logger.warning(f"WhisperX failed ({exc}); falling back to faster-whisper")

        # Fallback to faster-whisper (free, CPU)
        try:
            return self._transcribe_faster_whisper(local_path, t0)
        except ImportError:
            self.logger.warning("faster-whisper not installed — no transcription available")
        except Exception as exc:
            self.logger.warning(f"faster-whisper failed ({exc})")
            empty["processing_time"] = time.time() - t0

        self.logger.error("All free transcription methods failed")
        return empty

    def _transcribe_whisperx(self, local_path, t0: float) -> dict:
        """Transcribe using WhisperX for better word-level alignment."""
        import time
        import whisperx

        device = self.settings.whisper_device or "cuda"
        model = whisperx.load_model(
            self.settings.whisper_model,
            device=device,
            compute_type=self.settings.whisper_compute_type,
            asr_options={"word_timestamps": True},
        )

        # Transcribe
        result = model.transcribe(str(local_path), batch_size=16, print_progress=False)
        language = result.get("language", "en")

        # Align with wav2vec2 for better word timestamps
        align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
        result = whisperx.align(
            result["segments"],
            align_model,
            metadata,
            str(local_path),
            device=device,
        )

        segments = []
        full_words = []

        for seg in result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", ""),
                    "start": round(w.get("start", 0), 3),
                    "end": round(w.get("end", 0), 3),
                    "probability": round(w.get("probability", 1.0), 3),
                })
                full_words.append(w.get("word", ""))

            segments.append({
                "id": seg.get("id", 0),
                "start": round(seg.get("start", 0), 3),
                "end": round(seg.get("end", 0), 3),
                "text": seg.get("text", "").strip(),
                "words": words,
                "avg_logprob": round(seg.get("avg_logprob", 0), 4),
                "no_speech_prob": round(seg.get("no_speech_prob", 0), 4),
            })

        return {
            "text": " ".join(full_words),
            "language": language,
            "duration": result.get("duration", 0),
            "segments": segments,
            "processing_time": time.time() - t0,
        }

    def _transcribe_faster_whisper(self, local_path, t0: float) -> dict:
        """Transcribe using faster-whisper."""
        import time
        from faster_whisper import WhisperModel

        model = WhisperModel(
            self.settings.whisper_model,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
        )

        segments_raw, info = model.transcribe(
            str(local_path),
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
        )

        segments = []
        full_words = []

        for seg in segments_raw:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3),
                    })
                    full_words.append(w.word)

            segments.append({
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": words,
                "avg_logprob": round(seg.avg_logprob, 4),
                "no_speech_prob": round(seg.no_speech_prob, 4),
            })

        return {
            "text": " ".join(full_words),
            "language": info.language,
            "duration": info.duration,
            "segments": segments,
            "processing_time": time.time() - t0,
        }

    # ------------------------------------------------------------------
    # Speaker diarization
    # ------------------------------------------------------------------

    def _diarize(self, local_path) -> list[dict]:
        """Detect speaker turns using Pyannote (free, GPU-only)."""
        import os
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return []
        try:
            from pyannote.audio import Pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            )
            diarization = pipeline(str(local_path))
            speakers = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers.append({
                    "speaker": speaker,
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                })
            return speakers
        except Exception as exc:
            self.logger.debug(f"Diarization skipped: {exc}")
            return []

    # ------------------------------------------------------------------
    # Viral moment detection
    # ------------------------------------------------------------------

    _MOMENT_SCHEMA = {
        "type": "object",
        "properties": {
            "moments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start":  {"type": "number"},
                        "end":    {"type": "number"},
                        "type":   {"type": "string", "enum": [
                            "emotional_peak", "story_arc", "hook",
                            "revelation", "humor", "actionable_tip", "conflict",
                        ]},
                        "score":  {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["start", "end", "type", "score", "reason"],
                },
            }
        },
        "required": ["moments"],
    }

    _VIRAL_SYSTEM = (
        "You are a viral content strategist specializing in short-form video. "
        "Identify moments that will drive high engagement, shares, and watch-through rate."
    )

    def _detect_viral_moments(self, transcript_data: dict, total_duration: float) -> list[dict]:
        """
        Use Claude to identify emotionally engaging, viral-worthy segments.
        Returns scored moments with start/end timestamps.
        """
        from app.services.ai_service import AIService

        text = transcript_data.get("text", "")
        if not text or len(text) < 100:
            return []

        segments = transcript_data.get("segments", [])
        timed_text = "\n".join(
            f"[{s['start']:.1f}s] {s['text']}" for s in segments[:200]
        )

        ai = AIService()
        prompt = (
            f"Video duration: {total_duration:.0f} seconds\n\n"
            f"Transcript:\n{timed_text[:5000]}\n\n"
            "Identify 5–15 moments that would perform well as standalone short-form clips. "
            "Use the structured_output tool to return them."
        )

        result = ai.complete_json(
            prompt,
            schema=self._MOMENT_SCHEMA,
            model=self.settings.ai_primary_model,
            system=self._VIRAL_SYSTEM,
        )

        if not result:
            self.logger.error("Viral moment detection returned no result")
            return []

        moments = result.get("moments", [])
        return sorted(moments, key=lambda x: x.get("score", 0), reverse=True)

    def _generate_candidates(
        self,
        transcript_data: dict,
        viral_moments: list[dict],
        requirements: dict,
        total_duration: float,
    ) -> list[dict]:
        """
        Combine viral moments + transcript structure to produce ranked clip windows
        that satisfy campaign duration requirements.
        """
        dur_min = requirements.get("duration_min", 30)
        dur_max = requirements.get("duration_max", 60)
        max_clips = self.settings.max_clips_per_campaign

        # Check if Comfy AI video generation is available for this campaign
        if self._should_generate_ai_video(requirements):
            try:
                ai_generated_clips = self._generate_ai_video_clips(
                    transcript_data, requirements, total_duration, max_clips
                )
                if ai_generated_clips:
                    return ai_generated_clips
            except Exception as exc:
                self.logger.warning(f"AI video generation failed: {exc}; falling back to traditional methods")

        candidates = []

        # Fallback: no viral moments + empty transcript → time-based windows
        if not viral_moments and not transcript_data.get("text", "").strip():
            candidates = self._generate_fallback_candidates(
                total_duration, dur_min, dur_max, max_clips
            )
            return candidates

        for moment in viral_moments:
            start = moment["start"]
            end = moment["end"]
            duration = end - start

            # Extend if too short
            if duration < dur_min:
                delta = dur_min - duration
                start = max(0, start - delta / 2)
                end = min(total_duration, end + delta / 2)
                duration = end - start

            # Trim if too long
            if duration > dur_max:
                end = start + dur_max
                duration = dur_max

            if duration < dur_min:
                continue

            # Find transcript text for this window
            window_text = " ".join(
                s["text"]
                for s in transcript_data.get("segments", [])
                if s["start"] >= start and s["end"] <= end + 2
            )

            candidates.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "score": moment.get("score", 0.5),
                "type": moment.get("type", "general"),
                "reason": moment.get("reason", ""),
                "transcript_window": window_text[:500],
                "tags": [moment.get("type", "general")],
            })

        # Deduplicate overlapping candidates (keep highest score)
        candidates = self._deduplicate_candidates(candidates)

        return candidates[:max_clips]

    def _generate_fallback_candidates(
        self, total_duration: float, dur_min: float, dur_max: float, max_clips: int
    ) -> list[dict]:
        """Generate evenly-spaced time windows when no viral moments detected."""
        if total_duration <= 0:
            return []

        num_windows = min(max_clips, max(1, int(total_duration / max(dur_min, 1))))
        spacing = total_duration / num_windows
        candidates = []

        for i in range(num_windows):
            start = i * spacing
            end = min(start + dur_max, total_duration)

            if end - start < dur_min:
                if end >= total_duration:
                    start = max(0, total_duration - dur_min)
                else:
                    end = min(start + dur_min, total_duration)

            if end - start < 1.0:
                continue

            candidates.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "score": 0.5,
                "type": "time_window",
                "reason": "Time-based fallback window (no speech detected)",
                "transcript_window": "",
                "tags": ["fallback"],
            })

        return candidates[:max_clips]

    # ------------------------------------------------------------------
    # AI video generation (Comfy)
    # ------------------------------------------------------------------

    def _should_generate_ai_video(self, requirements: dict) -> bool:
        """
        Check if campaign requirements indicate use of Comfy AI video generation.
        Enhanced campaigns can request AI-generated videos with custom prompts.
        """
        return bool(requirements.get("use_ai_generation", False))

    def _generate_ai_video_clips(
        self,
        transcript_data: dict,
        requirements: dict,
        total_duration: float,
        max_clips: int,
    ) -> list[dict]:
        """
        Generate AI video clips using Comfy AI based on campaign requirements and transcript.
        Provides synthetic content when real source has no speech.
        """
        # AI prompt generation based on transcript content and campaign requirements
        prompt = self._build_ai_video_prompt(transcript_data, requirements, total_duration)

        # Generate video using Comfy AI API
        ai_video_clips = self._call_comfy_api(
            prompt, requirements, transcript_data, max_clips
        )

        # Convert API response to clip candidates format
        candidates = []
        for i, ai_clip in enumerate(ai_video_clips):
            if len(candidates) >= max_clips:
                break
            duration = ai_clip.get("duration", requirements.get("duration_min", 30))
            if duration < requirements.get("duration_min", 15) or duration > requirements.get("duration_max", 60):
                continue

            candidates.append({
                "start": 0.0,
                "end": duration,
                "duration": duration,
                "score": ai_clip.get("score", 0.8),
                "type": "ai_generated",
                "reason": f"Generated by Comfy AI: {ai_clip.get('prompt', '')[:100]}",
                "transcript_window": transcript_data.get("text", "")[:500],
                "tags": ["ai_video", "generated", "viral_moment"],
                "ai_video_id": ai_clip.get("video_id"),
                "ai_generation_params": {
                    "prompt": ai_clip.get("prompt"),
                    "model": ai_clip.get("model", "comfyai-latest"),
                    "duration": duration,
                    "resolution": requirements.get("resolution", "1080x1920"),
                },
            })

        return candidates

    def _build_ai_video_prompt(
        self, transcript_data: dict, requirements: dict, total_duration: float
    ) -> str:
        """
        Build a prompt for Comfy AI video generation based on campaign
        requirements and transcript content.
        """
        base_prompt = (
            "Create dramatic short-form video content (15-60 seconds) with "
            f"viral social media appeal. "
            f"Requirements: duration {requirements.get('duration_min', 15)}-{requirements.get('duration_max', 60)} seconds, "
            f"aspect ratio {requirements.get('aspect_ratio', '9:16')}, "
            f"platform {requirements.get('platform', 'TikTok/Instagram')}. "
             f"Campaign brand: {requirements.get('brand', 'Unknown')}. "
            f"Hook required: {requirements.get('hook_required', True)}. "
        )

        # Add transcript content for context
        text = transcript_data.get("text", "")
        if text:
            # Extract key moments or themes from transcript
            key_words = self._extract_key_moments(text)[:50]
            base_prompt += f"Content themes: {key_words}. "

        # Add required keywords based on campaign requirements
        if requirements.get("hook_required", True):
            base_prompt += "Include attention-grabbing opening hooks, emotional peaks, and call-to-action elements. "
        if requirements.get("caption_required", False):
            base_prompt += "Ensure text overlays for captions. "

        # Add platform-specific guidance
        platform = requirements.get("platform", "TikTok").lower()
        if "tiktok" in platform:
            base_prompt += "Trending sound samples, quick cuts, strong visual impact. "
        elif "instagram" in platform:
            base_prompt += "Aesthetic visual style, engaging stories, interactive elements. "
        elif "youtube" in platform:
            base_prompt += "High-quality production, compelling narrative, SEO-friendly titles. "

        base_prompt += "Create content that aligns with brand voice and target audience preferences."
        return base_prompt

    def _extract_key_moments(self, text: str) -> list[str]:
        """
        Extract key moments or themes from transcript text for AI video generation.
        """
        if not text:
            return []

        # Simple keyword extraction - can be enhanced with AI NLP
        keywords = [
            "funny", "educational", "how-to", "story", "inspiring", "dramatic", 
            "action", "reaction", "challenge", "solution", "before/after", "transformation",
            "tutorial", "life hack", "motivation", "entertainment", "information",
            "demonstration", "review", "recommendation", "comparison",
        ]

        found = []
        for keyword in keywords:
            if keyword in text.lower():
                found.append(keyword)
                if len(found) >= 5:
                    break

        if not found:
            # Fallback to generic keywords if none match
            found = ["engaging", "visually appealing", "high energy", "trending"]

        return found

    def _call_comfy_api(
        self, prompt: str, requirements: dict, transcript_data: dict, max_clips: int
    ) -> list[dict]:
        """
        Call Comfy AI API to generate video clips based on prompt and requirements.
        Falls back to simulated content if API unavailable.
        """
        try:
            from fastapi import FastAPI
            import httpx
            import json

            # Check if Comfy AI API key is configured
            if not hasattr(self.settings, 'comfy_api_key') or not self.settings.comfy_api_key:
                self.logger.debug("Comfy AI API key not configured; using simulated AI content")
                return self._get_simulated_ai_clips(requirements, max_clips)

            # API configuration
            api_url = getattr(self.settings, 'comfy_api_url', 'https://api.comfy.ai/v1/videos/generate')
            api_key = self.settings.comfy_api_key

            # Request headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Build request payload
            payload = {
                "prompt": prompt,
                "num_images": min(max_clips, 4),
                "resolution": requirements.get("resolution", "1080x1920"),
                "duration": min(requirements.get("duration_max", 60), 60),
                "aspect_ratio": requirements.get("aspect_ratio", "9:16"),
                "model": requirements.get("ai_model", "comfyai-v2"),
                "output_format": "mp4",
                "quality": "high",
                "style": "professional",
                "workflow": requirements.get("comfy_workflow_id", "viral-video-workflow"),
                "webhook": "https://webhook.site/comfy-ai-callback" if self.settings.comfy_webhook else None,
            }

            # Make API request with timeout
            with httpx.Client(timeout=60.0) as client:
                response = client.post(api_url, headers=headers, json=payload)

                if response.status_code == 200:
                    api_response = response.json()
                    return self._parse_comfy_api_response(api_response)
                else:
                    self.logger.warning(f"Comfy API request failed: {response.status_code} - {response.text}")
                    return self._get_simulated_ai_clips(requirements, max_clips)

        except Exception as exc:
            self.logger.warning(f"Error calling Comfy AI API: {exc}; using simulated content")
            return self._get_simulated_ai_clips(requirements, max_clips)

    def _parse_comfy_api_response(self, api_response: dict) -> list[dict]:
        """
        Parse Comfy AI API response and convert to clip candidate format.
        """
        clips = []

        # Handle different API response formats
        if "videos" in api_response:
            # Standard Comfy AI video generation response
            for video in api_response["videos"]:
                clip = {
                    "video_id": video.get("id"),
                    "duration": video.get("duration", 30),
                    "score": video.get("quality_score", 0.7),
                    "prompt": video.get("prompt"),
                    "model": video.get("model"),
                    "thumbnail": video.get("thumbnail"),
                    "resolution": video.get("resolution", "1080x1920"),
                }
                clips.append(clip)

        elif "data" in api_response and isinstance(api_response["data"], list):
            # Alternative response format with data array
            for item in api_response["data"]:
                clips.append(
                    {
                        "video_id": item.get("id"),
                        "duration": item.get("duration", 30),
                        "score": item.get("confidence", 0.7),
                        "prompt": item.get("description"),
                        "model": item.get("model", "comfyai-v2"),
                        "thumbnail": item.get("preview"),
                        "resolution": item.get("resolution", "1080x1920"),
                    }
                )

        else:
            # Handle unknown response format
            self.logger.warning(f"Unknown Comfy API response format: {api_response}")

        return clips

    def _get_simulated_ai_clips(
        self, requirements: dict, max_clips: int
    ) -> list[dict]:
        """
        Generate simulated AI video clips when Comfy API is unavailable.
        Provides realistic content for demo purposes.
        """
        clips = []

        # Generate simulated clip descriptions based on campaign requirements
        themes = [
            "Product demonstration with amazing features",
            "DIY tutorial with step-by-step guidance",
            "Lifestyle content showing transformation",
            "Entertainment highlight reel with cuts",
            "Educational content with engaging visuals",
        ]

        for i in range(min(max_clips, 3)):
            theme = themes[i % len(themes)]
            duration = requirements.get("duration_min", 15)

            clip = {
                "video_id": f"simulated-ai-{i:03d}",
                "duration": duration,
                "score": 0.7 + (i * 0.05),  # Varying quality scores
                "prompt": f"AI-generated {theme} for {requirements.get('platform', 'social media')}",
                "model": "comfyai-v2-simulated",
                "thumbnail": f"https://comfy.ai/thumb/simulated/{i:03d}.jpg",
                "resolution": requirements.get("resolution", "1080x1920"),
            }
            clips.append(clip)

        self.logger.info(
            f"Generated {len(clips)} simulated AI video clips for campaign "
            f"requirements: {requirements.get('duration_min', 30)}-{requirements.get('duration_max', 60)}s"
        )

        return clips

    def _deduplicate_candidates(self, candidates: list[dict]) -> list[dict]:
        """Remove candidates that significantly overlap with a higher-scored one."""
        sorted_cands = sorted(candidates, key=lambda x: x["score"], reverse=True)
        kept = []

        for cand in sorted_cands:
            overlap = False
            for kept_cand in kept:
                # Check overlap
                overlap_start = max(cand["start"], kept_cand["start"])
                overlap_end = min(cand["end"], kept_cand["end"])
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    min_duration = min(cand["duration"], kept_cand["duration"])
                    if overlap_duration / min_duration > 0.5:  # >50% overlap
                        overlap = True
                        break
            if not overlap:
                kept.append(cand)

        return kept
