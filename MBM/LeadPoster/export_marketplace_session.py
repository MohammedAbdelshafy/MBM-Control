"""
Export a logged-in session for a lead marketplace so LeadPoster can post via
form automation (manual/form posting — no API key needed).

Usage:
    cd MBM/LeadPoster
    python export_marketplace_session.py realestate_leadmarket
    # or pass the login URL directly:
    python export_marketplace_session.py --url https://SELLER_MARKETPLACE_URL/login

A Chromium browser opens. Log in to your marketplace seller account, reach the
"submit a lead" / dashboard page, then press Enter here to capture the session.
It is saved to sessions/<site>.json and printed as an env var value.

Add to your environment (or just keep the sessions/<site>.json file — LeadPoster
auto-loads it):
    REALESTATE_LEADMARKET_SESSION_STATE=<json>
"""
import json
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
SESSIONS = ROOT / "sessions"
SESSIONS.mkdir(exist_ok=True)

# site id -> default login url (override with --url)
DEFAULTS = {
    "realestate_leadmarket": "https://SELLER_MARKETPLACE_URL/login",
}

AUTO_CAPTURE_SECONDS = 15 * 60


def main():
    args = sys.argv[1:]
    site = None
    url = None
    for a in args:
        if a.startswith("--url="):
            url = a.split("=", 1)[1]
        elif a.startswith("--url"):
            pass
        elif a and not a.startswith("-"):
            site = a
    if url is None and site and site in DEFAULTS:
        url = DEFAULTS[site]
    if url is None:
        url = input("Login URL: ").strip()
    if not site:
        site = input("Session name (e.g. realestate_leadmarket): ").strip() or "marketplace"

    print(f"\n>>> Opening {url} for '{site}'")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="en-US")
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            print(f"    [warn] could not load {url}: {exc}; navigate manually.")
        print("    Log in to your marketplace seller account, then return here.")
        deadline = time.time() + AUTO_CAPTURE_SECONDS
        try:
            input(f"    Press Enter to capture (auto in {int(deadline - time.time())}s): ")
        except EOFError:
            pass
        storage = ctx.storage_state()
        browser.close()

    out = SESSIONS / f"{site}.json"
    out.write_text(json.dumps(storage, indent=2))
    env_name = f"{site.upper().replace('-', '_')}_SESSION_STATE"
    print(f"\nSaved {out}")
    print(f"Env var (optional, file is auto-loaded):\n{env_name}={json.dumps(storage)}\n")


if __name__ == "__main__":
    main()
