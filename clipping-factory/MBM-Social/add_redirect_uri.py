"""
Add localhost:8090 redirect URI to the YouTube OAuth client via Google Cloud Console.
Opens a Playwright browser — log in once, the script does the rest.
"""
import sys
import time
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip install playwright && playwright install chromium")
    sys.exit(1)

CLIENT_ID = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l"
REDIRECT_URI = "http://localhost:8090"
CONSOLE_URL = f"https://console.cloud.google.com/apis/credentials?project=graduation-project-123456789"

def main():
    print("=" * 60)
    print("ADDING REDIRECT URI TO OAUTH CLIENT")
    print(f"Client: {CLIENT_ID[:30]}...")
    print(f"Adding: {REDIRECT_URI}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\nOpening Google Cloud Console...")
        page.goto(CONSOLE_URL, wait_until="networkidle", timeout=60000)

        print("If prompted, log in with your Google account.")
        print("Waiting for Console to load fully...")

        # Wait until we see the credentials page (up to 5 minutes for manual login)
        for i in range(300):
            time.sleep(1)
            url = page.url
            title = page.title()
            if "credentials" in url.lower() or "credentials" in title.lower():
                break
            if i % 10 == 0:
                print(f"  Waiting for Console... ({i}s)")

        time.sleep(3)
        print(f"\nCurrent page: {page.url}")
        print(f"Page title: {page.title()}")

        # Click on the OAuth client
        print(f"\nLooking for OAuth client {CLIENT_ID[:20]}...")
        try:
            # The client ID appears as a link in the credentials table
            client_link = page.locator(f'text="{CLIENT_ID}"').first
            if client_link.count() > 0:
                print("Found client link, clicking...")
                client_link.click()
                time.sleep(3)
            else:
                # Try finding by partial match in the table
                rows = page.locator('tr, [role="row"]')
                count = rows.count()
                print(f"Scanning {count} table rows...")
                for i in range(count):
                    row_text = rows.nth(i).text_content() or ""
                    if CLIENT_ID[:20] in row_text:
                        print(f"Found in row {i}, clicking...")
                        rows.nth(i).click()
                        time.sleep(3)
                        break
        except Exception as e:
            print(f"Error finding client: {e}")

        print(f"\nCurrent page: {page.url}")
        time.sleep(2)

        # Now we should be on the client detail page
        # Look for the redirect URI section and add button
        print("Looking for 'Authorized redirect URIs' section...")

        # Try to find and click "ADD URI" or similar button
        add_buttons = [
            'text="ADD URI"',
            'text="Add URI"',
            'text="+ ADD URI"',
            'text="Add redirect URI"',
            '[aria-label="Add redirect URI"]',
            'button:has-text("ADD")',
        ]

        clicked = False
        for selector in add_buttons:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    print(f"Found add button: {selector}")
                    btn.click()
                    clicked = True
                    time.sleep(2)
                    break
            except Exception:
                continue

        if not clicked:
            # Maybe there's a pencil/edit icon next to redirect URIs
            print("Looking for edit/pencil icon near redirect URIs...")
            edit_selectors = [
                '[aria-label="Edit"]',
                '[aria-label="Edit redirect URIs"]',
                'button[aria-label*="edit"]',
                'button[aria-label*="Edit"]',
                '.编辑',  # unlikely but just in case
            ]
            for selector in edit_selectors:
                try:
                    btns = page.locator(selector)
                    for i in range(btns.count()):
                        btn = btns.nth(i)
                        if btn.is_visible():
                            # Check if this is near the redirect URIs section
                            parent_text = btn.evaluate("el => el.closest('tr, div, section')?.textContent || ''")
                            if 'redirect' in parent_text.lower() or 'uri' in parent_text.lower():
                                print(f"Found edit button near redirect URIs")
                                btn.click()
                                clicked = True
                                time.sleep(2)
                                break
                    if clicked:
                        break
                except Exception:
                    continue

        if not clicked:
            print("\nCould not auto-find the ADD URI button.")
            print("Taking screenshot for debugging...")
            page.screenshot(path="console_screenshot.png")
            print("Screenshot saved to console_screenshot.png")
            print("\nPlease manually add the redirect URI:")
            print(f"  1. Click on the OAuth client: {CLIENT_ID}")
            print(f'  2. Find "Authorized redirect URIs"')
            print(f"  3. Click ADD URI and type: {REDIRECT_URI}")
            print(f"  4. Click SAVE")
            input("\nPress ENTER when done...")
            browser.close()
            return

        # Type the redirect URI
        print(f"Typing redirect URI: {REDIRECT_URI}")
        # The input field that appears after clicking ADD URI
        time.sleep(1)
        input_field = page.locator('input[type="text"], input[type="url"], input[placeholder*="URI"], input[placeholder*="redirect"]').last
        if input_field.count() > 0:
            input_field.fill(REDIRECT_URI)
            time.sleep(1)
        else:
            # Try typing directly
            page.keyboard.type(REDIRECT_URI)
            time.sleep(1)

        # Find and click Save
        print("Looking for Save button...")
        save_selectors = [
            'text="SAVE"',
            'text="Save"',
            'button:has-text("Save")',
            '[aria-label="Save"]',
        ]
        for selector in save_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    print(f"Clicking Save: {selector}")
                    btn.click()
                    time.sleep(3)
                    break
            except Exception:
                continue

        print("\nDone! Taking screenshot...")
        page.screenshot(path="console_after_save.png")
        print("Screenshot saved to console_after_save.png")
        print(f"\nRedirect URI '{REDIRECT_URI}' should now be added to client {CLIENT_ID[:30]}...")

        # Wait a moment then close
        time.sleep(3)
        browser.close()

    print("\nYou can now run: python reauth_youtube_all.py")


if __name__ == "__main__":
    main()
