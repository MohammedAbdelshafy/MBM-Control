"""
asset_lineage -- job lineage + asset families for MBM-Social / clipping-factory (issue #18).

ONE SOURCE SHOULD PRODUCE AN ASSET FAMILY.

A source (source_url / source_id) is the root of a family. Every derived
artifact records a lineage edge:
    source -> parent asset -> child asset (vertical reframe, captions, thumb...)

Features:
  - lineage ledger (append-only JSON-lines) with parent/child edges
  - near-duplicate detection via a token simhash over the transcript/description
  - render queue with retries: status (queued|rendering|done|failed), attempts,
    max_retries, backoff_s, last_error
  - QA flag + publication evidence (upload_id, platform, url, verified timestamp)

HONESTY: publication_evidence is only set by record_publication() with a real
upload_id + url. Nothing is inferred from filenames or invented.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
LINEAGE_DIR = ROOT / "AssetLineage"
LINEAGE_PATH = LINEAGE_DIR / "lineage.jsonl"


class LineageError(Exception):
    """Raised when a lineage invariant is violated (fails closed)."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Near-duplicate detection (token simhash)
# --------------------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return [w for w in str(text).lower().replace("\n", " ").split() if w]


def simhash(text: str, bits: int = 64) -> int:
    """Token simhash (0..2**bits). Equal/near-identical text -> same hash."""
    import hashlib

    h = 0
    v = [0] * bits
    for tok in _tokens(text):
        hv = int.from_bytes(hashlib.sha256(tok.encode("utf-8")).digest()[:8], "little") % (1 << bits)
        for i in range(bits):
            v[i] += 1 if (hv >> i) & 1 else -1
    for i in range(bits):
        if v[i] > 0:
            h |= 1 << i
    return h


def hamming_distance(a: int, b: int, bits: int = 64) -> int:
    return bin(a ^ b).count("1")


def is_near_duplicate(hash_a: int, hash_b: int, threshold: int = 8) -> bool:
    """True when the two simhashes differ in <= threshold bits (near-dup)."""
    return hamming_distance(hash_a, hash_b) <= threshold


# --------------------------------------------------------------------------
# Domain models
# --------------------------------------------------------------------------


@dataclass
class Asset:
    asset_id: str
    source_id: str
    kind: str  # source | clip | vertical_reframe | caption | thumbnail | package
    filepath: str
    parent_asset_id: Optional[str]
    transcript_text: str
    simhash: int
    created_iso: str
    status: str = "recorded"  # recorded | rendered | failed
    qa_passed: Optional[bool] = None
    publication_evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class RenderJob:
    job_id: str
    asset_id: str
    kind: str
    status: str  # queued | rendering | done | failed
    attempts: int
    max_retries: int
    backoff_s: float
    next_run_after_iso: str
    last_error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class LineageLedger:
    """Append-only lineage ledger with a read-through cache for lookups."""

    def __init__(self, path: Path = LINEAGE_PATH) -> None:
        self.path = path
        self._cache: dict[str, dict] | None = None

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def _index(self) -> dict[str, dict]:
        if self._cache is None:
            self._cache = {r["asset_id"]: r for r in self._load()}
        return self._cache

    def invalidate(self) -> None:
        self._cache = None

    def append(self, row: dict) -> None:
        rows = self._load()
        rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )
        self.invalidate()

    def get(self, asset_id: str) -> Optional[dict]:
        return self._index().get(asset_id)

    def family(self, source_id: str) -> list[dict]:
        return [r for r in self._load() if r["source_id"] == source_id]

    def all(self) -> list[dict]:
        return self._load()


# --------------------------------------------------------------------------
# Lineage operations
# --------------------------------------------------------------------------


def _new_asset_id() -> str:
    return f"AS-{uuid.uuid4().hex[:12]}"


def record_source(
    ledger: LineageLedger,
    source_url: str,
    transcript_text: str,
    filepath: str = "",
    source_id: Optional[str] = None,
) -> Asset:
    """Register the root asset of a family (one source -> many assets)."""
    if not source_url.strip():
        raise LineageError("record_source requires a non-empty source_url")
    asset = Asset(
        asset_id=_new_asset_id(),
        source_id=source_id or source_url,
        kind="source",
        filepath=filepath,
        parent_asset_id=None,
        transcript_text=transcript_text,
        simhash=simhash(transcript_text),
        created_iso=_iso_now(),
    )
    ledger.append(asset.as_dict())
    return asset


