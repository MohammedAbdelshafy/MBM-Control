"""
GTM GMAIL EMAIL DISPATCH ADAPTER
=============================================================================
Production email dispatch via Gmail SMTP pool with Production Gate enforcement.

Features:
  - Round-robin across 5 Gmail accounts (SMTP_SENDER_POOL)
  - Production Gate check before every send (HUMAN_APPROVED required)
  - Anti-flagging delays (2-5 second random jitter between sends)
  - Per-account hourly rate limiting (default 20/hr per Gmail)
  - Append-only audit log to logs/gtm_email_dispatch.json
  - Event bus integration (EMAIL_SENT / EMAIL_FAILED)

Safety:
  Default mode is DRY-RUN.  Pass --live or set GTM_EMAIL_LIVE=true for real sends.
=============================================================================
"""

import json
import os
import re
import smtplib
import sys
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = ROOT_DIR / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DISPATCH_LOG = LOGS_DIR / "gtm_email_dispatch.json"

# Load environment
try:
    from dotenv import load_dotenv
    for env_file in [ROOT_DIR / ".env.local", ROOT_DIR / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
except Exception:
    pass

# Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
FROM_NAME = os.getenv("SMTP_FROM_NAME", "Mohammed Abdelshafy")
MAX_PER_ACCOUNT_HOUR = int(os.getenv("GTM_EMAIL_MAX_PER_HOUR", "20"))
MAX_DAILY_TOTAL = int(os.getenv("GTM_EMAIL_MAX_DAILY", "100"))
ANTI_FLAG_MIN_DELAY = float(os.getenv("GTM_EMAIL_DELAY_MIN", "2.0"))
ANTI_FLAG_MAX_DELAY = float(os.getenv("GTM_EMAIL_DELAY_MAX", "5.0"))

IS_LIVE = (
    os.getenv("GTM_EMAIL_LIVE", "").lower() in ("true", "1", "yes")
    or "--live" in sys.argv
)

# Event bus import (optional — works standalone too)
try:
    from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
    _HAS_EVENT_BUS = True
except Exception:
    _HAS_EVENT_BUS = False

# Production gate import (optional — works standalone with default-deny)
try:
    from MBM.LeadEngine.gtm.production_gate import ProductionGate, ApprovalStatus
    _HAS_GATE = True
except Exception:
    _HAS_GATE = False


def _parse_sender_pool() -> List[Dict[str, str]]:
    """Parse SMTP_SENDER_POOL env into list of {email, password} dicts."""
    pool_raw = os.getenv("SMTP_SENDER_POOL", "")
    accounts = []

    if ":" in pool_raw:
        entries = re.split(r"[,;]", pool_raw)
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            email = parts[0].strip()
            password = ":".join(parts[1:]).replace(" ", "")
            # Skip placeholder passwords
            if "REPLACE" in password.upper() or not password:
                continue
            accounts.append({"email": email, "password": password})
    else:
        # Single-account fallback
        user = os.getenv("MASTER_GMAIL", os.getenv("SMTP_USER", ""))
        pwd = os.getenv("GMAIL_APP_PASSWORD", os.getenv("SMTP_PASS", "")).replace(" ", "")
        if user and pwd and "REPLACE" not in pwd.upper():
            accounts.append({"email": user, "password": pwd})

    return accounts


class _SendCounter:
    """In-memory rate limiter tracking sends per account per hour and total daily."""

    def __init__(self):
        self._hourly: Dict[str, List[datetime]] = {}
        self._daily: List[datetime] = []

    def can_send(self, email: str) -> bool:
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)

        # Prune stale entries
        self._hourly.setdefault(email, [])
        self._hourly[email] = [t for t in self._hourly[email] if t > hour_ago]
        self._daily = [t for t in self._daily if t > day_ago]

        if len(self._hourly[email]) >= MAX_PER_ACCOUNT_HOUR:
            return False
        if len(self._daily) >= MAX_DAILY_TOTAL:
            return False
        return True

    def record(self, email: str) -> None:
        now = datetime.now(timezone.utc)
        self._hourly.setdefault(email, []).append(now)
        self._daily.append(now)


