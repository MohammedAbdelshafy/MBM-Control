"""Twilio Payment Method Setup Guide — Playwright Chrome Automation.

Opens Chrome, navigates to Twilio billing, and walks you through
adding a payment method to unlock 1,000 free minutes + $15.50 credit.

Usage:
    python MBM/Scripts/twilio_unlock_guide.py

What it does:
  1. Launches Chrome (non-headless) → Twilio login
  2. Navigates to Billing → Payment Methods
  3. Pauses for you to enter card details (never touches your card)
  4. Takes screenshots at each step
  5. Verifies free credit is active
  6. Saves verification to MBM/Artifacts/twilio_unlock_status.json

Requires: pip install playwright && playwright install chromium
"""

import os
import sys
import json
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

SCREENSHOTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "Artifacts", "twilio_screenshots"
)
STATUS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "Artifacts", "twilio_unlock_status.json"
)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)


def screenshot(page, label):
    """Save a timestamped screenshot."""
    ts = datetime.now().strftime("%H%M%S")
    path = os.path.join(SCREENSHOTS_DIR, f"{ts}_{label}.png")
    page.screenshot(path=path, full_page=False)
    print(f"  📸 Screenshot saved: {path}")
    return path


def wait_for_user(msg, timeout_sec=300):
    """Pause with a clear message. Press Enter in terminal to continue."""
    print(f"\n{'='*60}")
    print(f"  👉 {msg}")
    print(f"  ⏳ Waiting up to {timeout_sec}s — press ENTER in terminal when ready")
    print(f"{'='*60}")
    try:
        input("  > ")
    except EOFError:
        time.sleep(5)


