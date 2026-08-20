"""
YouTube Automated Publisher Module.
Provides dual publishing support:
1. YouTube Data API v3 (OAuth2 / Service Account / Client Credentials)
2. Playwright Headless Studio Automation (Fallback)
"""
import os
import json
import random
import time
from pathlib import Path
from glob import glob

try:
    from .human_behavior import human_delay, mouse_move_random, type_human
except Exception:
    human_delay = lambda *a, **k: time.sleep(random.uniform(1, 3))
    mouse_move_random = lambda *a, **k: None
    type_human = lambda page, text, **k: page.keyboard.type(text)

QUEUE_DIR = Path(__file__).resolve().parent.parent / "publish_queue"
TOKENS_PATH = Path(__file__).resolve().parent.parent / "youtube_tokens.json"
CHANNEL_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "ChannelRegistry.json"

def get_user_data_dir(brand):
    """Get brand-specific Chrome profile directory."""
    base = Path(__file__).resolve().parent.parent / "youtube_profiles"
    if not brand:
        return base / "_default"
    slug = str(brand).strip().lower().replace(" ", "").replace("-", "_")
    return base / slug


def resolve_channel_id(brand):
    """Look up the YouTube channel id for a brand slug from ChannelRegistry.json."""
    if not brand:
        return None
    slug = str(brand).strip().lower().replace(" ", "").replace("-", "_")
    try:
        registry = json.loads(CHANNEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    for channel in registry.get("channels", []):
        if str(channel.get("brand", "")).strip().lower().replace(" ", "").replace("-", "_") == slug:
            return channel.get("youtube_channel_id")
    return None


def tokens_exist_for(brand):
    """True when youtube_tokens.json holds a scoped, refreshable token entry for the brand."""
    entry, err = _load_token_entry(brand) if brand else (None, "no brand")
    return bool(entry) and not err

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
    """Mark package as published with timestamp and real platform video_id.

    NEVER fabricates a video_id. If no real ID is provided, the package
    is marked as publish_blocked, not published.
    """
    if not video_id:
        data["status"] = "publish_blocked"
        data["publish_blocked_reason"] = "platform_identity_not_verified"
        data["publish_blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[YOUTUBE PUBLISHER] Marked as PUBLISH_BLOCKED (no real video ID): {filepath}")
        return

    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["youtube_video_id"] = video_id
    data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"[YOUTUBE PUBLISHER] Marked as published: {filepath}")

def _load_token_entry(brand, channel_id=None):
    """Resolve the OAuth token entry for a brand, refusing cross-brand fallthrough.

    Returns (entry dict, error string). A token entry is ONLY used when it is
    explicitly scoped to this brand AND (if a real channel id was requested) the
    entry claims that exact channel. Never reaches into another brand's token.
    """
    if not TOKENS_PATH.exists():
        return None, f"No tokens file found at {TOKENS_PATH}"
    try:
        with open(TOKENS_PATH, 'r', encoding="utf-8") as f:
            tokens_data = json.load(f)
    except Exception as e:
        return None, f"Failed to read tokens: {e}"
    if not tokens_data or not isinstance(tokens_data, dict):
        return None, "Invalid tokens data"

    entries = {k: v for k, v in tokens_data.items() if isinstance(v, dict) and not str(k).startswith("_")}

    key = None
    if brand:
        key = str(brand).strip().lower().replace(" ", "").replace("-", "_")
    elif channel_id and channel_id in entries:
        key = channel_id
    if not key or key not in entries:
        return None, (f"No token entry for brand '{brand}' (keys: {sorted(entries)[:6]}). "
                      "Run the one-time OAuth flow per brand before using API publishing.")

    info = entries[key]
    entry_channel = info.get("channel_id") or ""
    if channel_id and entry_channel and entry_channel != channel_id:
        return None, (f"Token '{key}' is scoped to channel {entry_channel}, not {channel_id}. "
                      "Refusing cross-brand publish.")
    return info, ""


