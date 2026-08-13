"""
shortform_publisher -- cross-platform short-form publisher for MBM-Social.

Adds Instagram Reels + TikTok publishing alongside the existing YouTube
publisher. Each brand owns a Playwright browser profile per platform
(instagram_profile_<brand>/, tiktok_profile_<brand>/), mirroring the existing
youtube_profile_<brand> pattern. The first use opens the platform in a real
browser for a one-time login; the session persists in the profile dir.

Platforms are deliberately headless=False so login and any platform-native
verification can be completed interactively.

This module is for the user's automation of their own brand accounts. It does
NOT add new accounts; the handles are recorded as placeholders in
ChannelRegistry.json / BrandRegistry.json pending account creation.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import time
import uuid
import random
from pathlib import Path

# ─── ANTI-FLAGGING / ANTI-DETECTION HELPERS ──────────────────────────
def human_delay(min_seconds: float = 0.5, max_seconds: float = 3.0):
    """Sleep for a random human-like duration."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_move_delay():
    """Short pause simulating human cursor movement."""
    time.sleep(random.uniform(0.1, 0.4))

def human_type(page, locator, text: str):
    """Type text with human-like per-key delays."""
    import sys
    if sys.platform == "win32":
        locator.click()
        time.sleep(random.uniform(0.1, 0.3))
        for char in text:
            page.keyboard.insert_text(char)
            human_move_delay()
    else:
        locator.type(text, delay=random.randint(50, 150))

def random_mouse_move(page, max_x: int = 1920, max_y: int = 1080, moves: int = 3):
    """Jitter mouse cursor in a human-like pattern."""
    for _ in range(moves):
        x = random.randint(0, max_x)
        y = random.randint(0, max_y)
        page.mouse.move(x, y)
        human_move_delay()

