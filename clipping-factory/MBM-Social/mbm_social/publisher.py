import os
import json
import time
from glob import glob
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright_stealth import Stealth
import random

QUEUE_DIR = Path(__file__).resolve().parent.parent / "publish_queue"
USER_DATA_DIR = Path(__file__).resolve().parent.parent / "youtube_profile"

def get_next_draft():
    if not QUEUE_DIR.exists():
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        
    files = glob(str(QUEUE_DIR / "*.json"))
    for f in files:
        with open(f, 'r') as file:
            data = json.load(file)
            if data.get("status") == "draft":
                return f, data
    return None, None

def mark_published(filepath, data, video_id=None):
    """Mark package as published with real platform video_id.

    NEVER fabricates a video_id. Without a real ID, marks as publish_blocked.
    """
    if not video_id:
        data["status"] = "publish_blocked"
        data["publish_blocked_reason"] = "platform_identity_not_verified"
        data["publish_blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[PUBLISHER] Marked as PUBLISH_BLOCKED (no real video ID): {filepath}")
        return

    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["youtube_video_id"] = video_id
    data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[PUBLISHER] Marked as published: {filepath}")

def upload_to_youtube(video_path, title, description, brand=None):
    print(f"[PUBLISHER] Preparing to upload '{title}' to YouTube (Brand: {brand or 'default'})...")
    

    import re
    import shutil
    import tempfile
    
    # Extract tags from description
    tags = re.findall(r'#(\w+)', description)
    tags_string = ", ".join(tags)
    
    # Sanitize video path
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '', Path(video_path).name)
    if not safe_name.endswith('.mp4'):
        safe_name += '.mp4'
    safe_video_path = Path(tempfile.gettempdir()) / f"safe_{safe_name}"
    
    try:
        shutil.copy(video_path, safe_video_path)
        video_path = str(safe_video_path)
    except Exception as e:
        print(f"[PUBLISHER] Failed to create safe copy: {e}")

    if not Path(video_path).exists():

        print(f"[PUBLISHER] Video file not found: {video_path}")
        return False
    
    # Resolve brand-specific user profile directory if available
    profile_dir = USER_DATA_DIR
    if brand:
        brand_clean = brand.strip().lower().replace(" ", "").replace("-", "_")
        brand_profile = USER_DATA_DIR.parent / f"youtube_profile_{brand_clean}"
        if brand_profile.exists():
            profile_dir = brand_profile

    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if youtube_api_key and not youtube_api_key.startswith("your_"):
        print(f"[PUBLISHER] Using YouTube Data API... (set up tokens for real upload)")
        return False

    # OAuth tokens take priority over Studio automation when present for the brand.
    try:
        from mbm_social import youtube_api_publisher as api

        if api.tokens_exist_for(brand):
            print(f"[PUBLISHER] Brand token found for '{brand}'; using OAuth Data API...")
            ok, video_id = api.publish_via_api(video_path, title, description, brand=brand, channel_id=api.resolve_channel_id(brand))
            return (True, video_id) if ok else False
    except Exception as e:
        print(f"[PUBLISHER] OAuth API publisher unavailable ({e}); falling back to Studio automation.")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            
            page = browser.new_page()
            Stealth().apply_stealth_sync(page)
            page.goto("https://studio.youtube.com/", timeout=30000)
            
            if "accounts.google.com" in page.url:
                print("[PUBLISHER] You need to log in to YouTube Studio first.")
                print("[PUBLISHER] Please log in on the browser window and press Enter when ready...")
                try:
                    page.wait_for_url("**/studio.youtube.com/**", timeout=300000)
                    print("[PUBLISHER] Login successful!")
                except Exception as e:
                    print(f"[PUBLISHER] Login wait timeout or error: {e}")
                    browser.close()
                    return False
            
            time.sleep(2)
            
            try:
                page.wait_for_selector("ytcp-button#create-icon, #create-icon, ytcp-icon-button[aria-label='Create']", timeout=20000)
                upload_btn = page.locator("ytcp-button#create-icon, #create-icon, ytcp-icon-button[aria-label='Create']").first
                if upload_btn.count() > 0:
                    upload_btn.click()
                    print("[PUBLISHER] Clicked create button")
                    time.sleep(2)
                    upload_menu = page.locator("tp-yt-paper-item#text-item-0, tp-yt-paper-item:has-text('Upload video'), tp-yt-paper-item").first
                    upload_menu.click()
                    print("[PUBLISHER] Clicked Upload videos menu item")
                else:
                    page.click("body")
                    print("[PUBLISHER] Attempted to trigger upload fallback")
            except Exception as e:
                print(f"[PUBLISHER] Could not click upload button: {e}")
            
            time.sleep(3)
            
            file_input = None
            selectors = [
                "input[type='file'][accept*='video']",
                "input[type='file']",
                "tp-yt-paper-button#select-files-button",
            ]
            
            for selector in selectors:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0:
                        file_input = el
                        break
                except Exception:
                    continue
            
            if file_input is None:
                try:
                    file_input = page.locator("input[type='file']").first
                except Exception:
                    pass
            
            if file_input:
                try:
                    file_input.set_input_files(str(video_path))
                    print(f"[PUBLISHER] Set video file: {video_path}")
                except Exception as e:
                    print(f"[PUBLISHER] Could not set file via input: {e}")
            else:
                try:
                    with page.expect_file_chooser() as fc_info:
                        button = page.locator("tp-yt-paper-button:has-text('Select files')").first
                        button.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(str(video_path))
                    print(f"[PUBLISHER] Selected video file: {video_path}")
                except Exception as e:
                    print(f"[PUBLISHER] Could not select file: {e}")
                    browser.close()
                    return False
            
            time.sleep(5)
            
            try:
                title_box = page.locator('div#textbox[aria-label="Add a title that describes your video"], #title-textarea').first
                if title_box.count() > 0:
                    title_box.click()
                    title_box.press_sequentially(title[:100], delay=random.randint(30, 70))
                    print(f"[PUBLISHER] Set title: {title[:50]}...")
            except Exception as e:
                print(f"[PUBLISHER] Could not fill title: {e}")
            
            time.sleep(1)
            
            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea').first
                if desc_box.count() > 0:
                    desc_box.click()
                    desc_box.press_sequentially(description[:5000], delay=random.randint(10, 40))
            except Exception as e:
                print(f"[PUBLISHER] Could not fill description: {e}")
            
            time.sleep(1)
            
            try:
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click()
                print("[PUBLISHER] Set audience: Not made for kids")
                
                time.sleep(1)
                show_more = page.locator('ytcp-button#toggle-button').first
                if show_more.count() > 0:
                    show_more.click()
                    print("[PUBLISHER] Clicked Show more")
                    time.sleep(2)
                    
                    if tags_string:
                        tags_input = page.locator('input[aria-label="Tags"], #tags-container #text-input').first
                        if tags_input.count() > 0:
                            tags_input.click()
                            tags_input.press_sequentially(tags_string, delay=random.randint(20, 50))
                            tags_input.press("Enter")
                            print(f"[PUBLISHER] Added tags: {tags_string}")
            except Exception as e:
                print(f"[PUBLISHER] Error in audience/tags flow: {e}")
            
            time.sleep(1)
            
            for i in range(3):
                try:
                    next_btn = page.locator('ytcp-button#next-button').first
                    if next_btn.count() > 0:
                        next_btn.click()
                        print(f"[PUBLISHER] Clicked Next {i+1}/3")
                except Exception:
                    pass
                time.sleep(1)
            
            time.sleep(2)
            
            try:
                page.locator('tp-yt-paper-radio-button[name="PUBLIC"], #privacy-radio-public').first.click()
                print("[PUBLISHER] Set visibility: Public")
            except Exception:
                try:
                    page.locator("input[value='public']").first.click()
                except Exception:
                    pass
            
            time.sleep(1)
            
            try:
                publish_btn = page.locator('ytcp-button#done-button').first
                if publish_btn.count() > 0:
                    publish_btn.click()
                    print("[PUBLISHER] Clicked publish button")
                else:
                    page.locator("tp-yt-paper-button:has-text('Publish')").first.click()
                    print("[PUBLISHER] Clicked publish via text")
            except Exception as e:
                print(f"[PUBLISHER] Could not click publish: {e}")
                browser.close()
                return False
            
            print("[PUBLISHER] Video submitted for processing...")
            browser.close()
            return True
            
    except PWTimeout as e:
        print(f"[PUBLISHER] Timeout: {e}")
        return False
    except Exception as e:
        print(f"[PUBLISHER] Error: {e}")
        return False

def run():
    filepath, package = get_next_draft()
    if not filepath:
        print("No draft packages found in queue.")
        return
        
    print(f"Processing package: {filepath}")
    
    video_path = package.get("video_path")
    title = package.get("title", "Untitled Short")
    description = package.get("description", "")
    
    if not video_path or not Path(video_path).exists():
        print(f"Error: Video file '{video_path}' does not exist.")
        return
        
    success = upload_to_youtube(video_path, title, description)
    if success:
        mark_published(filepath, package)

if __name__ == "__main__":
    run()