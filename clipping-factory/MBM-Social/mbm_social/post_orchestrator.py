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
STATUS_PUBLISH_PENDING = "publish_pending_verification"
STATUS_VERIFY_FAILED = "verify_failed"
STATUS_BLOCKED_QUALITY_GATE = "blocked_quality_gate"
STATUS_PUBLISHED_IDENTITY_WARNING = "published_identity_warning"
STATUS_PUBLISH_BLOCKED_IDENTITY = "publish_blocked_identity_mismatch"

# Production publish policy: a factory-stamped package MUST carry a virality
# readiness score at or above this threshold before any platform call happens.
VIRALITY_MIN_PUBLISH = 80

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


def pending_packages(brand: str | None = None, dedupe: bool = True, limit: int | None = None,
                     production_only: bool = True) -> list[tuple[Path, dict]]:
    """Return (path, package) for every queue package that is a real, postable draft.

    Newest drafts first. When dedupe=True (default), only the newest draft per
    (brand, title) is considered so back-to-back factory runs do not flood a
    channel with the same rotating titles.

    When production_only=True (default), only REAL_PRODUCTION items are
    returned.  Set False to see all drafts regardless of classification.
    """
    queue = queue_dir()
    candidates = []
    skipped = {"legacy": 0, "test": 0, "invalid_identity": 0, "duplicate": 0, "stale": 0}
    for filepath in queue.glob("*.json"):
        try:
            package = _load_package(filepath)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ORCH] Skipping unreadable {filepath.name}: {e}")
            continue
        if not isinstance(package, dict):
            continue
        if package.get("status") != STATUS_DRAFT:
            continue
        # Queue item classification
        qclass = classify_queue_item(package)
        if qclass != QUEUE_CLASS_REAL_PRODUCTION:
            skipped[qclass.lower()] = skipped.get(qclass.lower(), 0) + 1
            if production_only:
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

    if production_only and any(v > 0 for v in skipped.values()):
        print(f"[ORCH] Queue classification: skipped {sum(skipped.values())} non-production items "
              f"(legacy={skipped.get('legacy',0)}, test={skipped.get('test',0)}, "
              f"invalid_identity={skipped.get('invalid_identity',0)}, "
              f"duplicate={skipped.get('duplicate',0)}, stale={skipped.get('stale',0)})")

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


# ── Queue item classification ──────────────────────────────────────────
# Every queue item is classified into one of the explicit production
# categories.  Only REAL_PRODUCTION items may be consumed by the
# publisher.  All others are skipped with a reason logged.

QUEUE_CLASS_REAL_PRODUCTION = "REAL_PRODUCTION"
QUEUE_CLASS_LEGACY_DRAFT = "LEGACY"
QUEUE_CLASS_TEST = "TEST"
QUEUE_CLASS_INVALID_IDENTITY = "INVALID_IDENTITY"
QUEUE_CLASS_DUPLICATE = "DUPLICATE"
QUEUE_CLASS_STALE = "STALE"


def classify_queue_item(package: dict) -> str:
    """Classify a queue package into its production category.

    Classification is based on explicit fields:
      - test:true → TEST (never enters production accounting)
      - status contains "invalid_identity" → INVALID_IDENTITY
      - status contains "duplicate" → DUPLICATE
      - brand not in known production set → LEGACY
      - source_system present and status=draft → REAL_PRODUCTION
      - no source_system → LEGACY (factory drafts without provenance)
      - age > 7 days and no virality_gate stamp → STALE
    """
    if package.get("test") is True:
        return QUEUE_CLASS_TEST

    status = (package.get("status") or "").lower()
    if "invalid_identity" in status:
        return QUEUE_CLASS_INVALID_IDENTITY
    if "duplicate" in status:
        return QUEUE_CLASS_DUPLICATE

    brand = _norm_brand(package.get("brand") or "")
    KNOWN_PRODUCTION_BRANDS = {
        _norm_brand(b) for b in [
            "clippingfactorymbm", "twistsrevealed", "cutedosage",
            "dontwatchthis", "goalmachinez",
        ]
    }

    if brand and brand not in KNOWN_PRODUCTION_BRANDS:
        return QUEUE_CLASS_LEGACY_DRAFT

    # Check staleness early: old items without a virality gate are stale
    # regardless of source_system (real clips always get a virality stamp)
    if not package.get("virality_gate"):
        created = package.get("created_at") or package.get("publish_pending_at")
        if created:
            try:
                from datetime import datetime, timezone
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).days
                if age_days > 7:
                    return QUEUE_CLASS_STALE
            except (ValueError, TypeError):
                pass

    if package.get("source_system") and status == "draft":
        return QUEUE_CLASS_REAL_PRODUCTION

    if not package.get("source_system"):
        return QUEUE_CLASS_LEGACY_DRAFT

    return QUEUE_CLASS_REAL_PRODUCTION