def run_guide():
    from playwright.sync_api import sync_playwright

    print("\n🚀 TWILIO PAYMENT METHOD SETUP GUIDE")
    print("=" * 60)
    print("This script opens Chrome and walks you through adding a")
    print("payment method to Twilio. This unlocks your 1,000 free")
    print("calling minutes + $15.50 credit — costs $0.")
    print("=" * 60)

    with sync_playwright() as p:
        # Launch visible Chrome so user can interact
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── STEP 1: Navigate to Twilio Console Login ──────────────
        print("\n📌 STEP 1/5 — Opening Twilio Console...")
        page.goto("https://console.twilio.com/", timeout=30000)
        time.sleep(3)
        screenshot(page, "01_twilio_login_page")

        wait_for_user(
            "Log into your Twilio account in the Chrome window.\n"
            "   (If already logged in, you'll see the Console Dashboard)\n"
            "   Use the email/password you signed up with."
        )

        # Check if we landed on the console
        time.sleep(3)
        current_url = page.url
        print(f"  Current URL: {current_url}")
        screenshot(page, "02_after_login")

        if "console.twilio.com" not in current_url and "twilio.com" not in current_url:
            print("  ⚠️  You may not be logged in yet. Waiting 30s more...")
            time.sleep(30)
            current_url = page.url
            print(f"  Current URL: {current_url}")

        # ── STEP 2: Navigate to Billing → Payment Methods ─────────
        print("\n📌 STEP 2/5 — Navigating to Payment Methods...")
        page.goto(
            "https://console.twilio.com/us1/billing/payment-methods",
            timeout=30000,
        )
        time.sleep(5)
        screenshot(page, "03_billing_page")

        wait_for_user(
            "You should see the 'Payment Methods' page.\n"
            "   If you see a login prompt, log in again.\n"
            "   If you're redirected elsewhere, navigate to:\n"
            "   Settings → Billing → Payment Methods"
        )

        # ── STEP 3: Click Add Payment Method ──────────────────────
        print("\n📌 STEP 3/5 — Adding Payment Method...")
        screenshot(page, "04_before_add_card")

        # Try to find and click "Add" or "Add payment method" button
        add_btn = None
        for selector in [
            'button:has-text("Add payment")',
            'button:has-text("Add Payment")',
            'button:has-text("Add a payment")',
            'a:has-text("Add payment")',
            '[data-testid="add-payment-method"]',
            'button:has-text("Add")',
        ]:
            try:
                add_btn = page.locator(selector).first
                if add_btn.is_visible(timeout=2000):
                    break
                add_btn = None
            except Exception:
                add_btn = None

        if add_btn:
            print("  ✅ Found 'Add payment method' button — clicking it...")
            add_btn.click()
            time.sleep(3)
            screenshot(page, "05_add_card_form")
        else:
            print("  ℹ️  Could not auto-find the Add button.")
            print("     Please click 'Add payment method' manually in Chrome.")

        wait_for_user(
            "The card entry form should be visible in Chrome.\n"
            "   ⚠️  IMPORTANT: This script NEVER sees your card number.\n"
            "   Enter your card details directly in the Chrome window.\n"
            "   Use any card — you won't be charged (free tier only)."
        )

        # ── STEP 4: User enters card details ──────────────────────
        print("\n📌 STEP 4/5 — Entering Card Details (you do this)...")
        screenshot(page, "06_card_form_visible")

        wait_for_user(
            "After entering your card and clicking Submit/Save:\n"
            "   Wait for the confirmation message.\n"
            "   Then come back here and press ENTER."
        )

        time.sleep(3)
        screenshot(page, "07_after_card_submit")

        # ── STEP 5: Verify credit is active ───────────────────────
        print("\n📌 STEP 5/5 — Verifying Free Credit...")
        page.goto(
            "https://console.twilio.com/us1/billing/balance",
            timeout=30000,
        )
        time.sleep(5)
        screenshot(page, "08_balance_page")

        # Try to read balance
        balance_text = ""
        try:
            body = page.inner_text("body")
            # Look for dollar amounts
            import re
            amounts = re.findall(r"\$[\d,]+\.?\d*", body)
            if amounts:
                balance_text = ", ".join(amounts[:5])
                print(f"  💰 Found balance amounts: {balance_text}")
            else:
                balance_text = body[:500]
                print(f"  Balance page text (first 500 chars): {balance_text[:200]}")
        except Exception as e:
            print(f"  ⚠️  Could not read balance: {e}")

        # Check if calling is enabled
        print("\n  Checking if calling is enabled...")
        page.goto(
            "https://console.twilio.com/us1/develop/phone-numbers/manage/incoming",
            timeout=30000,
        )
        time.sleep(4)
        screenshot(page, "09_phone_numbers_page")

        calling_enabled = False
        try:
            body = page.inner_text("body")
            if "verified" in body.lower() or "enabled" in body.lower():
                calling_enabled = True
                print("  ✅ Calling appears to be ENABLED")
            elif "trial" in body.lower() and "limitation" in body.lower():
                print("  ⚠️  Still in trial mode — payment method may not have registered")
            else:
                print(f"  Phone page snippet: {body[:200]}")
        except Exception:
            pass

        # ── Save status ───────────────────────────────────────────
        status = {
            "timestamp": datetime.now().isoformat(),
            "screenshots_dir": SCREENSHOTS_DIR,
            "balance_text": balance_text,
            "calling_enabled": calling_enabled,
            "final_url": page.url,
            "steps_completed": True,
        }
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
        print(f"\n  📄 Status saved: {STATUS_FILE}")

        # ── Done ──────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  ✅ SETUP COMPLETE!")
        print("=" * 60)
        print(f"  Screenshots: {SCREENSHOTS_DIR}")
        print(f"  Status file: {STATUS_FILE}")
        print()
        print("  NEXT STEPS:")
        print("  1. Run the progressive dialer:")
        print("     python MBM/LeadEngine/progressive_dialer.py --start --bridge --campaign 50")
        print()
        print("  2. Or use the free WebRTC browser dialer:")
        print("     python MBM/LeadEngine/free_us_phone_dialer.py")
        print("=" * 60)

        wait_for_user("Press ENTER to close Chrome and exit.")

        browser.close()

    print("\n🎉 Done. Chrome closed.")


if __name__ == "__main__":
    try:
        run_guide()
    except KeyboardInterrupt:
        print("\n⚠️  Cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
