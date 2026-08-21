"""
YouTube CDP Publisher Module.
Attaches to live Native Chrome browser running with --remote-debugging-port=9222.
Bypasses all bot flags and uses active Google login sessions.
"""
import os
import json
import re
import time
import glob as _glob
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
    """Mark package as published with real platform video_id.

    NEVER fabricates a video_id. Without a real ID, marks as publish_blocked.
    """
    if not video_id:
        data["status"] = "publish_blocked"
        data["publish_blocked_reason"] = "platform_identity_not_verified"
        data["publish_blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[CDP PUBLISHER] Marked as PUBLISH_BLOCKED (no real video ID): {filepath}")
        return

    data["status"] = "published"
    data["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["youtube_video_id"] = video_id
    data["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[CDP PUBLISHER] Marked as published: {filepath}")

def human_delay(min_s, max_s):
    delay = min_s + (max_s - min_s) * 0.5
    time.sleep(delay)

def publish_via_cdp(video_path, title, description, brand_display_name=None, cdp_url="http://localhost:9222"):
    if not os.path.exists(video_path):
        print(f"[CDP PUBLISHER] Video file not found: {video_path}")
        return False, None, None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[CDP PUBLISHER] Playwright not installed.")
        return False, None, None

    print(f"[CDP PUBLISHER] Connecting to native Chrome at {cdp_url}...")
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(cdp_url, timeout=10000)
            except Exception as e:
                print(f"[CDP PUBLISHER] Could not connect to Chrome at {cdp_url}: {e}")
                return False, None, None

            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = None
            _reused_page = False
            for _pg in context.pages:
                try:
                    if 'studio.youtube.com' in _pg.url and 'reauth' not in _pg.url:
                        page = _pg
                        _reused_page = True
                        break
                except Exception:
                    continue
            if page is None:
                page = context.new_page()
            else:
                print(f"[CDP PUBLISHER] Reusing authenticated Studio tab: {page.url[:80]}")
                page.bring_to_front()

            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'permissions', {
                    query: () => Promise.resolve({ state: 'granted' })
                });
                window.chrome = { runtime: {} };
            """)

            print(f"[CDP PUBLISHER] Navigating to YouTube Studio...")
            try:
                page.goto("https://studio.youtube.com/", timeout=45000, wait_until="domcontentloaded")
            except Exception:
                pass
            human_delay(2, 5)

            if "accounts.google.com" in page.url:
                print("[CDP PUBLISHER] Chrome is not logged in to Google.")
                if not _reused_page:
                    page.close()
                return False, None, None

            if brand_display_name:
                print(f"[CDP PUBLISHER] Switching account to '{brand_display_name}'...")
                try:
                    page.locator('button#avatar-btn').wait_for(state='visible', timeout=10000)
                    page.locator('button#avatar-btn').click()
                    
                    import time
                    time.sleep(1)
                    switch_btn = page.locator('yt-formatted-string:has-text("Switch account")').first
                    if switch_btn.count() > 0:
                        switch_btn.click()
                        time.sleep(1)
                        channel_btn = page.locator(f'yt-formatted-string:has-text("{brand_display_name}")').first
                        if channel_btn.count() > 0:
                            channel_btn.click()
                            time.sleep(5)
                            page.wait_for_load_state('domcontentloaded')
                            print(f"[CDP PUBLISHER] Successfully switched to '{brand_display_name}'.")
                        else:
                            print(f"[CDP PUBLISHER] Warning: Channel '{brand_display_name}' not found.")
                    else:
                        print("[CDP PUBLISHER] Warning: 'Switch account' option not found.")
                except Exception as e:
                    print(f"[CDP PUBLISHER] Warning: Could not switch account: {e}")

            print(f"[CDP PUBLISHER] Uploading '{title}'...")
            
            def _wait_for_verification(page, timeout=180):
                deadline = time.time() + timeout
                cleared_streak = 0
                while time.time() < deadline:
                    has_dialog = False
                    try:
                        has_dialog = page.locator('ytcp-auth-confirmation-dialog').count() > 0
                    except Exception:
                        pass
                    if has_dialog:
                        cleared_streak = 0
                        print("[CDP PUBLISHER] YouTube verification challenge present!")
                        print("[CDP PUBLISHER] >>> OPEN CHROME AND COMPLETE THE 'Verify it's you' PROMPT NOW <<<")
                        try:
                            page.wait_for_selector('ytcp-auth-confirmation-dialog', state='detached', timeout=10000)
                        except Exception:
                            pass
                    else:
                        cleared_streak += 1
                        if cleared_streak >= 3:
                            return True
                    time.sleep(2)
                print("[CDP PUBLISHER] Verification challenge NOT cleared in time — aborting.")
                return False

            def _open_upload_dialog(page):
                try:
                    page.goto("https://studio.youtube.com/", timeout=20000, wait_until="domcontentloaded")
                    human_delay(3, 5)
                except Exception:
                    pass
                for _ in range(6):
                    try:
                        if page.locator("input[type='file']").count() > 0:
                            return True
                    except Exception:
                        pass
                    try:
                        page.get_by_text("Create", exact=True).first.click(timeout=4000)
                        human_delay(1, 2)
                    except Exception:
                        pass
                    try:
                        for _sel in ['ytcp-menu-item:has-text("Upload videos")',
                                     'tp-yt-paper-listbox ytcp-list-item:has-text("Upload videos")',
                                     'div[role="menuitem"]:has-text("Upload videos")',
                                     'ytcp-button:has-text("Upload videos")']:
                            try:
                                loc = page.locator(_sel).first
                                if loc.count() > 0:
                                    loc.click(timeout=4000)
                                    break
                            except Exception:
                                continue
                        human_delay(2, 4)
                    except Exception:
                        pass
                return page.locator("input[type='file']").count() > 0

            if not _open_upload_dialog(page):
                print("[CDP PUBLISHER] Could not open upload dialog.")
                if not _reused_page:
                    page.close()
                return False, None, None

            human_delay(2, 4)

            file_input = page.locator("input[type='file']").first
            _set_ok = False
            for _try in range(4):
                try:
                    if file_input.count() > 0:
                        file_input.set_input_files(video_path, timeout=20000)
                        _set_ok = True
                        break
                except Exception as _e:
                    print(f"[CDP PUBLISHER] set_input_files retry {_try+1}: {str(_e)[:100]}")
                    human_delay(2, 3)
            if not _set_ok:
                try:
                    file_input.set_input_files(video_path, timeout=20000, force=True)
                    _set_ok = True
                except Exception as _e:
                    print(f"[CDP PUBLISHER] set_input_files failed: {str(_e)[:120]}")
                    if not _reused_page:
                        page.close()
                    return False, None, None
            human_delay(4, 8)

            if not _wait_for_verification(page):
                if not _reused_page:
                    page.close()
                return False, None, None

            try:
                title_box = page.locator('div#textbox[aria-label="Add a title that describes your video"], #title-textarea #textbox')
                title_box.first.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                human_delay(0.5, 1)
                page.keyboard.type(title[:100])
            except Exception as e:
                print(f"[CDP PUBLISHER] Title fill warning: {e}")

            human_delay(1, 2)
            _wait_for_verification(page, timeout=30)

            try:
                desc_box = page.locator('div#textbox[aria-label="Tell viewers about your video"], #description-textarea #textbox')
                desc_box.first.click()
                page.keyboard.type(description[:5000])
            except Exception as e:
                print(f"[CDP PUBLISHER] Description fill warning: {e}")

            human_delay(1, 2)

            try:
                page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click(timeout=5000)
            except Exception:
                pass

            human_delay(1, 2)
            _wait_for_verification(page, timeout=30)

            for _ in range(3):
                try:
                    page.locator('ytcp-button#next-button, ytcp-button[aria-label="Next"]').first.click(timeout=5000)
                except Exception:
                    pass
                human_delay(1, 2)
                _wait_for_verification(page, timeout=30)

            try:
                page.locator('tp-yt-paper-radio-button[name="PUBLIC"], #privacy-radio-public').first.click(timeout=5000)
            except Exception:
                pass

            human_delay(2, 4)

            try:
                page.locator('ytcp-button#publish-button, ytcp-button#done-button, button[aria-label="Publish"]').first.click(timeout=10000)
            except Exception as e:
                print(f"[CDP PUBLISHER] Publish click warning: {e}")

            human_delay(3, 6)
            _wait_for_verification(page, timeout=30)
            video_id = None
            channel_id = None
            try:
                page.wait_for_url("**/studio.youtube.com/video/*/edit**", timeout=45000)
            except Exception:
                pass
            m = re.search(r"/video/([A-Za-z0-9_-]{6,20})", page.url or "")
            if m:
                video_id = m.group(1)
                print(f"[CDP PUBLISHER] Captured real video id: {video_id}")
            else:
                try:
                    if page.locator('ytcp-video-share-dialog').count() > 0:
                        print("[CDP PUBLISHER] Publish share dialog detected - extracting video id...")
                        share = page.locator('ytcp-video-share-dialog').first
                        txt = share.inner_text(timeout=8000)
                        m2 = re.search(r"(?:watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,20})", txt)
                        if m2:
                            video_id = m2.group(1)
                            print(f"[CDP PUBLISHER] Captured video id from share dialog text: {video_id}")
                        else:
                            for el in share.locator('input, a').all():
                                try:
                                    val = el.get_attribute('value') or el.get_attribute('href') or ''
                                    m3 = re.search(r"(?:watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,20})", val)
                                    if m3:
                                        video_id = m3.group(1)
                                        print(f"[CDP PUBLISHER] Captured video id from share dialog field: {video_id}")
                                        break
                                except Exception:
                                    continue
                except Exception as e:
                    print(f"[CDP PUBLISHER] Share dialog id extraction failed: {e}")
                if not video_id:
                    try:
                        import urllib.request
                        if channel_id is None:
                            try:
                                channel_id = page.evaluate(
                                    "() => { try { return window.ytcfg && ytcfg.get ? "
                                    "(ytcfg.get('CHANNEL_ID') || ytcfg.get('CHANNEL_ID_DELEGATED') || null) : null } catch(e){ return null } }"
                                )
                            except Exception:
                                pass
                        feed_title = re.sub(r"\s+", " ", (title or "").strip())[:60]
                        feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=%s" % channel_id
                        req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            feed = r.read().decode("utf-8", errors="replace")
                        known = set()
                        try:
                            qdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "publish_queue")
                            for qf in _glob.glob(os.path.join(qdir, "*.json")):
                                try:
                                    with open(qf, encoding="utf-8") as qh:
                                        qd = json.load(qh)
                                    vid = qd.get("youtube_video_id")
                                    if vid and re.match(r"^[A-Za-z0-9_-]{11}$", str(vid)):
                                        known.add(str(vid))
                                except Exception:
                                    continue
                        except Exception:
                            pass
                        entries = re.findall(
                            r"<entry>.*?<yt:videoId>([A-Za-z0-9_-]{6,20})</yt:videoId>.*?<title>(.*?)</title>.*?</entry>",
                            feed, re.S)
                        for fid, ftitle in entries:
                            ftitle_clean = re.sub(r"<[^>]+>", "", ftitle).strip()
                            if feed_title and (feed_title.lower() in ftitle_clean.lower()
                                               or ftitle_clean.lower() in feed_title.lower()):
                                if fid in known:
                                    print(f"[CDP PUBLISHER] RSS title match {fid} already recorded - skipping")
                                    continue
                                video_id = fid
                                print(f"[CDP PUBLISHER] Captured NEW video id from RSS feed: {video_id}")
                                break
                    except Exception as e:
                        print(f"[CDP PUBLISHER] RSS fallback failed: {e}")
            if channel_id is None:
                try:
                    channel_id = page.evaluate(
                        "() => { try { return window.ytcfg && ytcfg.get ? "
                        "(ytcfg.get('CHANNEL_ID') || ytcfg.get('CHANNEL_ID_DELEGATED') || null) : null } catch(e){ return null } }"
                    )
                    if channel_id:
                        print(f"[CDP PUBLISHER] Current channel id: {channel_id}")
                except Exception:
                    pass
            if not _reused_page:
                page.close()
            if not video_id:
                print("[CDP PUBLISHER] No real video id captured - upload NOT confirmed.")
                return False, None, channel_id
            print(f"[CDP PUBLISHER] Video upload confirmed with real id: {video_id}")
            return True, video_id, channel_id

    except Exception as e:
        print(f"[CDP PUBLISHER] Execution error: {e}")
        return False, None, None

def get_current_channel(cdp_url="http://localhost:9222"):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            try:
                page.goto("https://studio.youtube.com/channel/UC/editing/details", timeout=30000)
                time.sleep(3)
            except Exception:
                try:
                    page.goto("https://www.youtube.com/", timeout=30000)
                except Exception:
                    pass
            info = {"channel_id": None, "name": None, "handle": None, "email": None, "url": page.url}
            if "accounts.google.com" not in page.url:
                try:
                    info["channel_id"] = page.evaluate(
                        "() => { try { const o={}; if (window.ytcfg && ytcfg.get){"
                        " ['CHANNEL_ID', 'CHANNEL_ID_DELEGATED'].forEach(k => { const v = ytcfg.get(k); if (v) o[k] = v });"
                        " const d = o.CHANNEL_ID_DELEGATED || o.CHANNEL_ID; if (d) return d;"
                        " const a = document.querySelector('a[href*=\"/channel/\"]'); "
                        " if (a) { const m = a.getAttribute('href').match(/channel\\/(UC[\\w-]+)/); if (m) return m[1]; }"
                        " const s = document.querySelector('#account-name, ytcp-text#account-name'); "
                        " if (s) return s.textContent.trim().slice(0,80); return null; } catch(e){ return null; } }"
                    )
                except Exception:
                    pass
                try:
                    info["name"] = page.evaluate(
                        "() => { try { const el = document.querySelector('a[href*=\"/@\"] > yt-formatted-string, "
                        "#channel-title, ytcp-text#channel-name, ytcd-text, #account-name'); "
                        "return el ? el.textContent.trim().slice(0,80) : null } catch(e){ return null } }"
                    )
                except Exception:
                    pass
                if info["channel_id"] and info["channel_id"].startswith("UC"):
                    try:
                        info["handle"] = page.evaluate(
                            "() => { try { const a = document.querySelector('a[href*=\"@\"]'); "
                            "if (a) { const m = a.getAttribute('href').match(/@([^/?]+)/); if (m) return '@'+m[1]; } "
                            "return null } catch(e){ return null } }"
                        )
                    except Exception:
                        pass
            page.close()
            return info
    except Exception as e:
        print(f"[CDP PUBLISHER] get_current_channel error: {e}")
        return None


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
        success, video_id, _channel_id = publish_via_cdp(video_path, title, description)
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
