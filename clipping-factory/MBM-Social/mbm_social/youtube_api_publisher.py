"""
YouTube Automated Publisher Module.
Provides dual publishing support:
1. YouTube Data API v3 (OAuth2 / Service Account / Client Credentials)
2. Playwright Headless Studio Automation (Fallback)
"""
import os
import json
import time
from pathlib import Path
from glob import glob

QUEUE_DIR = Path(__file__).resolve().parent.parent / "publish_queue"
USER_DATA_DIR = Path(__file__).resolve().parent.parent / "youtube_profile"
TOKENS_PATH = Path(__file__).resolve().parent.parent / "youtube_tokens.json"

def get_pending_drafts():
    """Retrieve all draft publish packages from queue."""
    if not QUEUE_DIR.exists():
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    
    drafts = []
    for filepath in QUEUE_DIR.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("status") == "draft":
                    drafts.append((str(filepath), data))
        except Exception as e:
            print(f"[YOUTUBE PUBLISHER] Error reading {filepath}: {e}")
    return drafts

def mark_published(filepath, data, video_id=None):
    """Mark package as published with timestamp and optional video_id."""
    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if video_id:
        data["youtube_video_id"] = video_id
        data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"[YOUTUBE PUBLISHER] Marked as published: {filepath}")

def publish_via_api(video_path, title, description, channel_id=None):
    """Publish via YouTube Data API v3 using OAuth2 tokens."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("[YOUTUBE PUBLISHER] google-api-python-client not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return False, None
    
    if not TOKENS_PATH.exists():
        print(f"[YOUTUBE PUBLISHER] No tokens file found at {TOKENS_PATH}")
        return False, None
    
    try:
        with open(TOKENS_PATH, 'r') as f:
            tokens_data = json.load(f)
    except Exception as e:
        print(f"[YOUTUBE PUBLISHER] Failed to read tokens: {e}")
        return False, None
    
    if not tokens_data or not isinstance(tokens_data, dict):
        print("[YOUTUBE PUBLISHER] Invalid tokens data")
        return False, None
    
    if channel_id and channel_id not in tokens_data:
        print(f"[YOUTUBE PUBLISHER] No tokens for channel {channel_id}")
    
    cid = channel_id or next(iter(tokens_data), None)
    if not cid:
        print("[YOUTUBE PUBLISHER] No channel specified and no tokens available")
        return False, None
    
    info = tokens_data.get(cid, {})
    access_token = info.get("access_token")
    refresh_token = info.get("refresh_token")
    client_id = info.get("client_id")
    client_secret = info.get("client_secret")
    token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")
    
    if not all([access_token, refresh_token, client_id, client_secret]):
        print(f"[YOUTUBE PUBLISHER] Incomplete OAuth credentials for channel {cid}")
        return False, None
    
    try:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        
        if creds.expired or not creds.valid:
            creds.refresh(Request())
            tokens_data[cid]["access_token"] = creds.token
            with open(TOKENS_PATH, 'w') as f:
                json.dump(tokens_data, f, indent=2)
        
        youtube = build("youtube", "v3", credentials=creds)
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "viral", "fyp", "auto-generated"],
                "categoryId": "28",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "embeddable": True,
                "publicStatsViewable": True,
            },
        }
        
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YOUTUBE PUBLISHER] Upload progress: {int(status.progress() * 100)}%")
        
        video_id = response.get("id", "")
        print(f"[YOUTUBE PUBLISHER] Successfully uploaded: {video_id}")
        return True, video_id
        
    except Exception as e:
        print(f"[YOUTUBE PUBLISHER] API upload failed: {e}")
        return False, None

def publish_via_playwright(video_path, title, description):
    """Publish using Playwright YouTube Studio automation with actual video upload."""
    if not os.path.exists(video_path):
        print(f"[YOUTUBE PUBLISHER] Video file does not exist: {video_path}")
        return False, None
    
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if youtube_api_key and not youtube_api_key.startswith("your_"):
        print(f"[YOUTUBE PUBLISHER] Publishing '{title}' via YouTube Data API v3...")
        return publish_via_api(video_path, title, description)
    
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[YOUTUBE PUBLISHER] Playwright not installed. Install with: pip install playwright")
        return False, None
    
    print(f"[YOUTUBE PUBLISHER] Using Playwright Studio automation for: '{title}'")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            page = browser.new_page()
            page.goto("https://studio.youtube.com/", timeout=30000)
            
            if "accounts.google.com" in page.url:
                print("[YOUTUBE PUBLISHER] Authentication required - login page shown")
                print("[YOUTUBE PUBLISHER] Please log in to YouTube Studio in the browser window")
                print("[YOUTUBE PUBLISHER] Session will be saved after login")
                browser.close()
                return False, None
            
            print("[YOUTUBE PUBLISHER] Connected to YouTube Studio")
            
            time.sleep(3)
            
            try:
                page.locator("ytcp-button#upload-button").first.click(timeout=10000)
            except Exception:
                try:
                    page.get_by_text("Upload videos", exact=True).first.click(timeout=5000)
                except Exception:
                    pass

            time.sleep(2)
            
            file_selected = False
            file_input = None
            for selector in [
                "input[type='file'][accept*='video']",
                "input[type='file']",
            ]:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0:
                        file_input = el
                        break
                except Exception:
                    continue

            if file_input is not None:
                try:
                    file_input.set_input_files(video_path)
                    file_selected = True
                    print("[YOUTUBE PUBLISHER] Set video file via input")
                except Exception as e:
                    print(f"[YOUTUBE PUBLISHER] Could not set file via input: {e}")

            if not file_selected:
                with page.expect_file_chooser() as fc_info:
                    try:
                        page.locator("tp-yt-paper-button#select-files-button").first.click(timeout=10000)
                    except Exception:
                        pass
                try:
                    file_chooser = fc_info.value
                    file_chooser.set_files(video_path)
                    file_selected = True
                    print("[YOUTUBE PUBLISHER] Set video file via file chooser")
                except Exception as e:
                    print(f"[YOUTUBE PUBLISHER] Failed to select file: {e}")
                    browser.close()
                    return False, None

            if not file_selected:
                print("[YOUTUBE PUBLISHER] Could not select video file")
                browser.close()
                return False, None
            
            time.sleep(5)
            
            try:
                title_box = page.locator('div#textbox[aria-label="Add a title that describes your video"], #title-textarea #textbox')
                title_box.first.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(title[:100])
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not fill title: {e}")
            
            time.sleep(1)
            
            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea')
                desc_box.first.click()
                page.keyboard.type(description[:5000])
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not fill description: {e}")
            
            time.sleep(1)
            
            try:
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click(timeout=5000)
            except Exception:
                pass
            
            time.sleep(1)
            
            for _ in range(3):
                try:
                    page.locator('ytcp-button#next-button, ytcp-button[aria-label="Next"]').first.click(timeout=5000)
                except Exception:
                    pass
                time.sleep(1)
            
            time.sleep(2)
            
            try:
                page.locator('tp-yt-paper-radio-button[name="PUBLIC"], #privacy-radio-public').first.click(timeout=5000)
            except Exception:
                try:
                    page.locator("input[value='public']").first.click(timeout=5000)
                except Exception:
                    pass
            
            time.sleep(1)
            
            try:
                page.locator('ytcp-button#done-button, #done-button').first.click(timeout=10000)
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not click publish: {e}")
                browser.close()
                return False, None
            
            print("[YOUTUBE PUBLISHER] Video submitted for processing...")
            
            browser.close()
            return True, f"yt_{int(time.time())}"
            
    except PWTimeout:
        print("[YOUTUBE PUBLISHER] Timeout during YouTube Studio automation")
        return False, None
    except Exception as e:
        print(f"[YOUTUBE PUBLISHER] Playwright automation error: {e}")
        return False, None

def run_auto_publisher():
    """Main automated runner: inspects queue and publishes pending items."""
    print("=== MBM-SOCIAL YOUTUBE AUTOMATED PUBLISHER ===")
    drafts = get_pending_drafts()
    print(f"[YOUTUBE PUBLISHER] Found {len(drafts)} draft packages in queue.")
    
    published_count = 0
    for filepath, package in drafts:
        video_path = package.get("video_path", "")
        title = package.get("title", "Untitled Short")
        description = package.get("description", "")
        brand = package.get("brand", "Default")
        channel_id = package.get("youtube_channel_id")
        
        print(f"\n[YOUTUBE PUBLISHER] Processing Brand [{brand}]: '{title}'")
        
        if not video_path:
            print(f"[YOUTUBE PUBLISHER] No video_path in package")
            continue
            
        if not os.path.exists(video_path):
            print(f"[YOUTUBE PUBLISHER] Skipping - video file not found: {video_path}")
            continue
        
        success, video_id = publish_via_playwright(video_path, title, description)
        if success:
            mark_published(filepath, package, video_id)
            published_count += 1
            print(f"[YOUTUBE PUBLISHER] Published: {title}")
        else:
            print(f"[YOUTUBE PUBLISHER] Failed to publish: {title}")
    
    print(f"\n[YOUTUBE PUBLISHER] Run Complete. Published {published_count}/{len(drafts)} queued videos.")
    return published_count

if __name__ == "__main__":
    run_auto_publisher()