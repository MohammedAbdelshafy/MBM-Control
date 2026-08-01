import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("services.higgsfield")


class HiggsfieldService:

    @staticmethod
    def _run(args: list[str], timeout: int = 300) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["higgsfield", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                logger.error(f"higgsfield error: {result.stderr}")
                return {"success": False, "error": result.stderr}
            if result.stdout:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"success": True, "raw": result.stdout}
            return {"success": True}
        except FileNotFoundError:
            logger.warning("higgsfield CLI not found on PATH")
            return {"success": False, "error": "higgsfield CLI not installed"}
        except subprocess.TimeoutExpired:
            logger.error(f"higgsfield command timed out after {timeout}s")
            return {"success": False, "error": "timeout"}
        except Exception as exc:
            logger.error(f"higgsfield service error: {exc}")
            return {"success": False, "error": str(exc)}

    @classmethod
    def generate_voiceover(cls, text: str, output_path: Path, voice: str | None = None) -> bool:
        prompt = voice or text
        result = cls._run([
            "generate", "create", "seed_audio",
            "--prompt", prompt,
            "--wait", "--json",
        ])
        if result.get("success"):
            urls = cls._extract_media_urls(result)
            if urls:
                cls._download(urls[0], output_path)
                return output_path.exists()
        logger.warning("Higgsfield voiceover generation failed, falling back")
        return False

    @classmethod
    def generate_image(cls, prompt: str, output_path: Path, aspect_ratio: str = "16:9") -> bool:
        result = cls._run([
            "generate", "create", "gpt_image_2",
            "--prompt", prompt,
            "--aspect_ratio", aspect_ratio,
            "--wait", "--json",
        ])
        if result.get("success"):
            urls = cls._extract_media_urls(result)
            if urls:
                cls._download(urls[0], output_path)
                return output_path.exists()
        return False

    @classmethod
    def generate_thumbnail(cls, prompt: str, text_overlay: str, output_path: Path) -> bool:
        full_prompt = (
            f"YouTube thumbnail, bold text '{text_overlay}', high contrast, "
            f"click-through optimized. {prompt}"
        )
        return cls.generate_image(full_prompt, output_path, aspect_ratio="16:9")

    @classmethod
    def analyze_virality(cls, video_path: Path) -> dict[str, Any]:
        result = cls._run([
            "generate", "create", "brain_activity",
            "--video", str(video_path),
            "--wait", "--json",
        ], timeout=600)
        if result.get("success"):
            return {
                "success": True,
                "report": result.get("raw") or result,
                "job_data": result,
            }
        return {"success": False, "error": result.get("error", "unknown")}

    @staticmethod
    def _extract_media_urls(result: dict) -> list[str]:
        urls = []
        try:
            if isinstance(result, dict):
                for item in result.get("jobs", []):
                    for output in item.get("outputs", []):
                        url = output.get("url", "")
                        if url:
                            urls.append(url)
        except Exception:
            pass
        return urls

    @staticmethod
    def _download(url: str, output_path: Path) -> bool:
        try:
            import requests
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as exc:
            logger.error(f"Download failed: {exc}")
            return False
