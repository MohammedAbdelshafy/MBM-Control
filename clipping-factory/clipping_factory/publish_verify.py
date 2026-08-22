"""
Publish + Verify — YouTube Data API v3.

Real resumable upload using the existing brand OAuth tokens
(MBM-Social/youtube_tokens.json). A publish only counts when the API returns a
real video_id; VERIFIED requires an independent videos.list check proving the
video exists on the expected channel with expected metadata.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests

REPO_ROOT = Path(__file__).parent.parent
TOKENS_FILE = REPO_ROOT / "MBM-Social" / "youtube_tokens.json"
BRAND = "twistsrevealed"

UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
API_BASE = "https://www.googleapis.com/youtube/v3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_brand_credentials(brand: str = BRAND) -> Dict[str, str]:
    data = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    creds = data.get(brand)
    if not creds or not creds.get("refresh_token"):
        raise RuntimeError(f"no OAuth credentials for brand '{brand}'")
    return creds


def _access_token(creds: Dict[str, str]) -> str:
    r = requests.post(creds.get("token_uri", "https://oauth2.googleapis.com/token"), data={
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def _resumable_upload(video_path: Path, meta: Dict[str, Any],
                      access_token: str) -> str:
    """Returns the real video_id. Raises on failure."""
    create = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=meta, timeout=120,
    )
    create.raise_for_status()
    location = create.headers.get("Location")
    if not location:
        raise RuntimeError(f"resumable session missing Location header: {create.status_code}")

    size = video_path.stat().st_size
    offset = 0
    with open(video_path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{size}",
            }
            resp = requests.put(location, data=chunk, headers=headers, timeout=600)
            if resp.status_code in (200, 201):
                body = resp.json()
                vid = body.get("id", "")
                if not vid:
                    raise RuntimeError(f"upload completed without video id: {body}")
                return vid
            if resp.status_code == 308:
                rng = resp.headers.get("Range", "bytes=0-0")
                offset = int(rng.split("-")[1]) + 1
                f.seek(offset)
                continue
            raise RuntimeError(f"upload chunk failed: {resp.status_code} {resp.text[:200]}")
    raise RuntimeError("upload stream ended without completion response")


def verify_video(video_id: str, channel_id: str, title_hint: str,
                 access_token: str) -> Dict[str, Any]:
    """Independent verification via videos.list. Never assumes success."""
    r = requests.get(
        f"{API_BASE}/videos",
        params={"part": "snippet,status", "id": video_id},
        headers={"Authorization": f"Bearer {access_token}"}, timeout=60,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return {"verified": False, "error": "VERIFY_FAILED: video not found by API"}

    sn = items[0].get("snippet", {})
    st = items[0].get("status", {})
    checks = {
        "exists": True,
        "channel_match": (not channel_id) or sn.get("channelId") == channel_id,
        "title_match": title_hint.lower() in (sn.get("title", "").lower()),
        "privacy_status": st.get("privacyStatus", ""),
        "upload_status": st.get("uploadStatus", ""),
    }
    verified = checks["channel_match"] and checks["title_match"] \
        and checks["upload_status"] in ("processed", "uploaded")
    return {"verified": verified, **checks}


def publish_and_verify(package: Dict[str, Any], channel_id: str,
                       brand: str = BRAND) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "failed", "at": _now(), "attempts": []}

    try:
        creds = _load_brand_credentials(brand)
        token = _access_token(creds)

        video_path = Path(package["video"])
        if not video_path.exists():
            result["error"] = f"PUBLISH_FAILED: missing video file {video_path}"
            return result

        privacy = package.get("privacy", "unlisted")
        meta = {
            "snippet": {
                "title": package["title"][:100],
                "description": package["description"][:4900],
                "tags": [t.replace("#", "") for t in package.get("tags", [])][:30],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        video_id = _resumable_upload(video_path, meta, token)
        result["video_id"] = video_id
        url = f"https://www.youtube.com/watch?v={video_id}"
        result["url"] = url
        result["attempts"].append({"step": "upload", "ok": True, "video_id": video_id})

        # post-publish verification against the live platform state
        v = verify_video(video_id, channel_id or creds.get("channel_id", ""),
                         meta["snippet"]["title"], token)
        result["verification"] = v
        result["status"] = "verified" if v.get("verified") else "published"
        result["published_at"] = _now()

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:400]

    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Verify a video is live (no upload)")
    ap.add_argument("video_id")
    args = ap.parse_args()
    creds = _load_brand_credentials()
    print(json.dumps(verify_video(args.video_id, creds.get("channel_id", ""), "",
                                  _access_token(creds)), indent=2))
