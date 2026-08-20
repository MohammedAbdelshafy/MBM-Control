"""
Capture a YouTube session for a specific brand channel.

Usage:
  python scripts/capture_brand_youtube_session.py --brand dontwatchthis
  python scripts/capture_brand_youtube_session.py --brand all
  python scripts/capture_brand_youtube_session.py               # single unknown brand

Steps:
  1. A browser opens with the brand-specific persistent profile.
  2. Log in with the Google account that owns that channel.
  3. If multiple channels exist under the account, switch to the right one.
  4. When studio.youtube.com loads, session is saved automatically.

Output:
  MBM-Social/sessions/youtube_<brand>.json
  backend/sessions/youtube_<brand>.json
"""
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND = SCRIPT_DIR.parent
MBM_SOCIAL = BACKEND.parent / "MBM-Social"
PROFILES_DIR = MBM_SOCIAL / "youtube_profiles"
BRANDS = ["dontwatchthis", "goalmachinez", "cutedosage", "clippingfactorymbm", "twistsrevealed"]
LOGIN_TIMEOUT_S = 300


def parse_args():
    brand = None
    do_all = False
    timeout = LOGIN_TIMEOUT_S
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--brand" and i < len(sys.argv):
            raw = sys.argv[i].strip().lower().replace(" ", "").replace("-", "_")
            if raw == "all":
                do_all = True
            else:
                brand = raw
        elif arg.isdigit():
            timeout = int(arg)
    if do_all:
        return BRANDS, timeout
    if brand:
        return [brand], timeout
    # default: capture first without a session
    for b in BRANDS:
        if not (MBM_SOCIAL / "sessions" / f"youtube_{b}.json").exists():
            return [b], timeout
    return [BRANDS[0]], timeout


def capture_brand(brand: str, timeout_s: int) -> int:
    from playwright.sync_api import sync_playwright

    profile_dir = PROFILES_DIR / brand
    profile_dir.mkdir(parents=True, exist_ok=True)

    session_dir_backend = BACKEND / "sessions"
    session_dir_mbm = MBM_SOCIAL / "sessions"
    session_dir_backend.mkdir(parents=True, exist_ok=True)
    session_dir_mbm.mkdir(parents=True, exist_ok=True)
    out_backend = session_dir_backend / f"youtube_{brand}.json"
    out_mbm = session_dir_mbm / f"youtube_{brand}.json"

    print("=" * 60)
    print(f"YouTube Session Capture — {brand}")
    print("=" * 60)
    print(f"Profile : {profile_dir}")
    print(f"Output  : {out_mbm}")
    print(f"Timeout : {timeout_s}s")
    print()
    print("A browser will open now.")
    print(f"1. Log in with the Google account that owns '{brand}'")
    print("2. If prompted, switch to the correct channel in YouTube Studio")
    print("3. Wait until the Studio dashboard is visible")
    print("4. Session is saved automatically.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=60000)

        started = time.time()
        while time.time() - started < timeout_s:
            if "accounts.google.com" in page.url or "accounts.youtube.com" in page.url:
                time.sleep(1)
                continue
            if "studio.youtube.com" in page.url:
                time.sleep(3)
                break
            time.sleep(1)
        else:
            print("[CAPTURE] Timed out waiting for login.")
            browser.close()
            return 1

        storage = browser.storage_state()
        out_backend.write_text(json.dumps(storage, indent=2), encoding="utf-8")
        out_mbm.write_text(json.dumps(storage, indent=2), encoding="utf-8")

        cookie_count = len(storage.get("cookies", []))
        yt_cookies = [c for c in storage.get("cookies", []) if "youtube" in c.get("domain", "")]

        print()
        print(f"[CAPTURE] Saved: {out_mbm}")
        print(f"[CAPTURE] Cookies: {cookie_count} total, {len(yt_cookies)} YouTube")
        browser.close()
        return 0


def main():
    brands, timeout = parse_args()
    results = {}
    for brand in brands:
        if brand not in BRANDS:
            print(f"[WARN] Unknown brand '{brand}', proceeding anyway")
        rc = capture_brand(brand, timeout)
        results[brand] = rc
        print()

    print("Summary:")
    for brand, rc in results.items():
        status = "OK" if rc == 0 else "FAILED"
        print(f"  {brand}: {status}")
    return 0 if all(rc == 0 for rc in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
