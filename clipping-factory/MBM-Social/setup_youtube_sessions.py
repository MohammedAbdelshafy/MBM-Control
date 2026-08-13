"""
Interactive setup script to manually log into YouTube Studio for each brand.
This saves the Playwright persistent profiles so the `post_orchestrator` can run headless later.
"""
import os
import json
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Please run: pip install playwright")
    exit(1)

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "ChannelRegistry.json"

def setup_sessions():
    if not REGISTRY_PATH.exists():
        print(f"Error: {REGISTRY_PATH} not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # Specific brands we want to configure
    target_brands = ["cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]

    channels = [c for c in registry.get("channels", []) if c.get("brand") in target_brands]

    print("=== YouTube Studio Manual Session Setup ===")
    print("This script will open a browser for each channel.")
    print("Please log in with the correct email account for each.")

    for channel in channels:
        brand = channel.get("brand")
        email = channel.get("owned_by", "Unknown")
        user_data_dir = ROOT / f"youtube_profile_{brand}"
        
        print(f"\n==================================================")
        print(f"Setting up Brand: {brand}")
        print(f"Target Email: {email}")
        print(f"Profile Path: {user_data_dir}")
        print(f"==================================================")
        
        print("Launching browser... Please complete the Google Login if prompted.")
        
        with sync_playwright() as p:
            # Launch in non-headless mode so user can see and interact
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            page = browser.new_page()
            page.goto("https://studio.youtube.com/")
            
            # Wait for user input to continue
            input(f"\n[ACTION REQUIRED]\nLog into Google using '{email}'.\nOnce you are looking at the YouTube Studio dashboard, press ENTER here to save the session and move to the next brand...")
            
            print("Saving session and closing browser...")
            browser.close()
            
    print("\nAll target channels configured! You can now run the `post_orchestrator`.")

if __name__ == "__main__":
    setup_sessions()