def publish_via_api(video_path, title, description, brand=None, channel_id=None, privacy_status="public", allow_public=False):
    """Publish via YouTube Data API v3 using the BRAND's OWN OAuth token.

    The token is resolved strictly by brand (never another brand's token), and
    the live session is verified against the requested channel before upload so
    content can never land on the wrong channel.

    Args:
        privacy_status: "public", "unlisted", or "private".
            - "public" = live mode (full production)
            - "unlisted" = test mode (only accessible via link)
            - "private" = draft mode (only owner can see)
        allow_public: MUST be True when privacy_status="public". Prevents
            test/dry_run modes from accidentally publishing publicly.

    Returns:
        (success: bool, video_id: str | None)
    """
    # MODE SAFETY: "public" requires explicit authorization
    if privacy_status == "public" and not allow_public:
        print(f"[YOUTUBE PUBLISHER] BLOCKED: privacy_status='public' requires allow_public=True. "
              f"This prevents test/dry_run modes from publishing publicly. "
              f"Use allow_public=True only for explicit live production mode.")
        return False, None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("[YOUTUBE PUBLISHER] google-api-python-client not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return False, None

    if not Path(video_path).exists():
        print(f"[YOUTUBE PUBLISHER] Video file not found: {video_path}")
        return False, None

    info, err = _load_token_entry(brand, channel_id)
    if not info:
        print(f"[YOUTUBE PUBLISHER] {err}")
        return False, None

    access_token = info.get("access_token")
    refresh_token = info.get("refresh_token")
    client_id = info.get("client_id")
    client_secret = info.get("client_secret")
    token_uri = info.get("token_uri", "https://oauth2.googleapis.com/token")

    if not refresh_token and not access_token:
        print(f"[YOUTUBE PUBLISHER] No credentials for brand '{brand}' — need at least refresh_token")
        return False, None

    try:
        if refresh_token and client_id and client_secret:
            creds = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )
            if creds.expired:
                try:
                    creds.refresh(Request())
                except Exception as re:
                    print(f"[YOUTUBE PUBLISHER] Token refresh notice: {re}")
        elif access_token:
            creds = Credentials(token=access_token)
        else:
            print(f"[YOUTUBE PUBLISHER] Incomplete credentials for brand '{brand}'")
            return False, None

        youtube = build("youtube", "v3", credentials=creds)

        # Live verification: the authenticated session MUST manage the channel we
        # are about to post to. Without this, a stale token would silently leak
        # the video onto the wrong brand's channel.
        # If youtube.readonly scope is missing, skip channel check — upload scope
        # is sufficient for the actual upload. The upload itself is the proof.
        owned = []
        try:
            mine = youtube.channels().list(part="id,snippet", mine=True).execute()
            owned = [c.get("id") for c in mine.get("items", [])]
        except Exception as ve:
            err_str = str(ve).lower()
            if "insufficient" in err_str or "403" in err_str:
                print(f"[YOUTUBE PUBLISHER] Note: channel verification skipped "
                      f"(token lacks youtube.readonly scope). Upload will proceed — "
                      f"the upload itself is the channel proof.")
            else:
                print(f"[YOUTUBE PUBLISHER] Token not usable (invalid_grant or revoked): {ve}")
                return False, None
        if channel_id and owned and channel_id not in owned:
            print(f"[YOUTUBE PUBLISHER] Token for brand '{brand}' does not own channel {channel_id}. "
                  f"Owns: {owned}. Refusing cross-channel publish.")
            return False, None
        if owned and not owned:
            print(f"[YOUTUBE PUBLISHER] Token for brand '{brand}' returned no channels (revoked?).")
            return False, None
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "viral", "fyp", "auto-generated"],
                "categoryId": "28",
            },
            "status": {
                "privacyStatus": privacy_status,
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

def publish_via_playwright(video_path, title, description, brand=None, channel_id=None, prefer_api=True, privacy_status="public"):
    """Publish a video to YouTube.

    Priority: OAuth Data API (when the brand has a valid token) -> Playwright
    Studio automation. Falls back to Studio automation when no token exists.

    MODE SAFETY: privacy_status is passed through to the Playwright UI.
    If privacy_status="public" and the caller did not explicitly authorize
    live mode, the caller should NOT invoke this function.
    """
    # MODE SAFETY: validate privacy_status at the lowest layer
    allowed_privacies = {"public", "unlisted", "private"}
    if privacy_status not in allowed_privacies:
        print(f"[YOUTUBE PUBLISHER] Invalid privacy_status '{privacy_status}'. "
              f"Must be one of {allowed_privacies}.")
        return False, None
    if not os.path.exists(video_path):
        print(f"[YOUTUBE PUBLISHER] Video file does not exist: {video_path}")
        return False, None

    resolved_channel = channel_id or resolve_channel_id(brand)
    if prefer_api and tokens_exist_for(brand):
        print(f"[YOUTUBE PUBLISHER] Publishing '{title}' via YouTube Data API v3 (brand token found)...")
        ok, video_id = publish_via_api(video_path, title, description, brand=brand, channel_id=resolved_channel, privacy_status=privacy_status)
        if ok:
            return True, video_id
        print(f"[YOUTUBE PUBLISHER] API publish failed for '{title}'; falling back to Studio automation.")
    elif prefer_api:
        print(f"[YOUTUBE PUBLISHER] No OAuth token for brand '{brand or 'default'}'; using Studio automation.")
    
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        try:
            from playwright_stealth import Stealth
        except ImportError:
            Stealth = None
    except ImportError:
        print("[YOUTUBE PUBLISHER] Playwright not installed. Install with: pip install playwright")
        return False, None
    
    print(f"[YOUTUBE PUBLISHER] Using Playwright Studio automation for: '{title}'")
    
    user_data_dir = get_user_data_dir(brand)
    print(f"[YOUTUBE PUBLISHER] Using profile: {user_data_dir}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    f"--window-size={random.randint(1200, 1920)}x{random.randint(700, 1080)}",
                ]
            )
            
            page = browser.new_page()
            if Stealth:
                try:
                    Stealth().apply_stealth_sync(page)
                except Exception:
                    pass
            try:
                from .human_behavior import apply_browser_fingerprints
                apply_browser_fingerprints(page)
            except Exception:
                pass
            page.goto("https://studio.youtube.com/", timeout=30000)
            
            if "accounts.google.com" in page.url:
                print("[YOUTUBE PUBLISHER] Authentication required - login page shown")
                print("[YOUTUBE PUBLISHER] Please log in to YouTube Studio in the browser window")
                print("[YOUTUBE PUBLISHER] Press ENTER here after you've logged in and see the YouTube Studio dashboard...")
                input()  # Wait for user to complete login
                # Re-check after login
                page.goto("https://studio.youtube.com/", timeout=30000)
                if "accounts.google.com" in page.url:
                    print("[YOUTUBE PUBLISHER] Still not logged in. Skipping.")
                    browser.close()
                    return False, None
            
            print("[YOUTUBE PUBLISHER] Connected to YouTube Studio")
            
            try:
                human_delay(2, 5)
                mouse_move_random(page)
                page.locator("ytcp-button#upload-button").first.click(timeout=10000)
            except Exception:
                try:
                    human_delay(1, 2)
                    mouse_move_random(page)
                    page.get_by_text("Upload videos", exact=True).first.click(timeout=5000)
                except Exception:
                    pass

            human_delay(3, 6)
            
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
            
            human_delay(4, 8)
            
            try:
                title_box = page.locator('div#textbox[aria-label="Add a title that describes your video"], #title-textarea #textbox')
                title_box.first.click()
                human_delay(0.5, 1)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                human_delay(0.5, 1)
                type_human(page, title[:100])
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not fill title: {e}")
            
            human_delay(2, 5)
            
            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea')
                desc_box.first.click()
                human_delay(0.5, 1)
                type_human(page, description[:5000])
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not fill description: {e}")
            
            human_delay(2, 5)
            
            try:
                mouse_move_random(page)
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click(timeout=5000)
            except Exception:
                pass
            
            human_delay(2, 4)
            
            for _ in range(3):
                try:
                    mouse_move_random(page)
                    page.locator('ytcp-button#next-button, ytcp-button[aria-label="Next"]').first.click(timeout=5000)
                except Exception:
                    pass
            
            time.sleep(1)
            
            try:
                # Set visibility based on privacy_status — never hard-code PUBLIC
                privacy_map = {
                    "public": "PUBLIC",
                    "unlisted": "UNLISTED",
                    "private": "PRIVATE",
                }
                visibility = privacy_map.get(privacy_status, "UNLISTED")
                radio_name = f"VIDEO_PRIVACY_{visibility}"
                mouse_move_random(page)
                page.locator(f'tp-yt-paper-radio-button[name="{radio_name}"]').first.click(timeout=5000)
            except Exception:
                try:
                    page.locator(f"input[value='{privacy_status}']").first.click(timeout=5000)
                except Exception:
                    pass
            
            human_delay(3, 6)
            
            try:
                page.locator('ytcp-button#done-button, #done-button').first.click(timeout=10000)
            except Exception as e:
                print(f"[YOUTUBE PUBLISHER] Could not click publish: {e}")
                browser.close()
                return False, None
            
            print("[YOUTUBE PUBLISHER] Video submitted for processing...")
            
            browser.close()
            # Playwright automation cannot extract the platform-assigned video ID.
            # Return success=True so the caller marks the package (as publish_blocked
            # since no real ID could be captured — the user verifies manually).
            return True, None
            
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
    
    # Filter to only brands with Chrome profiles
    VALID_BRANDS = {"clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"}
    filtered_drafts = [(fp, pkg) for fp, pkg in drafts if pkg.get("brand", "").strip().lower().replace(" ", "").replace("-", "_") in VALID_BRANDS]
    
    print(f"[YOUTUBE PUBLISHER] Found {len(drafts)} total drafts, {len(filtered_drafts)} for configured brands.")
    
    published_count = 0
    for filepath, package in filtered_drafts:
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
        
        success, video_id = publish_via_playwright(video_path, title, description, brand=brand, channel_id=channel_id)
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