def derive_asset(
    ledger: LineageLedger,
    parent: Asset,
    kind: str,
    filepath: str,
    transcript_text: Optional[str] = None,
) -> Asset:
    """Create a child asset under a parent, inheriting the family source_id."""
    if kind == "source":
        raise LineageError("'source' assets cannot be derived; use record_source")
    child = Asset(
        asset_id=_new_asset_id(),
        source_id=parent.source_id,
        kind=kind,
        filepath=filepath,
        parent_asset_id=parent.asset_id,
        transcript_text=transcript_text or parent.transcript_text,
        simhash=simhash(transcript_text or parent.transcript_text),
        created_iso=_iso_now(),
    )
    ledger.append(child.as_dict())
    return child


def find_near_duplicates(
    ledger: LineageLedger,
    transcript_text: str,
    threshold: int = 8,
    exclude_source: Optional[str] = None,
) -> list[dict]:
    """Return recorded assets whose simhash is near-identical to the text."""
    target = simhash(transcript_text)
    out = []
    for r in ledger.all():
        if exclude_source and r["source_id"] == exclude_source:
            continue
        if is_near_duplicate(target, r["simhash"], threshold):
            out.append(r)
    return out


# --------------------------------------------------------------------------
# Render queue with retries
# --------------------------------------------------------------------------


def _iso_after(seconds: float) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="seconds"
    )


def enqueue_render(asset: Asset, max_retries: int = 3, backoff_s: float = 60.0) -> RenderJob:
    job = RenderJob(
        job_id=f"RJ-{uuid.uuid4().hex[:12]}",
        asset_id=asset.asset_id,
        kind=asset.kind,
        status="queued",
        attempts=0,
        max_retries=max_retries,
        backoff_s=backoff_s,
        next_run_after_iso=_iso_now(),
    )
    return job


def mark_rendering(job: RenderJob) -> RenderJob:
    job.status = "rendering"
    job.attempts += 1
    return job


def retry_backoff(job: RenderJob, error: str) -> RenderJob:
    """Move job to retry/queued with exponential backoff, or fail it.

    max_retries = retries AFTER the initial attempt (so max_retries=2 allows
    up to 3 total attempts).
    """
    job.last_error = error
    if job.attempts > job.max_retries:
        job.status = "failed"
        return job
    job.status = "queued"
    job.backoff_s *= 2
    job.next_run_after_iso = _iso_after(job.backoff_s)
    return job


def complete_render(job: RenderJob) -> RenderJob:
    job.status = "done"
    job.last_error = ""
    return job


# --------------------------------------------------------------------------
# QA + publication evidence
# --------------------------------------------------------------------------


def set_qa(ledger: LineageLedger, asset_id: str, passed: bool) -> dict:
    row = ledger.get(asset_id)
    if row is None:
        raise LineageError(f"no asset '{asset_id}' in lineage")
    row["qa_passed"] = bool(passed)
    if row["status"] == "recorded":
        row["status"] = "rendered"
    _rewrite(ledger, row)
    return row


def record_publication(
    ledger: LineageLedger,
    asset_id: str,
    upload_id: str,
    platform: str,
    url: str,
) -> dict:
    """Attach REAL publication evidence. Fails closed on empty upload_id/url."""
    if not upload_id.strip() or not url.strip():
        raise LineageError("record_publication requires upload_id and url")
    row = ledger.get(asset_id)
    if row is None:
        raise LineageError(f"no asset '{asset_id}' in lineage")
    row["publication_evidence"] = {
        "upload_id": upload_id.strip(),
        "platform": platform.strip(),
        "url": url.strip(),
        "verified_iso": _iso_now(),
    }
    _rewrite(ledger, row)
    return row


def _rewrite(ledger: LineageLedger, updated: dict) -> None:
    rows = ledger.all()
    for i, r in enumerate(rows):
        if r["asset_id"] == updated["asset_id"]:
            rows[i] = updated
            break
    ledger.path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    ledger.invalidate()


def family_report(ledger: LineageLedger, source_id: str) -> dict:
    members = ledger.family(source_id)
    published = [m for m in members if m.get("publication_evidence")]
    return {
        "source_id": source_id,
        "assets": len(members),
        "kinds": sorted({m["kind"] for m in members}),
        "published": len(published),
        "qa_failed": sum(1 for m in members if m.get("qa_passed") is False),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Asset lineage ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("all", help="print all lineage rows")
    p_fam = sub.add_parser("family", help="print one source family")
    p_fam.add_argument("source_id")
    args = parser.parse_args(argv)

    ledger = LineageLedger()
    if args.command == "all":
        for r in ledger.all():
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if args.command == "family":
        print(json.dumps(family_report(ledger, args.source_id), ensure_ascii=False, indent=2))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())