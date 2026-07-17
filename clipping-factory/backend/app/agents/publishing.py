"""
PublishingAgent — publishes a finished clip to social platforms
(TikTok, Instagram, YouTube) via Playwright browser automation.

Design mirrors DeliveryAgent:
  - Reuses an exported logged-in session (Playwright storage_state) per platform,
    configured in settings (tiktok/instagram/youtube_session_state).
  - Gracefully degrades to a SIMULATED result when Playwright is unavailable or
    no session is configured — so the pipeline never hard-fails in dev/demo.
  - Records one SocialPost row per (clip, platform) and writes an audit entry.

Browser publishing is inherently brittle (DOM + anti-bot change often). Each
platform's flow is expressed as a small selector config consumed by one generic
driver, so updating a selector is a one-line change. Official APIs are the
durable long-term path (see master doc §6) — this agent is the no-API-approval
bridge between the clipping engine and the channel manager.
"""
import json
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent
from app.models.social_post import SocialPlatform, SocialPostStatus


# Per-platform browser flow. Selectors are best-effort and intentionally broad
# (multiple comma-separated candidates) so minor DOM changes don't break upload.
_PLATFORM_FLOWS = {
    SocialPlatform.TIKTOK: {
        "upload_url": "https://www.tiktok.com/tiktokstudio/upload",
        "file_input": "input[type='file']",
        "caption": "div[contenteditable='true'], div[data-text='true'], textarea",
        "submit": "button[data-e2e='post_video_button'], button:has-text('Post')",
        "success_url_contains": "/tiktokstudio/content",
    },
    SocialPlatform.INSTAGRAM: {
        "upload_url": "https://www.instagram.com/",
        # IG create flow: click create, then file input appears
        "pre_clicks": [
            "svg[aria-label='New post'], a[href*='/create/'], div[role='button']:has-text('Create')",
            "div[role='button']:has-text('Post')",
        ],
        "file_input": "input[type='file']",
        "caption": "textarea[aria-label*='caption'], div[contenteditable='true']",
        "submit": "div[role='button']:has-text('Share'), button:has-text('Share')",
        "success_url_contains": "/",
    },
    SocialPlatform.YOUTUBE: {
        "upload_url": "https://studio.youtube.com/",
        "pre_clicks": [
            "ytcp-button#create-icon, #create-icon",
            "tp-yt-paper-item:has-text('Upload videos'), #text-item-0",
        ],
        "file_input": "input[type='file']",
        "caption": "#title-textarea #textbox, #textbox",
        "submit": "ytcp-button#done-button, #done-button",
        "success_url_contains": "studio.youtube.com",
    },
}


