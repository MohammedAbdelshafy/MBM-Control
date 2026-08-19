"""
post_orchestrator -- single authoritative publishing engine for MBM-Social.

Reads `publish_queue/*.json` packages produced by the render pipeline and posts
each one to the correct per-brand YouTube channel PLUS cross-posts to Instagram
Reels and TikTok. It is the ONLY place that transitions a package's status from
`draft` to `published` -- nothing here fabricates URLs or claims a live post.

Publishing strategy per platform (best -> fallback):
  - YouTube: 1) existing native Chrome via CDP (--remote-debugging-port=9222);
              2) per-brand Playwright profile (youtube_profile_<brand>/).
  - Instagram / TikTok: per-brand Playwright profile (brand_config resolution).

A package is only marked `published` when at least one real platform reported
success. Per-platform outcomes are recorded under `published_platforms`.
Packages that could not be posted (e.g. no logged-in session) remain `draft`
so a human can complete the login and re-run -- nothing is silently dropped.

Usage:
  python -m mbm_social.post_orchestrator                    # publish all pending (live mode)
  python -m mbm_social.post_orchestrator --brand cute       # only one brand
  python -m mbm_social.post_orchestrator --mode dry_run     # validate only, no posting
  python -m mbm_social.post_orchestrator --mode test        # publish as unlisted/private
  python -m mbm_social.post_orchestrator --mode live        # full production publish
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Assorted titles contain emoji/unicode; force UTF-8-safe output on Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "publish_queue"

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_PUBLISH_BLOCKED = "publish_blocked"

# Publish mode control — enforced at orchestrator level
PUBLISH_MODES = ("dry_run", "test", "live")
PUBLISH_MODE = os.getenv("PUBLISH_MODE", "dry_run").strip().lower()
if PUBLISH_MODE not in PUBLISH_MODES:
    PUBLISH_MODE = "dry_run"

# In test mode, videos are published as unlisted; in live mode, as public
DEFAULT_PRIVACY = {"dry_run": "private", "test": "unlisted", "live": "public"}


def _norm_brand(value) -> str:
    if not value:
        return ""
    return str(value).strip().lower().replace(" ", "").replace("-", "_")


def resolve_registry_channel(brand):
    """Map a brand slug to its channel id via ChannelRegistry.json (no framework imports)."""
    if not brand:
        return None
    try:
        import json as _json

        registry = _json.loads((ROOT / "ChannelRegistry.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    slug = _norm_brand(brand)
    for channel in registry.get("channels", []):
        if _norm_brand(channel.get("brand")) == slug:
            return channel.get("youtube_channel_id")
    return None


def _load_package(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_package(filepath: Path, data: dict) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def queue_dir() -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    return QUEUE_DIR


def pending_packages(brand: str | None = None, dedupe: bool = True, limit: int | None = None) -> list[tuple[Path, dict]]:
    """Return (path, package) for every queue package that is a real, postable draft.

    Newest drafts first. When dedupe=True (default), only the newest draft per
    (brand, title) is considered so back-to-back factory runs do not flood a
    channel with the same rotating titles.
    """
    queue = queue_dir()
    candidates = []
    for filepath in queue.glob("*.json"):
        try:
            package = _load_package(filepath)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ORCH] Skipping unreadable {filepath.name}: {e}")
            continue
        if package.get("status") != STATUS_DRAFT:
            continue
        pkg_brand = resolve_brand(package)
        if brand and _norm_brand(pkg_brand) != _norm_brand(brand):
            continue
        video = resolve_video(package)
        if not video or not Path(video).exists():
            print(f"[ORCH] Skipping draft {filepath.name}: no existing video file.")
            continue
        if not pkg_brand or pkg_brand == "default":
            print(f"[ORCH] Skipping draft {filepath.name}: no brand assigned; cannot pick a channel.")
            continue
        candidates.append((filepath, package))

    candidates.sort(key=lambda item: item[0].stat().st_mtime, reverse=True)

    pending = []
    if dedupe:
        seen: set[tuple[str, str]] = set()
        for filepath, package in candidates:
            key = (resolve_brand(package), (package.get("title") or "").strip())
            if key in seen:
                continue
            seen.add(key)
            pending.append((filepath, package))
    else:
        pending = candidates

    if limit:
        pending = pending[:limit]
    return pending


def resolve_brand(package: dict) -> str:
    return package.get("brand") or package.get("slug") or "default"


def resolve_video(package: dict) -> str:
    for key in ("video_path", "clip_file_path", "video_file", "source", "clip_path"):
        value = package.get(key)
        if value and Path(str(value)).exists():
            return str(value)
    return ""


def _publish_youtube(package: dict, brand: str, video: str, dry_run: bool, privacy_status: str = "public") -> tuple[bool, str | None, str | None]:
    title = (package.get("title") or "Untitled Short")[:100]
    description = (package.get("description") or title)[:5000]
    channel_id = package.get("youtube_channel_id") or resolve_registry_channel(brand)

    # 1) Preferred: OAuth Data API using the brand's own token (no browser needed).
    try:
        from mbm_social import youtube_api_publisher as api

        if dry_run:
            if api.tokens_exist_for(brand):
                print(f"[dry-run] Would publish YouTube '{title}' via OAuth API (brand token found).")
            else:
                print(f"[dry-run] Would publish YouTube '{title}' via OAuth API (NO token -- needs reauth).")
        elif api.tokens_exist_for(brand):
            ok, video_id = api.publish_via_api(video, title, description, brand=brand, channel_id=channel_id, privacy_status=privacy_status)
            if ok and video_id:
                return True, video_id, channel_id
            print(f"[ORCH] OAuth API publish failed for '{title}'; falling back to CDP.")
    except Exception as e:
        print(f"[ORCH] OAuth API publisher unavailable ({e}); continuing with browser paths.")

    # 2) Live native-Chrome session via CDP (no bot flags, logged in already).
    try:
        from mbm_social import youtube_cdp_publisher as cdp

        if not dry_run:
            # Resolve brand display name from ChannelRegistry.json
            brand_display_name = None
            try:
                import json as _json
                registry = _json.loads((ROOT / "ChannelRegistry.json").read_text(encoding="utf-8"))
                slug = _norm_brand(brand)
                for c in registry.get("channels", []):
                    if _norm_brand(c.get("brand")) == slug:
                        brand_display_name = c.get("display_name")
                        break
            except Exception as e:
                print(f"[ORCH] Could not resolve display name: {e}")
            
            ok, video_id, channel_id = cdp.publish_via_cdp(video, title, description, brand_display_name=brand_display_name)

            if ok and video_id:
                return True, video_id, channel_id
            print(f"[ORCH] CDP YouTube publish failed for '{title}'; falling back to Playwright profile.")
        else:
            print(f"[dry-run] Would publish YouTube '{title}' via CDP/native Chrome.")
    except Exception as e:
        print(f"[ORCH] CDP publisher unavailable ({e}) -- falling back to Playwright profile.")

    # 3) Per-brand Playwright persistent profile.
    try:
        from mbm_social import publisher as pw
        if not dry_run:
            ok = pw.upload_to_youtube(video, title, description, brand=brand)
            if isinstance(ok, tuple):
                ok, real_id = ok
            else:
                real_id = None
            if ok and real_id:
                return True, real_id, None
            print(f"[ORCH] Playwright profile publish did not confirm a real video id for '{title}'.")
        else:
            print(f"[dry-run] Would publish YouTube '{title}' via brand profile '{brand}'.")
    except Exception as e:
        print(f"[ORCH] Playwright publisher error: {e}")
    return False, "", None


def _publish_social(package: dict, brand: str, dry_run: bool) -> dict[str, bool]:
    """Cross-post to Instagram Reels + TikTok. Returns platform -> success."""
    results: dict[str, bool] = {}
    try:
        from mbm_social import shortform_publisher as sf

        platforms = ["instagram", "tiktok"]
        if dry_run:
            for platform in platforms:
                results[platform] = False
            print(f"[dry-run] Would cross-post '{package.get('title')}' to {platforms}.")
            return results
        results = sf.publish(package, platforms=platforms, _brand=brand)
    except Exception as e:
        print(f"[ORCH] Short-form publisher unavailable ({e}); skipping IG/TikTok.")
        for platform in ("instagram", "tiktok"):
            results[platform] = False
    return results


def publish_package(filepath: Path, package: dict, dry_run: bool = False, mode: str = "dry_run") -> dict:
    brand = resolve_brand(package)
    video = resolve_video(package)
    title = package.get("title") or "Untitled Short"

    # Mode enforcement
    if mode == "dry_run":
        dry_run = True
        privacy_status = "private"
    elif mode == "test":
        dry_run = False
        privacy_status = "unlisted"
        package["publish_visibility"] = "unlisted"
        package["publish_mode"] = "test"
    elif mode == "live":
        dry_run = False
        privacy_status = "public"
        package["publish_visibility"] = "public"
        package["publish_mode"] = "live"
    else:
        print(f"[ORCH] Unknown mode '{mode}', defaulting to dry_run.")
        dry_run = True
        privacy_status = "private"

    print(f"[ORCH] Processing [{brand}] (mode={mode}): '{title}' ({filepath.name})")

    yt_ok, yt_id, yt_channel = _publish_youtube(package, brand, video, dry_run, privacy_status=privacy_status)
    social = _publish_social(package, brand, dry_run)

    published_platforms: dict[str, bool] = {}
    if yt_ok:
        published_platforms["youtube"] = True
        package["youtube_video_id"] = yt_id
        package["youtube_url"] = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else ""
        if yt_channel:
            package["youtube_channel_id"] = yt_channel
    else:
        published_platforms["youtube"] = False
    for platform, ok in social.items():
        published_platforms[platform] = bool(ok)

    package["published_platforms"] = published_platforms
    package["publish_mode"] = mode

    if any(published_platforms.values()):
        package["status"] = STATUS_PUBLISHED
        package["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[ORCH] PUBLISHED ({mode}) {brand}: {published_platforms}")
    else:
        package["status"] = STATUS_DRAFT
        print(f"[ORCH] No real post succeeded for '{title}' -- kept as draft. "
              "Check brand logins (Chrome @9222 or Playwright profiles).")

    if not dry_run:
        _save_package(filepath, package)
    return package


def publish_all(brand: str | None = None, dry_run: bool = False, limit: int | None = None, dedupe: bool = True, mode: str = "dry_run") -> dict:
    pending = pending_packages(brand, dedupe=dedupe, limit=limit)
    print(f"[ORCH] Found {len(pending)} postable draft package(s) in publish_queue (mode={mode}).")
    summary = {
        "processed": 0,
        "published": 0,
        "skipped_drafts": 0,
        "mode": mode,
        "by_platform": {"youtube": 0, "instagram": 0, "tiktok": 0},
        "next_action": "review package statuses for any that require human login",
        "owner": "system",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for filepath, package in pending:
        result = publish_package(filepath, package, dry_run=dry_run, mode=mode)
        summary["processed"] += 1
        if result.get("status") == STATUS_PUBLISHED:
            summary["published"] += 1
            for platform, ok in result.get("published_platforms", {}).items():
                if ok:
                    summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1
        else:
            summary["skipped_drafts"] += 1
    print(f"[ORCH] Done ({mode}): {summary['published']}/{summary['processed']} published "
          f"(YouTube {summary['by_platform']['youtube']}, IG {summary['by_platform']['instagram']}, "
          f"TikTok {summary['by_platform']['tiktok']}).")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MBM-Social authoritative publisher.")
    parser.add_argument("--brand", help="Only publish packages for this brand slug.")
    parser.add_argument("--dry-run", action="store_true", help="Alias for --mode dry_run.")
    parser.add_argument("--mode", choices=PUBLISH_MODES, default=PUBLISH_MODE,
                        help=f"Publish mode: dry_run (validate only), test (unlisted), live (public). Default: $PUBLISH_MODE={PUBLISH_MODE}")
    parser.add_argument("--limit", type=int, default=None, help="Post at most N newest drafts.")
    parser.add_argument("--no-dedupe", action="store_true", help="Post every draft, even identical brand/title repeats.")
    args = parser.parse_args(argv)

    mode = args.mode
    if args.dry_run:
        mode = "dry_run"

    # Safety gate: never allow live mode unless explicitly set
    if mode == "live" and os.getenv("PUBLISH_MODE") != "live":
        print("[ORCH] BLOCKED: --mode live requires PUBLISH_MODE=live env var. Use --mode test for safe testing.")
        return 2

    dry_run = (mode == "dry_run")
    summary = publish_all(brand=args.brand, dry_run=dry_run, limit=args.limit, dedupe=not args.no_dedupe, mode=mode)
    return 0 if dry_run else (0 if not summary["skipped_drafts"] else 1)


if __name__ == "__main__":
    sys.exit(main())