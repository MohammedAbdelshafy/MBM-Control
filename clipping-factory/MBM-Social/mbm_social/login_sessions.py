"""
login_sessions -- ONE-TIME interactive login for every MBM-Social brand account.

Opens each brand's real Playwright persistent profile in a visible browser and
waits for you to sign in once. The session (cookies/localStorage) is persisted
to the SAME folder `publisher.py` and `shortform_publisher.py` reuse, so after
this runs once the orchestrator can post without any login prompt.

Profiles bootstrapped (per brand):
  - YouTube:     <MBM-Social>/youtube_profile_<brand>/
  - Instagram:   <MBM-Social>/instagram_profile_<brand>/
  - TikTok:      <MBM-Social>/tiktok_profile_<brand>/

Usage:
  python -m mbm_social.login_sessions                      # all brands, all platforms
  python -m mbm_social.login_sessions --brand twistsrevealed
  python -m mbm_social.login_sessions --platform youtube
  python -m mbm_social.login_sessions --check-only         # show which sessions are ready
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from . import brand_config as bc
except ImportError:
    import brand_config as bc

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None
    PWTimeout = TimeoutError  # type: ignore[name-defined]

ROOT = Path(__file__).resolve().parent.parent
BRANDS = ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]

PLATFORM_URLS = {
    "youtube": "https://studio.youtube.com/",
    "instagram": "https://www.instagram.com/",
    "tiktok": "https://www.tiktok.com/",
}
PLATFORM_LABEL = {
    "youtube": "YouTube Studio",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}


def _profile_dir(platform: str, brand: str) -> Path:
    if platform == "youtube":
        return ROOT / f"youtube_profile_{brand}"
    dirs = bc.shortform_session_dirs(brand)
    name = dirs.get(platform) or f"{platform}_profile_{brand}"
    return ROOT / name


def _write_profile_info(platform: str, slug: str, authed: bool) -> None:
    profile = _profile_dir(platform, slug)
    profile.mkdir(parents=True, exist_ok=True)
    handle = bc.social_handles_for_brand(slug).get(platform, "")
    info = {
        "platform": platform,
        "brand": slug,
        "handle": handle,
        "status": "PLAYWRIGHT_READY" if authed else "PENDING_SETUP",
        "logged_in": authed,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (profile / "profile_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")


def _has_real_session(platform: str, slug: str) -> bool:
    """A profile is 'ready' only if we recorded a confirmed logged-in session."""
    profile = _profile_dir(platform, slug)
    if not profile.exists():
        return False
    info = profile / "profile_info.json"
    if info.exists():
        try:
            data = json.loads(info.read_text(encoding="utf-8"))
            if data.get("logged_in") is not None:
                return bool(data.get("logged_in"))
        except Exception:
            pass
    # Legacy fallback: a real browser profile with cookies indicates a session.
    return any((profile / m).exists() for m in ("Default", "Local State", "Cookies"))


def _is_logged_in(page, platform: str) -> bool:
    try:
        url = page.url.lower()
    except Exception:
        return False
    if platform == "youtube":
        if "accounts.google.com" in url:
            return False
        try:
            return page.locator("ytcp-button#upload-button, ytcp-avatar-editor, [aria-label*='create' i]").count() > 0
        except Exception:
            return False
    if platform == "instagram":
        if "login" in url or "accounts.google.com" in url:
            return False
        try:
            # Signed-in nav has no /accounts/login/ link; signed-out page shows it.
            return page.locator("[href*='/accounts/login/']").count() == 0 and page.locator("[href*='/explore/']").count() > 0
        except Exception:
            return False
    if platform == "tiktok":
        if "login" in url or "passport" in url:
            return False
        try:
            # Logged-in TikTok shows the top-right avatar/user chip; signed-out shows a Log in button.
            has_user = page.locator("[data-e2e='user-info'], [data-e2e='top-user-info'], [data-e2e='nav-profile']").count() > 0
            has_login_btn = page.locator("[data-e2e='top-login-button'], [data-e2e='login-button'], a[href*='/login']").count() > 0
            return has_user and not has_login_btn
        except Exception:
            return False
    return False


def run_login(platform: str, slug: str, force: bool = False, interactive: bool = True) -> bool:
    if sync_playwright is None:
        print("[LOGIN] Playwright is not installed. Run: pip install playwright && playwright install chromium")
        return False
    profile = _profile_dir(platform, slug)
    if not force and _has_real_session(platform, slug):
        print(f"[LOGIN] {platform}/{slug}: already logged in (profile has cookies). Use --force to redo.")
        return True

    print(f"\n=== ONE-TIME LOGIN: {PLATFORM_LABEL[platform]} / {slug} ===")
    print(f"  Profile : {profile}")
    handle = bc.social_handles_for_brand(slug).get(platform, "")
    print(f"  Handle  : {handle or '(not set)'}")
    print(f"  URL     : {PLATFORM_URLS[platform]}")

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            page = ctx.new_page()
            page.goto(PLATFORM_URLS[platform], timeout=60000)
            time.sleep(2)
            if not interactive:
                deadline = time.time() + 600
                while time.time() < deadline:
                    time.sleep(2)
                    if _is_logged_in(page, platform):
                        break
            else:
                for attempt in range(1, 4):
                    if _is_logged_in(page, platform):
                        print("[LOGIN] Already signed in.")
                        break
                    print("[LOGIN] Sign in on the browser window, then press Enter...")
                    try:
                        input()
                    except EOFError:
                        break
                    time.sleep(2)
                    if _is_logged_in(page, platform):
                        break
            logged_in = _is_logged_in(page, platform)
            if logged_in:
                _write_profile_info(platform, slug, True)
                print(f"[LOGIN] SUCCESS: {platform}/{slug} signed in. Session saved.")
            else:
                _write_profile_info(platform, slug, False)
                print(f"[LOGIN] NOT signed in yet for {platform}/{slug}.")
            ctx.close()
            return logged_in
    except PWTimeout:
        print(f"[LOGIN] Timeout while opening {platform}/{slug}.")
        return False
    except Exception as e:
        print(f"[LOGIN] Error for {platform}/{slug}: {e}")
        return False


def _check_only(brand: str | None = None) -> None:
    platforms = ("youtube", "instagram", "tiktok")
    brands = [brand] if brand else BRANDS
    print("=== SESSION STATUS ===")
    for slug in brands:
        print(f"  {slug}:")
        for platform in platforms:
            ready = _has_real_session(platform, slug)
            print(f"    - {platform:11s}: {'READY (cookies present)' if ready else 'PENDING (login required)'}")


def real_targets(brand: str | None, platform: str | None) -> list[tuple[str, str]]:
    platforms = [platform] if platform else ["youtube", "instagram", "tiktok"]
    brands = [brand] if brand else BRANDS
    return [(p, b) for p in platforms for b in brands]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One-time login for MBM-Social brand + platforms.")
    parser.add_argument("--brand", help="Only set up this brand slug.")
    parser.add_argument("--platform", choices=["youtube", "instagram", "tiktok"], help="Only this platform.")
    parser.add_argument("--check-only", action="store_true", help="Report ready/pending sessions without opening browsers.")
    parser.add_argument("--force", action="store_true", help="Re-open even if a session already exists.")
    parser.add_argument("--non-interactive", action="store_true", help="Wait silently for login (no Enter prompts).")
    args = parser.parse_args(argv)

    if args.check_only:
        _check_only(args.brand)
        return 0

    targets = real_targets(args.brand, args.platform)
    print(f"[LOGIN] Will set up {len(targets)} session(s).")
    results = []
    for platform, brand in targets:
        ok = run_login(platform, brand, force=args.force, interactive=not args.non_interactive)
        results.append((platform, brand, ok))
    ok_all = all(ok for _, _, ok in results)
    for platform, brand, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {platform}/{brand}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
