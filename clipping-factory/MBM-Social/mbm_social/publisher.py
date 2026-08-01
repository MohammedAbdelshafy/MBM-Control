import os
import json
import time
from glob import glob
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

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
    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if video_id:
        data["youtube_video_id"] = video_id
        data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[PUBLISHER] Marked as published: {filepath}")

def upload_to_youtube(video_path, title, description):
    print(f"[PUBLISHER] Preparing to upload '{title}' to YouTube...")
    
    if not Path(video_path).exists():
        print(f"[PUBLISHER] Video file not found: {video_path}")
        return False
    
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if youtube_api_key and not youtube_api_key.startswith("your_"):
        print(f"[PUBLISHER] Using YouTube Data API... (set up tokens for real upload)")
        return False
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            
            page = browser.contexts[0].new_page() if browser.contexts else browser.new_page()
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
                upload_btn = page.locator("ytcp-button#create-icon, #create-icon, ytcp-button#create-icon").first
                if upload_btn.count() > 0:
                    upload_btn.click()
                    print("[PUBLISHER] Clicked upload button")
                else:
                    page.click("body")
                    print("[PUBLISHER] Attempted to trigger upload")
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
                    title_box.fill(title[:100])
                    print(f"[PUBLISHER] Set title: {title[:50]}...")
            except Exception as e:
                print(f"[PUBLISHER] Could not fill title: {e}")
            
            time.sleep(1)
            
            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea').first
                if desc_box.count() > 0:
                    desc_box.click()
                    desc_box.fill(description[:5000])
            except Exception as e:
                print(f"[PUBLISHER] Could not fill description: {e}")
            
            time.sleep(1)
            
            try:
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click()
                print("[PUBLISHER] Set audience: Not made for kids")
            except Exception:
                pass
            
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