def apply_browser_fingerprints(page):
    """Strip automation-detection signals from the page."""
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'permissions', {
            query: () => Promise.resolve({ state: 'granted' })
        });
        window.chrome = { runtime: {} };
    """)

def vary_caption(text: str, brand: str) -> str:
    """Add random emoji and variation to avoid duplicate-content flags."""
    emojis = ["", " 🔥", " 🤯", " 🎯", " 😱", " 💯", " ⚡"]
    return f"{text}{random.choice(emojis)}"

# Gradle/cache dirs that should never be copied between profile runs.
_NONCOPY_DIRS = {
    "Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
    "GrShaderCache", "ShaderCache", "component_crashes", "GraphiteDawnCache",
    "CacheStorage",
}

try:
    from . import brand_config as bc
except ImportError:
    import brand_config as bc

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from playwright_stealth import Stealth
    import random
except ImportError:  # pragma: no cover - dependency may not be installed yet
    sync_playwright = None
    PWTimeout = TimeoutError  # type: ignore[name-defined]

ROOT = Path(__file__).resolve().parent.parent


def _temp_profile_copy(source: Path) -> Path:
    """Throwaway working copy of a profile for ONE run (see publisher.py)."""
    root = Path(tempfile.gettempdir()) / "mbm_social_runs"
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"{source.name or 'profile'}_{time.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def _copy_node(src: Path, dst: Path) -> None:
        if src.is_dir():
            if src.name in _NONCOPY_DIRS:
                return
            dst.mkdir(parents=True, exist_ok=True)
            for child in os.listdir(src):
                _copy_node(src / child, dst / child)
        elif src.is_file():
            try:
                shutil.copy2(src, dst)
            except (PermissionError, OSError):
                pass

    if source.exists():
        _copy_node(source, dest)
    return dest


def _kill_chromium_for(user_data_dir: str) -> None:
    """Force-kill any Chromium instance bound to the given profile dir."""
    if not user_data_dir:
        return
    frag = user_data_dir.replace("\\", "_")
    wide = user_data_dir.replace("\\", "\\\\")
    ps = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.Name -match 'chrome|chromium' -and $_.CommandLine -and "
        f"($_.CommandLine -match '{frag}' -or $_.CommandLine -match '{wide}' -or "
        f"$_.CommandLine -match '{user_data_dir}') }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=60, shell=True)
    except Exception:
        pass

PLATFORM_URLS = {
    "instagram": "https://www.instagram.com/",
    "tiktok": "https://www.tiktok.com/upload/",
}


def _profile_dir(platform: str, brand: str) -> Path:
    """Resolve the persistent Playwright profile dir for a brand+platform."""
    dirs = bc.shortform_session_dirs(brand)
    name = dirs.get(platform) or f"{platform}_profile_{brand}"
    return ROOT / name


def resolve_handle(brand: str, platform: str) -> str:
    """Return the recorded handle for a brand+platform, or a clear placeholder."""
    handles = bc.social_handles_for_brand(brand)
    handle = handles.get(platform, "")
    return handle or f"@{brand}_{platform}_pending"


def _ensure_logged_in(page, platform: str, brand: str) -> bool:
    """Block until the user completes a one-time login when the profile is fresh."""
    url = PLATFORM_URLS.get(platform, "")
    if not url:
        return False
    page.goto(url, timeout=60000)
    time.sleep(random.uniform(3.0, 5.0))
    if platform == "instagram":
        if "login" in page.url or "accounts.google.com" in page.url:
            print(f"[SHORTFORM] Instagram login required for brand '{brand}'.")
            import os, sys
            if os.getenv("SOCIAL_DAEMON_MODE") == "1" or not sys.stdin.isatty():
                print("[SHORTFORM] Non-interactive mode. Failing auth.")
                return False
            print("[SHORTFORM] Log in on the browser window, then press Enter here...")
            try:
                input()
            except EOFError:
                return False
            time.sleep(random.uniform(3.0, 5.0))
            if "login" in page.url:
                print("[SHORTFORM] Still showing Instagram login after confirmation.")
                return False
        return True
    # TikTok: upload page shows an auth wall until logged in
    for _ in range(6):
        if "login" in page.url or page.locator("text=/Log in|Login/").count() > 0:
            print(f"[SHORTFORM] TikTok login required for brand '{brand}'.")
            import os, sys
            if os.getenv("SOCIAL_DAEMON_MODE") == "1" or not sys.stdin.isatty():
                print("[SHORTFORM] Non-interactive mode. Failing auth.")
                return False
            print("[SHORTFORM] Log in on the browser window, then press Enter...")
            try:
                input()
            except EOFError:
                return False
            time.sleep(random.uniform(3.0, 5.0))
        else:
            break
    return "login" not in page.url


def upload_to_instagram(video_path, title, description, brand=None):
    """Upload a short to Instagram Reels via the persistent brand profile."""
    if sync_playwright is None:
        print("[SHORTFORM] Playwright not installed. Install with: pip install playwright")
        return False
    video_path = str(Path(video_path))
    if not Path(video_path).exists():
        print(f"[SHORTFORM] Video file not found: {video_path}")
        return False
    brand = (brand or "default").strip().lower().replace(" ", "").replace("-", "_")
    profile = _profile_dir("instagram", brand)
    handle = resolve_handle(brand, "instagram")
    print(f"[SHORTFORM] Instagram Reels upload for '{title}' (brand {brand}, handle {handle})...")

    work_dir = _temp_profile_copy(profile)
    ctx = None
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(work_dir),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-web-security",
                ],
            )
            page = ctx.new_page()
            if Stealth:
                Stealth().apply_stealth_sync(page)
            apply_browser_fingerprints(page)
            if not _ensure_logged_in(page, "instagram", brand):
                return False
            page.goto("https://www.instagram.com/reels/create/", timeout=60000)
            random_mouse_move(page, moves=5)
            human_delay(3, 6)
            # The create flow exposes a hidden file input covering the drop zone.
            # Some sessions land on a CTA screen first -- click "Select video from
            # computer" if present, then look again for the real <input type=file>.
            file_input = None
            for attempt in range(8):
                if file_input is None:
                    try:
                        pick = page.get_by_role("button", name=re.compile(r"Select video|from computer|Create reel", re.I)).first
                        if pick.count() > 0 and pick.is_visible():
                            pick.click()
                            human_delay(1, 3)
                    except Exception:
                        pass
                for sel in ("input[accept*=video]", "input[accept*='video/*']", "input[type='file']"):
                    try:
                        loc = page.locator(sel).first
                        if loc.count() > 0:
                            file_input = loc
                            break
                    except Exception:
                        continue
                if file_input:
                    break
                time.sleep(4)
            if file_input is None:
                print("[SHORTFORM] Instagram file input not found.")
                return False
            file_input.set_input_files(video_path)
            print("[SHORTFORM] Video attached to Instagram Reels.")

            caption = vary_caption(title, brand)
            for sel in ['div[contenteditable="true"][role="textbox"]', "textarea", "[aria-label*='captio' i]"]:
                try:
                    box = page.locator(sel).first
                    if box.count() > 0:
                        human_type(page, box, caption[:2200])
                        print("[SHORTFORM] Caption set.")
                        break
                except Exception:
                    continue

            human_delay(2, 4)
            random_mouse_move(page, moves=3)
            for label in ("Share", "Post"):
                try:
                    btn = page.get_by_role("button", name=label, exact=False).first
                    if btn.count() > 0:
                        btn.click(timeout=6000)
                        print(f"[SHORTFORM] Clicked '{label}'.")
                        break
                except Exception:
                    continue
            human_delay(4, 8)
            print("[SHORTFORM] Reel submitted for processing.")
            return True
    except PWTimeout:
        print("[SHORTFORM] Timeout during Instagram automation.")
        return False
    except Exception as e:
        print(f"[SHORTFORM] Instagram automation error: {e}")
        return False
    finally:
        try:
            if ctx is not None:
                ctx.close()
        except Exception:
            pass
        try:
            _kill_chromium_for(str(work_dir))
        except Exception:
            pass
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def upload_to_tiktok(video_path, title, description="", brand=None):
    """Publish a short to TikTok via the brand Playwright profile."""
    if sync_playwright is None:
        print("[SHORTFORM] Playwright not installed. Install with: pip install playwright")
        return False
    video_path = str(Path(video_path))
    if not Path(video_path).exists():
        print(f"[SHORTFORM] Video file not found: {video_path}")
        return False
    brand = (brand or "default").strip().lower().replace(" ", "").replace("-", "_")
    profile = _profile_dir("tiktok", brand)
    handle = resolve_handle(brand, "tiktok")
    print(f"[SHORTFORM] TikTok upload for '{title}' (brand {brand}, handle {handle})...")

    work_dir = _temp_profile_copy(profile)
    ctx = None
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(work_dir),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-web-security",
                ],
            )
            page = ctx.new_page()
            if Stealth:
                Stealth().apply_stealth_sync(page)
            apply_browser_fingerprints(page)
            if not _ensure_logged_in(page, "tiktok", brand):
                return False
            page.goto("https://www.tiktok.com/upload/", timeout=60000)
            random_mouse_move(page, moves=5)
            human_delay(3, 6)
            file_input = None
            for attempt in range(4):
                try:
                    cand = page.locator("input[type='file']").first
                    if cand.count() > 0:
                        file_input = cand
                        break
                except Exception:
                    pass
                time.sleep(4)
            if file_input is None:
                print("[SHORTFORM] TikTok file input not found.")
                return False
            file_input.set_input_files(video_path)
            print("[SHORTFORM] Video file selected on TikTok.")
            human_delay(5, 10)
            for sel in ("[data-e2e='edit-caption']", "div[contenteditable='true']"):
                try:
                    box = page.locator(sel).first
                    if box.count() > 0:
                        caption = vary_caption(title, brand)
                        human_type(page, box, caption[:2200])
                        print("[SHORTFORM] TikTok caption set.")
                        break
                except Exception:
                    continue
            human_move_delay()
            for label in ("Post", "Upload"):
                try:
                    btn = page.get_by_role("button", name=label, exact=False).first
                    if btn.count() > 0:
                        btn.click(timeout=6000)
                        print(f"[SHORTFORM] TikTok clicked '{label}'.")
                        break
                except Exception:
                    continue
            human_delay(4, 8)
            print("[SHORTFORM] TikTok upload submitted.")
            return True
    except PWTimeout:
        print("[SHORTFORM] Timeout during TikTok automation.")
        return False
    except Exception as e:
        print(f"[SHORTFORM] TikTok automation error: {e}")
        return False
    finally:
        try:
            if ctx is not None:
                ctx.close()
        except Exception:
            pass
        try:
            _kill_chromium_for(str(work_dir))
        except Exception:
            pass
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


UPLOADERS = {
    "instagram": upload_to_instagram,
    "tiktok": upload_to_tiktok,
    "instagram_reels": upload_to_instagram,
}


def _session_ready(platform: str, brand: str) -> bool:
    """True only if this brand+platform has a recorded login for its Playwright profile."""
    try:
        profile = _profile_dir(platform, brand)
        info = profile / "profile_info.json"
        if info.exists():
            data = json.loads(info.read_text(encoding="utf-8"))
            if data.get("logged_in") is not None:
                return bool(data.get("logged_in"))
        return (profile / "Default").exists() or (profile / "Cookies").exists()
    except Exception:
        return False


def publish(package, platforms=None, _brand=None):
    """Publish a single package to one or more short-form platforms.

    platforms: sequence of whitelisted keys, defaults to ["instagram", "tiktok"].
    Returns dict of platform -> bool. Platforms without a logged-in session are
    skipped (False) and never open a browser window.
    """
    platforms = platforms or ["instagram", "tiktok"]
    brand = _brand or package.get("brand") or package.get("slug")
    video = package.get("video_path") or package.get("clip_file_path")
    title = package.get("title") or "Untitled Short"
    description = package.get("description") or title
    results: dict[str, bool] = {}
    norm = {"youtube_shorts": "instagram", "instagram": "instagram", "instagram_reels": "instagram", "tiktok": "tiktok"}
    for platform in platforms:
        key = norm.get(platform)
        uploader = UPLOADERS.get(platform)
        if not uploader or not key:
            print(f"[SHORTFORM] No uploader for platform '{platform}' (skipped).")
            results[platform] = False
            continue
        if not _session_ready(key, brand):
            print(f"[SHORTFORM] '{key}' session not logged in for brand '{brand}' -- skipped. "
                  "Run: python -m mbm_social.login_sessions --platform tiktok --brand <brand>")
            results[platform] = False
            continue
        results[platform] = bool(uploader(video, title, description, brand=brand))
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python shortform_publisher.py <video_path> [instagram|tiktok] ...")
        sys.exit(1)
    video_path = sys.argv[1]
    platforms = sys.argv[2:] or ["instagram", "tiktok"]
    package = {"video_path": video_path, "title": "Manual short upload", "brand": "default"}
    results = publish(package, platforms=platforms)
    print(json.dumps({"platforms": results}, indent=2))