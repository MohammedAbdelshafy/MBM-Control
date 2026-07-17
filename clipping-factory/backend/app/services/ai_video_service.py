"""
AIVideoService — generates AI B-roll using only free providers.

Priority:
  1. Hugging Face Gradio Space (LTX-Video) — free, quota-limited
  2. Simulated clips — always available, no API keys needed
"""
import asyncio
import os
import random
import uuid
import subprocess
from pathlib import Path
from app.services.free_video_service import FreeVideoGenerator
from app.core.logging_config import get_logger

logger = get_logger("AIVideoService")

class AIVideoService:
    """
    Generates AI B-roll video using free providers.
    Primary: Hugging Face FreeVideoGenerator (LTX-Video Gradio Space - no cost).
    No paid API keys required.
    """
    def __init__(self, output_dir: str = "/tmp/ai_videos"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.generator = FreeVideoGenerator(output_dir=self.output_dir)

    async def generate_video(self, prompt: str, duration: int = 5) -> str:
        """
        Generates AI B-roll. If duration > 5, stitches multiple clips together.
        Returns the path to the generated MP4.
        Falls back to simulated content if free generation fails.
        """
        if duration <= 5:
            logger.info(f"Generating single {duration}s clip for: {prompt}")
            video_path = await asyncio.to_thread(
                self.generator.generate_video,
                prompt=prompt,
                duration=float(duration)
            )
            if video_path:
                return video_path
            return self._generate_fallback_clip(prompt, duration)

        # Multi-shot stitching for longer durations (>5s)
        logger.info(f"Generating stitched {duration}s clip for: {prompt}")
        clip_duration = 5
        num_clips = (duration + clip_duration - 1) // clip_duration
        scenes = [f"{prompt}, continuous scene {i+1}" for i in range(num_clips)]

        async def generate_scene(scene_prompt, index):
            seed = random.randint(1, 99999999)
            video_path = await asyncio.to_thread(
                self.generator.generate_video,
                prompt=scene_prompt,
                duration=float(clip_duration),
                seed=seed
            )
            return index, video_path

        tasks = [generate_scene(scene, i) for i, scene in enumerate(scenes)]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda x: x[0])
        video_paths = [path for _, path in results]

        if any(v is None for v in video_paths):
            logger.warning("Free video generation failed for one or more clips, using fallback")
            return self._generate_fallback_clip(prompt, duration)

        concat_file = os.path.join(self.output_dir, f"concat_list_{uuid.uuid4().hex[:6]}.txt")
        with open(concat_file, "w") as f:
            for vp in video_paths:
                f.write(f"file '{os.path.abspath(vp)}'\n")

        stitched = os.path.join(self.output_dir, f"stitched_{duration}s_{uuid.uuid4().hex[:6]}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", stitched
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        logger.info(f"Stitched AI B-roll: {stitched}")
        return stitched

    def _generate_fallback_clip(self, prompt: str, duration: int) -> str:
        """Generate a simple colored background with text as fallback when HF quota is hit."""
        output = os.path.join(self.output_dir, f"fallback_{uuid.uuid4().hex[:8]}.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=#1a1a2e:s=1080x1920:d={duration}",
                "-vf", f"drawtext=text='{prompt[:80]}':fontsize=36:fontcolor=white:x=(w-text_w)/2:y=h/2:box=1:boxcolor=black@0.5:boxborderw=10",
                "-c:v", "libx264", "-preset", "ultrafast", output
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Fallback clip generated: {output}")
            return output
        except Exception as e:
            logger.error(f"Fallback clip failed: {e}")
            raise