class PublishingAgent(BaseAgent):
    name = "publishing"

    def __init__(self, db: Session | None = None):
        super().__init__(db)

    def run(self, clip_id: str, platforms: list[str] | None = None) -> AgentResult:
        from app.models.clip import Clip
        from app.models.deliverable import Deliverable
        from app.models.social_post import SocialPost
        from app.core.storage import download_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        targets = SocialPlatform.resolve(platforms or self.settings.publish_platform_list)
        targets = [p for p in targets if p in SocialPlatform.ALL_PLATFORMS]
        if not targets:
            return AgentResult.fail("No valid target platforms (tiktok|instagram|youtube|linkedin|twitter)")

        # Prefer the packaged deliverable file; fall back to the clip's own output.
        deliverable = (
            self.db.query(Deliverable).filter(Deliverable.clip_id == clip_id).first()
        )
        if deliverable and deliverable.storage_key:
            bucket, key, fname = (
                deliverable.storage_bucket,
                deliverable.storage_key,
                deliverable.file_name,
            )
        elif clip.storage_key:
            bucket, key, fname = clip.storage_bucket, clip.storage_key, f"{clip.id[:8]}.mp4"
        else:
            return AgentResult.fail("Clip has no rendered file to publish")

        campaign = clip.campaign
        caption, title = self._build_caption(clip, campaign)

        results: dict[str, dict] = {}
        with tempfile.TemporaryDirectory(prefix="clip_publish_") as tmpdir:
            local_path = download_file(bucket, key, Path(tmpdir) / (fname or "clip.mp4"))

            for platform in targets:
                post = (
                    self.db.query(SocialPost)
                    .filter(SocialPost.clip_id == clip_id, SocialPost.platform == platform)
                    .first()
                )
                if post is None:
                    post = SocialPost(
                        clip_id=clip_id,
                        campaign_id=campaign.id if campaign else None,
                        platform=platform,
                        caption=caption,
                        title=title,
                    )
                    self.db.add(post)
                post.status = SocialPostStatus.UPLOADING
                post.attempts = (post.attempts or 0) + 1
                self.db.flush()

                outcome = self._publish(platform, local_path, caption, title)

                post.status = outcome["status"]
                post.platform_post_id = outcome.get("platform_post_id")
                post.post_url = outcome.get("post_url")
                post.last_error = outcome.get("error")
                post.post_metadata = outcome
                self.db.flush()

                self._audit("clip", clip_id, f"published_{platform}", metadata=outcome)
                results[platform] = outcome
                self.logger.info(
                    f"[{platform}] clip {clip_id[:8]} -> {outcome['status']} "
                    f"{outcome.get('post_url') or outcome.get('error') or ''}"
                )

        published = [p for p, o in results.items() if o["status"] in
                     (SocialPostStatus.PUBLISHED, SocialPostStatus.SIMULATED)]

        # Send Telegram notification for published clips
        for platform, outcome in results.items():
            if outcome["status"] == SocialPostStatus.PUBLISHED and outcome.get("post_url"):
                self._notify_telegram(platform, clip_id, outcome["post_url"], campaign)

        return AgentResult.ok({"clip_id": clip_id, "results": results, "published": published})

    # ------------------------------------------------------------------

    def _build_caption(self, clip, campaign) -> tuple[str, str]:
        """Compose a caption/title from the clip hook and campaign metadata."""
        hooks = (clip.scores or {}).get("hook_variants", [])
        hook = (clip.hook_text or "").strip()
        if not hook and hooks:
            hook = hooks[0]

        brand = (campaign.brand_name if campaign and campaign.brand_name else "").strip()
        title = hook or (campaign.title if campaign else "New clip")
        parts = [hook] if hook else []
        if brand:
            parts.append(f"#{brand.replace(' ', '')}")
        parts.append("#shorts #viral #fyp")
        caption = " ".join(parts).strip()
        return caption[:2200], title[:100]

    def _publish(self, platform: str, video_path: Path, caption: str, title: str) -> dict:
        """Publish to one platform; simulate when Playwright/session unavailable."""
        flow = _PLATFORM_FLOWS[platform]
        session_state = self.settings.social_session_state(platform)

        # YouTube: try Data API first (no session needed), then Playwright
        if platform == SocialPlatform.YOUTUBE:
            api_result = self._publish_youtube_api(video_path, caption, title)
            if api_result:
                return api_result

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return self._simulated(platform, "playwright not installed")

        if not session_state:
            return self._simulated(platform, "no session configured")

        try:
            storage_state = json.loads(session_state)
        except json.JSONDecodeError as exc:
            return {"status": SocialPostStatus.FAILED, "platform": platform,
                    "error": f"invalid session_state JSON: {exc}"}

        result = {"status": SocialPostStatus.FAILED, "platform": platform,
                  "platform_post_id": None, "post_url": None, "error": None}

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.settings.publish_headless,
                slow_mo=self.settings.publish_slow_mo_ms or 0,
                args=["--no-sandbox"],
            )
            try:
                context = browser.new_context(
                    storage_state=storage_state,
                    locale="en-US",
                    timezone_id="America/New_York",
                    geolocation={"longitude": -74.006, "latitude": 40.7128},
                    permissions=["geolocation"]
                )
                pw_page = context.new_page()
                timeout = self.settings.publish_timeout_ms

                pw_page.goto(flow["upload_url"], wait_until="domcontentloaded", timeout=timeout)

                # Optional pre-clicks to reach the upload widget (IG/YouTube).
                for selector in flow.get("pre_clicks", []):
                    el = pw_page.query_selector(selector)
                    if el:
                        el.click()
                        pw_page.wait_for_timeout(1500)

                pw_page.wait_for_selector(flow["file_input"], timeout=timeout)
                pw_page.set_input_files(flow["file_input"], str(video_path))
                # Give the platform time to process/transcode the upload.
                pw_page.wait_for_timeout(5000)

                caption_el = pw_page.query_selector(flow["caption"])
                if caption_el:
                    try:
                        caption_el.click()
                        caption_el.fill(caption)
                    except Exception:
                        caption_el.type(caption, delay=10)

                submit_el = pw_page.query_selector(flow["submit"])
                if not submit_el:
                    result["error"] = "submit button not found (DOM changed?)"
                    return result

                submit_el.click()
                pw_page.wait_for_timeout(5000)

                result["status"] = SocialPostStatus.PUBLISHED
                result["post_url"] = pw_page.url
                result["error"] = None

            except PWTimeout:
                result["error"] = "Playwright timeout during publish"
            except Exception as exc:  # noqa: BLE001 — record any browser failure
                result["error"] = str(exc)
            finally:
                browser.close()

        if result["status"] != SocialPostStatus.PUBLISHED and result["error"]:
            self.logger.warning(f"[{platform}] publish failed: {result['error']}")
        return result

    def _publish_youtube_api(self, video_path: Path, caption: str, title: str) -> dict | None:
        """Try YouTube Data API upload using stored OAuth tokens. Returns None if no tokens."""
        tokens_path = Path(__file__).parent.parent.parent.parent / "youtube_tokens.json"
        if not tokens_path.exists():
            return None

        try:
            import json as _json
            tokens = _json.loads(tokens_path.read_text())
            if not tokens:
                return None

            # Use first configured channel
            cid = next(iter(tokens))
            info = tokens[cid]

            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials(
                token=info.get("access_token"),
                refresh_token=info["refresh_token"],
                token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=info["client_id"],
                client_secret=info["client_secret"],
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )
            if creds.expired or not creds.token:
                creds.refresh(Request())
                tokens[cid]["access_token"] = creds.token
                tokens_path.write_text(_json.dumps(tokens, indent=2))

            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": caption[:5000],
                    "tags": ["shorts", "viral", "fyp"],
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

            video_id = response.get("id", "")
            self.logger.info(f"[youtube] API upload success: {video_id}")

            return {
                "status": SocialPostStatus.PUBLISHED,
                "platform": "youtube",
                "platform_post_id": video_id,
                "post_url": f"https://youtube.com/watch?v={video_id}",
                "error": None,
                "method": "youtube_data_api",
            }

        except Exception as exc:
            self.logger.warning(f"[youtube] API upload failed: {exc}")
            return None

    def _simulated(self, platform: str, reason: str) -> dict:
        """Mock result so the pipeline stays runnable without creds/Playwright."""
        self.logger.info(f"[{platform}] simulated publish ({reason})")
        return {
            "status": SocialPostStatus.SIMULATED,
            "platform": platform,
            "platform_post_id": f"sim-{platform}",
            "post_url": f"https://{platform}.com/@demo/simulated",
            "error": None,
            "simulated_reason": reason,
        }

    def _notify_telegram(self, platform: str, clip_id: str, post_url: str, campaign) -> None:
        """Send Telegram notification with the published clip video + link."""
        try:
            from app.services.telegram_notifier import TelegramNotifier
            from app.models.clip import Clip
            db = self.db
            clip = db.query(Clip).filter(Clip.id == clip_id).first() if db else None
            tg = TelegramNotifier(self.settings)

            if clip:
                tg.notify_clip_published(platform, clip, post_url)
            else:
                brand = (campaign.brand_name if campaign and campaign.brand_name else "").strip()
                title = (campaign.title if campaign else "")[:50] or "New clip"
                tg.send_message(
                    f"🌐 *Clip Published*\n"
                    f"Platform: {platform.title()}\n"
                    f"Campaign: {brand or title}\n"
                    f"URL: {post_url}"
                )
            self.logger.info(f"Telegram notified: {platform} clip {clip_id[:8]}")
        except Exception as exc:
            self.logger.error(f"Telegram notification failed: {exc}")
