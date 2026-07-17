"""Run orchestrator: ties collector -> media -> analysis -> storage -> knowledge,
writes Markdown files, commits to Git per run, and emits the output contract.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .analysis import Analyzer
from .collector import InstagramCollector, CollectedReel
from .config import Config
from .db import DB
from .knowledge import KnowledgeLayer
from .media import download_video, sample_frames
from .schema import Reel, render_markdown, slugify


class RunResult:
    def __init__(self):
        self.status = "success"
        self.reels_processed = 0
        self.new_reels = 0
        self.skipped = 0
        self.databases_updated: list[str] = []
        self.reports: list[str] = []
        self.errors: list[str] = []
        self.next_action = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reels_processed": self.reels_processed,
            "new_reels": self.new_reels,
            "skipped": self.skipped,
            "databases_updated": self.databases_updated,
            "reports": self.reports,
            "errors": self.errors,
            "next_action": self.next_action,
            "owner": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def run(config_path: str | Path, log: Callable[[str], None] = print) -> RunResult:
    res = RunResult()
    cfg = Config.load(config_path).resolve()
    for d in (cfg.media_dir, cfg.knowledge_dir, cfg.db_dir, cfg.cache_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    db = DB(cfg.db_dir)
    try:
        # 1. collect
        collector = InstagramCollector(cfg, log)
        collected: list[CollectedReel] = collector.collect()
        res.reels_processed = len(collected)
        log(f"[run] collected {len(collected)} reels")

        analyzer = Analyzer(cfg, log)
        knowledge = KnowledgeLayer(db, log)
        processed: list[Reel] = []

        for item in collected:
            reel = Reel(
                reel_id=item.reel_id,
                url=item.url,
                creator=item.creator,
                caption=item.caption,
                date_saved=item.date_saved,
                raw=dict(item.metrics or {}),
            )
            # 2. media (optional; needs direct video url)
            video = None
            if item.thumbnail_url:
                video = download_video(item.thumbnail_url, Path(cfg.media_dir) / f"{item.reel_id}.mp4",
                                       cfg.ffmpeg_path, log)
            if video:
                frames = sample_frames(video, Path(cfg.cache_dir) / item.reel_id,
                                        cfg.sample_frames_every_sec, cfg.ffmpeg_path)
                tr = analyzer.transcribe(video)
                reel.transcript = tr.get("transcript", "")
                ocr = analyzer.ocr_frames(frames)
                reel.caption = (reel.caption + "\n" + ocr.get("subtitles", "")).strip()
                reel.raw.update({k: ocr.get(k, "") for k in ("numbers", "contacts")})
                vision = analyzer.vision(frames, reel.transcript)
                for k, v in vision.items():
                    if hasattr(reel, k):
                        setattr(reel, k, v)
            # 3. classify (works from caption/transcript even without media)
            reel = analyzer.classify(reel)

            # 4. store
            changed = db.upsert_reel(reel)
            if changed:
                res.new_reels += 1
            else:
                res.skipped += 1
            # write markdown
            folder = Path(cfg.knowledge_dir) / (reel.niche or "Unsorted")
            folder.mkdir(parents=True, exist_ok=True)
            md_path = folder / f"{reel.reel_id}_{slugify(reel.title)}.md"
            md_path.write_text(render_markdown(reel), encoding="utf-8")
            processed.append(reel)

        res.databases_updated = list(db._conns.keys())

        # 5. knowledge layer
        knowledge.build_creator_profiles(processed)
        knowledge.detect_duplicates(processed)
        report = knowledge.weekly_report(Path(cfg.knowledge_dir))
        res.reports.append(str(report))

        # 6. git
        if cfg.git_auto_commit:
            _git_commit(cfg, res, log)
        res.next_action = "Review new reels; push when ready." if not cfg.git_auto_push \
            else "Run complete."
    except Exception as e:  # noqa: BLE001
        res.status = "failure"
        res.errors.append(str(e))
        log(f"[run] FAILED: {e}")
    finally:
        db.close()
    return res


def _git_commit(cfg: Config, res: RunResult, log: Callable[[str], None]):
    try:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        msg = f"{cfg.git_commit_prefix}/{date}: {res.new_reels} new reels, {res.skipped} skipped"
        subprocess.run(["git", "add", "MBM/Instagram"], check=True, capture_output=True)
        # only commit if there is something staged
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if staged.returncode != 0:
            subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
            log(f"[git] committed: {msg}")
            if cfg.git_auto_push:
                subprocess.run(["git", "push"], check=True, capture_output=True)
                log("[git] pushed")
        else:
            log("[git] no changes to commit")
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"git: {e}")
        log(f"[git] error: {e}")
