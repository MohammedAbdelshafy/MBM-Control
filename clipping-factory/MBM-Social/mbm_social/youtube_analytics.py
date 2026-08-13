"""
youtube_analytics -- honest YouTube publishing + analytics tracking (jarvis-mbm #18).

Tracks per-video, per-channel:
  upload status, scheduling, publication ID, analytics (views, retention,
  subscribers, revenue), US audience % and watch time, revenue per minute.

INTEGRITY RULES:
  - reported_* values come ONLY from an injected provider (YouTube Data API,
    Studio CSV export, or manual entry) via verify_analytics().
  - Nothing is estimated as if it were real: fields without a provider stay
    null. We never spoof geography, buy views, or fabricate metrics.
  - revenue_per_minute is computed ONLY from reported/actual values.

CREDENTIAL BLOCKER (recorded, not fabricated):
  The YouTube Data API 'videos.list + reporting' path needs a valid OAuth
  access token for each channel. Those were REVOKED/ROTATED as part of the
  secret scrub (see SCRUB_REPORT) — currently BLOCKED. Until then the module
  operates with provider=None (nulls) or caller-supplied provider adapters
  (e.g. a Studio CSV parser). Tests use a fake provider to prove the wiring.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
YT_DIR = ROOT / "YouTubeAnalytics"
LEDGER_PATH = YT_DIR / "videos.jsonl"


class YouTubeAnalyticsError(Exception):
    """Raised when analytics integrity is violated."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# A provider returns real numbers for one video:
#   callable(video_id, channel) -> dict | None
# Keys (all optional, nulls allowed): views, avg_view_duration_s, subscribers,
#   us_audience_pct, us_watch_time_s, revenue_usd, monetized_plays.
Provider = Callable[[str, str], Optional[dict]]


@dataclass
class Video:
    video_id: str
    channel: str
    brand: str
    upload_status: str  # planned | scheduled | uploaded | private | public
    scheduled_for: Optional[str]
    publication_id: Optional[str]
    publication_url: Optional[str]
    created_iso: str
    analytics: dict = field(default_factory=dict)  # reported_* + revenue_per_minute

    def as_dict(self) -> dict:
        return asdict(self)


