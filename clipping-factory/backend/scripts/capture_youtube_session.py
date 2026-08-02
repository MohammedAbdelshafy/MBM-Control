"""
Capture YouTube session into sessions/youtube.json using the persistent
youtube_profile (the same profile MBM-Social publisher.py uses).

Steps:
1. A browser opens with the existing youtube_profile.
2. Log in to YouTube Studio (or switch to the correct channel).
3. When the dashboard loads, the session is saved automatically.

The browser closes itself once logged in or after the timeout.
"""
import json
import sys
import time
from pathlib import Path

brand_arg = None
if "--brand" in sys.argv:
    idx = sys.argv.index("--brand")
    if idx + 1 < len(sys.argv):
        brand_arg = sys.argv[idx + 1].strip().lower().replace(" ", "").replace("-", "_")

filename = f"youtube_{brand_arg}.json" if brand_arg else "youtube.json"
PROFILE = MBM_SOCIAL / (f"youtube_profile_{brand_arg}" if brand_arg else "youtube_profile")
OUT = BASE.parent / "sessions" / filename
MBM_OUT = MBM_SOCIAL / "sessions" / filename
BACKUP_OUT = BASE.parent / filename

LOGIN_TIMEOUT_S = 300
for arg in sys.argv[1:]:
    if arg.isdigit():
        LOGIN_TIMEOUT_S = int(arg)


def main() -> int:
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    print("YouTube Session Capture (persistent profile)")
    print("=" * 60)
    print(f"Profile : {PROFILE}")
    print(f"Output  : {OUT}")
    print(f"Timeout : {LOGIN_TIMEOUT_S}s")
    print()
    print("A browser will open now.")
    print("1. Log in with your Google account (abdelshafyclapps@gmail.com)")
    print("2. Choose the channel you want to publish from")
    print("3. Wait until the YouTube Studio dashboard is visible")
    print("4. Session is saved automatically once logged in.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page()
        page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=60000)

        started = time.time()
        while time.time() - started < LOGIN_TIMEOUT_S:
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

        OUT.parent.mkdir(parents=True, exist_ok=True)
        MBM_OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(storage, indent=2), encoding="utf-8")
        MBM_OUT.write_text(json.dumps(storage, indent=2), encoding="utf-8")
        BACKUP_OUT.write_text(json.dumps(storage, indent=2), encoding="utf-8")

        print()
        print(f"[CAPTURE] Session saved to: {OUT}")
        print(f"[CAPTURE] MBM-Social copy:   {MBM_OUT}")
        print(f"[CAPTURE] Backup saved to:   {BACKUP_OUT}")
        print()
        print("Add this to your .env.local (single line):")
        print("YOUTUBE_SESSION_STATE=" + json.dumps(storage))
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