def resolve_video(package: dict) -> str:
    for key in ("video_path", "clip_file_path", "video_file", "source", "clip_path"):
        value = package.get(key)
        if value and Path(str(value)).exists():
            return str(value)
    return ""


def evaluate_quality_gate(package: dict) -> dict:
    """Enforce the virality publish gate for packages that carry virality_gate.

    Packages without the gate stamp (legacy/filler drafts) are allowed through
    here; factory-produced packages always stamp it, so sub-80 content can
    never reach a platform call. Unknown score = blocked (never guessed).
    """
    gate = package.get("virality_gate")
    if not gate:
        return {"allowed": True, "reason": "no_gate_stamp"}
    threshold = int(gate.get("min_score", VIRALITY_MIN_PUBLISH))
    score = (package.get("virality") or {}).get("score")
    if score is None:
        return {"allowed": False, "reason": "virality_score_missing",
                "threshold": threshold, "score": None}
    if int(score) < threshold:
        return {"allowed": False, "reason": "below_virality_threshold",
                "threshold": threshold, "score": int(score)}
    return {"allowed": True, "reason": "virality_gate_passed",
            "threshold": threshold, "score": int(score)}


def _validate_hard_channel_routing(package: dict, brand: str, binding) -> dict:
    """Hard channel routing guard for TWO-CHANNEL production.

    Enforces immutable brand/channel identity before ANY platform call.
    Required fields (pre-publish): brand, channel_id, channel_handle (if present),
    campaign_id/artifact lineage, source identity. Also enforces content
    category allowlist via CampaignRouter exclude_topics and virality threshold.

    Returns {"allowed": bool, "reason": str, "details": str}.
    On failure, caller must set STATUS=BLOCKED, reason=CHANNEL_IDENTITY_MISMATCH
    and never publish.
    """
    slug = _norm_brand(brand)
    pkg_brand = _norm_brand(resolve_brand(package))
    details: list[str] = []

    # 1) Brand must be present and match the publishing target (no cross-queue)
    if not slug or slug == "default":
        return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH", "details": "publishing brand missing/default"}
    if pkg_brand != slug:
        return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                "details": f"package brand '{pkg_brand}' != publishing brand '{slug}' (cross-channel blocked)"}

    # 2) Channel ID consistency: package-declared channel must match registry binding
    if binding is not None:
        cfg_id = getattr(binding, "configured_channel_id", "") or ""
        cfg_handle = getattr(binding, "configured_handle", "") or ""
        pkg_cid = package.get("youtube_channel_id") or package.get("channel_id") or package.get("channelId") or ""
        if pkg_cid and cfg_id and pkg_cid != cfg_id:
            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                    "details": f"package channel_id '{pkg_cid}' != registered '{cfg_id}' for brand '{slug}'"}
        pkg_handle = package.get("handle") or package.get("channel_handle") or package.get("channelHandle") or ""
        if pkg_handle and cfg_handle:
            # normalize handles for comparison (@ prefix optional, case-insensitive)
            nh_pkg = pkg_handle.strip().lower().lstrip("@")
            nh_cfg = cfg_handle.strip().lower().lstrip("@")
            if nh_pkg != nh_cfg:
                return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                        "details": f"package handle '@{nh_pkg}' != registered '@{nh_cfg}' for brand '{slug}'"}
        # Token channel must match configured (already checked in resolver, but re-assert)
        tok_id = getattr(binding, "token_channel_id", "") or ""
        if tok_id and cfg_id and tok_id != cfg_id:
            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                    "details": f"token channel '{tok_id}' != configured '{cfg_id}' for brand '{slug}'"}

    # 3) Immutable lineage: campaign/package must carry stable identity
    # Require at least one of campaign_id/id/artifact lineage for production
    has_campaign = bool(package.get("campaign_id") or package.get("origin_campaign_id") or package.get("id"))
    has_artifact = bool(package.get("artifact_dir") or package.get("artifact_id") or package.get("video") or package.get("video_path") or package.get("video_file"))
    has_source = bool(package.get("source_system") or package.get("provenance") or package.get("source_uri") or package.get("source_identifier") or package.get("source_id"))
    # For REAL_PRODUCTION packages, all three should be present; for legacy we already filtered
    # but hard check ensures no anonymous package slips through
    if package.get("source_system") == "clipping_factory":
        if not has_campaign:
            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH", "details": "missing campaign_id for clipping_factory package"}
        if not has_source:
            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH", "details": "missing source identity for clipping_factory package"}
        if not has_artifact:
            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH", "details": "missing artifact/video lineage for clipping_factory package"}

    # 4) Content category allowlist: enforce CampaignRouter exclude_topics
    # Cute content must not go to Twists and vice versa. Uses title+description+tags+script.
    try:
        from mbm_social.brand_config import load_campaign_router
        router = load_campaign_router()
        rules = {r.get("brand"): r for r in router.get("rules", [])}
        rule = rules.get(slug, {})
        exclude = [e.lower() for e in rule.get("exclude_topics", [])]
        if exclude:
            text_parts = [
                package.get("title") or "",
                package.get("description") or "",
                " ".join(package.get("tags") or []),
                package.get("script") or package.get("niche") or "",
                package.get("theme") or "",
            ]
            text = " ".join(text_parts).lower()
            # For twistsrevealed, block cute/baby/pet/sports content; for cutedosage, block dark/horror/suspense/sports
            for topic in exclude:
                # Only block on strong keyword presence (whole word or phrase)
                if topic and topic in text:
                    # Require at least one strong signal; avoid false positives on short words
                    if len(topic) >= 4:
                        details.append(f"content contains excluded topic '{topic}' for brand '{slug}'")
                        # For two-channel strict isolation, immediate block on cross-category
                        # twistsrevealed exclude: sports,cute,baby,tutorial -> cute dosage content
                        # cutedosage exclude: dark,crime,suspense,sports -> twist content
                        # We block when the text is strongly in the excluded set AND also matches the other brand's eligible
                        # To avoid over-blocking, check if the package's theme/niche also signals cross-brand
                        other_brand = "cutedosage" if slug == "twistsrevealed" else "twistsrevealed" if slug == "cutedosage" else None
                        if other_brand and other_brand in ["twistsrevealed", "cutedosage"]:
                            # If topic is in the other brand's core keywords, treat as hard cross-block
                            other_rule = rules.get(other_brand, {})
                            other_eligible = [e.lower() for e in other_rule.get("eligible_topics", [])]
                            if topic in other_eligible or any(t in text for t in other_eligible):
                                return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                                        "details": f"content category '{topic}' not allowed for brand '{slug}' (cross-channel blocked)"}
                        # For remaining excludes, flag but allow if not cross-brand core
                        # (e.g., twistsrevealed tutorial exclusion on non-tutorial content should not block)
                        # So we only block when the hard channel mismatch above is met; otherwise warn but pass
                        # For safety, we treat any hard exclude hit as BLOCK for two-channel production
                        # to prevent any cute content entering twists queue etc.
                        # Uncomment to enforce strict: return block
                        # For now, enforce strict for the two target brands only
                        if slug in ("twistsrevealed", "cutedosage"):
                            # Enforce strict category isolation for the two production channels
                            return {"allowed": False, "reason": "CHANNEL_IDENTITY_MISMATCH",
                                    "details": f"content category '{topic}' not allowed for brand '{slug}' (cross-channel blocked)"}
    except Exception as e:
        # Routing config missing should not silently pass cross-channel content
        details.append(f"router check skipped: {e}")

    return {"allowed": True, "reason": "hard_routing_passed", "details": "; ".join(details) if details else "identity and category validated"}


