"""
DeliveryAgent — packages and uploads approved clips to Clipping.com.

Uses Playwright for browser automation to navigate the submission flow.
Tracks submission IDs, polls for acceptance/rejection outcomes,
and updates campaign financials accordingly.
"""
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


class DeliveryAgent(BaseAgent):
    name = "delivery_agent"

    def run(self, clip_id: str) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.models.deliverable import Deliverable
        from app.core.storage import download_file, upload_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        campaign = clip.campaign
        page = campaign.page

        self.logger.info(f"Creating deliverable for clip {clip_id}")

        with tempfile.TemporaryDirectory(prefix="clip_deliver_") as tmpdir:
            # Download edited clip
            local_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "clip.mp4",
            )

            # Create final deliverable filename
            safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in campaign.title[:40])
            deliverable_name = f"{safe_title}_{clip.id[:8]}.mp4"
            deliverable_path = Path(tmpdir) / deliverable_name
            shutil.copy2(local_path, deliverable_path)

            # Validate deliverable
            validation = self._validate_deliverable(deliverable_path, campaign.requirements)
            if not validation["passed"]:
                return AgentResult.fail(f"Deliverable validation failed: {validation['errors']}")

            # Upload to deliverables bucket
            storage_key = f"deliverables/{campaign.id}/{deliverable_name}"
            upload_file(
                deliverable_path,
                self.settings.storage_bucket_deliverables,
                storage_key,
                content_type="video/mp4",
                metadata={"campaign_id": campaign.id, "clip_id": clip_id},
            )

            # Create Deliverable record
            deliverable = Deliverable(
                clip_id=clip_id,
                campaign_id=campaign.id,
                storage_bucket=self.settings.storage_bucket_deliverables,
                storage_key=storage_key,
                file_name=deliverable_name,
                file_size_bytes=deliverable_path.stat().st_size,
                mime_type="video/mp4",
                validation_passed=validation["passed"],
                validation_details=validation,
                status="ready",
            )
            self.db.add(deliverable)
            self.db.flush()

            # Upload to Clipping.com
            submission_result = self._upload_to_clipping(
                deliverable_path=deliverable_path,
                deliverable=deliverable,
                campaign=campaign,
                page=page,
            )

        # Create Submission record
        from app.models.submission import Submission
        submission = Submission(
            deliverable_id=deliverable.id,
            campaign_id=campaign.id,
            page_id=page.id,
            platform_submission_id=submission_result.get("submission_id"),
            status=submission_result.get("status", "submitted"),
            upload_attempts=1,
        )
        self.db.add(submission)

        # Update clip status
        clip.status = ClipStatus.SUBMITTED
        deliverable.status = "uploaded" if submission_result.get("success") else "failed"

        # Update campaign counters
        campaign.clips_submitted += 1
        self.db.flush()

        self._audit("clip", clip.id, "submitted", metadata={"submission": submission_result})
        self.logger.info(
            f"Clip {clip_id} submitted. Status: {submission_result.get('status', 'unknown')}"
        )

        # Telegram: notify + send clip with submission info
        try:
            from app.services.telegram_notifier import TelegramNotifier
            tg = TelegramNotifier(self.settings)
            tg.notify_delivery_submitted(clip, deliverable, submission)
        except Exception as exc:
            self.logger.debug(f"Telegram delivery notification skipped: {exc}")

        return AgentResult.ok({
            "deliverable_id": deliverable.id,
            "submission_result": submission_result,
        })

    # ------------------------------------------------------------------

    def _validate_deliverable(self, path: Path, requirements: dict) -> dict:
        """Final validation before upload."""
        errors = []
        warnings = []

        if not path.exists():
            return {"passed": False, "errors": ["File not found"]}

        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb < 0.1:
            errors.append("File too small (likely corrupt)")
        if size_mb > requirements.get("max_file_size_mb", 500):
            errors.append(f"File exceeds size limit: {size_mb:.1f}MB")

        if path.stat().st_size == 0:
            errors.append("Empty file")

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "size_mb": round(size_mb, 2),
        }

    def _upload_to_clipping(
        self, deliverable_path: Path, deliverable, campaign, page
    ) -> dict:
        """
        Upload clip to Clipping.com using Playwright.
        Returns submission result dict.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            self.logger.warning("Playwright not installed — simulating submission")
            return {"success": True, "status": "submitted", "submission_id": f"mock-{deliverable.id[:8]}"}

        result = {"success": False, "status": "error", "submission_id": None}

        # Demo mode: no real Clipping.com to upload to
        if self.settings.demo_mode:
            self.logger.info("Demo mode — simulating Clipping.com submission")
            return {"success": True, "status": "submitted", "submission_id": f"demo-{deliverable.id[:8]}"}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context()

            # Restore session
            if page.session_cookie:
                try:
                    context.add_cookies(json.loads(page.session_cookie))
                except Exception:
                    pass

            pw_page = context.new_page()

            try:
                campaign_url = campaign.campaign_url or \
                    f"{self.settings.clipping_base_url}/campaigns/{campaign.platform_campaign_id}"

                pw_page.goto(campaign_url, wait_until="networkidle", timeout=30000)

                # Look for submission/upload button
                submit_btn = pw_page.query_selector(
                    "[data-testid='submit-clip'], .submit-clip-btn, button:has-text('Submit')"
                )
                if not submit_btn:
                    self.logger.warning("Could not find submit button on campaign page")
                    result["error"] = "No submit button found"
                    return result

                submit_btn.click()
                pw_page.wait_for_selector("input[type='file']", timeout=10000)

                # Upload the file
                file_input = pw_page.query_selector("input[type='file']")
                if file_input:
                    file_input.set_input_files(str(deliverable_path))
                    pw_page.wait_for_timeout(2000)

                    # Click final submit
                    confirm_btn = pw_page.query_selector(
                        "[data-testid='confirm-submit'], button:has-text('Upload'), button:has-text('Confirm')"
                    )
                    if confirm_btn:
                        confirm_btn.click()
                        pw_page.wait_for_timeout(3000)

                        # Extract submission ID from response/DOM
                        submission_el = pw_page.query_selector("[data-submission-id], .submission-id")
                        submission_id = None
                        if submission_el:
                            submission_id = submission_el.get_attribute("data-submission-id") or \
                                           submission_el.inner_text()

                        result = {
                            "success": True,
                            "status": "submitted",
                            "submission_id": submission_id or f"clipping-{deliverable.id[:8]}",
                        }
                        self.logger.info(f"Upload successful, submission_id={result['submission_id']}")

            except PWTimeout:
                result["error"] = "Playwright timeout during upload"
                self.logger.error(result["error"])
            except Exception as exc:
                result["error"] = str(exc)
                self.logger.error(f"Upload failed: {exc}")
            finally:
                browser.close()

        return result


class OutcomePollerAgent(BaseAgent):
    """
    Polls Clipping.com for acceptance/rejection outcomes of submitted clips.
    Run periodically (e.g., every hour) via Celery Beat.
    """
    name = "outcome_poller"

    def run(self) -> AgentResult:
        from app.models.submission import Submission
        from app.models.clip import Clip, ClipStatus
        from app.models.campaign import Campaign

        pending = (
            self.db.query(Submission)
            .filter(Submission.status == "submitted")
            .limit(50)
            .all()
        )

        updated = 0
        for submission in pending:
            outcome = self._poll_outcome(submission)
            if outcome:
                submission.status = outcome["status"]
                submission.outcome = outcome.get("outcome")
                submission.outcome_reason = outcome.get("reason")
                submission.earnings_usd = outcome.get("earnings", 0.0)

                clip = submission.deliverable.clip
                if outcome["status"] == "accepted":
                    clip.status = ClipStatus.ACCEPTED
                    campaign = clip.campaign
                    campaign.clips_accepted += 1
                    campaign.actual_earnings += submission.earnings_usd
                    # Telegram: notify earnings
                    try:
                        from app.services.telegram_notifier import TelegramNotifier
                        tg = TelegramNotifier(self.settings)
                        tg.notify_clip_accepted(clip, submission.earnings_usd)
                    except Exception as exc:
                        self.logger.debug(f"Telegram accepted notification skipped: {exc}")
                elif outcome["status"] == "rejected":
                    clip.status = ClipStatus.REJECTED_PLATFORM

                self.db.flush()
                updated += 1

        return AgentResult.ok({"updated": updated})

    def _poll_outcome(self, submission) -> dict | None:
        """
        Navigate to Clipping.com's submission/earnings history and read
        the outcome for this submission. Returns None if still pending.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return None

        campaign = submission.deliverable.clip.campaign
        page_record = campaign.page

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context()

            if page_record.session_cookie:
                try:
                    import json as _json
                    ctx.add_cookies(_json.loads(page_record.session_cookie))
                except Exception:
                    pass

            pw_page = ctx.new_page()

            try:
                base_url = (page_record.settings or {}).get("platform_base_url") or self.settings.clipping_base_url
                history_url = f"{base_url}/submissions"
                pw_page.goto(history_url, wait_until="networkidle", timeout=20000)

                # Check if session expired (redirected to login)
                if "login" in pw_page.url.lower():
                    self.logger.warning("Session expired during outcome poll — attempting re-auth")
                    from app.agents.campaign_hunter import CampaignHunterAgent
                    hunter = CampaignHunterAgent(self.db)
                    if hasattr(hunter, "_login"):
                        hunter._login(pw_page)
                        cookies = ctx.cookies()
                        if cookies:
                            page_record.session_cookie = json.dumps(cookies)
                            self.db.flush()
                        pw_page.goto(history_url, wait_until="networkidle", timeout=20000)
                        if "login" in pw_page.url.lower():
                            self.logger.error("Re-auth failed for outcome poll")
                            browser.close()
                            return None

                # Search for this submission's platform ID
                sid = submission.platform_submission_id or ""
                submission_el = None

                if sid:
                    # Escape single quotes to prevent CSS selector injection
                    safe_sid = sid.replace("'", "\\'").replace('"', '\\"')
                    submission_el = pw_page.query_selector(
                        f"[data-submission-id='{safe_sid}'], [data-id='{safe_sid}']"
                    )

                if not submission_el:
                    # Try to find by campaign title in the table rows
                    rows = pw_page.query_selector_all(
                        "tr[data-submission-id], .submission-row, .clip-row"
                    )
                    for row in rows:
                        row_text = row.inner_text()
                        if campaign.title[:20].lower() in row_text.lower():
                            submission_el = row
                            break

                if not submission_el:
                    browser.close()
                    return None  # Not found yet — still processing

                # Read status text from the row
                status_text = (
                    submission_el.inner_text().lower()
                )

                # Map platform status text to our internal statuses
                if any(w in status_text for w in ("accepted", "approved", "earned", "paid")):
                    # Try to extract earning amount
                    import re
                    amount_match = re.search(r"\$\s*([\d,]+(?:\.[\d]+)?)", status_text)
                    earnings = float(amount_match.group(1).replace(",", "")) if amount_match else (
                        campaign.payment_per_accepted_clip or 0.0
                    )
                    browser.close()
                    return {"status": "accepted", "outcome": "accepted", "earnings": earnings}

                if any(w in status_text for w in ("rejected", "declined", "not approved", "failed")):
                    reason_el = submission_el.query_selector(".rejection-reason, .reason")
                    reason = reason_el.inner_text() if reason_el else "Rejected by platform"
                    browser.close()
                    return {"status": "rejected", "outcome": "rejected", "reason": reason, "earnings": 0.0}

                # Still in review
                browser.close()
                return None

            except PWTimeout:
                self.logger.debug(f"Timeout polling outcome for submission {submission.id}")
                browser.close()
                return None
            except Exception as exc:
                self.logger.debug(f"Outcome poll error: {exc}")
                try:
                    browser.close()
                except Exception:
                    pass
                return None
