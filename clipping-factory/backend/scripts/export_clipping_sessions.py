"""
Export creator-account sessions for the clipping platforms so the
MultiPlatformDeliveryAgent can post REAL submissions instead of simulating.

Usage (run on YOUR machine — it opens browsers you must log into):
    cd clipping-factory/backend
    .venv/Scripts/python.exe scripts/export_clipping_sessions.py
    # optional: only some platforms
    .venv/Scripts/python.exe scripts/export_clipping_sessions.py vyro reach_cat clip_affiliates

For each platform a Chromium browser opens at the sign-in page. You:
  1. Click "Sign in with Google" (or the site's login)
  2. Log in with your gmail + password (+2FA if prompted)
  3. Wait until you reach the creator dashboard / upload page
  4. Return to this terminal and press Enter to capture the session
     (or just wait — it auto-captures after 15 min as a safety net)

The logged-in storage state is saved to backend/sessions/<platform>.json
and printed as an env var value. Paste those lines into backend/.env, e.g.:
    VYRO_SESSION_STATE=<json>
    REACHCAT_SESSION_STATE=<json>
    CLIPAFFILIATES_SESSION_STATE=<json>
    CLIPPINGCOM_SESSION_STATE=<json>
then restart the API / workers.
"""
import json
import sys
import time
from pathlib import Path

# platform id -> (human label, sign-in landing URL)
PLATFORMS = [
    ("whop", "Whop", "https://whop.com"),
    ("clipping_com", "Clipping.com", "https://clipping.com"),
    ("clipping_net", "Clipping.net", "https://clipping.net"),
    ("vyro", "Vyro", "https://vyro.ai"),
    ("reach_cat", "Reach.cat", "https://reach.cat"),
    ("clip_affiliates", "ClipAffiliates", "https://clipaffiliates.com"),
]

ENV_NAMES = {
    "whop": "WHOP_SESSION_STATE",
    "clipping_com": "CLIPPINGCOM_SESSION_STATE",
    "clipping_net": "CLIPPINGNET_SESSION_STATE",
    "vyro": "VYRO_SESSION_STATE",
    "reach_cat": "REACHCAT_SESSION_STATE",
    "clip_affiliates": "CLIPAFFILIATES_SESSION_STATE",
}

AUTO_CAPTURE_SECONDS = 15 * 60


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    only = set(sys.argv[1:])

    out_dir = Path(__file__).parent.parent / "sessions"
    out_dir.mkdir(exist_ok=True)

    results = {}

    print("=" * 64)
    print("Clipping Platform Session Export")
    print("=" * 64)
    print()
    print("For EACH platform a browser opens. Log in with your gmail,")
    print("reach the dashboard, then press Enter here to capture.")
    print("If you walk away, it auto-captures after 15 minutes.")
    print()

    for pid, label, url in PLATFORMS:
        if only and pid not in only:
            continue
        print(f"\n>>> Opening {label}  ({url})")
        print(f"    If the browser doesn't open, visit: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                print(f"    [warn] could not load {url}: {exc}")
                print(f"    Navigate manually in the opened browser, then continue.")
            print(f"    -> Log in to {label} with your gmail, then return here.")
            deadline = time.time() + AUTO_CAPTURE_SECONDS
            remaining = int(deadline - time.time())
            try:
                input(f"    Press Enter to capture {label} session (auto in {remaining}s): ")
            except EOFError:
                pass
            storage = context.storage_state()
            browser.close()

        out_path = out_dir / f"{pid}.json"
        out_path.write_text(json.dumps(storage, indent=2))
        results[pid] = storage
        print(f"    -> saved {out_path}")

    print()
    print("=" * 64)
    print("Add these to your backend/.env file (single line each):")
    print("=" * 64)
    for pid, _, _ in PLATFORMS:
        if pid not in results:
            continue
        value = json.dumps(results[pid])
        print(f"\n{ENV_NAMES[pid]}={value}")
    print()
    print("Then restart the API / workers so delivery uses real sessions.")


if __name__ == "__main__":
    main()
