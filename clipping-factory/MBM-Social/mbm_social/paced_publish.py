"""
paced_publish -- throttle real publishing so channels never get flagged.

Gate: max N posts per UTC day (default 5), at least MIN_GAP_MINUTES
(default 120) between actual publish attempts, rotating the brand drawn from
the publish queue so every channel stays active without spamming.

Each run publishes AT MOST ONE package. It reuses post_orchestrator's
publish_package() so YouTube (CDP -> brand Playwright profile) + Instagram +
TikTok all get a real attempt and status only flips to `published` on a real
success. Posts that fail stay `draft` and the clock still advances, so a hung
session cannot loop-publish.

Usage:
  python -m mbm_social.paced_publish                # respect pacing
  python -m mbm_social.paced_publish --dry-run       # show pick, post nothing
  python -m mbm_social.paced_publish --force        # ignore budget/gap (human)
  python -m mbm_social.paced_publish --brand cute   # force this brand only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "paced_state.json"

# Defaults match the documented throttle: max 5 posts/day, >=120 min apart.
# Override via env (PACED_MAX_DAILY / PACED_GAP_MINUTES) for per-account tuning.
MAX_DAILY = int(os.getenv("PACED_MAX_DAILY", "5"))
GAP_MINUTES = int(os.getenv("PACED_GAP_MINUTES", "120"))

BRANDS = [
    "cutedosage",
    "dontwatchthis",
    "goalmachinez",
    "twistsrevealed",
    "clippingfactorymbm",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _posted_today(state: dict) -> list[dict]:
    today = _now().strftime("%Y-%m-%d")
    if state.get("date") != today:
        return []
    return state.get("posts", [])


def pick_brand(state: dict) -> tuple[str, list]:
    """Rotate the brand cursor, return best brand + its newest real draft."""
    idx = int(state.get("rotation_idx", 0))
    ordered = BRANDS[idx:] + BRANDS[:idx]
    for brand in ordered:
        from mbm_social import post_orchestrator as orch

        pending = orch.pending_packages(brand, dedupe=True, limit=2)
        if pending:
            return brand, pending
    return "", []


def run_paced(
    dry_run: bool = False,
    force: bool = False,
    brand_only: str | None = None,
    mode: str | None = None,
) -> dict:
    from mbm_social import post_orchestrator as orch

    # Resolve publish mode: explicit arg > PUBLISH_MODE env > dry_run flag.
    if mode is None:
        mode = os.getenv("PUBLISH_MODE", "dry_run").strip().lower()
    if mode not in orch.PUBLISH_MODES:
        mode = "dry_run"
    if dry_run:
        mode = "dry_run"

    state = _load_state()
    now = _now()
    today = now.strftime("%Y-%m-%d")
    if state.get("date") != today:
        state = {"date": today, "posts": [], "rotation_idx": 0}
        _save_state(state)

    posts = state.get("posts", [])

    finish = {
        "date": today,
        "posted": 0,
        "mode": mode,
        "skipped_reason": "",
        "next_action": "wait for next paced window",
        "owner": "system",
        "timestamp": now.isoformat(),
    }

    if not force:
        successes = [p for p in posts if p.get("status") == "published"]
        if len(successes) >= MAX_DAILY:
            finish["skipped_reason"] = f"daily budget reached ({MAX_DAILY})"
            print(f"[PACED] {finish['skipped_reason']} -- nothing posted.")
            return finish
        if posts:
            last_at = posts[-1].get("at")
            if last_at:
                gap = (now - datetime.fromisoformat(last_at)).total_seconds() / 60
                if gap < GAP_MINUTES:
                    wait = int(GAP_MINUTES - gap)
                    finish["skipped_reason"] = f"next post in ~{wait} min (gap={GAP_MINUTES}min)"
                    print(f"[PACED] {finish['skipped_reason']}")
                    return finish

    brand, pending = (brand_only, []) if brand_only else ("", [])
    if not pending and brand_only:
        brand = brand_only
        pending = orch.pending_packages(brand, dedupe=True, limit=2)

    if not brand or not pending:
        brand, pending = pick_brand(state)

    if not brand or not pending:
        finish["skipped_reason"] = "no postable draft (fill publish_queue first)"
        print(f"[PACED] {finish['skipped_reason']}")
        return finish

    filepath, package = pending[0]
    title = package.get("title") or "Untitled"

    print(f"[PACED] Window open -> publishing [{brand}]: '{title}' ({filepath.name})")
    if dry_run:
        print(f"[dry-run] Would call publish_package on newest {brand} draft (mode={mode}); ")
        print(f"[dry-run] remaining today now = {MAX_DAILY - len([p for p in posts if p.get('status')=='published'])}")
        state["rotation_idx"] = (state.get("rotation_idx", 0) + 1) % len(BRANDS)
        _save_state(state)
        finish["skipped_reason"] = "dry-run only; no real post"
        return finish

    # Mode is passed explicitly so post_orchestrator does not silently
    # fall back to dry_run (previous bug: run_paced omitted mode entirely).
    result = orch.publish_package(filepath, package, dry_run=False, mode=mode)
    published = result.get("status") == "published"

    posts.append({
        "brand": brand,
        "at": now.isoformat(),
        "file": filepath.name,
        "title": title,
        "status": "published" if published else "failed",
        "platforms": result.get("published_platforms", {}),
    })
    state["posts"] = posts
    state["date"] = today
    state["rotation_idx"] = (state.get("rotation_idx", 0) + 1) % len(BRANDS)
    _save_state(state)

    finish["posted"] = 1 if published else 0
    finish["brand"] = brand
    finish["status"] = "success" if published else "failure"
    finish["platforms"] = result.get("published_platforms", {})
    if published:
        print(f"[PACED] POSTED [{brand}] -> {result.get('published_platforms', {})}")
    else:
        print(f"[PACED] No real post for [{brand}] yet (logins missing?); budget untouched.")
    return finish


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Paced multi-platform publishing gate.")
    parser.add_argument("--dry-run", action="store_true", help="Pick a brand, post nothing.")
    parser.add_argument("--force", action="store_true", help="Ignore daily budget + gap window.")
    parser.add_argument("--brand", help="Post only this brand (ignores rotation).")
    parser.add_argument("--mode", choices=("dry_run", "test", "live"),
                        default=os.getenv("PUBLISH_MODE", "dry_run"),
                        help="Publish mode forwarded to post_orchestrator. Default: $PUBLISH_MODE.")
    args = parser.parse_args(argv)

    mode = args.mode
    if args.dry_run:
        mode = "dry_run"
    res = run_paced(dry_run=args.dry_run, force=args.force, brand_only=args.brand, mode=mode)
    try:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return 0 if res.get("posted") or args.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())