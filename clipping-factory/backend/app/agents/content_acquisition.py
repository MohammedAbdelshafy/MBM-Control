"""
ContentAcquisitionAgent — downloads source material from any supported provider.

Supported: YouTube, TikTok, Instagram (all via yt-dlp), Google Drive,
Dropbox, Direct URLs.
All downloads are verified with MD5 checksums, size-limited, and uploaded to MinIO.
Credentials for cloud providers stored in env / settings only.
"""
import hashlib
import os
import re as _re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent
from app.core.config import get_settings

SUPPORTED_DOMAINS = {
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "instagr.am",
    "drive.google.com", "dropbox.com", "dropboxusercontent.com",
}
MAX_FILE_SIZE_BYTES = 2 * 1024 ** 3  # 2 GB
DOWNLOAD_RETRIES = 3
DOWNLOAD_RETRY_DELAY_SECS = 5

settings = get_settings()


class ContentAcquisitionAgent(BaseAgent):
    name = "content_acquisition"

    def run(self, campaign_id: str) -> AgentResult:
        from app.models.campaign import Campaign, CampaignStatus
        from app.models.source_content import SourceContent

        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return AgentResult.fail(f"Campaign {campaign_id} not found")

        if not campaign.source_url:
            return AgentResult.fail("Campaign has no source URL")

        self.logger.info(f"Acquiring content for campaign {campaign_id}: {campaign.source_url}")

        if not self._is_supported_url(campaign.source_url):
            return AgentResult.fail(f"Unsupported URL: {campaign.source_url}")

        source_type = self._detect_source_type(campaign.source_url)
        campaign.source_type = source_type
        self.db.flush()

        # Create a source_content record
        source = SourceContent(
            campaign_id=campaign_id,
            source_url=campaign.source_url,
            source_type=source_type,
            status="downloading",
        )
        self.db.add(source)
        self.db.flush()

        # Download to temp dir with retries
        with tempfile.TemporaryDirectory(prefix="clip_acquire_") as tmpdir:
            local_path = None
            for attempt in range(1, DOWNLOAD_RETRIES + 1):
                try:
                    local_path = self._download(campaign.source_url, source_type, tmpdir)
                    break
                except Exception as exc:
                    self.logger.warning(f"Download attempt {attempt}/{DOWNLOAD_RETRIES} failed: {exc}")
                    if attempt < DOWNLOAD_RETRIES:
                        time.sleep(DOWNLOAD_RETRY_DELAY_SECS)
                    else:
                        source.status = "failed"
                        source.error_message = str(exc)
                        self.db.flush()
                        return AgentResult.fail(f"Download failed after {DOWNLOAD_RETRIES} attempts: {exc}")

            if not local_path or not local_path.exists():
                source.status = "failed"
                source.error_message = "Downloaded file not found"
                self.db.flush()
                return AgentResult.fail("File not found after download")

            file_size = local_path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                source.status = "failed"
                source.error_message = f"File too large: {file_size / (1024**3):.2f} GB (limit: {MAX_FILE_SIZE_BYTES / (1024**3):.1f} GB)"
                self.db.flush()
                return AgentResult.fail(f"File exceeds size limit ({file_size / (1024**3):.2f} GB)")

            # Verify and extract metadata
            checksum = self._md5(local_path)
            video_meta = self._probe_video(local_path)

            # Upload to MinIO
            storage_key = f"source/{campaign_id}/{local_path.name}"
            try:
                from app.core.storage import upload_file
                upload_file(
                    local_path,
                    settings.storage_bucket_source,
                    storage_key,
                    content_type="video/mp4",
                    metadata={"campaign_id": campaign_id, "source_type": source_type},
                )
            except Exception as exc:
                source.status = "failed"
                source.error_message = f"Upload failed: {exc}"
                self.db.flush()
                return AgentResult.fail(f"Storage upload failed: {exc}")

            # Update source record
            source.storage_bucket = settings.storage_bucket_source
            source.storage_key = storage_key
            source.file_size_bytes = local_path.stat().st_size
            source.checksum_md5 = checksum
            source.status = "ready"
            source.original_title = video_meta.get("title", "")
            source.duration_seconds = video_meta.get("duration")
            source.width = video_meta.get("width")
            source.height = video_meta.get("height")
            source.fps = video_meta.get("fps")
            source.codec = video_meta.get("codec")
            source.audio_codec = video_meta.get("audio_codec")
            source.extra_metadata = video_meta

            campaign.status = CampaignStatus.PROCESSING
            self.db.flush()

        self._audit("source_content", source.id, "acquired", metadata={"source_type": source_type})
        self.logger.info(
            f"Content acquired: {local_path.name} "
            f"({source.duration_seconds:.1f}s, {source.file_size_bytes // 1024 // 1024}MB)"
        )

        # Trigger transcription
        from app.workers.video_tasks import analyze_content
        analyze_content.apply_async(args=[source.id], queue="analysis")

        return AgentResult.ok({"source_content_id": source.id, "storage_key": storage_key})

    # ------------------------------------------------------------------
    # Source detection
    # ------------------------------------------------------------------

    def _is_supported_url(self, url: str) -> bool:
        """Check if URL is from a supported provider."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain = _re.sub(r"^www\.", "", domain)
        if domain in SUPPORTED_DOMAINS:
            return True
        # Check for direct video file extensions
        if url.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return True
        self.logger.warning(f"Unsupported URL domain: {domain}")
        return False

    def _detect_source_type(self, url: str) -> str:
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "instagram.com" in url_lower or "instagr.am" in url_lower:
            return "instagram"
        if "drive.google.com" in url_lower:
            return "gdrive"
        if "dropbox.com" in url_lower:
            return "dropbox"
        if url_lower.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return "direct"
        return "direct"

    # ------------------------------------------------------------------
    # Downloaders
    # ------------------------------------------------------------------

    def _download(self, url: str, source_type: str, tmpdir: str) -> Optional[Path]:
        dispatch = {
            "youtube": self._download_ytdlp,
            "tiktok": self._download_ytdlp,
            "instagram": self._download_ytdlp,
            "gdrive": self._download_gdrive,
            "dropbox": self._download_dropbox,
            "direct": self._download_direct,
        }
        fn = dispatch.get(source_type, self._download_direct)
        return fn(url, tmpdir)

    def _download_ytdlp(self, url: str, tmpdir: str) -> Path:
        """Generic yt-dlp downloader — handles YouTube, TikTok and Instagram."""
        import yt_dlp

        max_duration = self.settings.max_video_duration_seconds
        ydl_opts = {
            # mp4-first with a permissive fallback so short-form platforms
            # (TikTok/IG) that serve a single progressive stream still work.
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {max_duration}"),
            "socket_timeout": 60,
            "retries": 5,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            path = Path(filename)
            if not path.exists():
                # Try .mp4 fallback
                path = path.with_suffix(".mp4")
            return path

    def _download_gdrive(self, url: str, tmpdir: str) -> Path:
        """Download from Google Drive public link."""
        import re
        import requests

        # Extract file ID from various Google Drive URL formats
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if not match:
            match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if not match:
            raise ValueError(f"Cannot extract Google Drive file ID from URL: {url}")

        file_id = match.group(1)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

        session = requests.Session()
        response = session.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        # Handle the virus-scan warning page
        if "confirm=" not in download_url and "text/html" in response.headers.get("Content-Type", ""):
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith("download_warning"):
                    confirm_token = value
            if confirm_token:
                response = session.get(
                    f"{download_url}&confirm={confirm_token}", stream=True, timeout=60
                )

        out_path = Path(tmpdir) / f"{file_id}.mp4"
        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return out_path

    def _download_dropbox(self, url: str, tmpdir: str) -> Path:
        """Download from Dropbox shared link."""
        import requests

        # Convert shared link to direct download
        direct_url = url.replace("?dl=0", "?dl=1").replace("www.dropbox.com", "dl.dropboxusercontent.com")

        response = requests.get(direct_url, stream=True, timeout=60)
        response.raise_for_status()

        filename = "dropbox_source.mp4"
        content_disposition = response.headers.get("Content-Disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1].strip('"')

        out_path = Path(tmpdir) / filename
        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return out_path

    def _download_direct(self, url: str, tmpdir: str) -> Path:
        """Download a direct video URL."""
        import requests

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        filename = url.split("/")[-1].split("?")[0] or "source.mp4"
        out_path = Path(tmpdir) / filename

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return out_path

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _md5(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _probe_video(self, path: Path) -> dict:
        """Use ffprobe to extract video metadata."""
        import subprocess
        import json as _json

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams", "-show_format",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {}

            data = _json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

            fps = 30.0
            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) else 30.0

            return {
                "duration": float(fmt.get("duration", 0)),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": fps,
                "codec": video_stream.get("codec_name"),
                "audio_codec": audio_stream.get("codec_name"),
                "bit_rate": int(fmt.get("bit_rate", 0)),
                "title": fmt.get("tags", {}).get("title", ""),
            }
        except Exception as exc:
            self.logger.warning(f"ffprobe failed: {exc}")
            return {}
