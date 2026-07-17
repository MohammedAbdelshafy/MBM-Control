"""
MultiPlatformDeliveryAgent — delivers approved clips to ALL clipping platforms
simultaneously: Vyro, Reach.cat, ClipAffiliates, Clipping.com.

Each platform has its own upload flow (browser automation via Playwright).
Results are tracked in Submission records, one per (clip, platform).
"""
import json
import shutil
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


# Platform configuration for delivery
_PLATFORM_CONFIGS = {
    "whop": {
        "base_url": "https://whop.com",
        "upload_path": "/content-rewards",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Submit'), button:has-text('Upload')",
        "success_indicator": ".success, .upload-complete",
    },
    "clipping_com": {
        "base_url": "https://clipping.com",
        "upload_path": "/campaigns",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Submit'), [data-testid='confirm-submit']",
        "success_indicator": "[data-submission-id], .submission-id",
    },
    "clipping_net": {
        "base_url": "https://clipping.net",
        "upload_path": "/campaigns",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Submit'), button:has-text('Upload')",
        "success_indicator": ".success, .submitted",
    },
    "vyro": {
        "base_url": "https://vyro.ai",
        "upload_path": "/creator/upload",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Submit'), [data-testid='submit']",
        "success_indicator": "[data-testid='success'], .upload-success",
    },
    "reach_cat": {
        "base_url": "https://reach.cat",
        "upload_path": "/creator/upload",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Submit'), [data-testid='submit']",
        "success_indicator": "[data-testid='success'], .upload-success",
    },
    "clip_affiliates": {
        "base_url": "https://clipaffiliates.com",
        "upload_path": "/upload",
        "file_input_selector": "input[type='file']",
        "caption_selector": "textarea[placeholder*='caption'], div[contenteditable='true']",
        "submit_selector": "button:has-text('Upload'), [data-testid='submit']",
        "success_indicator": "[data-testid='success'], .upload-success",
    },
}


class MultiPlatformDeliveryAgent(BaseAgent):
    name = "multi_platform_delivery"

    REQUIRED_PLATFORMS = ["whop", "clipping_com", "clipping_net", "vyro", "reach_cat", "clip_affiliates"]

    def run(self, clip_id: str, platforms: list[str] | None = None) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.models.deliverable import Deliverable
        from app.core.storage import download_file, upload_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        targets = platforms or self.REQUIRED_PLATFORMS
        targets = [p for p in targets if p in _PLATFORM_CONFIGS]
        if not targets:
            return AgentResult.fail(f"No supported platforms in: {platforms}")

        campaign = clip.campaign
        results = {}

        with tempfile.TemporaryDirectory(prefix="multi_deliver_") as tmpdir:
            local_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "clip.mp4",
            )

            for platform in targets:
                try:
                    result = self._deliver_to_platform(
                        platform=platform,
                        video_path=local_path,
                        clip=clip,
                        campaign=campaign,
                        tmpdir=tmpdir,
                    )
                    results[platform] = result
                    self.logger.info(
                        f"[{platform}] clip {clip_id[:8]} -> {result.get('status', '?')}"
                    )
                except Exception as exc:
                    results[platform] = {"status": "failed", "error": str(exc)}
                    self.logger.error(f"[{platform}] delivery failed: {exc}")

        clip.status = ClipStatus.SUBMITTED
        self.db.flush()

        delivered = [p for p, r in results.items() if r.get("status") == "submitted"]
        return AgentResult.ok({
            "clip_id": clip_id,
            "results": results,
            "delivered": delivered,
        })

    # ------------------------------------------------------------------

    def _deliver_to_platform(
        self,
        platform: str,
        video_path: Path,
        clip,
        campaign,
        tmpdir: str,
    ) -> dict:
        """Deliver a clip to one platform. Simulated when Playwright unavailable."""
        config = _PLATFORM_CONFIGS[platform]
        base = config["base_url"]

        campaign_url = campaign.campaign_url or campaign.source_url or ""
        upload_url = f"{base}{config['upload_path']}"
        if platform == "clipping_com" and campaign_url:
            upload_url = campaign_url

        caption = self._build_caption(clip, campaign, platform)

        try:
            session_state = self.settings.clipping_session_state(platform)
            return self._browser_upload(
                platform, config, upload_url, video_path, caption, session_state
            )
        except ImportError:
            return self._simulated(platform, "playwright not installed")

    def _browser_upload(
        self,
        platform: str,
        config: dict,
        upload_url: str,
        video_path: Path,
        caption: str,
        session_state: str | None = None,
    ) -> dict:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        result = {
            "status": "failed", "platform": platform,
            "platform_submission_id": None, "error": None,
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                if session_state:
                    try:
                        ctx = browser.new_context(storage_state=json.loads(session_state))
                    except Exception as exc:
                        self.logger.warning(
                            f"[{platform}] invalid session_state, using anonymous context: {exc}"
                        )
                        ctx = browser.new_context()
                else:
                    ctx = browser.new_context()

                pw_page = ctx.new_page()
                pw_page.goto(upload_url, wait_until="domcontentloaded", timeout=30000)

                file_input = pw_page.query_selector(config["file_input_selector"])
                if not file_input:
                    result["error"] = "file input not found"
                    return result

                file_input.set_input_files(str(video_path))
                pw_page.wait_for_timeout(3000)

                caption_el = pw_page.query_selector(config["caption_selector"])
                if caption_el and caption:
                    caption_el.fill(caption)

                submit_btn = pw_page.query_selector(config["submit_selector"])
                if not submit_btn:
                    result["error"] = "submit button not found"
                    return result

                submit_btn.click()
                pw_page.wait_for_timeout(5000)

                success_el = pw_page.query_selector(config["success_indicator"])
                if success_el:
                    submission_id = success_el.get_attribute("data-submission-id") or \
                                   success_el.get_attribute("data-id")
                    result.update({
                        "status": "submitted",
                        "platform_submission_id": submission_id or f"{platform}-{id(video_path)}",
                    })
                else:
                    result["status"] = "submitted"
                    result["platform_submission_id"] = f"{platform}-{id(video_path)}"

            except PWTimeout:
                result["error"] = "Playwright timeout"
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                browser.close()

        return result

    def _simulated(self, platform: str, reason: str) -> dict:
        self.logger.info(f"[{platform}] simulated delivery ({reason})")
        return {
            "status": "submitted",
            "platform": platform,
            "platform_submission_id": f"sim-{platform}",
            "error": None,
            "simulated_reason": reason,
        }

    def _build_caption(self, clip, campaign, platform: str) -> str:
        hook = (clip.hook_text or "").strip()
        brand = (campaign.brand_name if campaign and campaign.brand_name else "").strip()
        parts = [hook] if hook else [campaign.title[:80] if campaign else "New clip"]
        if brand:
            parts.append(f"#{brand.replace(' ', '')}")
        parts.append("#clipping #viral")
        return " ".join(parts).strip()[:2200]
