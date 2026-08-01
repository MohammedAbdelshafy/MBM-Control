"""
VideoProcessor — utility class for all FFmpeg operations.
Agents delegate video processing here. Not a Celery task — called synchronously.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("services.video")


class VideoProcessor:

    @staticmethod
    def probe(path: str | Path) -> dict:
        """Full ffprobe output as a dict."""
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        return json.loads(result.stdout)

    @staticmethod
    def get_duration(path: str | Path) -> float:
        data = VideoProcessor.probe(path)
        return float(data.get("format", {}).get("duration", 0))

    @staticmethod
    def get_dimensions(path: str | Path) -> tuple[int, int]:
        data = VideoProcessor.probe(path)
        video = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), {}
        )
        return video.get("width", 0), video.get("height", 0)

    @staticmethod
    def extract_audio(video_path: str | Path, audio_path: str | Path) -> bool:
        """Extract audio track to WAV for transcription."""
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            str(audio_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def create_thumbnail(video_path: str | Path, image_path: str | Path, timestamp: float = 0.0) -> bool:
        """Extract a single frame as a JPEG thumbnail."""
        cmd = [
            settings.ffmpeg_path, "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(image_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def concat_clips(clip_paths: list[Path], output_path: Path, tmpdir: str) -> bool:
        """Concatenate multiple clips in sequence."""
        list_file = Path(tmpdir) / "concat_list.txt"
        with open(list_file, "w") as f:
            for p in clip_paths:
                f.write(f"file '{str(p)}'\n")
        cmd = [
            settings.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def crossfade_clips(
        clip_paths: list[Path], output_path: Path, tmpdir: str,
        transition: str = "fade", duration: float = 0.5
    ) -> bool:
        """Stitch multiple clips with crossfade transitions."""
        if len(clip_paths) < 2:
            return VideoProcessor.concat_clips(clip_paths, output_path, tmpdir)

        if len(clip_paths) == 2:
            overlap = duration
            clip_dur = VideoProcessor.get_duration(clip_paths[0])
            offset = max(0, clip_dur - overlap)
            cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(clip_paths[0]),
                "-i", str(clip_paths[1]),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition={transition}:duration={overlap}:offset={offset}[v];"
                f"[0:a][1:a]acrossfade=d={overlap}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac",
                str(output_path),
            ]
            return VideoProcessor._run(cmd)

        current = clip_paths[0]
        for i in range(1, len(clip_paths)):
            next_clip = clip_paths[i]
            temp_path = Path(tmpdir) / f"xfade_{i}.mp4"
            clip_dur = VideoProcessor.get_duration(current)
            offset = max(0, clip_dur - duration)
            cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(current),
                "-i", str(next_clip),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset}[v];"
                f"[0:a][1:a]acrossfade=d={duration}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac",
                str(temp_path),
            ]
            if not VideoProcessor._run(cmd):
                return False
            current = temp_path

        current.rename(output_path)
        return True

    @staticmethod
    def add_fade(
        src: Path, dst: Path,
        fade_in: float = 0.3,
        fade_out: float = 0.3,
        duration: Optional[float] = None,
    ) -> bool:
        """Add fade in/out effects."""
        if duration is None:
            duration = VideoProcessor.get_duration(src)
        fade_out_start = max(0, duration - fade_out)
        vf = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
        af = f"afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}"
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def add_watermark(
        src: Path, dst: Path,
        watermark_path: Path,
        position: str = "bottom_right",
    ) -> bool:
        positions = {
            "bottom_right": "W-w-10:H-h-10",
            "bottom_left": "10:H-h-10",
            "top_right": "W-w-10:10",
            "top_left": "10:10",
        }
        overlay = positions.get(position, positions["bottom_right"])
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-i", str(watermark_path),
            "-filter_complex", f"overlay={overlay}",
            "-c:a", "copy",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def compress(src: Path, dst: Path, target_bitrate_kbps: int = 2000) -> bool:
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-c:v", "libx264",
            "-b:v", f"{target_bitrate_kbps}k",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    # ------------------------------------------------------------------
    # Enhancement (FFmpeg filter pipeline)
    # ------------------------------------------------------------------

    @staticmethod
    def enhance_video(
        src: Path, dst: Path,
        sharpen: bool = True,
        sharpen_luma_strength: float = 5.0,
        sharpen_luma_radius: float = 5.0,
        sharpen_luma_threshold: float = 0.8,
        sharpen_chroma_strength: float = 3.0,
        sharpen_chroma_radius: float = 3.0,
        sharpen_chroma_threshold: float = 0.4,
        color_grade: bool = True,
        contrast: float = 1.05,
        brightness: float = 0.02,
        saturation: float = 1.1,
        denoise: bool = True,
        denoise_spatial_luma: float = 1.5,
        denoise_spatial_chroma: float = 1.5,
        denoise_temp_luma: float = 3.0,
        denoise_temp_chroma: float = 3.0,
        dehaze: bool = False,
        dehaze_strength: float = 0.7,
        film_grain: bool = False,
        film_grain_strength: int = 25,
        film_grain_size: int = 3,
        deband: bool = False,
        deband_strength: float = 0.02,
        crf: int = 18,
        preset: str = "slow",
        fade_in: float = 0,
        fade_out: float = 0,
    ) -> bool:
        """Apply quality enhancements to a video:
        1. Dehaze (optional) — contrast stretch + histeq
        2. Denoise (optional) — hqdn3d
        3. Unsharp mask sharpen (optional)
        4. Deband (optional) — remove banding
        5. Color levels/contrast grade (optional)
        6. Film grain (optional) — cinematic texture
        7. High-quality re-encode with CRF
        8. Fade in/out (optional)
        """
        filter_parts = []
        duration = VideoProcessor.get_duration(src)

        # Order matters — dehaze first (cleaner input for other filters)
        if dehaze:
            opacity = max(0.0, min(1.0, dehaze_strength))
            filter_parts.append(f"histeq=strength={opacity}")

        if denoise:
            filter_parts.append(
                f"hqdn3d={denoise_spatial_luma}:{denoise_spatial_chroma}:"
                f"{denoise_temp_luma}:{denoise_temp_chroma}"
            )

        if sharpen:
            filter_parts.append(
                f"unsharp={sharpen_luma_radius}:{sharpen_luma_strength}:{sharpen_luma_threshold}:"
                f"{sharpen_chroma_radius}:{sharpen_chroma_strength}:{sharpen_chroma_threshold}"
            )

        if deband:
            bd = deband_strength
            filter_parts.append(
                f"deband=1thr={bd}:2thr={bd}:3thr={bd}:4thr={bd}"
                f":blur=16:range=15:direction=3:dither=fs:plane=7"
            )

        if color_grade:
            filter_parts.append(
                f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation}"
            )

        if film_grain:
            filter_parts.append(
                f"noise=c0s={film_grain_strength}:c0f={film_grain_size}"
                f":allf=t+u:allst=8"
            )

        if fade_in > 0:
            filter_parts.append(f"fade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            fade_out_start = max(0, duration - fade_out)
            filter_parts.append(f"fade=t=out:st={fade_out_start}:d={fade_out}")

        if not filter_parts:
            return False

        vf = ",".join(filter_parts)

        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def real_esrgan_upscale(
        src: Path, dst: Path,
        model: str = "realesrgan-x4plus",
        scale: int = 2,
        crf: int = 18,
        preset: str = "slow",
        real_esrgan_bin: str = "realesrgan-ncnn-vulkan",
    ) -> bool:
        """
        Upscale video using Real-ESRGAN (ncnn-vulkan).
        Extracts frames, upscales each with Real-ESRGAN, re-encodes.
        Falls back to lanczos resize if Real-ESRGAN is unavailable.
        """
        import subprocess as _subprocess
        import tempfile
        import shutil

        # Check if Real-ESRGAN binary exists
        if not shutil.which(real_esrgan_bin) and not Path(real_esrgan_bin).exists():
            logger.warning("Real-ESRGAN binary not found, falling back to lanczos upscale")
            new_w = None
            new_h = None
            probe = VideoProcessor.probe(src)
            video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
            w = video.get("width", 0)
            h = video.get("height", 0)
            if w and h:
                new_w = w * scale
                new_h = h * scale
            if new_w and new_h:
                cmd = [
                    settings.ffmpeg_path, "-y",
                    "-i", str(src),
                    "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
                    "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(dst),
                ]
                return VideoProcessor._run(cmd)
            return False

        with tempfile.TemporaryDirectory(prefix="esrgan_") as tmpdir:
            frames_dir = Path(tmpdir) / "frames"
            upscaled_dir = Path(tmpdir) / "upscaled"
            frames_dir.mkdir()
            upscaled_dir.mkdir()

            # Extract frames
            extract_cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(src),
                "-q:v", "2",
                str(frames_dir / "frame_%08d.png"),
            ]
            if not VideoProcessor._run(extract_cmd):
                return False

            frame_files = sorted(frames_dir.glob("*.png"))
            if not frame_files:
                return False

            # Upscale each frame with Real-ESRGAN
            for i, frame in enumerate(frame_files):
                out_path = upscaled_dir / frame.name
                esrgan_cmd = [
                    real_esrgan_bin,
                    "-i", str(frame),
                    "-o", str(out_path),
                    "-n", model,
                    "-s", str(scale),
                ]
                try:
                    _subprocess.run(esrgan_cmd, capture_output=True, text=True, timeout=120)
                except Exception as exc:
                    logger.warning(f"Real-ESRGAN failed on frame {i}: {exc}")
                    shutil.copy2(frame, out_path)
                if (i + 1) % 10 == 0:
                    logger.info(f"Upscaled {i + 1}/{len(frame_files)} frames")

            # Re-encode frames back to video
            reencode_cmd = [
                settings.ffmpeg_path, "-y",
                "-framerate", str(VideoProcessor._get_fps(src)),
                "-i", str(upscaled_dir / "frame_%08d.png"),
                "-i", str(src),
                "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-movflags", "+faststart",
                str(dst),
            ]
            return VideoProcessor._run(reencode_cmd)

    @staticmethod
    def _get_fps(path: Path) -> float:
        try:
            data = VideoProcessor.probe(path)
            video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
            fps_str = video.get("r_frame_rate", "30/1")
            n, d = fps_str.split("/") if "/" in fps_str else (fps_str, "1")
            return float(n) / float(d) if float(d) else 30.0
        except Exception:
            return 30.0

    # ------------------------------------------------------------------
    # Advanced Enhancement Filters
    # ------------------------------------------------------------------

    @staticmethod
    def dehaze_video(
        src: Path, dst: Path,
        strength: float = 0.7,
        contrast: float = 1.15,
        brightness: float = 0.05,
        saturation: float = 1.2,
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Remove haze/fog using contrast stretching + saturation boost + adaptive histogram eq.
        Simulates dehaze by:
          1. Ahequalize CLAHE-style via histeq
          2. Contrast/saturation boost
          3. Unsharp for detail recovery
        """
        # Blend histeq with original based on strength
        opacity = max(0.0, min(1.0, strength))
        vf = (
            f"histeq=strength={opacity},"
            f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation},"
            f"unsharp=3:3:0.5:3:3:0.0"
        )
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def apply_lut(
        src: Path, dst: Path,
        lut_file: Optional[Path] = None,
        lut_intensity: float = 1.0,
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Apply a 3D LUT (.cube file) for color grading.
        If no LUT file provided, applies a built-in cinematic warm tone via curves.
        lut_intensity: 0.0 = no effect, 1.0 = full LUT.
        """
        if lut_file and lut_file.exists():
            filter_str = f"lut3d='{str(lut_file).replace(chr(39), chr(39)+chr(39))}'"
            if lut_intensity < 1.0:
                # Blend original with LUT-processed
                filter_str = (
                    f"[0:v]split[main][lut];"
                    f"[lut]{filter_str}[graded];"
                    f"[main][graded]blend=all_mode=normal:"
                    f"all_opacity={lut_intensity}[v]"
                )
                cmd = [
                    settings.ffmpeg_path, "-y",
                    "-i", str(src),
                    "-filter_complex", filter_str,
                    "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(dst),
                ]
            else:
                cmd = [
                    settings.ffmpeg_path, "-y",
                    "-i", str(src),
                    "-vf", filter_str,
                    "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(dst),
                ]
        else:
            # Built-in cinematic warm grade via curves
            vf = (
                "curves=r='0/0 0.25/0.28 0.5/0.55 0.75/0.78 1/1':"
                "g='0/0 0.25/0.25 0.5/0.52 0.75/0.76 1/0.98':"
                "b='0/0.02 0.25/0.22 0.5/0.47 0.75/0.72 1/0.95',"
                f"eq=contrast=1.08:saturation=1.15"
            )
            cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(src),
                "-vf", vf,
                "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(dst),
            ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def add_film_grain(
        src: Path, dst: Path,
        grain_strength: int = 25,
        grain_size: int = 3,
        temporal_strength: int = 8,
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Add cinematic film grain using FFmpeg's noise filter.
        grain_strength: 0-100, controls grain intensity.
        grain_size: 1-3, grain颗粒大小.
        temporal_strength: 0-100, temporal variation of grain pattern.
        """
        vf = (
            f"noise=c0s={grain_strength}:c0f={grain_size}"
            f":allf=t+u:allst={temporal_strength}"
        )
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def tone_map_hdr(
        src: Path, dst: Path,
        tonemap_mode: str = "hable",
        target_colorspace: str = "bt709",
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Tone-map HDR/HLG content to SDR using FFmpeg tonemap filter.
        tonemap_mode: hable, reinhard, mobius, bt2390, bt2390_ocr.
        Converts from PQ/HLG to bt709 SDR for platform compatibility.
        """
        vf = (
            f"zscale=t=linear:npl=100,format=gbrpf32le,"
            f"tonemap={tonemap_mode},"
            f"zospace=t={target_colorspace}:m=bt709:range=pc"
        )
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_trc", "bt709", "-color_primaries", "bt709",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def interpolate_frames(
        src: Path, dst: Path,
        target_fps: Optional[float] = None,
        interp_mode: str = "mci",
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Interpolate frames to higher FPS using motion-compensated interpolation.
        Useful for creating smoother slow-motion or upsampling 24/30fps to 60fps.
        interp_mode: mci (motion-compensated), blend (simple blend).
        If target_fps is None, doubles the current FPS.
        """
        src_fps = VideoProcessor._get_fps(src)
        if target_fps is None:
            target_fps = src_fps * 2

        if interp_mode == "mci":
            vf = (
                f"minterpolate=fps={target_fps}:mi_mode=mci"
                f":mc_mode=aobmc:me_mode=bidir:vsbmc=1"
            )
        else:
            vf = f"minterpolate=fps={target_fps}:mi_mode=blend"

        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def deband_video(
        src: Path, dst: Path,
        band_detect: float = 0.02,
        blur: int = 16,
        range: int = 15,
        direction: int = 3,
        crf: int = 18,
        preset: str = "slow",
    ) -> bool:
        """Remove compression banding artifacts using FFmpeg deband filter.
        Useful for heavily compressed or color-graded footage.
        band_detect: detection threshold (lower = stronger debanding).
        blur: blur radius for detection.
        range: max pixel difference for debanding.
        """
        vf = (
            f"deband=1thr={band_detect}:2thr={band_detect}"
            f":3thr={band_detect}:4thr={band_detect}"
            f":blur={blur}:range={range}:direction={direction}"
            f":dither=fs:plane=7"
        )
        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
        return VideoProcessor._run(cmd)

    # ------------------------------------------------------------------
    # Voice-over & TTS
    # ------------------------------------------------------------------

    @staticmethod
    async def generate_voiceover(
        script: str,
        output_path: Path,
        voice: str = "en-US-JennyNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> bool:
        """Generate TTS voiceover audio using edge-tts."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                script,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            await communicate.save(str(output_path))
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception as exc:
            logger.error(f"Voiceover generation failed: {exc}")
            return False

    @staticmethod
    def generate_voiceover_sync(
        script: str,
        output_path: Path,
        voice: str = "en-US-JennyNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> bool:
        """Synchronous wrapper for generate_voiceover."""
        import asyncio
        try:
            asyncio.run(VideoProcessor.generate_voiceover(script, output_path, voice, rate, pitch))
            return True
        except Exception as exc:
            logger.error(f"Voiceover sync failed: {exc}")
            return False

    @staticmethod
    def mix_voiceover(
        video_path: Path,
        voiceover_path: Path,
        output_path: Path,
        original_volume: float = 0.15,
        voiceover_volume: float = 1.0,
    ) -> bool:
        """
        Mix voiceover audio with original video audio (ducking original).
        original_volume: how much to reduce original audio (0.0-1.0)
        voiceover_volume: voiceover track volume (0.0-1.0)
        """
        has_audio = VideoProcessor.has_audio_stream(str(video_path))
        if not has_audio:
            # Source has no audio track (e.g. silent demo). Just add the
            # voiceover as the sole audio stream.
            cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(video_path),
                "-i", str(voiceover_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path),
            ]
            return VideoProcessor._run(cmd)

        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-i", str(voiceover_path),
            "-filter_complex",
            f"[0:a]volume={original_volume}[orig];"
            f"[1:a]volume={voiceover_volume}[vo];"
            f"[orig][vo]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def add_background_music(
        video_path: Path,
        music_path: Path,
        output_path: Path,
        music_volume: float = 0.1,
    ) -> bool:
        """Overlay background music on video at reduced volume."""
        has_audio = VideoProcessor.has_audio_stream(str(video_path))
        if not has_audio:
            cmd = [
                settings.ffmpeg_path, "-y",
                "-i", str(video_path),
                "-i", str(music_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path),
            ]
            return VideoProcessor._run(cmd)

        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={music_volume}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def add_image_overlay(
        video_path: Path,
        image_path: Path,
        output_path: Path,
        position: str = "center",
        scale: Optional[str] = None,
    ) -> bool:
        """Overlay an image (logo, B-roll overlay) on the video.
        position: center, bottom_right, bottom_left, top_right, top_left
        scale: optional e.g. "640:360"
        """
        positions = {
            "center": "(W-w)/2:(H-h)/2",
            "bottom_right": "W-w-10:H-h-10",
            "bottom_left": "10:H-h-10",
            "top_right": "W-w-10:10",
            "top_left": "10:10",
        }
        overlay_pos = positions.get(position, positions["center"])

        filter_parts = []
        if scale:
            filter_parts.append(f"scale={scale}")
        filter_parts.append(f"overlay={overlay_pos}")
        filter_chain = ",".join(filter_parts)

        cmd = [
            settings.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-i", str(image_path),
            "-filter_complex", filter_chain,
            "-c:a", "copy",
            str(output_path),
        ]
        return VideoProcessor._run(cmd)

    @staticmethod
    def generate_srt_from_transcript(
        segments: list[dict],
        output_path: Path,
        offset_seconds: float = 0.0,
    ) -> str:
        """Generate an SRT subtitle file from transcript segments.
        Returns the SRT content as a string, and writes the file.
        """
        lines = []
        for i, seg in enumerate(segments, 1):
            start = max(0, seg.get("start", 0) - offset_seconds)
            end = max(0, seg.get("end", 0) - offset_seconds)
            text = seg.get("text", "").strip()
            if not text:
                continue
            lines.append(str(i))
            lines.append(f"{VideoProcessor._ts(start)} --> {VideoProcessor._ts(end)}")
            lines.append(text)
            lines.append("")
        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return content

    @staticmethod
    def _ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    @staticmethod
    def _ffprobe_exe() -> str:
        """Resolve ffprobe from the configured ffmpeg path (same dir/bin)."""
        try:
            exe = settings.ffmpeg_path or "ffmpeg"
            if exe.lower().endswith("ffmpeg" + ".exe") or exe.lower().endswith("ffmpeg"):
                base = exe[:-len("ffmpeg")]
                probe = base + "ffprobe" + (".exe" if exe.lower().endswith(".exe") else "")
                import shutil
                if shutil.which(probe) or os.path.exists(probe):
                    return probe
            import shutil
            if shutil.which("ffprobe"):
                return "ffprobe"
        except Exception:
            pass
        return "ffprobe"

    @staticmethod
    def has_audio_stream(path: str) -> bool:
        """Return True if the video file contains an audio stream."""
        try:
            probe = [
                VideoProcessor._ffprobe_exe(), "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0", str(path),
            ]
            res = subprocess.run(probe, capture_output=True, text=True, timeout=60)
            return bool(res.stdout.strip())
        except Exception:
            return False

    @staticmethod
    def get_video_dimensions(path: str) -> tuple[int, int]:
        """Return (width, height) of the first video stream, or (0, 0)."""
        try:
            probe = [
                VideoProcessor._ffprobe_exe(), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0", str(path),
            ]
            res = subprocess.run(probe, capture_output=True, text=True, timeout=60)
            parts = res.stdout.strip().split(",")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except Exception:
            pass
        return 0, 0

    def _run(cmd: list, timeout: int = 600) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.warning(f"FFmpeg error: {result.stderr[-400:]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            return False
        except Exception as exc:
            logger.error(f"FFmpeg exception: {exc}")
            return False
