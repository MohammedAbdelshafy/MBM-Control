"""
Export YouTube Studio session for PublishingAgent.

Usage:
    cd clipping-factory/backend
    python scripts/export_youtube_session.py

Steps:
1. Run this script
2. A Chromium browser opens → navigate to YouTube Studio
3. Log in with your Google account
4. Once you see the YouTube Studio dashboard, come back to this terminal
5. Press Enter → session is saved
6. Copy the output into .env as YOUTUBE_SESSION_STATE=<json>
"""
import json
import sys
from pathlib import Path

def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    output_path = Path(__file__).parent.parent / "youtube_session.json"

    print("=" * 60)
    print("YouTube Session Export")
    print("=" * 60)
    print()
    print("A browser will open. Steps:")
    print("  1. Navigate to https://studio.youtube.com")
    print("  2. Log in with your Google account")
    print("  3. Wait until you see the YouTube Studio dashboard")
    print("  4. Come back here and press Enter")
    print()
    input("Press Enter to launch browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()

        page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        print()
        print("Browser opened. Log in to YouTube Studio.")
        print("Press Enter here when you see the dashboard...")
        input()

        storage = context.storage_state()
        browser.close()

    output_path.write_text(json.dumps(storage, indent=2))
    print()
    print(f"Session saved to: {output_path}")
    print()
    print("Add this to your .env file:")
    print("-" * 60)

    # Print the env var value (single line, no indentation)
    env_value = json.dumps(storage)
    print(f"YOUTUBE_SESSION_STATE={env_value}")
    print("-" * 60)
    print()
    print("Then restart the API container:")
    print("  docker compose restart api")

if __name__ == "__main__":
    main()