def _publish_youtube(package: dict, brand: str, video: str, dry_run: bool, privacy_status: str = "public", mode: str = "dry_run") -> tuple[bool, str | None, str | None]:
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
            # allow_public only when explicitly in live mode
            allow_pub = (mode == "live")
            ok, video_id = api.publish_via_api(video, title, description, brand=brand, channel_id=channel_id,
                                               privacy_status=privacy_status, allow_public=allow_pub)
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
            ok = pw.upload_to_youtube(video, title, description, brand=brand, privacy_status=privacy_status)
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


def _write_post_publish_artifacts(package: dict, brand: str, video_id: str, verification: dict | None, queue_filepath: Path, mode: str) -> None:
    """Write publication receipt + analytics ledger + learning placeholder after verified publish.

    Every real publication must produce:
      - publication_id, video_id, brand, channel_id, campaign_id, artifact_id, published_at, analytics_status=PENDING
    Verification is already done. Analytics remain PENDING until provider supplies real metrics.
    Learning stays blocked until actual metrics exist.
    """
    try:
        channel_id = package.get("youtube_channel_id") or package.get("channel_id") or resolve_registry_channel(brand) or ""
        # Resolve handle for ledger
        handle = ""
        try:
            reg = json.loads((ROOT / "ChannelRegistry.json").read_text(encoding="utf-8"))
            for c in reg.get("channels", []):
                if _norm_brand(c.get("brand")) == _norm_brand(brand):
                    handle = c.get("handle") or ""
                    break
        except Exception:
            handle = ""
        campaign_id = package.get("campaign_id") or package.get("origin_campaign_id") or package.get("id") or "unknown"
        artifact_id = package.get("artifact_id") or package.get("artifact_dir") or ""
        if artifact_id and "/" in str(artifact_id):
            artifact_id = str(Path(str(artifact_id)).name)
        source_id = package.get("source_identifier") or package.get("source_id") or package.get("source_uri") or ""
        publication_id = video_id
        published_at = package.get("published_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1) Artifact-level receipt (if artifact_dir exists)
        artifact_dir = package.get("artifact_dir")
        if artifact_dir and Path(str(artifact_dir)).exists():
            try:
                ad = Path(str(artifact_dir))
                receipt = {
                    "campaign_id": campaign_id,
                    "artifact_dir": str(artifact_dir),
                    "artifact_id": artifact_id or ad.name,
                    "final_mp4": package.get("video") or package.get("video_path") or "",
                    "qa_creative_score": (package.get("quality") or {}).get("creative_score"),
                    "virality_readiness": (package.get("virality") or {}).get("score"),
                    "virality_threshold": (package.get("virality") or {}).get("threshold") or VIRALITY_MIN_PUBLISH,
                    "queue_package": queue_filepath.name,
                    "publisher": "mbm_social.post_orchestrator (authoritative)",
                    "platform": "youtube",
                    "platform_post_id": video_id,
                    "publication_id": publication_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                    "brand": brand,
                    "channel_id": channel_id,
                    "channel_handle": handle,
                    "source_id": source_id,
                    "verification_method": (verification or {}).get("method", "oembed_public"),
                    "verification_checks": (verification or {}).get("checks", {}),
                    "verification": verification or {},
                    "analytics_id": f"VID-{video_id}" if video_id else "",
                    "analytics_status": "PENDING",
                    "analytics_note": "metrics remain null until a real analytics provider runs",
                    "learning_record": "learning_data.json (metrics None - learning blocked until actual metrics exist)",
                    "learning_blocked": True,
                    "learning_block_reason": "no real analytics yet (PENDING)",
                    "published_at": published_at,
                    "publish_mode": mode,
                }
                (ad / "publish_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
                print(f"[ORCH] Receipt written: {ad / 'publish_receipt.json'}")
            except Exception as e:
                print(f"[ORCH] Receipt write skipped: {e}")

        # 2) Analytics ledger (YouTubeAnalytics/videos.jsonl) — always PENDING initially
        try:
            from mbm_social.youtube_analytics import VideoLedger, Video
            ledger = VideoLedger()
            # Use VID- prefix for internal id, keep youtube id as publication_id
            vid_internal = f"VID-{video_id}" if video_id and not video_id.startswith("VID-") else (video_id or f"VID-{campaign_id}")
            # Avoid duplicate ledger entry for same video_id
            existing = ledger.get(vid_internal)
            if not existing:
                # Prefer handle/channel for channel field, but also store channel_id
                channel_label = handle or channel_id or brand
                video = Video(
                    video_id=vid_internal,
                    channel=channel_label,
                    brand=brand,
                    upload_status="uploaded",
                    scheduled_for=None,
                    publication_id=publication_id,
                    publication_url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                    created_iso=published_at,
                    analytics={},
                )
                ledger.append(video)
                # Patch in extended lineage + PENDING status (VideoLedger stores analytics dict)
                row = ledger.get(vid_internal)
                if row is not None:
                    row["channel_id"] = channel_id
                    row["campaign_id"] = campaign_id
                    row["artifact_id"] = artifact_id
                    row["source_id"] = source_id
                    row["analytics_status"] = "PENDING"
                    row["analytics_note"] = "metrics remain null until a real analytics provider runs"
                    row["learning_blocked"] = True
                    ledger.update(row)
                print(f"[ORCH] Analytics ledger PENDING: {vid_internal} -> {brand}/{channel_id}")
            else:
                print(f"[ORCH] Ledger entry exists for {vid_internal}, skipping duplicate.")
        except Exception as e:
            print(f"[ORCH] Analytics ledger write skipped: {e}")

        # 3) Package-level publication receipt fields (for queue file auditing)
        package["publication_id"] = publication_id
        package["artifact_id"] = artifact_id
        package["source_id"] = source_id
        package["channel_handle"] = handle
        package["channel_id"] = channel_id
        if channel_id:
            package["youtube_channel_id"] = channel_id
        package["analytics_status"] = "PENDING"

        # 4) ContentRewards attribution (unified revenue ledger)
        # Every verified publish gets a deterministic tracking record that ties
        # content_id -> campaign -> tracking_id -> publish_id -> revenue.
        # This is the MBM Social -> ContentRewards handoff.
        try:
            from mbm_social.tracking import build_tracking_context, record_publish_event
            from mbm_social.content_rewards import (
                normalize_campaign,
                estimate_forecast,
                plan_campaigns,
                submit,
                RevenueLedger,
                economics_event,
            )
            tctx = build_tracking_context(package)
            event = record_publish_event(package, video_id, channel_id, verification)
            # Write unified attribution record (inspectable, deterministic)
            attrib_dir = ROOT / "ContentRewards"
            attrib_dir.mkdir(parents=True, exist_ok=True)
            attrib_path = attrib_dir / f"attribution_{tctx['tracking_id']}.json"
            if not attrib_path.exists():
                # Build full attribution payload
                payload = {
                    **event,
                    "publisher": "mbm_social.post_orchestrator",
                    "queue_package": queue_filepath.name,
                    "artifact_id": artifact_id,
                    "verification": verification or {},
                    "mode": mode,
                    "attribution_created_at": published_at,
                }
                # Add economics forecast if campaign is ContentRewards-eligible
                try:
                    camp = package_to_campaign = None
                    # Try to build a Campaign for economics scoring
                    from mbm_social.tracking import package_to_content_rewards_campaign
                    camp = package_to_content_rewards_campaign(package)
                    if camp is not None:
                        forecast = estimate_forecast(camp)
                        payload["economics"] = {
                            "estimated_views": forecast.estimated_views,
                            "basis": forecast.basis,
                            "confidence": forecast.confidence,
                            "rpm_estimate_usd": forecast.rpm_estimate_usd,
                            "expected_net_revenue_usd": forecast.expected_net_revenue_usd,
                            "net_per_min": forecast.net_revenue_per_production_minute_usd,
                        }
                except Exception:
                    pass
                attrib_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"[ORCH] Attribution record: {attrib_path.name} -> {tctx['campaign']} ({tctx['tracking_id']})")

            # Also append to ContentRewards revenue ledger (estimated vs actual kept separate)
            try:
                from mbm_social.content_rewards import RevenueLedger, normalize_campaign, estimate_forecast
                from pathlib import Path as _P
                ledger = RevenueLedger(path=ROOT / "ContentRewards" / "ledger.jsonl")
                # Check duplicate: if tracking_id already in ledger, skip
                existing = None
                for row in ledger._load():
                    if row.get("submission_id") == tctx["tracking_id"] or row.get("campaign_id") == tctx["content_id"]:
                        existing = row
                        break
                if not existing:
                    camp = None
                    try:
                        from mbm_social.tracking import package_to_content_rewards_campaign
                        camp = package_to_content_rewards_campaign(package)
                    except Exception:
                        pass
                    if camp is not None:
                        forecast = estimate_forecast(camp)
                        # Use tracking_id as submission_id for deterministic dedup
                        from mbm_social.content_rewards import _ledger_row
                        import uuid
                        row = _ledger_row(camp, forecast, tctx["tracking_id"], "submitted")
                        # Override submission_id to be our deterministic tracking_id and set platform/channel
                        row.submission_id = tctx["tracking_id"]
                        row.platform = "youtube"
                        row.asset_id = artifact_id or tctx["clip_id"]
                        # Append with our deterministic IDs
                        ledger.path.parent.mkdir(parents=True, exist_ok=True)
                        # Use ledger.append but ensure deterministic tracking_id
                        # Build row dict manually to preserve tracking_id
                        data = row.as_dict()
                        data["submission_id"] = tctx["tracking_id"]
                        data["publish_id"] = video_id
                        data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                        data["tracking_link"] = tctx["tracking_link"]
                        data["channel_id"] = channel_id
                        # Append manually (ledger.append creates new uuid row_id)
                        import csv
                        ledger.path.parent.mkdir(parents=True, exist_ok=True)
                        # Use internal _load/_write to avoid overwriting
                        rows = ledger._load()
                        rows.append(data)
                        ledger.path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
                        print(f"[ORCH] ContentRewards ledger appended: {tctx['tracking_id']} ({tctx['content_id']})")
            except Exception as le:
                print(f"[ORCH] ContentRewards ledger skipped: {le}")

        except Exception as e:
            print(f"[ORCH] ContentRewards attribution skipped: {e}")

    except Exception as e:
        print(f"[ORCH] post-publish artifacts skipped: {e}")


def _publish_social(package: dict, brand: str, dry_run: bool, mode: str = "dry_run") -> dict[str, bool]:
    """Cross-post to Instagram Reels + TikTok. Returns platform -> success.

    TEST mode: Instagram and TikTok have no unlisted/private sandbox endpoint.
    All test-mode social publishes are SKIPPED (not silently faked).
    """
    results: dict[str, bool] = {}
    platforms = ["instagram", "tiktok"]
    if dry_run:
        for platform in platforms:
            results[platform] = False
        print(f"[dry-run] Would cross-post '{package.get('title')}' to {platforms}.")
        return results
    # TEST mode: IG/TikTok have no sandbox/test endpoint — skip entirely
    if mode == "test":
        for platform in platforms:
            results[platform] = False
        print(f"[ORCH] TEST mode: skipping IG/TikTok cross-post for '{package.get('title')}' "
              "(no sandbox/test endpoint available).")
        return results
    try:
        from mbm_social import shortform_publisher as sf
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

    gate = evaluate_quality_gate(package)
    if not gate["allowed"]:
        package["status"] = STATUS_BLOCKED_QUALITY_GATE
        package["quality_gate"] = {**gate,
                                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        print(f"[ORCH] BLOCKED_QUALITY_GATE [{brand}]: {gate['reason']} "
              f"(score={gate.get('score')} < threshold={gate.get('threshold')}). "
              "Rewrite/regenerate required -- no platform call attempted.")
        if not dry_run:
            _save_package(filepath, package)
        return package

    # ── Identity binding gate: ONE brand → ONE channel → ONE token ────
    # Resolve before ANY platform call.  On MISMATCH/INVALID_AUTH/BLOCKED,
    # the package is held — no upload is attempted.
    try:
        from mbm_social.brand_identity_resolver import resolve_brand_binding
        binding = resolve_brand_binding(brand, live_check=(not dry_run))
        package["brand_binding"] = binding.to_dict()
        if binding.should_block:
            package["status"] = STATUS_PUBLISH_BLOCKED_IDENTITY
            package["publish_blocked_reason"] = f"identity_{binding.binding_status.lower()}"
            package["publish_blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[ORCH] PUBLISH_BLOCKED_IDENTITY [{brand}]: "
                  f"binding_status={binding.binding_status} — {binding.error}. "
                  "No platform call attempted. Founder re-auth required.")
            if not dry_run:
                _save_package(filepath, package)
            return package
        if binding.binding_status == "VALID":
            print(f"[ORCH] Identity binding OK [{brand}]: "
                  f"channel={binding.configured_channel_id}")
    except Exception as _ie:
        print(f"[ORCH] brand identity resolver unavailable ({_ie}) -- proceeding with caution")
        binding = None

    # ── HARD CHANNEL ROUTING (TWO-CHANNEL PRODUCTION) ──────────────────
    # Every package must carry immutable brand/channel identity. Before any
    # platform call, enforce:
    #   - package.brand is valid and matches the publishing brand
    #   - package.channel_id (youtube_channel_id) matches registered brand channel
    #   - OAuth token channel matches configured channel (via binding)
    #   - content category is allowed for that brand (exclude_topics guard)
    #   - required immutable fields present: brand, channel_id/handle, campaign/artifact lineage
    # If ANY check fails: STATUS=BLOCKED, reason=CHANNEL_IDENTITY_MISMATCH, never publish.
    hard = _validate_hard_channel_routing(package, brand, binding)
    if not hard["allowed"]:
        package["status"] = STATUS_PUBLISH_BLOCKED_IDENTITY
        package["publish_blocked_reason"] = hard["reason"]
        package["publish_blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        package["hard_routing_check"] = hard
        print(f"[ORCH] BLOCKED CHANNEL_IDENTITY_MISMATCH [{brand}]: {hard['reason']}. "
              f"Details: {hard.get('details','')}. No platform call attempted.")
        if not dry_run:
            _save_package(filepath, package)
        return package

    # ── TRACKING INJECTION (CONTENT -> DISTRIBUTION -> TRACKING LINK) ────
    # Every package gets a deterministic tracking identity BEFORE any publish.
    # This is the glue between Clipping Factory -> MBM Social -> ContentRewards.
    # Idempotent: safe to call twice, safe on retry.
    try:
        from mbm_social.tracking import build_tracking_context, inject_tracking_into_description
        tctx = build_tracking_context(package)
        inject_tracking_into_description(package, tctx)
        # Persist tracking fields immediately so retry is idempotent
        package["tracking_context"] = tctx
        package["tracking_id"] = tctx["tracking_id"]
        package["tracking_link"] = tctx["tracking_link"]
        package["neteller_link"] = tctx["neteller_link"]
        package["content_id"] = tctx["content_id"]
        package["campaign"] = tctx["campaign"]
        # Attribution stamp: links are now inspectable in the queue file
        if not dry_run:
            _save_package(filepath, package)
        print(f"[ORCH] Tracking injected [{brand}]: tracking_id={tctx['tracking_id']} campaign={tctx['campaign']}")
        print(f"[ORCH] Tracking link: {tctx['tracking_link'][:80]}...")
    except Exception as te:
        print(f"[ORCH] Tracking injection skipped ({te}) -- proceeding without tracking")

    yt_ok, yt_id, yt_channel = _publish_youtube(package, brand, video, dry_run, privacy_status=privacy_status, mode=mode)
    social = _publish_social(package, brand, dry_run, mode=mode)

    verification: dict | None = None
    if yt_ok and yt_id and not dry_run:
        try:
            from mbm_social import youtube_api_publisher as _api
            verification = _api.verify_upload(
                yt_id, brand=brand, channel_id=yt_channel,
                expected_title=(package.get("title") or "Untitled Short")[:100],
                privacy_status=privacy_status)
        except Exception as e:
            verification = {"verified": False, "error": str(e)}
        # Identity-intent audit: the brand label we targeted vs the channel the
        # platform says actually received the upload. Upload-scope tokens cannot
        # self-report their channel, so this comparison is the ONLY reliable
        # binding check -- and it has already caught one scrambled mapping.
        try:
            reg_handle = ""
            registry = json.loads((ROOT / "ChannelRegistry.json").read_text(encoding="utf-8"))
            for c in registry.get("channels", []):
                if _norm_brand(c.get("brand")) == _norm_brand(brand):
                    reg_handle = (c.get("handle") or "").lower()
                    break
            actual_handle = (verification.get("actual_author_handle") or "").lower()
            if actual_handle and reg_handle and actual_handle != reg_handle:
                verification["identity_mismatch"] = {
                    "intended_brand": brand,
                    "intended_handle": reg_handle,
                    "actual_author_handle":
                        verification.get("actual_author_handle") or actual_handle,
                    "note": ("token-to-channel binding differs from registry label; "
                             "content landed on the actual author channel above")}
        except Exception as _ie:
            print(f"[ORCH] identity audit skipped: {_ie}")
        package["verification"] = verification
        if verification and not verification.get("verified"):
            print(f"[ORCH] VERIFY_FAILED for {yt_id}: "
                  f"{verification.get('error') or verification.get('checks')}")

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
        # If YouTube succeeded but has no video ID, it submitted but cannot be verified
        # → PUBLISH_PENDING_VERIFICATION (prevents auto-retry / duplicate upload)
        if yt_ok and not yt_id:
            package["status"] = STATUS_PUBLISH_PENDING
            package["publish_pending_reason"] = "submitted_without_verified_id"
            package["publish_pending_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[ORCH] PUBLISH_PENDING_VERIFICATION ({mode}) {brand}: "
                  "upload submitted but video ID not extracted. Will verify before retry.")
        elif verification is not None and not verification.get("verified"):
            # Real upload happened, but the platform response did not confirm
            # channel/title/privacy/state. Never claim verified on local say-so.
            package["status"] = STATUS_VERIFY_FAILED
            print(f"[ORCH] VERIFY_FAILED ({mode}) {brand}: video_id={yt_id} "
                  "kept unverified -- human review required.")
        elif verification is not None and verification.get("identity_mismatch"):
            # Platform-verified real post on a channel other than the brand
            # label. Real identity captured; binding repair flagged, never hidden.
            package["status"] = STATUS_PUBLISHED_IDENTITY_WARNING
            package["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[ORCH] PUBLISHED_WITH_IDENTITY_WARNING ({mode}) {brand}: "
                  f"{yt_id} landed on {verification['identity_mismatch']['actual_author_handle']} "
                  "(platform-verified). Founder re-auth required to fix bindings.")
            _write_post_publish_artifacts(package, brand, yt_id, verification, filepath, mode)
        else:
            package["status"] = STATUS_PUBLISHED
            package["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[ORCH] PUBLISHED ({mode}) {brand}: {published_platforms}")
            _write_post_publish_artifacts(package, brand, yt_id, verification, filepath, mode)
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
        "identity_blocked": 0,
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
        elif result.get("status") == STATUS_PUBLISH_BLOCKED_IDENTITY:
            summary["identity_blocked"] += 1
        else:
            summary["skipped_drafts"] += 1
    print(f"[ORCH] Done ({mode}): {summary['published']}/{summary['processed']} published "
          f"(YouTube {summary['by_platform']['youtube']}, IG {summary['by_platform']['instagram']}, "
          f"TikTok {summary['by_platform']['tiktok']}), "
          f"identity_blocked={summary['identity_blocked']}.")
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