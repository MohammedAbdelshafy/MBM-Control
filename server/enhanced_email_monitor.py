#!/usr/bin/env python3
"""
Enhanced Email Queue Monitor with real-time status tracking
"""
import json
import os
import asyncio
import httpx
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("EnhancedEmailMonitor")

class EnhancedEmailQueueMonitor:
    def __init__(self, supabase_url: str, service_role_key: str):
        self.supabase_url = supabase_url
        self.service_role_key = service_role_key
        self.logger = logging.getLogger("EnhancedEmailQueueMonitor")

    async def check_queue_status(self):
        """Check email queue status and send alerts if needed"""
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json"
        }

        # Get queue statistics
        async with httpx.AsyncClient() as client:
            # Check queued emails
            queued_response = await client.get(
                f"{self.supabase_url}/rest/v1/email_queue",
                headers={
                    **headers,
                    "Prefer": "count=exact"
                },
                params={
                    "status": "eq.qued",
                    "select": "id,recipient_email,subject,created_at",
                    "limit": 100
                }
            )

            # Get failed emails (last hour)
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            failed_response = await client.get(
                f"{self.supabase_url}/rest/v1/email_queue",
                headers=headers,
                params={
                    "status": "neq.sent",
                    "updated_at": f"gte.{one_hour_ago}",
                    "select": "id,recipient_email,subject,error,updated_at"
                }
            )

        queued_count = int(queued_response.headers.get('count', '0'))
        failed_count = len(failed_response.json()) if failed_response.status_code == 200 else 0

        logger.info(f"📮 Queue Status: {queued_count} pending, {failed_count} failed (last hour)")

        # Send alert if queue is growing
        if queued_count > 50 or failed_count > 5:
            await self.send_queue_alert(queued_count, failed_count)

    async def send_queue_alert(self, queued_count: int, failed_count: int):
        """Send Telegram alert for queue issues"""
        try:
            message = f"""📬 EMAIL QUEUE ALERT ⚠️

📊 Queue Status:
• Pending: {queued_count}
• Failed (last hour): {failed_count}
• Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

🔍 Health Check:
• {'⚠️ HIGH' if queued_count + failed_count > 100 else '🟡 MEDIUM' if queued_count + failed_count > 50 else '✅ OK'}

This is an automated alert from the Email Queue Monitoring System."""

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://api.telegram.org/botTELEGRAM_BOT_TOKEN_REDACTED/sendMessage",
                    json={
                        "chat_id": "6617518949",
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )

                if response.status_code == 200:
                    logger.info("📤 Queue alert sent successfully")
                else:
                    logger.error(f"❌ Failed to send queue alert: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Failed to send queue alert: {e}")

    async def run_continuous_monitor(self, interval_minutes: int = 30):
        """Run continuous monitoring with specified interval"""
        logger.info(f"🔄 Starting continuous email queue monitoring (every {interval_minutes} minutes)")

        while True:
            try:
                await self.check_queue_status()
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")

            await asyncio.sleep(interval_minutes * 60)

    async def trigger_retry_if_needed(self):
        """Check if emails need retrying based on failure thresholds"""
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json"
        }

        # Get emails that have failed 3+ times
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.supabase_url}/rest/v1/email_queue",
                headers=headers,
                params={
                    "status": "neq.sent",
                    "retry_count": "gte.2",
                    "select": "id,recipient_email,subject,retry_count,error,updated_at",
                    "limit": 50
                }
            )

        emails = response.json() if response.status_code == 200 else []
        if emails:
            logger.info(f"🔄 Found {len(emails)} emails that may need retry")
            await self.send_retry_alert(emails)

    async def send_retry_alert(self, emails: list):
        """Send alert about emails needing retry"""
        try:
            message = f"""🔄 EMAIL RETRY NEEDED ⚠️

📧 {len(emails)} emails failed multiple times and may need retry:

{''.join(f"• {email['recipient_email']} (retry: {email['retry_count'] or 0}) - {email.get('error', 'Unknown error')}\n" for email in emails[:5])}

🔧 Please check the retry mechanism and consider retrying these emails.
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} """

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://api.telegram.org/botTELEGRAM_BOT_TOKEN_REDACTED/sendMessage",
                    json={
                        "chat_id": "6617518949",
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )

                if response.status_code == 200:
                    logger.info("📤 Retry alert sent successfully")
                else:
                    logger.error(f"❌ Failed to send retry alert: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Failed to send retry alert: {e}")


if __name__ == "__main__":
    # Configuration
    SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "https://prgmwljhbjtcjmwnjaao.supabase.co")
    SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not SERVICE_ROLE_KEY:
        logger.error("❌ SUPABASE_SERVICE_ROLE_KEY environment variable is required")
        exit(1)

    async def main():
        monitor = EnhancedEmailQueueMonitor(SUPABASE_URL, SERVICE_ROLE_KEY)

        # Check queue status once
        await monitor.check_queue_status()

        # Check for retries
        await monitor.trigger_retry_if_needed()

        # Start continuous monitoring if running as a daemon
        if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            await monitor.run_continuous_monitor(interval)

    import sys
    asyncio.run(main())
