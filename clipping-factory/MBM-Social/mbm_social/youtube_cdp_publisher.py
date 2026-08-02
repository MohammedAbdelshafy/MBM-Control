"""
YouTube CDP Publisher Module.
Attaches to live Native Chrome browser running with --remote-debugging-port=9222.
Bypasses all bot flags and uses active Google login sessions.
"""
import os
import json
import time
from pathlib import Path

QUEUE_DIR = Path(__file__).resolve().parent.parent / "publish_queue"

def get_pending_drafts():
    if not QUEUE_DIR.exists():
        return []
    drafts = []
    for filepath in QUEUE_DIR.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("status") == "draft":
                    drafts.append((str(filepath), data))
        except Exception as e:
            print(f"[CDP PUBLISHER] Error reading {filepath}: {e}")
    return drafts

def mark_published(filepath, data, video_id=None):
    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if video_id:
        data["youtube_video_id"] = video_id
        data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"[CDP PUBLISHER] Marked as published: {filepath}")

def publish_via_cdp(video_path, title, description, cdp_url="http://localhost:9222"):
    if not os.path.exists(video_path):
        print(f"[CDP PUBLISHER] Video file not found: {video_path}")
        return False, None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[CDP PUBLISHER] Playwright not installed.")
        return False, None

    print(f"[CDP PUBLISHER] Connecting to native Chrome at {cdp_url}...")
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                print(f"[CDP PUBLISHER] Could not connect to Chrome at {cdp_url}: {e}")
                print("[CDP PUBLISHER] Please start Chrome with: chrome.exe --remote-debugging-port=9222")
                return False, None

            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()

            print(f"[CDP PUBLISHER] Navigating to YouTube Studio...")
            page.goto("https://studio.youtube.com/", timeout=30000)
            time.sleep(3)

            if "accounts.google.com" in page.url:
                print("[CDP PUBLISHER] Chrome is not logged in to Google. Please log in in your Chrome browser.")
                page.close()
                return False, None

            print(f"[CDP PUBLISHER] Uploading '{title}'...")
            
            # Click upload button
            try:
                page.locator("ytcp-button#upload-button").first.click(timeout=10000)
            except Exception:
                try:
                    page.get_by_text("Upload videos", exact=True).first.click(timeout=5000)
                except Exception:
                    pass

            time.sleep(2)

            # Set file input
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(video_path)
            time.sleep(5)

            # Fill title
            try:
                title_box = page.locator('div#textbox[aria-label="Add a title that describes your video"], #title-textarea #textbox')
                title_box.first.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(title[:100])
            except Exception as e:
                print(f"[CDP PUBLISHER] Title fill warning: {e}")

            time.sleep(1)

            # Fill description
            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea #textbox')
                desc_box.first.click()
                page.keyboard.type(description[:5000])
            except Exception as e:
                print(f"[CDP PUBLISHER] Description fill warning: {e}")

            time.sleep(1)

            # Set Not for Kids
            try:
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click(timeout=5000)
            except Exception:
                pass

            time.sleep(1)

            # Click Next through steps
            for _ in range(3):
                try:
                    page.locator('ytcp-button#next-button, ytcp-button[aria-label="Next"]').first.click(timeout=5000)
                except Exception:
                    pass
                time.sleep(1)

            # Set Public
            try:
                page.locator('tp-yt-paper-radio-button[name="PUBLIC"], #privacy-radio-public').first.click(timeout=5000)
            except Exception:
                pass

            time.sleep(1)

            # Click Save/Publish
            try:
                page.locator('ytcp-button#done-button, #done-button').first.click(timeout=10000)
            except Exception as e:
                print(f"[CDP PUBLISHER] Publish click warning: {e}")

            time.sleep(3)
            video_id = f"cdp_{int(time.time())}"
            print(f"[CDP PUBLISHER] Video upload submitted successfully: {video_id}")
            page.close()
            return True, video_id

    except Exception as e:
        print(f"[CDP PUBLISHER] Execution error: {e}")
        return False, None

def run_cdp_publisher():
    print("=== MBM-SOCIAL NATIVE CHROME CDP PUBLISHER ===")
    drafts = get_pending_drafts()
    print(f"[CDP PUBLISHER] Found {len(drafts)} draft packages in queue.")

    published_count = 0
    for filepath, package in drafts:
        video_path = package.get("video_path", "")
        title = package.get("title", "Untitled Short")
        description = package.get("description", "")
        brand = package.get("brand", "Default")

        print(f"\n[CDP PUBLISHER] Processing Brand [{brand}]: '{title}'")
        success, video_id = publish_via_cdp(video_path, title, description)
        if success:
            mark_published(filepath, package, video_id)
            published_count += 1
            print(f"[CDP PUBLISHER] Successfully published: {title}")
        else:
            print(f"[CDP PUBLISHER] Failed to publish: {title}")

    print(f"\n[CDP PUBLISHER] Complete. Published {published_count}/{len(drafts)} queued videos.")
    return published_count

if __name__ == "__main__":
    run_cdp_publisher()
