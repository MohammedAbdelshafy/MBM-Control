"""
Full Production Cycle — Twists Revealed end-to-end execution.

DISCOVERY -> RESEARCH -> SOURCE ACQUISITION -> SCRIPT -> TTS -> VISUAL SEGMENTS
-> CAPTIONS -> FINAL RENDER -> VIDEO QA -> CREATIVE QA -> PACKAGE -> (PUBLISH -> VERIFY)

Invariants:
  NO_REAL_SOURCE -> NO_PRODUCTION_CLIP (SOURCE_BLOCKED, never demo substitution)
  QA below channel threshold -> REJECTED (thresholds never lowered)
  Publishing only with a REAL platform video ID; verification requires evidence.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .channel_profiles import get_profile
from .movie_discovery import discover_movies, MovieCandidate, MovieStatus
from .script_agent import generate_recap_script, _build_caption_beats
from .source_acquisition import acquire_source
from .tts_agent import generate_voiceover, probe_audio_duration
from .heartbeat import acquire_run_lock, release_run_lock, complete_heartbeat, write_heartbeat

REPO_ROOT = Path(__file__).parent.parent
ARTIFACTS_ROOT = REPO_ROOT / "artifacts" / "twistsrevealed"
STATUS_FILE = REPO_ROOT / "artifacts" / "clipping_factory" / "movie_status.json"
FFMPEG = "ffmpeg"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe(path: Path) -> Dict[str, Any]:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams",
             "-print_format", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        a = next((s for s in streams if s.get("codec_type") == "audio"), {})
        fps = 0.0
        fr = v.get("r_frame_rate", "0/1")
        try:
            num, den = fr.split("/")
            fps = int(num) / int(den) if int(den) else 0.0
        except Exception:
            pass
        return {
            "duration": float(fmt.get("duration", 0)),
            "width": int(v.get("width", 0)),
            "height": int(v.get("height", 0)),
            "fps": round(fps, 2),
            "size": int(fmt.get("size", 0)),
            "video_codec": v.get("codec_name", ""),
            "audio_codec": a.get("codec_name", ""),
        }
    except Exception:
        return {"duration": 0, "width": 0, "height": 0, "fps": 0, "size": 0,
                "video_codec": "", "audio_codec": ""}


def _run_ffmpeg(args: List[str], cwd: Path, timeout: int = 1800) -> bool:
    try:
        r = subprocess.run([FFMPEG, "-y", *args], cwd=str(cwd),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def _load_state() -> Dict[str, Any]:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def set_campaign_state(campaign_id: str, status: str, extra: Optional[Dict] = None) -> None:
    state = _load_state()
    entry = state.get(campaign_id, {})
    entry.update({"campaign_id": campaign_id, "status": status, "updated_at": _now()})
    if extra:
        entry.update(extra)
    state[campaign_id] = entry
    _save_state(state)


def update_ledger(run_record: Dict[str, Any]) -> None:
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    ledger_path = ARTIFACTS_ROOT / "ledger.json"
    ledger = {"runs": [], "counts": {}}
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    ledger["runs"] = ([run_record] + ledger.get("runs", []))[:100]
    counts = {}
    if STATUS_FILE.exists():
        try:
            for v in json.loads(STATUS_FILE.read_text(encoding="utf-8")).values():
                s = v.get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1
        except Exception:
            pass
    ledger["counts"] = counts
    ledger["updated_at"] = _now()
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


# ── visual assembly ──────────────────────────────────────────────

def _cut_vertical_segment(src: Path, work: Path, name: str, start: float, dur: float) -> bool:
    """Real edit: cut one film segment, convert to vertical blur-fill 1080x1920."""
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:4[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30[v]"
    )
    return _run_ffmpeg(
        ["-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", src.name,
         "-filter_complex", vf, "-map", "[v]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", name],
        cwd=work,
    )


def _concat_segments(work: Path, names: List[str], out_name: str) -> bool:
    lst = work / "concat_list.txt"
    lst.write_text("\n".join(f"file '{n}'" for n in names), encoding="utf-8")
    return _run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", out_name],
        cwd=work,
    )


def _final_render(work: Path, concat_name: str, vo_name: str, srt_name: str, out_path: Path) -> bool:
    fc = (
        "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,"
        "apad=pad_dur=1.0[a];"
        "[0:v]subtitles={srt}:force_style='FontName=Arial,FontSize=16,"
        "Outline=2,Bold=1,MarginV=72'[v]"
    ).format(srt=srt_name)
    return _run_ffmpeg(
        ["-i", concat_name, "-i", vo_name,
         "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         "-shortest", out_path.name],
        cwd=work,
    ) and out_path.exists()


def _extract_frames(final_path: Path, work: Path, count: int = 5) -> List[str]:
    probe = _probe(final_path)
    dur = probe.get("duration", 0)
    frames = []
    if dur <= 0:
        return frames
    for i in range(count):
        ts = dur * (i + 0.5) / count
        name = f"frame_{i + 1:02d}.png"
        ok = _run_ffmpeg(["-ss", f"{ts:.2f}", "-i", final_path.name,
                          "-frames:v", "1", name], cwd=work, timeout=120)
        if ok and (work / name).exists():
            frames.append(name)
    return frames


# ── QA ───────────────────────────────────────────────────────────

def _qa_and_score(final_path: Path, vo_duration: float, narration_words: int,
                  caption_beats: List[Dict], segment_count: int,
                  profile) -> Dict[str, Any]:
    probe = _probe(final_path)
    notes = []
    score = 0.0

    # Technical (6 pts)
    if probe["duration"] > 0:
        score += 1.0
        notes.append(f"duration {probe['duration']:.1f}s")
    else:
        notes.append("FAIL: zero duration")
    if probe["width"] == 1080 and probe["height"] == 1920:
        score += 2.0
        notes.append("resolution 1080x1920")
    else:
        notes.append(f"FAIL resolution {probe['width']}x{probe['height']}")
    if probe["fps"] >= 24:
        score += 1.0
        notes.append(f"fps {probe['fps']}")
    else:
        notes.append(f"FAIL fps {probe['fps']}")
    if probe["audio_codec"]:
        score += 1.0
        notes.append(f"audio {probe['audio_codec']}")
    else:
        notes.append("FAIL no audio stream")
    if probe["size"] > 200_000:
        score += 1.0
        notes.append(f"size {probe['size'] // 1024}KB")
    else:
        notes.append("FAIL file too small")

    # Creative (4 pts)
    dur_ok = (profile.target_duration_min - 2) <= probe["duration"] <= (profile.target_duration_max + 15)
    if dur_ok:
        score += 1.5
        notes.append(f"duration fits {profile.target_duration_min}-{profile.target_duration_max}s band")
    else:
        notes.append(f"duration outside band ({probe['duration']:.1f}s)")

    wpm = (narration_words / probe["duration"] * 60.0) if probe["duration"] else 0
    if 120 <= wpm <= 185:
        score += 1.25
        notes.append(f"narration pace {wpm:.0f} wpm")
    else:
        notes.append(f"pace off-band {wpm:.0f} wpm")

    if caption_beats:
        coverage = caption_beats[-1]["timestamp_end"] / max(vo_duration, 0.01)
        if coverage >= 0.85:
            score += 1.25
            notes.append(f"caption coverage {coverage * 100:.0f}%")
        else:
            notes.append(f"caption coverage low {coverage * 100:.0f}%")
    else:
        notes.append("FAIL no captions")

    passed = score >= profile.min_creative_score and dur_ok and probe["audio_codec"]
    return {
        "probe": probe, "score": round(score, 2),
        "threshold": profile.min_creative_score, "passed": passed,
        "notes": notes, "wpm": round(wpm), "segment_count": segment_count,
    }


# ── main cycle ───────────────────────────────────────────────────

def run_full_cycle(channel_slug: str = "twistsrevealed",
                   movie_count: int = 0,
                   publish: bool = False) -> Dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started = time.time()
    profile = get_profile(channel_slug)

    if not acquire_run_lock(timeout_sec=7200):
        return {"status": "skipped_already_running", "run_id": run_id}

    results = []
    try:
        count = movie_count or profile.daily_target

        # 1. DISCOVERY — draw a wide pool first, then prioritize candidates whose
        #    real source is verifiably available (public domain provenance)
        exclude = [cid for cid, v in _load_state().items()
                   if isinstance(v, dict) and v.get("status") in ("published", "verified")]
        pool = discover_movies(genres=profile.genres, count=max(count * 6, 24),
                               exclude_ids=exclude, status_file=None)
        pd_first = sorted(
            pool,
            key=lambda m: (0 if m.source_class == "public_domain" else 1, -m.rating),
        )
        print(f"[discovery] pool={len(pool)} selected={len(pd_first)}: "
              + ", ".join(f"{m.title} ({m.year})[{m.source_class}]" for m in pd_first))

        produced_so_far = 0
        for movie in pd_first:
            if produced_so_far >= count:
                break
            res = _produce_one(movie, profile, run_id, publish)
            results.append(res)
            if res.get("status") in ("ready", "verified", "published"):
                produced_so_far += 1

    finally:
        release_run_lock()

    produced = sum(1 for r in results if r.get("status") in ("ready", "verified", "published"))
    rejected = sum(1 for r in results if r.get("status") == "rejected")
    failed = sum(1 for r in results if r.get("status") in ("failed", "source_blocked"))
    complete_heartbeat(
        status="success" if produced else "failed",
        campaigns_found=len(pd_first),
        clips_produced=produced,
        clips_rejected=rejected,
        duration_sec=time.time() - started,
    )
    update_ledger({
        "run_id": run_id, "at": _now(),
        "status": "success" if produced else "failed",
        "produced": produced, "rejected": rejected, "failed": failed,
        "campaigns": [{"id": r.get("campaign_id"), "movie": r.get("movie"),
                       "status": r.get("status"),
                       "qa": r.get("qa", {}).get("score")} for r in results],
    })
    return {
        "status": "success" if produced else "failed",
        "run_id": run_id,
        "results": results,
        "produced": produced,
        "rejected": rejected,
        "failed": failed,
        "duration_sec": round(time.time() - started, 1),
    }


def _produce_one(movie: MovieCandidate, profile, run_id: str, publish: bool) -> Dict[str, Any]:
    campaign_id = movie.campaign_id
    print(f"\n[cycle] === {movie.title} ({movie.year}) [{campaign_id}] ===")

    # artifact dirs
    adir = ARTIFACTS_ROOT / f"{run_id}_{campaign_id}"
    work = adir / "work"
    work.mkdir(parents=True, exist_ok=True)

    record: Dict[str, Any] = {
        "campaign_id": campaign_id, "movie": f"{movie.title} ({movie.year})",
        "run_id": run_id, "started_at": _now(), "stages": {},
    }

    def stage(name: str, **data):
        record["stages"][name] = {"at": _now(), **data}
        print(f"[{campaign_id}] {name}: {json.dumps({k: v for k, v in data.items() if k != 'research'})[:300]}")

    try:
        # 2. RESEARCH (structured factual object from curated research data)
        research = {
            "title": movie.title, "year": movie.year, "director": movie.director,
            "genres": movie.genres, "premise": movie.synopsis,
            "major_events": [movie.synopsis],
            "twist": movie.ending_description,
            "key_characters": movie.key_characters,
            "sources": ["curated_twist_database_v1"],
            "confidence": "high",
            "ending_strength": "canonical_twist",
            "rating_imdb_like": movie.rating,
        }
        set_campaign_state(campaign_id, "researched",
                           {"title": movie.title, "year": movie.year})
        stage("research", confidence="high")

        # 3. SOURCE ACQUISITION — hard gate
        src = acquire_source(campaign_id, movie.title, movie.year,
                             movie.source_class, movie.source_uri,
                             allowed_provenance=profile.source_policy)
        record["source"] = src.to_dict()
        if src.status not in ("acquired", "cached"):
            set_campaign_state(campaign_id, "blocked",
                               {"reason": src.error})
            stage("source_acquisition", status=src.status, error=src.error)
            record["status"] = "source_blocked"
            (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record
        stage("source_acquisition", status=src.status,
              provenance=src.provenance, duration_sec=src.duration_sec,
              sha256=src.checksum_sha256[:16])

        source_path = Path(src.local_path)
        source_copy = work / "source.mp4"
        shutil.copyfile(source_path, source_copy)
        script = generate_recap_script(
            campaign_id=campaign_id, title=movie.title, year=movie.year,
            synopsis=movie.synopsis, ending_description=movie.ending_description,
            key_characters=movie.key_characters, genres=movie.genres,
            tone=profile.tone,
            target_duration_min=profile.target_duration_min,
            target_duration_max=profile.target_duration_max,
            director=movie.director,
        )
        (adir / "script.txt").write_text(script.narration, encoding="utf-8")
        (adir / "script.json").write_text(json.dumps(script.to_dict(), indent=2), encoding="utf-8")
        set_campaign_state(campaign_id, "scripted", {"script_id": script.script_id})
        stage("script", script_id=script.script_id,
              words=script.narration_words, est_sec=round(script.estimated_duration_sec, 1))

        # 5. TTS (real voiceover; edge-tts -> SAPI fallback)
        vo = generate_voiceover(
            script.narration, adir / "voiceover.mp3",
            voice_config={
                "provider": profile.voice.provider,
                "voice_id": profile.voice.voice_id,
                "rate": profile.voice.rate,
                "pitch": profile.voice.pitch,
                "fallback_voices": profile.voice.fallback_voices,
            },
            estimated_duration_sec=script.estimated_duration_sec,
        )
        record["voiceover"] = vo
        if not vo["valid"]:
            set_campaign_state(campaign_id, "failed", {"reason": vo["error"]})
            stage("tts", valid=False, error=vo["error"])
            record["status"] = "failed"
            (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record
        vo_duration = vo["duration_sec"]
        stage("tts", provider=vo["provider"], duration_sec=vo_duration)

        # copy real assets into work dir (ffmpeg runs with cwd=work for safe relative filters)

        # 6. VISUAL SEGMENTS from the real film, aligned to story structure
        structure = profile.story_structure or ["hook", "setup", "escalation", "reveal", "ending", "sting"]
        n_seg = max(len(structure), 6)
        seg_len = vo_duration / n_seg
        sdur = src.duration_sec
        usable_start = sdur * 0.03
        usable_len = sdur * 0.92
        seg_files = []
        for i, phase in enumerate(structure[:n_seg] + ["beat"] * max(0, n_seg - len(structure))):
            start = usable_start + ((i + 0.5) / n_seg) * usable_len
            name = f"seg_{i:02d}.mp4"
            ok = _cut_vertical_segment(source_copy, work, name, start, seg_len + 0.2)
            if ok:
                seg_files.append(name)
        if len(seg_files) < max(3, n_seg // 2):
            set_campaign_state(campaign_id, "failed", {"reason": "visual segmentation failed"})
            stage("visuals", segments=len(seg_files), ok=False)
            record["status"] = "failed"
            (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record
        concat_ok = _concat_segments(work, seg_files, "concat.mp4")
        stage("visuals", segments=len(seg_files), concat=concat_ok)

        # 7. CAPTIONS timed to ACTUAL voiceover duration
        beats = _build_caption_beats(script.narration, vo_duration)
        lines = []
        for i, b in enumerate(beats, 1):
            def fmt(ts):
                h = int(ts // 3600); m = int((ts % 3600) // 60)
                s = int(ts % 60); ms = int(round((ts % 1) * 1000))
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            lines += [str(i), f"{fmt(b['timestamp_start'])} --> {fmt(b['timestamp_end'])}",
                      b["text"], ""]
        (work / "captions.srt").write_text("\n".join(lines), encoding="utf-8")
        (adir / "captions.srt").write_text("\n".join(lines), encoding="utf-8")
        stage("captions", beats=len(beats))

        # 8. FINAL RENDER (burned captions + loudness-normalized voice)
        shutil.copyfile(adir / "voiceover.mp3", work / "voiceover.mp3")
        final_local = "final.mp4"
        render_ok = _final_render(work, "concat.mp4", "voiceover.mp3", "captions.srt",
                                  work / final_local)
        final_src = work / final_local
        final_dst = adir / "final.mp4"
        if render_ok:
            shutil.copyfile(final_src, final_dst)
        stage("render", ok=bool(render_ok))

        if not render_ok or not final_dst.exists():
            set_campaign_state(campaign_id, "failed", {"reason": "final render failed"})
            record["status"] = "failed"
            (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record

        # 9. VIDEO QA + CREATIVE SCORE
        qa = _qa_and_score(final_dst, vo_duration, script.narration_words,
                           beats, len(seg_files), profile)
        frames = _extract_frames(final_dst, work)
        for f in frames:
            shutil.copyfile(work / f, adir / f)
        qa["frames_extracted"] = frames
        (adir / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
        record["qa"] = {"score": qa["score"], "passed": qa["passed"],
                        "notes": qa["notes"]}
        stage("qa", score=qa["score"], threshold=qa["threshold"], passed=qa["passed"])

        if not qa["passed"]:
            set_campaign_state(campaign_id, "rejected",
                               {"score": qa["score"], "notes": qa["notes"]})
            record["status"] = "rejected"
            (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record

        set_campaign_state(campaign_id, "ready_to_publish",
                           {"score": qa["score"], "artifact": str(adir)})
        record["status"] = "ready"
        record["artifact_dir"] = str(adir)

        # 10. PACKAGE
        package = {
            "campaign_id": campaign_id,
            "title": script.title,
            "description": script.description,
            "tags": script.tags,
            "video": str(final_dst),
            "privacy": profile.publishing.youtube_privacy,
            "provenance": src.provenance,
            "source_uri": src.uri,
            "status": "READY_FOR_PUBLISH",
            "packaged_at": _now(),
        }
        (adir / "publish_package.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
        stage("package", path=str(adir))

        # 11/12. PUBLISH + VERIFY (only when explicitly requested)
        if publish:
            from .publish_verify import publish_and_verify
            pv = publish_and_verify(package, channel_id=_channel_id())
            record["publish"] = pv
            stage("publish_verify", status=pv["status"], video_id=pv.get("video_id", ""))
            if pv["status"] == "verified":
                set_campaign_state(campaign_id, "verified",
                                   {"video_id": pv["video_id"], "url": pv.get("url", "")})
                record["status"] = "verified"
            elif pv["status"] == "published":
                set_campaign_state(campaign_id, "published", {"video_id": pv["video_id"]})
                record["status"] = "published"
            else:
                set_campaign_state(campaign_id, "publish_failed",
                                   {"error": pv.get("error", "")})

        (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    except Exception as exc:
        traceback.print_exc()
        record["status"] = "failed"
        record["error"] = str(exc)
        set_campaign_state(campaign_id, "failed", {"reason": str(exc)[:300]})
        (adir / "campaign.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record


def _channel_id() -> str:
    tokens = REPO_ROOT / "MBM-Social" / "youtube_tokens.json"
    try:
        data = json.loads(tokens.read_text(encoding="utf-8"))
        return data.get("twistsrevealed", {}).get("channel_id", "")
    except Exception:
        return ""


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Twists Revealed full production cycle")
    ap.add_argument("--movies", type=int, default=0)
    ap.add_argument("--publish", action="store_true",
                    help="upload unlisted + verify (real upload)")
    args = ap.parse_args()
    out = run_full_cycle(movie_count=args.movies, publish=args.publish)
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for r in out["results"]:
        print(f"  {r['campaign_id']} {r.get('movie','')} -> {r.get('status')} "
              f"(qa={r.get('qa',{}).get('score')})")
    raise SystemExit(0 if out["status"] == "success" else 1)
