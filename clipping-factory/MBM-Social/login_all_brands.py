"""
YouTube Session Setup - Opens browsers for each brand profile.
User logs in manually, session is saved. Then the publisher works.
"""
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip install playwright && playwright install chromium")
    exit(1)

ROOT = Path(__file__).resolve().parent

brands = {
    "clippingfactorymbm": "abdelshafyclapps@gmail.com",
    "cutedosage": "moeaiagenticteamz@gmail.com",
    "dontwatchthis": "abdelshafyplay@gmail.com",
    "goalmachinez": "abdelshafyplays@gmail.com",
    "twistsrevealed": "bigmoeshafy@gmail.com",
}

print("=" * 60)
print("YOUTUBE LOGIN SETUP - All 5 Brands")
print("=" * 60)
print()
print("This script opens a browser for each brand.")
print("Log in with the correct email in each one.")
print("After seeing YouTube Studio, press ENTER to save and continue.")
print()

with sync_playwright() as p:
    for brand, email in brands.items():
        user_data_dir = ROOT / f"youtube_profile_{brand}"
        print(f"--- {brand} ({email}) ---")
        print(f"Opening browser with profile: {user_data_dir}")
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=["--disable-blink-features=AutomationDetected"]
        )
        
        page = browser.new_page()
        page.goto("https://studio.youtube.com/", timeout=60000)
        
        if "accounts.google.com" in page.url:
            print(f"  Login required. Please log in with: {email}")
            print(f"  After reaching YouTube Studio homepage, press ENTER here.")
            input()
            page.goto("https://studio.youtube.com/", timeout=60000)
            if "accounts.google.com" in page.url:
                print(f"  STILL NOT LOGGED IN. Skipping.")
                browser.close()
                continue
        else:
            print(f"  Already logged in!")
        
        print(f"  Session saved for {brand}!")
        browser.close()
        print()

print("\nAll done! Run the publisher now:")
print("  python -m mbm_social.youtube_api_publisher")