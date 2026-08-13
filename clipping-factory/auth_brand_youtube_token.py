"""
Per-Brand YouTube Data API OAuth token generator for MBM-Social.

Each brand's channel is owned by a separate Google account. A refresh token is
scoped to ONE Google account, so every brand needs its OWN OAuth consent flow.
This script runs the flow per brand, VERIFIES the returned token actually owns
the brand's expected channel (channels().list mine=True), and only then saves
it to MBM-Social/youtube_tokens.json -- never clobbering other brands' tokens.

Usage:
  python clipping-factory/auth_brand_youtube_token.py --brand dontwatchthis
  python clipping-factory/auth_brand_youtube_token.py --all        # one browser open per brand
  python clipping-factory/auth_brand_youtube_token.py --verify     # audit existing tokens
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = Path(__file__).parent.resolve()
MBM_SOCIAL_DIR = BASE_DIR / "MBM-Social"
TOKENS_PATH = MBM_SOCIAL_DIR / "youtube_tokens.json"
REGISTRY_PATH = MBM_SOCIAL_DIR / "ChannelRegistry.json"

CLIENT_ID = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
SCOPE = "https://www.googleapis.com/auth/youtube.upload"

BRANDS = ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]


def load_channel_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        print(f"[AUTH] ChannelRegistry not found: {REGISTRY_PATH}")
        return []
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8")).get("channels", [])


def brand_channel(slug: str) -> dict | None:
    for ch in load_channel_registry():
        if ch.get("brand") == slug:
            return ch
    return None


def _load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    try:
        return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tokens(tokens: dict) -> None:
    if TOKENS_PATH.exists():
        backup = TOKENS_PATH.with_suffix(f".json.bak_{int(time.time())}")
        shutil.copy2(TOKENS_PATH, backup)
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    print(f"[AUTH] Saved tokens -> {TOKENS_PATH}")


def _owned_channel_ids(creds) -> list[str]:
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    owned = [c.get("id") for c in resp.get("items", [])]
    return owned


def auth_one_brand(slug: str, force: bool = False) -> bool:
    ch = brand_channel(slug)
    expected_channel = (ch or {}).get("youtube_channel_id")
    owner_email = (ch or {}).get("owned_by", "unknown")
    if not ch:
        print(f"[AUTH] No ChannelRegistry entry for brand '{slug}'. Skipping.")
        return False

    tokens = _load_tokens()
    entry = tokens.get(slug, {})
    if entry.get("refresh_token") and not force:
        res = input(
            f"[AUTH] Brand '{slug}' already has a refresh_token. Re-run consent flow? [y/N] "
        ).strip().lower()
        if res != "y":
            print(f"[AUTH] Skipped {slug} (keep existing token).")
            return True

    print("=" * 70)
    print(f"  YouTube OAuth for brand: {slug}")
    print(f"  Expected channel       : {expected_channel}")
    print(f"  Sign in AS             : {owner_email}")
    print("  Scope                  : " + SCOPE)
    print("=" * 70)

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(
        client_config, scopes=[SCOPE], redirect_uri="http://localhost:8095/"
    )
    flow.run_local_server(port=8095, prompt="consent", access_type="offline")

    print("[AUTH] Verifying the token owns the expected channel...")
    owned = _owned_channel_ids(flow.credentials)
    print(f"[AUTH] Token owns channels: {owned or 'NONE'}")
    if expected_channel and expected_channel not in owned:
        print(
            f"[AUTH] ERROR: token does NOT own {expected_channel}. "
            f"It owns {owned}. You likely signed in as the wrong account. NOT saving."
        )
        return False

    tokens[slug] = {
        "channel_id": expected_channel or (owned[0] if owned else ""),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": flow.credentials.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "access_token": flow.credentials.token,
        "google_account_email": owner_email,
        "last_verified": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_tokens(tokens)
    print(f"[AUTH] SUCCESS: saved distinct refresh token for '{slug}'.")
    return True


def verify_tokens(quiet: bool = False) -> int:
    """Check every brand token actually owns its registered channel. Returns #bad."""
    bad = 0
    tokens = _load_tokens()
    print("=== TOKEN AUDIT ===")
    for slug in BRANDS:
        entry = tokens.get(slug)
        expected = (brand_channel(slug) or {}).get("youtube_channel_id")
        if not entry or not entry.get("refresh_token"):
            print(f"  {slug:22s} MISSING (no token entry)")
            bad += 1
            continue
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials(
                token=entry.get("access_token", ""),
                refresh_token=entry.get("refresh_token"),
                token_uri=entry.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=entry.get("client_id"),
                client_secret=entry.get("client_secret"),
                scopes=[SCOPE],
            )
            creds.refresh(Request())
            owned = _owned_channel_ids(creds)
        except Exception as e:
            print(f"  {slug:22s} FAIL (token invalid/revoked): {e}")
            bad += 1
            continue
        if expected and expected not in owned:
            print(f"  {slug:22s} WRONG CHANNEL  owns={owned} expected={expected}")
            bad += 1
        else:
            print(f"  {slug:22s} OK  owns={owned}")
    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Per-brand YouTube OAuth token manager.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--brand", help="a single brand slug, e.g. dontwatchthis")
    g.add_argument("--all", action="store_true", help="run OAuth for every brand")
    g.add_argument("--verify", action="store_true", help="audit existing tokens")
    parser.add_argument("--force", action="store_true", help="re-run consent even if a token exists")
    args = parser.parse_args(argv)

    if args.verify:
        bad = verify_tokens()
        print(f"\n[AUTH] Audit complete: {bad} bad/missing token(s).")
        return 1 if bad else 0

    brands = BRANDS if args.all else [args.brand]
    results = []
    for slug in brands:
        try:
            ok = auth_one_brand(slug, force=args.force)
        except KeyboardInterrupt:
            print(f"[AUTH] Cancelled during '{slug}'.")
            ok = False
        except Exception as e:
            print(f"[AUTH] Flow error for '{slug}': {e}")
            ok = False
        results.append((slug, ok))

    for slug, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {slug}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())