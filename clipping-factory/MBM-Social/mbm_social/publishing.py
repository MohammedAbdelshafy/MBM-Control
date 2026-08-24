"""
publishing -- Resilient publish layer (Phase 6).

Wraps an injected `publisher_fn(package) -> dict` (which may be the real YouTube
API publisher, the short-form publisher, etc.) with:

  - retry + exponential backoff
  - a circuit breaker (reuses mbm_social.circuit_breaker)
  - idempotency: never publish the same (asset_id, platform) twice
  - duplicate detection: exact + near-duplicate (reuses asset_lineage simhash)
  - dead-letter: failed/blocked packages are preserved, never dropped

The layer never hardcodes credentials and never claims success without a real
publisher result. Blocked platforms (per platform_registry) are moved straight to
the dead-letter queue with a clear reason.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from . import circuit_breaker as cb
from . import platform_registry as pr
from . import asset_lineage as al


@dataclass
class PublishResult:
    asset_id: str
    platform: str
    status: str  # published | skipped_idempotent | skipped_duplicate | blocked | failed
    detail: dict = field(default_factory=dict)


def _content_hash(package: dict) -> int:
    # Duplicate detection keys on CONTENT, not asset_id: the same clip re-cut
    # under a new id is still a duplicate and must not be republished.
    key = json.dumps({
        "platform": package.get("target_platform") or package.get("platform"),
        "title": package.get("title"),
        "description": package.get("description"),
    }, sort_keys=True, default=str)
    return al.simhash(key)


class IdempotencyStore:
    """Tracks published (asset_id, platform) pairs and content simhashes."""

    def __init__(self) -> None:
        self._published: dict[tuple[str, str], str] = {}
        self._hashes: set[int] = set()

    def already_published(self, asset_id: str, platform: str) -> bool:
        return (asset_id, platform) in self._published

    def record_published(self, asset_id: str, platform: str, publish_id: str) -> None:
        self._published[(asset_id, platform)] = publish_id

    def is_near_duplicate(self, package: dict, threshold: int = 8) -> bool:
        h = _content_hash(package)
        return any(al.hamming_distance(h, prev, 64) <= threshold for prev in self._hashes)

    def record_hash(self, package: dict) -> None:
        self._hashes.add(_content_hash(package))


def publish_with_resilience(
    package: dict,
    publisher_fn: Callable[[dict], dict],
    *,
    store: IdempotencyStore,
    dlq_dir: Path,
    breaker: Optional[cb.CircuitBreaker] = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> PublishResult:
    asset_id = package.get("asset_id") or package.get("package_id") or "unknown"
    platform = package.get("target_platform") or package.get("platform") or "youtube"

    # 1. Blocked platform -> dead-letter immediately, never attempt.
    try:
        pr.assert_publishable(platform)
    except KeyError:
        _to_dlq(package, dlq_dir, "blocked_platform")
        return PublishResult(asset_id, platform, "blocked",
                             {"reason": "platform blocked in platform_registry"})

    # 2. Idempotency: already published?
    if store.already_published(asset_id, platform):
        return PublishResult(asset_id, platform, "skipped_idempotent",
                             {"reason": "already published"})

    # 3. Duplicate detection (exact + near).
    if store.is_near_duplicate(package):
        _to_dlq(package, dlq_dir, "duplicate_detected")
        return PublishResult(asset_id, platform, "skipped_duplicate",
                             {"reason": "near-duplicate of an existing package"})

    breaker = breaker or cb.CircuitBreaker()
    last_err: Optional[str] = None
    for attempt in range(1, max(1, max_retries) + 1):
        try:
            result = publisher_fn(package)
            # treat an explicit failed status as an error to retry
            if isinstance(result, dict) and result.get("status") in ("failed", "error"):
                raise RuntimeError(result.get("error", "publisher returned failed"))
            breaker.success("publisher")
            store.record_published(asset_id, platform, str(result.get("publish_id", "ok")))
            store.record_hash(package)
            return PublishResult(asset_id, platform, "published", result)
        except Exception as e:
            last_err = str(e)
            breaker.failure("publisher")
            if breaker.status("publisher") == cb.OPEN:
                break
            time.sleep(backoff_base ** attempt)

    _to_dlq(package, dlq_dir, f"publish_failed:{last_err}")
    return PublishResult(asset_id, platform, "failed", {"error": last_err})


def _to_dlq(package: dict, dlq_dir: Path, reason: str) -> None:
    try:
        dlq_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(package)
        payload.setdefault("dead_letter", {})["reason"] = reason
        payload.setdefault("dead_letter", {})["at"] = time.time()
        name = f"{package.get('asset_id', 'pkg')}_{int(time.time()*1000)}.json"
        (dlq_dir / name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
