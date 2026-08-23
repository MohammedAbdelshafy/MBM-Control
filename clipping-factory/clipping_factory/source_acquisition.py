"""
Source Acquisition — downloads and verifies REAL source material.

Invariant: NO_REAL_SOURCE -> NO_PRODUCTION_CLIP.
Every acquired source carries provenance (license class, URI, checksum).
A failed acquisition returns SOURCE_BLOCKED — never a demo substitute.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).parent.parent
SOURCES_DIR = REPO_ROOT / "video_repos" / "public_domain"

MIN_SOURCE_BYTES = 10 * 1024 * 1024  # a feature film under 10 MB is corrupt/incomplete


@dataclass
class SourceResult:
    campaign_id: str
    status: str                 # acquired | cached | blocked | rejected_provenance
    source_class: str
    provenance: str             # licensed | public_domain | owner_provided | authorized | unverified
    uri: str
    local_path: str = ""
    checksum_sha256: str = ""
    size_bytes: int = 0
    duration_sec: float = 0.0
    error: str = ""
    acquired_at: str = ""

    def __post_init__(self):
        if not self.acquired_at:
            self.acquired_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return asdict(self)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _download(uri: str, dest: Path, timeout_sec: int = 900) -> bool:
    """Stream-download a source file. Uses curl.exe (ships with Windows 10+) or requests."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        curl = r"C:\Windows\System32\curl.exe"
        if Path(curl).exists():
            r = subprocess.run(
                [curl, "-L", "--fail", "--retry", "3", "--connect-timeout", "30",
                 "-o", str(tmp), uri],
                capture_output=True, timeout=timeout_sec,
            )
        else:
            import requests
            with requests.get(uri, stream=True, timeout=(30, 600), allow_redirects=True) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            r = None
        if tmp.exists() and tmp.stat().st_size >= MIN_SOURCE_BYTES:
            tmp.rename(dest)
            return True
        return False
    except Exception:
        return False
    finally:
        if tmp.exists() and not dest.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def acquire_source(
    campaign_id: str,
    title: str,
    year: int,
    source_class: str,
    source_uri: str,
    allowed_provenance: Optional[list] = None,
) -> SourceResult:
    """
    Acquire the real source film for a campaign.

    Rules:
      - provenance must be in the channel's source_policy (default: public_domain/licensed/authorized/owner_provided)
      - UNVERIFIED provenance is never auto-acquired for production -> blocked
      - download failure -> blocked (SOURCE_BLOCKED), never substituted
    """
    allowed = allowed_provenance or ["public_domain", "licensed", "authorized", "owner_provided"]
    provenance = (source_class or "unverified").lower()

    result = SourceResult(
        campaign_id=campaign_id, status="blocked",
        source_class=source_class, provenance=provenance, uri=source_uri,
    )

    if not source_uri:
        result.error = "SOURCE_BLOCKED: no source_uri recorded by discovery"
        return result

    if provenance not in allowed:
        result.status = "rejected_provenance"
        result.error = (
            f"SOURCE_BLOCKED: provenance '{provenance}' not in allowed policy {allowed}. "
            "Production requires verified rights."
        )
        return result

    slug = "".join(c if c.isalnum() else "_" for c in f"{title}_{year}".lower())
    dest = SOURCES_DIR / slug / "source.mp4"

    if dest.exists() and dest.stat().st_size >= MIN_SOURCE_BYTES:
        result.status = "cached"
    else:
        ok = _download(source_uri, dest)
        if not ok:
            result.error = f"SOURCE_BLOCKED: download failed from {source_uri}"
            return result
        result.status = "acquired"

    size = dest.stat().st_size
    dur = _ffprobe_duration(dest)
    if dur < 1800:  # feature-length sanity floor (>=30 min) blocks recuts/clips
        result.error = f"SOURCE_BLOCKED: probed duration {dur:.0f}s too short for a feature source"
        return result

    result.local_path = str(dest)
    result.size_bytes = size
    result.checksum_sha256 = _sha256(dest)
    result.duration_sec = round(dur, 2)
    return result


if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else "TEST"
    title = sys.argv[2] if len(sys.argv) > 2 else "Carnival of Souls"
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 1962
    uri = sys.argv[4] if len(sys.argv) > 4 else \
        "https://archive.org/download/CarnivalOfSouls/CarnivalOfSouls_512kb.mp4"
    print(json.dumps(acquire_source(cid, title, year, "public_domain", uri).to_dict(), indent=2))