class VideoLedger:
    """Append-only JSON-lines ledger of video publishing + analytics."""

    def __init__(self, path: Path = LEDGER_PATH) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def append(self, video: Video) -> None:
        rows = self._load()
        rows.append(video.as_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

    def get(self, video_id: str) -> Optional[dict]:
        for r in self._load():
            if r["video_id"] == video_id:
                return r
        return None

    def update(self, row: dict) -> None:
        rows = self._load()
        for i, r in enumerate(rows):
            if r["video_id"] == row["video_id"]:
                rows[i] = row
                break
        else:
            raise YouTubeAnalyticsError(f"video '{row['video_id']}' not in ledger")
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

    def all(self) -> list[dict]:
        return self._load()

    def summary(self) -> dict:
        rows = self._load()
        with_reported = [r for r in rows if r["analytics"].get("reported_views") is not None]
        return {
            "videos": len(rows),
            "with_reported_analytics": len(with_reported),
            "sum_reported_views": sum(r["analytics"]["reported_views"] for r in with_reported),
            "sum_revenue_usd": round(
                sum((r["analytics"].get("revenue_usd") or 0.0) for r in with_reported), 2
            ),
            "avg_revenue_per_minute_usd": round(
                sum(r["analytics"].get("revenue_per_minute_usd") or 0.0 for r in with_reported)
                / len(with_reported),
                4,
            )
            if with_reported
            else 0.0,
        }


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------


def _new_video_id() -> str:
    return f"VID-{uuid.uuid4().hex[:10]}"


def plan_video(
    ledger: VideoLedger,
    channel: str,
    brand: str,
    *,
    video_id: Optional[str] = None,
    scheduled_for: Optional[str] = None,
) -> Video:
    """Register a planned/uploaded video with its publication ID when known."""
    video = Video(
        video_id=video_id or _new_video_id(),
        channel=channel,
        brand=brand,
        upload_status="scheduled" if scheduled_for else "planned",
        scheduled_for=scheduled_for,
        publication_id=None,
        publication_url=None,
        created_iso=_iso_now(),
    )
    ledger.append(video)
    return video


def record_publication_id(
    ledger: VideoLedger, video_id: str, publication_id: str, url: str
) -> dict:
    """Attach a REAL publication ID + URL. Empty values rejected."""
    if not publication_id.strip() or not url.strip():
        raise YouTubeAnalyticsError("publication requires publication_id and url")
    row = ledger.get(video_id)
    if row is None:
        raise YouTubeAnalyticsError(f"video '{video_id}' not in ledger")
    row["publication_id"] = publication_id.strip()
    row["publication_url"] = url.strip()
    row["upload_status"] = "uploaded"
    ledger.update(row)
    return row


def _revenue_per_minute(revenue_usd: Optional[float], duration_s: Optional[float]) -> Optional[float]:
    if revenue_usd is None or duration_s is None or duration_s <= 0:
        return None
    return round(revenue_usd / (duration_s / 60.0), 4)


def verify_analytics(
    ledger: VideoLedger,
    video_id: str,
    provider: Optional[Provider] = None,
    manual: Optional[dict] = None,
) -> dict:
    """
    Attach platform-REPORTED analytics. Accepts either an injected provider or
    an explicit manual dict. Nulls stay null when nothing is provided.
    """
    row = ledger.get(video_id)
    if row is None:
        raise YouTubeAnalyticsError(f"video '{video_id}' not in ledger")

    reported: dict = {}
    if manual is not None:
        reported = dict(manual)
    elif provider is not None:
        reported = provider(video_id, row["channel"]) or {}
    else:
        raise YouTubeAnalyticsError(
            "verify_analytics needs a provider or manual dict (never fabricate analytics)"
        )

    views = reported.get("views")
    duration = reported.get("avg_view_duration_s")
    revenue = reported.get("revenue_usd")

    row["analytics"] = {
        "reported_views": views,
        "avg_view_duration_s": duration,
        "subscribers": reported.get("subscribers"),
        "us_audience_pct": reported.get("us_audience_pct"),
        "us_watch_time_s": reported.get("us_watch_time_s"),
        "revenue_usd": revenue,
        "monetized_plays": reported.get("monetized_plays"),
        "revenue_per_minute_usd": _revenue_per_minute(revenue, duration),
        "source": manual is not None and "manual" or "provider",
        "verified_iso": _iso_now(),
    }
    ledger.update(row)
    return row


def export_csv(ledger: VideoLedger, path: Path) -> None:
    rows = ledger.all()
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = ["video_id", "channel", "brand", "upload_status", "publication_id"]
    for extra in ("reported_views", "revenue_usd", "us_audience_pct", "revenue_per_minute_usd"):
        fieldnames.append(extra)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            a = r["analytics"]
            writer.writerow(
                {
                    "video_id": r["video_id"],
                    "channel": r["channel"],
                    "brand": r["brand"],
                    "upload_status": r["upload_status"],
                    "publication_id": r["publication_id"] or "",
                    "reported_views": a.get("reported_views") or "",
                    "revenue_usd": a.get("revenue_usd") or "",
                    "us_audience_pct": a.get("us_audience_pct") or "",
                    "revenue_per_minute_usd": a.get("revenue_per_minute_usd") or "",
                }
            )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="YouTube publishing + analytics ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="print analytics summary")
    sub.add_parser("rows", help="print raw video rows")
    p_csv = sub.add_parser("export-csv", help="export videos.csv")
    p_csv.add_argument("--out", default=str(YT_DIR / "videos.csv"))
    args = parser.parse_args(argv)

    ledger = VideoLedger()
    if args.command == "summary":
        print(json.dumps(ledger.summary(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "rows":
        for r in ledger.all():
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if args.command == "export-csv":
        export_csv(ledger, Path(args.out))
        print(f"wrote {args.out}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())