"""
MonetizationAgent — 24/7 monitoring & automated recovery.

Responsibilities:
- Detects stalled/failed pipeline stages and re-triggers recovery (silently)
- Reboots failed campaigns and stuck tasks automatically
- Tracks earnings/revenue against min viable thresholds
- GOOD-NEWS-ONLY alerts: sends ONLY positive events to Telegram/webhook
  (winnings, new accepted clips, completed campaigns, recovered earnings).
  Security / storage / pipeline-health / low-revenue ("no money") issues are
  auto-recovered and logged locally but NEVER sent to the user.
- Ensures auto_submit / auto_publish remain active
"""
import time
from datetime import datetime, timedelta, timezone

from app.agents.base_agent import AgentResult, BaseAgent
from app.core.logging_config import get_logger

logger = get_logger("agent.monetization")


class MonetizationAgent(BaseAgent):
    name = "monetization_agent"

    ACTIONS = {
        "retry_failed_campaigns": "Re-queue failed campaigns for re-acquisition",
        "restart_stalled_tasks": "Restart campaigns stuck in DISCOVERED",
        "clear_backed_up_queues": "Re-trigger stuck pending tasks",
        "report_earnings": "Send earnings summary to Telegram",
    }

    def run(self) -> AgentResult:
        if not self.settings.monetization_enabled:
            return AgentResult.ok({"status": "disabled"})

        actions_taken = []
        report = {"timestamp": datetime.now(timezone.utc).isoformat()}

        # 1. Check pipeline health → auto-reboot if unhealthy
        health = self._check_pipeline_health()
        report["pipeline_health"] = health
        if not health.get("healthy", True):
            reboot = self._reboot_pipeline(health.get("issues", []))
            actions_taken.extend(reboot)

        # 2. Check earnings / revenue → GOOD-NEWS-ONLY notifications.
        #    Negative cases (below_threshold / no money) are intentionally
        #    never reported; they are only used internally for auto-recovery.
        earnings = self._check_earnings()
        report["earnings"] = earnings
        if earnings.get("total_earnings", 0) > 0:
            self._send_earnings_report(earnings)
            actions_taken.append("report_earnings")
        recent = earnings.get("recent_clips_24h", 0) or 0
        if recent > 0:
            self._notify(
                "accepted_clips",
                "\U0001f389 New Clips Accepted",
                f"{recent} clip(s) accepted in the last 24h. Keep them coming! \U0001f525",
            )
            actions_taken.append("notified_accepted_clips")

        # 3. Re-trigger failed campaigns
        retried = self._retry_failed_campaigns()
        if retried:
            actions_taken.append(f"retried_{retried}_campaigns")

        # 4. Process stalled campaigns (DISCOVERED but not picked up)
        unstalled = self._process_stalled_campaigns()
        if unstalled:
            actions_taken.append(f"unstalled_{unstalled}_campaigns")

        # 5. Check queue depths → auto-recover backed-up queues
        queues = self._check_queues()
        report["queues"] = queues
        if queues.get("backed_up", False):
            cleared = self._clear_queue_backup(queues)
            actions_taken.extend(cleared)

        # 6. Verify auto-submit/auto-publish are active
        pipeline_config = self._check_pipeline_config()
        report["pipeline_config"] = pipeline_config
        if not pipeline_config.get("auto_submit", False):
            actions_taken.append("auto_submit_disabled")
        if not pipeline_config.get("auto_publish", False):
            actions_taken.append("auto_publish_disabled")

        report["actions_taken"] = actions_taken
        self._audit("system", "monetization", "check", metadata={"actions": actions_taken})
        return AgentResult.ok(report)

    def _check_pipeline_health(self) -> dict:
        issues = []
        healthy = True
        worker_count = 0

        try:
            from app.core.celery_app import celery_app
            ping = celery_app.control.ping(timeout=5)
            if not ping:
                issues.append("No Celery workers responded to ping")
                healthy = False
            else:
                worker_count = len(ping)
        except Exception as exc:
            issues.append(f"Celery ping failed: {exc}")
            healthy = False

        try:
            from sqlalchemy import text
            self.db.execute(text("SELECT 1"))
            self.db.commit()
        except Exception as exc:
            issues.append(f"Database unreachable: {exc}")
            healthy = False

        return {"healthy": healthy, "issues": issues, "worker_count": worker_count}

    def _check_earnings(self) -> dict:
        from app.models.campaign import Campaign, CampaignStatus
        from sqlalchemy import text as _sql

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            recent_clips = self.db.execute(
                _sql("SELECT COUNT(*) FROM clips WHERE status = 'accepted' AND updated_at >= :cutoff"),
                {"cutoff": cutoff},
            ).scalar() or 0

            total_accepted = self.db.execute(
                _sql("SELECT COUNT(*) FROM clips WHERE status = 'accepted'")
            ).scalar() or 0

            completed_campaigns = self.db.query(Campaign).filter(
                Campaign.status == CampaignStatus.COMPLETED
            ).count()

            failed_24h = self.db.execute(
                _sql("SELECT COUNT(*) FROM clips WHERE status IN ('qc_fail', 'rejected_platform') AND updated_at >= :cutoff"),
                {"cutoff": cutoff},
            ).scalar() or 0

            total_earnings_float = 0.0
            try:
                total = (
                    self.db.query(Campaign.actual_earnings)
                    .filter(Campaign.actual_earnings > 0)
                    .all()
                )
                total_earnings_float = sum(e[0] for e in total) if total else 0.0
            except Exception:
                pass

            return {
                "recent_clips_24h": recent_clips,
                "total_accepted": total_accepted,
                "completed_campaigns": completed_campaigns,
                "failed_24h": failed_24h,
                "total_earnings": total_earnings_float,
                "below_threshold": total_earnings_float < self.settings.monetization_min_viable_revenue,
            }
        except Exception as exc:
            logger.error(f"Earnings check failed: {exc}")
            return {"error": str(exc), "below_threshold": False}

    # Categories that are NEVER delivered to the user while good-news-only is on.
    # These are still auto-recovered and logged locally — they just stay silent.
    _SUPPRESSED_CATEGORIES = {
        "security",        # Celery/worker failures
        "storage",         # DB unreachable / storage problems
        "pipeline_health", # general health issues
        "money_low",       # below min viable revenue / "no money" issues
        "error",           # generic errors
    }

    def _notify(self, category: str, title: str, body: str) -> None:
        """Send a notification. Negative categories are suppressed under good-news-only.

        Positive categories (e.g. "winnings", "accepted_clips", "campaign_done",
        "recovered") always go through.
        """
        if self.settings.monetization_good_news_only and category in self._SUPPRESSED_CATEGORIES:
            logger.info(f"Suppressed [{category}] alert (good-news-only): {title}")
            return
        self._dispatch_telegram(title, body)
        self._dispatch_webhook(category, title, body)

    def _dispatch_telegram(self, title: str, body: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        try:
            import httpx
            text = f"*{title}*\n{body}"
            url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            with httpx.Client(timeout=10) as client:
                client.post(url, json={
                    "chat_id": self.settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
        except Exception:
            pass

    def _dispatch_webhook(self, category: str, title: str, body: str) -> None:
        if not self.settings.monetization_webhook_url:
            return
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                client.post(self.settings.monetization_webhook_url, json={
                    "category": category,
                    "title": title,
                    "body": body,
                })
        except Exception:
            pass

    def _send_earnings_report(self, earnings: dict) -> None:
        """GOOD NEWS ONLY — send winnings/earnings, never problems."""
        text = (
            f"\U0001f4b0 *Winnings Report*\n"
            f"Total earnings: *${earnings.get('total_earnings', 0):.2f}*\n"
            f"Accepted clips: {earnings.get('total_accepted', 0)}\n"
            f"Recent (24h): {earnings.get('recent_clips_24h', 0)} clips accepted, "
            f"{earnings.get('failed_24h', 0)} failed\n"
            f"Completed campaigns: {earnings.get('completed_campaigns', 0)}"
        )
        self._notify("winnings", "Winnings Report", text)

    def _reboot_pipeline(self, issues: list[str]) -> list[str]:
        """Auto-recover from pipeline issues — this is the reboot mechanism."""
        actions = []
        for issue in issues:
            if "No Celery workers" in issue:
                self._restart_celery_workers()
                actions.append("restarted_celery_workers")
            elif "Database" in issue:
                logger.critical("Database unreachable — cannot auto-recover")
                actions.append("database_unreachable")
            else:
                logger.warning(f"Unknown pipeline issue: {issue}")
        return actions

    def _restart_celery_workers(self) -> None:
        """Re-trigger celery beat scheduling to re-spawn worker tasks."""
        try:
            from app.core.celery_app import celery_app
            celery_app.control.broadcast("shutdown", destination=None)
            time.sleep(2)
        except Exception:
            pass

    def _retry_failed_campaigns(self) -> int:
        from app.models.campaign import Campaign, CampaignStatus
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        failed = (
            self.db.query(Campaign)
            .filter(
                Campaign.status == CampaignStatus.FAILED,
                Campaign.updated_at >= cutoff,
            )
            .all()
        )
        count = 0
        for campaign in failed:
            try:
                campaign.status = CampaignStatus.READY
                campaign.retry_count = (campaign.retry_count or 0) + 1
                campaign.error_message = None
                self.db.flush()
                if campaign.source_url:
                    from app.workers.video_tasks import acquire_content
                    acquire_content.apply_async(args=[campaign.id], queue="acquisition")
                count += 1
            except Exception as exc:
                logger.error(f"Failed to retry campaign {campaign.id}: {exc}")
        if count:
            self.db.flush()
            logger.info(f"Re-triggered {count} failed campaigns")
        return count

    def _process_stalled_campaigns(self) -> int:
        from app.models.campaign import Campaign, CampaignStatus
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        stalled = (
            self.db.query(Campaign)
            .filter(
                Campaign.status == CampaignStatus.DISCOVERED,
                Campaign.created_at < cutoff,
                Campaign.source_url.isnot(None),
            )
            .all()
        )
        count = 0
        for campaign in stalled:
            try:
                campaign.status = CampaignStatus.READY
                self.db.flush()
                from app.workers.video_tasks import acquire_content
                acquire_content.apply_async(args=[campaign.id], queue="acquisition")
                count += 1
            except Exception as exc:
                logger.error(f"Failed to restart stalled campaign {campaign.id}: {exc}")
        if count:
            self.db.flush()
            logger.info(f"Restarted {count} stalled campaigns")
        return count

    def _check_queues(self) -> dict:
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            queues = ["default", "campaigns", "acquisition", "analysis", "video", "delivery", "publish", "health"]
            queue_info = {}
            total = 0
            for q in queues:
                key = f"celery@clipping_factory/{q}"
                try:
                    length = r.llen(key) if r.exists(key) else 0
                    queue_info[q] = length
                    total += length
                except Exception:
                    queue_info[q] = -1
            r.close()
            return {
                "queues": queue_info,
                "total_pending": total,
                "backed_up": total > 50,
                "details": f"{total} pending tasks across {len(queues)} queues" if total > 50 else "",
            }
        except Exception as exc:
            return {"queues": {}, "total_pending": 0, "backed_up": False, "details": str(exc)}

    def _clear_queue_backup(self, queues: dict) -> list[str]:
        actions = []
        backed_up = [q for q, v in queues.get("queues", {}).items() if isinstance(v, int) and v > 20]
        if "acquisition" in backed_up:
            self._retry_failed_campaigns()
            actions.append("acquisition_retry")
        if "delivery" in backed_up:
            self._retry_pending_deliveries()
            actions.append("delivery_retry")
        return actions

    def _retry_pending_deliveries(self) -> None:
        from sqlalchemy import text as _sql
        try:
            pending = self.db.execute(
                _sql("SELECT id FROM submissions WHERE status = 'pending' AND updated_at < now() - interval '1 hour'")
            ).fetchall()
            for (sid,) in pending:
                from app.workers.video_tasks import deliver_clip
                deliver_clip.apply_async(args=[sid], queue="delivery")
            if pending:
                logger.info(f"Re-triggered {len(pending)} pending deliveries")
        except Exception as exc:
            logger.error(f"Failed to retry pending deliveries: {exc}")

    def _check_pipeline_config(self) -> dict:
        return {
            "auto_submit": self.settings.auto_submit,
            "auto_publish": self.settings.auto_publish,
            "publish_platforms": self.settings.publish_platforms,
            "clip_score_threshold": self.settings.clip_score_threshold,
        }
