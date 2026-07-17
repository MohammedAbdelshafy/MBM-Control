"""
Extract logged-in sessions directly from your running Chrome browser.
No need to log in again — connects to your open Chrome and captures sessions.

Prerequisites:
  1. Close Chrome completely
  2. Reopen Chrome with remote debugging enabled:
     chrome.exe --remote-debugging-port=9222
  3. Log into all your clipping platforms in Chrome
  4. Run this script

Usage:
  cd clipping-factory/backend
  .venv/Scripts/python.exe scripts/extract_chrome_sessions.py
"""
import json
import sys
import time
from pathlib import Path

# Platform configs: (id, label, urls_to_check)
PLATFORMS = [
    ("whop", "Whop", ["whop.com"]),
    ("clipping_com", "Clipping.com", ["clipping.com"]),
    ("vyro", "Vyro", ["vyro.ai"]),
    ("reach_cat", "Reach.cat", ["reach.cat"]),
    ("clip_affiliates", "ClipAffiliates", ["clipaffiliates.com"]),
    ("clipping_net", "Clipping.net", ["clipping.net"]),
]

ENV_NAMES = {
    "whop": "WHOP_SESSION_STATE",
    "clipping_com": "CLIPPINGCOM_SESSION_STATE",
    "vyro": "VYRO_SESSION_STATE",
    "reach_cat": "REACHCAT_SESSION_STATE",
    "clip_affiliates": "CLIPAFFILIATES_SESSION_STATE",
    "clipping_net": "CLIPPINGNET_SESSION_STATE",
}


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    out_dir = Path(__file__).parent.parent / "sessions"
    out_dir.mkdir(exist_ok=True)

    print("=" * 64)
    print("Chrome Session Extractor")
    print("=" * 64)
    print()
    print("This connects to your running Chrome browser and extracts")
    print("logged-in sessions from all clipping platforms.")
    print()
    print("PREREQUISITE: Chrome must be running with remote debugging:")
    print('  1. Close ALL Chrome windows')
    print('  2. Open CMD and run:')
    print('     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
    print('  3. Log into all clipping platforms in that Chrome window')
    print('  4. Come back here and press Enter')
    print()

    input("Press Enter when Chrome is ready with remote debugging on port 9222...")

    results = {}

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print(f"\nConnected to Chrome! Found {len(browser.contexts)} context(s)")
        except Exception as e:
            print(f"\nERROR: Could not connect to Chrome: {e}")
            print("Make sure Chrome is running with --remote-debugging-port=9222")
            sys.exit(1)

        # Get all pages from all contexts
        all_pages = []
        for context in browser.contexts:
            all_pages.extend(context.pages)

        print(f"Found {len(all_pages)} open tab(s)")

        for pid, label, urls in PLATFORMS:
            print(f"\n>>> Checking {label}...")

            # Find a page that matches this platform
            matched_page = None
            for page in all_pages:
                page_url = page.url.lower()
                if any(u in page_url for u in urls):
                    matched_page = page
                    break

            if matched_page:
                print(f"    Found tab: {matched_page.url}")

                # Get storage state from the browser context
                context = matched_page.context
                storage = context.storage_state()

                # Check if there are cookies for this platform
                platform_cookies = [
                    c for c in storage.get("cookies", [])
                    if any(u in c.get("domain", "") for u in urls)
                ]

                if platform_cookies:
                    out_path = out_dir / f"{pid}.json"
                    out_path.write_text(json.dumps(storage, indent=2))
                    results[pid] = storage
                    print(f"    -> Saved {len(platform_cookies)} cookies to {out_path}")
                else:
                    print(f"    -> No cookies found for {label} — are you logged in?")
            else:
                print(f"    -> No open tab found for {label}")
                print(f"       Open {urls[0]} in Chrome and log in, then re-run this script")

        # Don't close the browser — it's the user's Chrome!
        print()
        print("=" * 64)

    if results:
        print("Sessions extracted! Add these to backend/.env:")
        print()
        for pid in results:
            value = json.dumps(results[pid])
            print(f"{ENV_NAMES[pid]}={value}")
        print()
        print("Then restart the workers:")
        print("  docker compose restart worker-video worker-delivery celery-beat")
    else:
        print("No sessions were extracted.")
        print("Make sure you're logged into the platforms in Chrome.")

    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