class GmailDispatchAdapter:
    """
    Production Gmail email dispatch adapter for the GTM pipeline.

    Default: DRY-RUN (logs intent but does not actually send).
    Pass --live or set GTM_EMAIL_LIVE=true to enable real SMTP sends.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self.accounts = _parse_sender_pool()
        self._counter = _SendCounter()
        self._pool_index = 0
        self._event_bus = event_bus
        self._gate = ProductionGate() if _HAS_GATE else None
        self._verified: Dict[str, bool] = {}

    # -- Pool management -------------------------------------------------

    def _next_account(self) -> Optional[Dict[str, str]]:
        """Round-robin through verified, rate-limited accounts."""
        if not self.accounts:
            return None
        for _ in range(len(self.accounts)):
            acct = self.accounts[self._pool_index % len(self.accounts)]
            self._pool_index += 1
            if self._counter.can_send(acct["email"]):
                return acct
        return None  # All accounts exhausted

    def verify_account(self, acct: Dict[str, str]) -> bool:
        """Verify SMTP credentials for a single account."""
        email = acct["email"]
        if email in self._verified:
            return self._verified[email]
        try:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.ehlo()
            server.starttls()
            server.login(email, acct["password"])
            server.quit()
            self._verified[email] = True
            return True
        except Exception as e:
            self._verified[email] = False
            self._log_event("VERIFY_FAILED", email, "", str(e))
            return False

    def get_pool_status(self) -> List[Dict[str, Any]]:
        """Return health status of all accounts in the sender pool."""
        statuses = []
        for acct in self.accounts:
            verified = self.verify_account(acct)
            can_send = self._counter.can_send(acct["email"])
            statuses.append({
                "email": acct["email"],
                "verified": verified,
                "rate_limited": not can_send,
                "password_present": bool(acct["password"]),
            })
        return statuses

    # -- Gate check ------------------------------------------------------

    def _check_gate(self, entity_id: str, opportunity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check Production Gate. Returns gate result dict."""
        if not self._gate:
            # No gate available — default deny in live mode, allow in dry-run
            return {
                "can_execute": not IS_LIVE,
                "human_approved": not IS_LIVE,
                "gate_available": False,
            }

        opp = opportunity or {}
        opp.setdefault("id", entity_id)
        opp.setdefault("recommended_channel", "EMAIL")
        return self._gate.evaluate_gate(opp)

    # -- Core send -------------------------------------------------------

    def _build_message(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart()
        msg["From"] = f'"{FROM_NAME}" <{from_email}>'
        msg["To"] = to_email
        msg["Subject"] = subject

        # Detect HTML vs plain text
        if "<" in body and ">" in body:
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and Path(attachment_path).exists():
            part = MIMEBase("application", "octet-stream")
            with open(attachment_path, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={Path(attachment_path).name}",
            )
            msg.attach(part)

        return msg

    def _dispatch(
        self,
        entity_id: str,
        to_email: str,
        subject: str,
        body: str,
        email_type: str = "COLD_EMAIL",
        attachment_path: Optional[str] = None,
        opportunity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Core dispatch method used by all public send methods."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Validate recipient
        if not to_email or "@" not in to_email or "." not in to_email:
            result = {
                "status": "REJECTED",
                "reason": "Invalid recipient email",
                "entity_id": entity_id,
                "to": to_email,
                "timestamp": timestamp,
            }
            self._log_event("REJECTED", "", to_email, "Invalid email", entity_id=entity_id)
            return result

        # Check Production Gate
        gate = self._check_gate(entity_id, opportunity)
        if IS_LIVE and not gate.get("can_execute"):
            result = {
                "status": "GATE_BLOCKED",
                "reason": "Production Gate denied",
                "gate_result": gate,
                "entity_id": entity_id,
                "to": to_email,
                "timestamp": timestamp,
            }
            self._log_event("GATE_BLOCKED", "", to_email, json.dumps(gate), entity_id=entity_id)
            self._emit_event("EMAIL_FAILED", entity_id, {"reason": "GATE_BLOCKED", "to": to_email})
            return result

        # Get next available account
        acct = self._next_account()
        if not acct:
            result = {
                "status": "POOL_EXHAUSTED",
                "reason": "All Gmail accounts rate-limited or unavailable",
                "entity_id": entity_id,
                "to": to_email,
                "timestamp": timestamp,
            }
            self._log_event("POOL_EXHAUSTED", "", to_email, "No accounts available", entity_id=entity_id)
            self._emit_event("EMAIL_FAILED", entity_id, {"reason": "POOL_EXHAUSTED"})
            return result

        from_email = acct["email"]

        # DRY-RUN mode
        if not IS_LIVE:
            result = {
                "status": "DRY_RUN",
                "would_send_from": from_email,
                "to": to_email,
                "subject": subject,
                "body_preview": body[:200],
                "email_type": email_type,
                "entity_id": entity_id,
                "gate_result": gate,
                "timestamp": timestamp,
            }
            self._log_event("DRY_RUN", from_email, to_email, subject, entity_id=entity_id, email_type=email_type)
            print(f"[GTM EMAIL DRY-RUN] {from_email} -> {to_email} | {subject}")
            return result

        # Verify account (cached)
        if not self.verify_account(acct):
            result = {
                "status": "SMTP_VERIFY_FAILED",
                "reason": f"SMTP login failed for {from_email}",
                "entity_id": entity_id,
                "to": to_email,
                "timestamp": timestamp,
            }
            self._emit_event("EMAIL_FAILED", entity_id, {"reason": "SMTP_VERIFY_FAILED", "from": from_email})
            return result

        # LIVE SEND
        try:
            msg = self._build_message(from_email, to_email, subject, body, attachment_path)
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.login(from_email, acct["password"])
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()

            self._counter.record(from_email)

            result = {
                "status": "SENT",
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "email_type": email_type,
                "entity_id": entity_id,
                "timestamp": timestamp,
            }
            self._log_event("SENT", from_email, to_email, subject, entity_id=entity_id, email_type=email_type)
            self._emit_event("EMAIL_SENT", entity_id, {"from": from_email, "to": to_email, "type": email_type})
            print(f"[GTM EMAIL SENT] {from_email} -> {to_email} | {subject}")

            # Anti-flagging delay
            delay = random.uniform(ANTI_FLAG_MIN_DELAY, ANTI_FLAG_MAX_DELAY)
            time.sleep(delay)

            return result

        except Exception as e:
            result = {
                "status": "SEND_FAILED",
                "reason": str(e),
                "from": from_email,
                "to": to_email,
                "entity_id": entity_id,
                "timestamp": timestamp,
            }
            self._log_event("SEND_FAILED", from_email, to_email, str(e), entity_id=entity_id)
            self._emit_event("EMAIL_FAILED", entity_id, {"reason": str(e), "from": from_email, "to": to_email})
            return result

    # -- Public API ------------------------------------------------------

    def send_cold_email(
        self,
        entity_id: str,
        to_email: str,
        subject: str,
        body: str,
        opportunity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a cold email via the Gmail pool with gate enforcement."""
        return self._dispatch(entity_id, to_email, subject, body, "COLD_EMAIL", opportunity=opportunity)

    def send_followup(
        self,
        entity_id: str,
        to_email: str,
        subject: str,
        body: str,
        opportunity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a follow-up email via the Gmail pool."""
        return self._dispatch(entity_id, to_email, subject, body, "FOLLOWUP", opportunity=opportunity)

    def send_proposal(
        self,
        entity_id: str,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None,
        opportunity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a proposal email with optional attachment."""
        return self._dispatch(entity_id, to_email, subject, body, "PROPOSAL", attachment_path, opportunity=opportunity)

    def get_send_history(self, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read the append-only dispatch log, optionally filtered by entity_id."""
        if not DISPATCH_LOG.exists():
            return []
        try:
            records = json.loads(DISPATCH_LOG.read_text(encoding="utf-8"))
            if entity_id:
                return [r for r in records if r.get("entity_id") == entity_id]
            return records
        except Exception:
            return []

    # -- Logging & Events ------------------------------------------------

    def _log_event(
        self,
        status: str,
        from_email: str,
        to_email: str,
        detail: str,
        entity_id: str = "",
        email_type: str = "",
    ) -> None:
        """Append to the audit log file."""
        record = {
            "status": status,
            "from": from_email,
            "to": to_email,
            "detail": detail[:500],
            "entity_id": entity_id,
            "email_type": email_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        existing = []
        if DISPATCH_LOG.exists():
            try:
                existing = json.loads(DISPATCH_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.append(record)
        DISPATCH_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def build_seller_email_queue(self, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Reads canonical dialer database, extracts verified real estate sellers with verified email,
        preserving queue_rank priority order. Sellers without email are kept out (zero fabrication).
        """
        from MBM.GLM.single_writer_lock import DialerSingleWriter
        from MBM.LeadEngine.dialer_priority_engine import is_lead_suppressed, is_real_estate_seller

        target_path = db_path or (ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json")
        writer = DialerSingleWriter(db_path=target_path)
        leads = writer.read_leads()

        email_queue = []
        for lead in leads:
            if is_lead_suppressed(lead):
                continue
            if not is_real_estate_seller(lead):
                continue
            if lead.get("callable") is False or lead.get("is_callable") is False:
                continue

            raw_email = str(lead.get("email") or (lead.get("details") or {}).get("email") or "").strip()
            if raw_email and "@" in raw_email and "." in raw_email:
                owner = lead.get("contact") or lead.get("owner_name") or "Property Owner"
                first_name = owner.split()[0] if owner else "there"
                prop = lead.get("address") or lead.get("property_address") or lead.get("company") or "the property"

                subject = f"Question regarding {prop}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"I'm reaching out regarding {prop} in Texas. Are you still the owner of this property?\n\n"
                    f"We are actively acquiring residential and commercial properties in your area for direct portfolio investment. "
                    f"If you would be open to a fair, all-cash, as-is offer with zero closing costs and flexible timeline, please let me know.\n\n"
                    f"Best regards,\n"
                    f"Mohammed Abdelshafy\n"
                    f"MBM Real Estate Acquisitions"
                )
                email_queue.append({
                    "lead_id": lead.get("id"),
                    "owner": owner,
                    "to_email": raw_email,
                    "phone": lead.get("phone"),
                    "property": prop,
                    "subject": subject,
                    "body": body,
                    "queue_rank": lead.get("queue_rank"),
                    "priority_score": lead.get("priority_score"),
                })

        email_queue.sort(key=lambda x: (x.get("queue_rank") if isinstance(x.get("queue_rank"), int) else 999999))
        return email_queue

    def dispatch_seller_email_queue(self, limit: int = 10, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Dispatches outbound property inquiry emails to verified-email sellers in priority order."""
        queue = self.build_seller_email_queue(db_path=db_path)[:limit]
        results = []
        for item in queue:
            res = self.send_cold_email(
                entity_id=item["lead_id"],
                to_email=item["to_email"],
                subject=item["subject"],
                body=item["body"],
                opportunity={"property": item["property"], "lane": "REAL_ESTATE_WHOLESALE"},
            )
            results.append(res)
        return results

    def _emit_event(self, event_type_name: str, entity_id: str, payload: Dict[str, Any]) -> None:
        """Emit an event on the GTM event bus if available."""
        if not _HAS_EVENT_BUS or not self._event_bus:
            return
        try:
            etype = GtmEventType(event_type_name)
            event = GtmEvent(
                event_type=etype,
                entity_id=entity_id,
                producer="GmailDispatchAdapter",
                payload=payload,
            )
            self._event_bus.publish(event)
        except (ValueError, Exception):
            pass



# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("GTM GMAIL DISPATCH ADAPTER - POOL STATUS CHECK")
    print(f"Mode: {'LIVE' if IS_LIVE else 'DRY-RUN (pass --live for real sends)'}")
    print("=" * 70)

    adapter = GmailDispatchAdapter()
    pool = adapter.get_pool_status()

    if not pool:
        print("\n[!] No Gmail accounts found in SMTP_SENDER_POOL / MASTER_GMAIL.")
        print("    Set SMTP_SENDER_POOL=email:apppassword in .env or .env.local")
    else:
        for acct in pool:
            icon = "[OK]" if acct["verified"] else "[FAIL]"
            rate = "[RATE-LIMITED]" if acct["rate_limited"] else "[AVAILABLE]"
            print(f"  {icon} {acct['email']} - {rate}")

    print(f"\nDispatch log: {DISPATCH_LOG}")
    history = adapter.get_send_history()
    print(f"Total logged dispatches: {len(history)}")
