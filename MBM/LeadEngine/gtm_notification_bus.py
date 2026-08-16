"""
GTM NOTIFICATION BUS
=================================================================================================================
First-class delivery center for GTM notifications.

  NotificationBus
      ↓
  PriorityRouter
      ↓
  DeliveryAdapter  →  in_app | email | telegram | webhook

Design invariants:
  * Idempotency: delivery keys (daily_brief_YYYY-MM-DD, meeting_booked_<id>,
    positive_reply_<message_id>, hot_buyer_<opportunity_id>, deal_won_<deal_id>,
    failure_<event_id>) make duplicate notifications impossible under repeated runs.
  * Failure isolation: a Telegram/webhook failure NEVER breaks GTM. The bus catches
    every adapter error and keeps the pipeline (dialer, lead gen, CRM, email, in-app)
    running independently.
  * Honest delivery state: GENERATED -> QUEUED -> SENT -> DELIVERED / FAILED.
    Telegram is only marked DELIVERED when the Bot API responds with a message_id;
    a rejected message is FAILED, never DELIVERED.

CLI:
  python MBM/LeadEngine/gtm_notification_bus.py --test-telegram   # connectivity test (never a sales message)
  python MBM/LeadEngine/gtm_notification_bus.py --preview <kind>  # render a message preview without sending
=================================================================================================================
"""

import os
import sys
import json
import uuid
import re
import argparse
import smtplib
import imaplib
import email
import email.mime.text
import email.mime.multipart
import email.utils
import urllib.parse
import urllib.request
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import dotenv
    dotenv.load_dotenv(ROOT_DIR / ".env")
except Exception:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GTM_ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts" / "GTM"
GTM_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STATE_PATH = GTM_ARTIFACTS_DIR / "delivery_state.json"


# ---------------------------------------------------------------------------
# 1. Notification kinds & priorities
# ---------------------------------------------------------------------------

class NotificationKind(str, Enum):
    DAILY_BRIEF = "DAILY_BRIEF"
    HOT_BUYER = "HOT_BUYER"
    LEAD_WARMED = "LEAD_WARMED"
    POSITIVE_REPLY = "POSITIVE_REPLY"
    MEETING_BOOKED = "MEETING_BOOKED"
    MEETING_CONFIRMED = "MEETING_CONFIRMED"
    MEETING_WITHIN_1H = "MEETING_WITHIN_1H"
    MEETING_CANCELLED = "MEETING_CANCELLED"
    DEAL_WON = "DEAL_WON"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    REVENUE_RECEIVED = "REVENUE_RECEIVED"
    HIGH_VALUE_FOLLOWUP = "HIGH_VALUE_FOLLOWUP"
    CRITICAL_FAILURE = "CRITICAL_FAILURE"
    QUALIFIED_CONVERSATION = "QUALIFIED_CONVERSATION"
    NEW_LEADS = "NEW_LEADS"
    WARM_SIGNAL = "WARM_SIGNAL"
    ROUTINE_FOLLOWUP = "ROUTINE_FOLLOWUP"


class PriorityLevel(str, Enum):
    P0 = "P0"  # immediate — critical failure / deal won / revenue / meeting within 1h
    P1 = "P1"  # near-immediate — meeting booked / positive reply / HOT buyer / lead warmed / qualified conversation
    P2 = "P2"  # daily digest — daily brief / new leads / statistics


class DeliveryStatus(str, Enum):
    GENERATED = "GENERATED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"


# Telegram per-kind flags (env-gated, never spam every micro-event).
KIND_TELEGRAM_FLAG = {
    NotificationKind.DAILY_BRIEF: "GTM_TELEGRAM_DAILY_BRIEF",
    NotificationKind.HOT_BUYER: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.LEAD_WARMED: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.POSITIVE_REPLY: "GTM_TELEGRAM_POSITIVE_REPLIES",
    NotificationKind.MEETING_BOOKED: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.MEETING_CONFIRMED: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.MEETING_WITHIN_1H: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.MEETING_CANCELLED: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.DEAL_WON: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.PAYMENT_RECEIVED: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.PROPOSAL_SENT: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.REVENUE_RECEIVED: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.HIGH_VALUE_FOLLOWUP: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.CRITICAL_FAILURE: "GTM_TELEGRAM_FAILURES",
    NotificationKind.QUALIFIED_CONVERSATION: "GTM_TELEGRAM_POSITIVE_REPLIES",
    NotificationKind.NEW_LEADS: "GTM_TELEGRAM_DAILY_BRIEF",
    NotificationKind.WARM_SIGNAL: "GTM_TELEGRAM_DAILY_BRIEF",
    NotificationKind.ROUTINE_FOLLOWUP: "GTM_TELEGRAM_DAILY_BRIEF",
}


class PriorityRouter:
    """Routes notification kinds to priority levels and default channel sets."""

    DEFAULT_CHANNELS = {
        PriorityLevel.P0: ["telegram", "gmail", "email", "in_app", "webhook"],
        PriorityLevel.P1: ["telegram", "gmail", "in_app", "email"],
        PriorityLevel.P2: ["in_app", "email", "gmail", "telegram"],
    }

    KIND_PRIORITY = {
        NotificationKind.CRITICAL_FAILURE: PriorityLevel.P0,
        NotificationKind.DEAL_WON: PriorityLevel.P0,
        NotificationKind.PAYMENT_RECEIVED: PriorityLevel.P0,
        NotificationKind.REVENUE_RECEIVED: PriorityLevel.P0,
        NotificationKind.MEETING_WITHIN_1H: PriorityLevel.P0,
        NotificationKind.MEETING_BOOKED: PriorityLevel.P1,
        NotificationKind.MEETING_CONFIRMED: PriorityLevel.P1,
        NotificationKind.MEETING_CANCELLED: PriorityLevel.P1,
        NotificationKind.POSITIVE_REPLY: PriorityLevel.P1,
        NotificationKind.LEAD_WARMED: PriorityLevel.P1,
        NotificationKind.PROPOSAL_SENT: PriorityLevel.P1,
        NotificationKind.HOT_BUYER: PriorityLevel.P1,
        NotificationKind.HIGH_VALUE_FOLLOWUP: PriorityLevel.P1,
        NotificationKind.QUALIFIED_CONVERSATION: PriorityLevel.P1,
        NotificationKind.DAILY_BRIEF: PriorityLevel.P2,
        NotificationKind.NEW_LEADS: PriorityLevel.P2,
        NotificationKind.WARM_SIGNAL: PriorityLevel.P2,
        NotificationKind.ROUTINE_FOLLOWUP: PriorityLevel.P2,
    }

    @classmethod
    def route(cls, kind: NotificationKind) -> PriorityLevel:
        return cls.KIND_PRIORITY.get(kind, PriorityLevel.P2)

    @classmethod
    def default_channels(cls, kind: NotificationKind) -> List[str]:
        return list(cls.DEFAULT_CHANNELS.get(cls.route(kind), ["in_app"]))


# ---------------------------------------------------------------------------
# 2. Delivery state & idempotency store
# ---------------------------------------------------------------------------

@dataclass
class NotificationRecord:
    event_id: str
    delivery_key: str
    kind: str
    channel: str
    priority: str
    created_at: str
    status: str = DeliveryStatus.GENERATED.value
    attempts: int = 0
    last_error: str = ""
    last_attempt_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationRecord":
        return cls(**data)


class DeliveryStateStore:
    """Persistent per-channel delivery state keyed by `delivery_key|channel`."""

    def __init__(self, path: Path = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self._records: Dict[str, NotificationRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for key, rec in raw.items():
                self._records[key] = NotificationRecord.from_dict(rec)
        except Exception:
            self._records = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._records.items()}, indent=2),
            encoding="utf-8",
        )

    def channel_key(self, delivery_key: str, channel: str) -> str:
        return f"{delivery_key}|{channel}"

    def get(self, delivery_key: str, channel: str) -> Optional[NotificationRecord]:
        return self._records.get(self.channel_key(delivery_key, channel))

    def upsert(self, record: NotificationRecord) -> None:
        self._records[self.channel_key(record.delivery_key, record.channel)] = record
        self.save()

    def already_delivered(self, delivery_key: str, channel: str) -> bool:
        rec = self.get(delivery_key, channel)
        if not rec:
            return False
        return rec.status in {DeliveryStatus.SENT.value, DeliveryStatus.DELIVERED.value}

    def all_records(self) -> List[NotificationRecord]:
        return list(self._records.values())


# ---------------------------------------------------------------------------
# 3. Delivery adapters (in_app / email / telegram / webhook)
# ---------------------------------------------------------------------------

class DeliveryError(Exception):
    """Raised by an adapter when a channel rejects delivery."""


class DeliveryAdapter:
    channel = "base"

    def is_configured(self) -> bool:
        return True

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError


class InAppDeliveryAdapter(DeliveryAdapter):
    """Appends notifications to the in-app feed; confirms via local file write."""

    channel = "in_app"

    def __init__(self, feed_path: Optional[Path] = None):
        self.feed_path = Path(feed_path) if feed_path else GTM_ARTIFACTS_DIR / "in_app" / "notifications.jsonl"

    def is_configured(self) -> bool:
        return True

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "event_id": record.event_id,
            "delivery_key": record.delivery_key,
            "kind": record.kind,
            "priority": record.priority,
            "created_at": record.created_at,
            "summary": payload.get("summary", ""),
            "data": payload.get("data", {}),
        }
        with open(self.feed_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        record.status = DeliveryStatus.DELIVERED.value
        return True


class EmailDeliveryAdapter(DeliveryAdapter):
    """Hands notifications to the Email Center outbox (the SMTP rail delivers them).
    Does NOT re-implement SMTP — the existing email queue/sender owns delivery."""

    channel = "email"

    def __init__(self, outbox_dir: Optional[Path] = None):
        self.outbox_dir = Path(outbox_dir) if outbox_dir else GTM_ARTIFACTS_DIR / "email" / "outbox"

    def is_configured(self) -> bool:
        return True

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        body = payload.get("text", "")
        subject = payload.get("subject", f"[MBM GTM] {record.kind}")
        safe_key = "".join(c if c.isalnum() or c in "_-" else "_" for c in record.delivery_key)
        md = (
            f"# {subject}\n\n"
            f"**Delivery Key:** `{record.delivery_key}`  \n"
            f"**Event ID:** `{record.event_id}`  \n"
            f"**Priority:** `{record.priority}`  \n"
            f"**Generated:** {record.created_at}\n\n"
            "---\n\n"
            f"{body}\n"
        )
        (self.outbox_dir / f"{safe_key}.md").write_text(md, encoding="utf-8")
        record.status = DeliveryStatus.DELIVERED.value
        return True


class GmailDeliveryAdapter(DeliveryAdapter):
    """
    Real authenticated Gmail SMTP transport & IMAP inbound processor for GTM.
    - Outbound: Sends authenticated MIME email via smtp.gmail.com:587 (STARTTLS)
    - Inbound: Checks UNSEEN emails & prospect reply detection via imap.gmail.com:993
    - Isolation: Catches authentication/socket errors cleanly without disrupting GTM.
    """

    channel = "gmail"
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993

    def __init__(self, smtp_sender: Optional[Callable] = None, imap_client: Optional[Callable] = None):
        self._smtp_sender = smtp_sender
        self._imap_client = imap_client

    def is_enabled(self) -> bool:
        explicit = os.environ.get("GTM_GMAIL_ENABLED", "").strip().lower()
        if explicit in {"0", "false", "no", "off"}:
            return False
        if explicit in {"1", "true", "yes", "on"}:
            return True
        return bool(self.account_user() and self.account_password())

    def account_user(self) -> str:
        return (
            os.environ.get("GTM_GMAIL_USER", "").strip()
            or os.environ.get("MASTER_GMAIL", "").strip()
            or os.environ.get("SMTP_USER", "").strip()
            or "abdelshafyclapps@gmail.com"
        )

    def account_password(self) -> str:
        return (
            os.environ.get("GTM_GMAIL_APP_PASSWORD", "").strip()
            or os.environ.get("GMAIL_APP_PASSWORD", "").strip()
            or os.environ.get("SMTP_PASS", "").strip()
        ).replace(" ", "")

    def owner_email(self) -> str:
        return (
            os.environ.get("OWNER_EMAIL", "").strip()
            or os.environ.get("ALERT_EMAIL", "").strip()
            or self.account_user()
        )

    def is_configured(self) -> bool:
        if self._smtp_sender is not None:
            return True
        return self.is_enabled() and bool(self.account_user()) and bool(self.account_password())

    def validate(self) -> Dict[str, Any]:
        errors: List[str] = []
        hints: List[str] = []
        user = self.account_user()
        pwd = self.account_password()
        enabled = self.is_enabled()

        if not user:
            errors.append("Gmail account user is empty.")
        if not pwd:
            errors.append("Gmail App Password / SMTP_PASS is empty.")
            hints.append("Generate a 16-character Google App Password under Google Account -> Security -> 2-Step Verification -> App Passwords.")

        return {
            "ok": bool(user and pwd),
            "account": user,
            "has_password": bool(pwd),
            "enabled": enabled,
            "errors": errors,
            "hints": hints,
        }

    def send_email(self, to_addr: str, subject: str, body_text: str, html_body: Optional[str] = None) -> Dict[str, Any]:
        if self._smtp_sender:
            return self._smtp_sender(to_addr, subject, body_text)

        if not self.is_configured():
            raise DeliveryError("Gmail not configured (missing user or app password)")

        user = self.account_user()
        pwd = self.account_password()

        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["From"] = f"MBM GTM Delivery Center <{user}>"
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid(domain="mbm-gtm.local")

        msg.attach(email.mime.text.MIMEText(body_text, "plain", "utf-8"))
        if html_body:
            msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

        try:
            server = smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT, timeout=15)
            server.starttls()
            server.login(user, pwd)
            server.sendmail(user, [to_addr], msg.as_string())
            server.quit()
            return {"sent": True, "to": to_addr, "subject": subject, "message_id": msg["Message-ID"]}
        except Exception as e:
            raise DeliveryError(f"Gmail SMTP send failed: {e}")

    def check_inbound_replies(self, query: str = "UNSEEN") -> List[Dict[str, Any]]:
        """Check Gmail inbox via IMAP for positive prospect replies."""
        if self._imap_client:
            return self._imap_client(query)

        if not self.is_configured():
            return []

        user = self.account_user()
        pwd = self.account_password()

        replies = []
        try:
            mail = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT, timeout=15)
            mail.login(user, pwd)
            mail.select("INBOX", readonly=True)
            status, data = mail.search(None, query)
            if status == "OK" and data[0]:
                for num in data[0].split()[-10:]:
                    res, msg_data = mail.fetch(num, "(RFC822.HEADER)")
                    if res == "OK":
                        header_msg = email.message_from_bytes(msg_data[0][1])
                        replies.append({
                            "from": header_msg.get("From", ""),
                            "subject": header_msg.get("Subject", ""),
                            "date": header_msg.get("Date", ""),
                        })
            mail.logout()
        except Exception as e:
            pass
        return replies

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        subject = payload.get("email_subject") or payload.get("subject") or f"[MBM GTM] {record.kind}"
        body = payload.get("email_text") or payload.get("text", "")
        recipient = payload.get("recipient") or self.owner_email()

        res = self.send_email(recipient, subject, body)
        if res.get("sent"):
            record.status = DeliveryStatus.DELIVERED.value
            return True
        record.status = DeliveryStatus.FAILED.value
        return False


class WebhookDeliveryAdapter(DeliveryAdapter):
    """POSTs JSON to a configured webhook endpoint. Any 2xx response = delivered."""

    channel = "webhook"

    def __init__(self, url: Optional[str] = None, http_post: Optional[Callable] = None):
        self._explicit_url = (url or "").strip()
        self._http_post = http_post

    def _url(self) -> str:
        return self._explicit_url or os.environ.get("GTM_WEBHOOK_URL", "").strip()

    def is_configured(self) -> bool:
        return bool(self._url())

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        if not self.is_configured():
            raise DeliveryError("webhook not configured (GTM_WEBHOOK_URL empty)")
        body = json.dumps({
            "event_id": record.event_id,
            "delivery_key": record.delivery_key,
            "kind": record.kind,
            "priority": record.priority,
            "created_at": record.created_at,
            "text": payload.get("text", ""),
        }).encode("utf-8")
        if self._http_post:
            ok = bool(self._http_post(self._url(), body))
            if not ok:
                raise DeliveryError("webhook rejected delivery")
        else:
            req = urllib.request.Request(self._url(), data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if not (200 <= resp.status < 300):
                    raise DeliveryError(f"webhook returned HTTP {resp.status}")
        record.status = DeliveryStatus.DELIVERED.value
        return True


class TelegramDeliveryAdapter(DeliveryAdapter):
    """Env-only Telegram Bot API adapter. Never hardcoded into GTM agents — always
    reached through the NotificationBus. Failure here is fully isolated."""

    channel = "telegram"
    API_BASE = "https://api.telegram.org"

    def __init__(self, http_post: Optional[Callable] = None):
        self._http_post = http_post

    # -- configuration ------------------------------------------------------
    def is_enabled(self) -> bool:
        explicit = os.environ.get("GTM_TELEGRAM_ENABLED", "").strip().lower()
        if explicit in {"0", "false", "no", "off"}:
            return False
        if explicit in {"1", "true", "yes", "on"}:
            return True
        # No explicit switch: activate when credentials are present on either
        # the GTM rail or the legacy TELEGRAM_* rail already configured.
        return bool(self.bot_token() and self.chat_id())

    def bot_token(self) -> str:
        return (
            os.environ.get("GTM_TELEGRAM_BOT_TOKEN", "").strip()
            or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        )

    def chat_id(self) -> str:
        return (
            os.environ.get("GTM_TELEGRAM_CHAT_ID", "").strip()
            or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        )

    def is_configured(self) -> bool:
        return self.is_enabled() and bool(self.bot_token()) and bool(self.chat_id())

    def kind_enabled(self, kind: NotificationKind) -> bool:
        flag = KIND_TELEGRAM_FLAG.get(kind)
        if not flag:
            return True
        raw = os.environ.get(flag, "").strip().lower()
        if raw in {"0", "false", "no", "off"}:
            return False
        if raw in {"1", "true", "yes", "on"}:
            return True
        # Unset -> P0/P1 alerts deliver by default (never silence a critical);
        # P2 digest kinds are opt-in so we never spam Telegram micro-events.
        return PriorityRouter.route(kind) in {PriorityLevel.P0, PriorityLevel.P1}

    def validate(self) -> Dict[str, Any]:
        errors: List[str] = []
        hints: List[str] = []
        enabled = self.is_enabled()
        token = self.bot_token()
        cid = self.chat_id()
        if not enabled:
            hints.append("Set GTM_TELEGRAM_ENABLED=true to activate the Telegram channel.")
        if enabled and not token:
            errors.append("GTM_TELEGRAM_BOT_TOKEN is empty (required when enabled).")
        if enabled and not cid:
            errors.append("GTM_TELEGRAM_CHAT_ID is empty (required when enabled).")
        if token and not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            hints.append("Bot token looks malformed (expected <digits>:<alphanumeric>).")
        return {
            "ok": enabled and not errors,
            "enabled": enabled,
            "token_set": bool(token),
            "chat_id_set": bool(cid),
            "errors": errors,
            "hints": hints,
        }

    # -- transport ----------------------------------------------------------
    def _api_call(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self._http_post:
            url = f"{self.API_BASE}/bot{self.bot_token()}/{method}"
            return self._http_post(url, urllib.parse.urlencode(data).encode())
        url = f"{self.API_BASE}/bot{self.bot_token()}/{method}"
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def deliver(self, record: NotificationRecord, payload: Dict[str, Any]) -> bool:
        if not self.is_configured():
            raise DeliveryError("telegram not configured (GTM_TELEGRAM_ENABLED/token/chat_id missing)")
        text = payload.get("telegram_text") or payload.get("text", "")
        if not text:
            raise DeliveryError("no message text supplied for telegram delivery")
        response = self._api_call("sendMessage", {
            "chat_id": self.chat_id(),
            "text": text,
            "parse_mode": "Markdown",
        })
        if not response.get("ok"):
            error = response.get("description") or "telegram rejected message"
            raise DeliveryError(f"telegram rejected message: {error}")
        # A message_id means Telegram accepted the message for the chat.
        if response.get("result", {}).get("message_id"):
            record.status = DeliveryStatus.DELIVERED.value
        else:
            record.status = DeliveryStatus.SENT.value
        return True


# ---------------------------------------------------------------------------
# 4. Message formatters (Telegram / email previews)
# ---------------------------------------------------------------------------

TEST_TELEGRAM_MESSAGE = (
    "🧪 MBM GTM TEST\n\n"
    "Telegram notification channel is connected.\n"
    "No production action was triggered."
)


def format_telegram_daily_brief(brief: Dict[str, Any]) -> str:
    """Executive Money + Progress Daily Brief for Telegram (zero technical noise)."""
    money = brief.get("money", {})
    progress = brief.get("progress", {})
    meetings = brief.get("meetings", {})
    outreach = brief.get("outreach", {})
    calling = brief.get("calling", {})
    top_opps = brief.get("top_opportunities", [])
    biggest_win = brief.get("biggest_win", "")
    blocker = brief.get("blocker")
    next_moves = brief.get("next_moves", [])

    date_str = brief.get("date", str(date.today()))
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = dt.strftime("%b %d")
    except Exception:
        formatted_date = date_str

    # Legacy dictionary fallbacks if nested structures are missing
    d = brief.get("daily", {})
    leads = d.get("leads", {})
    em = d.get("email", {})
    cl = d.get("calling", {})
    mt = d.get("meetings", {})
    pip = d.get("pipeline", {})

    conf_rev = money.get("confirmed_revenue_usd", pip.get("confirmed_revenue_usd", 0.0))
    pipeline_val = money.get("new_pipeline_usd", pip.get("pipeline_value_usd", 0.0))
    exp_val = money.get("expected_value_usd", pip.get("expected_value_usd", 0.0))
    proposals_cnt = money.get("proposals_count", pip.get("proposals", 0))
    deals_won_cnt = money.get("deals_won_count", 0)

    verified = progress.get("new_verified", leads.get("verified", 0))
    contacted = progress.get("contacted", cl.get("attempted", 0))
    connected = progress.get("connected", cl.get("connected", 0))
    warmed = progress.get("warmed", leads.get("warm", 0))
    qualified = progress.get("qualified", cl.get("qualified", 0))
    mt_booked = meetings.get("booked", mt.get("booked", 0))
    mt_confirmed = meetings.get("confirmed", mt.get("confirmed", mt_booked))
    mt_today = meetings.get("today", mt.get("today", 0))
    mt_tomorrow = meetings.get("tomorrow", 0)

    pos_replies = outreach.get("positive_replies", em.get("positive", 0))
    demo_reqs = outreach.get("demo_requests", 0)
    pricing_reqs = outreach.get("pricing_requests", 0)
    followups = outreach.get("followups_due", em.get("followups", 0))

    lines = [
        "🚀 MBM GTM DAILY REVENUE BRIEF",
        f"📅 {formatted_date}",
        "",
        "💰 MONEY",
        f"Confirmed Revenue: ${conf_rev:,.0f}",
        f"New Pipeline: ${pipeline_val:,.0f}",
        f"Expected Value: ${exp_val:,.0f}",
        f"Proposals: {proposals_cnt}",
        f"Deals Won: {deals_won_cnt}",
        "",
        "🔥 PROGRESS",
        f"New Verified Leads: {verified}",
        f"Contacted: {contacted}",
        f"Connected: {connected}",
        f"Warmed: {warmed}",
        f"Qualified: {qualified}",
        f"Meetings Booked: {mt_booked}",
        f"Proposals: {proposals_cnt}",
        f"Deals Won: {deals_won_cnt}",
        "",
        "📅 MEETINGS",
        f"Booked: {mt_booked}",
        f"Confirmed: {mt_confirmed}",
        f"Today: {mt_today}",
        f"Tomorrow: {mt_tomorrow}",
        "",
        "📧 OUTREACH",
        f"Positive Replies: {pos_replies}",
        f"Demo Requests: {demo_reqs}",
        f"Pricing Requests: {pricing_reqs}",
        f"Follow-Ups Due: {followups}",
        "",
        "📞 CALLING",
        f"Connected: {connected}",
        f"Qualified: {qualified}",
        f"Meetings Requested: {mt_booked}",
    ]

    if top_opps:
        lines += ["", "🎯 TOP OPPORTUNITIES", ""]
        for i, opp in enumerate(top_opps[:3], start=1):
            comp = opp.get("company", "—")
            buyer = opp.get("buyer", "")
            role = opp.get("role", "")
            buyer_str = f"{buyer} · {role}".strip(" ·") if buyer else ""
            offer = opp.get("offer", opp.get("ai_fit", "AI Assistant Retainer"))
            stage = opp.get("stage", "QUALIFIED")
            ev = opp.get("expected_value_usd", opp.get("priority", 0.0))
            action = opp.get("next_action", opp.get("action", "Follow up"))
            lines.append(f"{i}. {comp}")
            if buyer_str:
                lines.append(f"   {buyer_str}")
            lines.append(f"   {offer}")
            lines.append(f"   Stage: {stage}")
            lines.append(f"   Expected Value: ${ev:,.0f}" if isinstance(ev, (int, float)) else f"   Expected Value: {ev}")
            lines.append(f"   Next Action: {action}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()

    if biggest_win:
        lines += [
            "",
            "🏆 BIGGEST WIN",
            biggest_win,
        ]

    if blocker and isinstance(blocker, dict) and blocker.get("issue"):
        lines += [
            "",
            "⚠️ BLOCKER",
            blocker["issue"],
            "",
            f"Action:\n{blocker.get('action', 'Address immediately.')}",
        ]
    elif blocker and isinstance(blocker, str):
        lines += [
            "",
            "⚠️ BLOCKER",
            blocker,
        ]

    if next_moves:
        lines += [
            "",
            "➡️ NEXT BEST MOVES",
        ]
        for i, move in enumerate(next_moves[:3], start=1):
            lines.append(f"{i}. {move}")

    return "\n".join(lines)


def format_hot_buyer_message(buyer: Dict[str, Any]) -> str:
    ev = buyer.get("expected_value_usd", buyer.get("priority", 0))
    ev_str = f"${ev:,.0f}" if isinstance(ev, (int, float)) and ev > 0 else "High"
    return (
        "🔥 HOT BUYER\n\n"
        f"{buyer.get('company', '—')}\n"
        f"{buyer.get('decision_maker', buyer.get('buyer', '—'))} · {buyer.get('role', 'Decision Maker')}\n\n"
        f"Pain:\n{buyer.get('pain', buyer.get('pain_point', '—'))}\n\n"
        f"Offer:\n{buyer.get('ai_fit', buyer.get('recommended_ai_assistant', buyer.get('offer', '24/7 AI Receptionist & Voice Agent')))}\n\n"
        f"Expected Value:\n{ev_str}\n\n"
        "Next:\n📞 Call discovery"
    )


def format_lead_warmed_message(lead: Dict[str, Any]) -> str:
    return (
        "🔥 LEAD WARMED\n\n"
        f"{lead.get('company', '—')}\n"
        f"{lead.get('decision_maker', lead.get('buyer', '—'))}\n\n"
        f"Offer:\n{lead.get('ai_fit', lead.get('offer', 'AI Assistant Retainer'))}\n\n"
        f"Signal:\n{lead.get('signal', lead.get('pain', 'Interested in seeing a live demo.'))}\n\n"
        "Next:\n📅 Book meeting"
    )


def format_positive_reply_message(reply: Dict[str, Any]) -> str:
    next_action = reply.get("next_action", "Book 15-min demo")
    return (
        "🔥 POSITIVE REPLY\n\n"
        f"{reply.get('company', '—')}\n"
        f"Buyer: {reply.get('buyer', reply.get('decision_maker', '—'))}\n\n"
        f"Signal:\n{reply.get('signal', reply.get('summary', 'Requested pricing and workflow demo.'))}\n\n"
        f"Next:\n📅 {next_action}"
    )


def format_meeting_booked_message(meeting: Dict[str, Any]) -> str:
    when = meeting.get("date", "") or meeting.get("when", "TBD")
    if meeting.get("time"):
        when = f"{when} · {meeting['time']}"
    brief_ready = meeting.get("brief_ready", False)
    why = (
        meeting.get("why_agreed")
        or meeting.get("why_now")
        or meeting.get("pain")
        or meeting.get("observed_problem")
        or "Agreed to 15-min diagnostic demo."
    )
    next_action = meeting.get("next_action", "Prepare demo brief")
    return (
        "📅 MEETING BOOKED\n\n"
        f"{meeting.get('company', '—')}\n"
        f"Buyer: {meeting.get('buyer', meeting.get('decision_maker', '—'))}\n\n"
        f"When:\n{when}\n\n"
        f"Offer:\n{meeting.get('ai_fit', meeting.get('recommended_ai_assistant', meeting.get('offer', 'AI Assistant Retainer')))}\n\n"
        f"Why They Agreed:\n{why}\n\n"
        f"Brief:\n{'✅ Ready' if brief_ready else '⚠️ Not ready'}\n\n"
        f"Next Action:\n{next_action}"
    )


def format_deal_won_message(deal: Dict[str, Any]) -> str:
    val = deal.get("value", deal.get("deal_value", "$4,000/mo"))
    rev_state = deal.get("revenue_state", deal.get("payment_state", "CONFIRMED (Neteller)"))
    next_step = deal.get("next_step", deal.get("next_action", "Onboarding kickoff & client setup"))
    return (
        "💰 DEAL WON\n\n"
        f"Company:\n{deal.get('company', '—')}\n\n"
        f"Offer:\n{deal.get('offer', 'AI Assistant Retainer')}\n\n"
        f"Value:\n{val}\n\n"
        f"Revenue State:\n{rev_state}\n\n"
        f"Next Step:\n{next_step}"
    )


def format_proposal_message(proposal: Dict[str, Any]) -> str:
    val = proposal.get("value", proposal.get("deal_value", "$3,500/mo"))
    return (
        "📑 PROPOSAL\n\n"
        f"{proposal.get('company', '—')}\n\n"
        f"Offer:\n{proposal.get('offer', 'AI Assistant Retainer')}\n\n"
        f"Value:\n{val}\n\n"
        "Status:\nAwaiting decision"
    )


def format_failure_message(failure: Dict[str, Any]) -> str:
    return (
        "🚨 GTM BLOCKER\n\n"
        f"Type:\n{failure.get('type', 'Unknown')}\n\n"
        f"Impact:\n{failure.get('impact', '—')}\n\n"
        f"Action:\n{failure.get('action', 'Investigate immediately.')}"
    )


# ---------------------------------------------------------------------------
# 5. Notification Bus
# ---------------------------------------------------------------------------

class NotificationBus:
    """Central delivery hub. GTM agents never touch Telegram directly."""

    def __init__(
        self,
        state_path: Optional[Path] = None,
        adapters: Optional[Dict[str, DeliveryAdapter]] = None,
    ):
        self.state = DeliveryStateStore(state_path or DEFAULT_STATE_PATH)
        self.adapters: Dict[str, DeliveryAdapter] = adapters or {
            "in_app": InAppDeliveryAdapter(),
            "email": EmailDeliveryAdapter(),
            "gmail": GmailDeliveryAdapter(),
            "telegram": TelegramDeliveryAdapter(),
            "webhook": WebhookDeliveryAdapter(),
        }
        self.router = PriorityRouter()

    # -- idempotent keys ----------------------------------------------------
    @staticmethod
    def daily_brief_key(day: Optional[str] = None) -> str:
        return f"daily_brief_{day or date.today().isoformat()}"

    @staticmethod
    def meeting_key(meeting_id: str) -> str:
        return f"meeting_booked_{meeting_id}"

    @staticmethod
    def reply_key(message_id: str) -> str:
        return f"positive_reply_{message_id}"

    @staticmethod
    def hot_buyer_key(opportunity_id: str) -> str:
        return f"hot_buyer_{opportunity_id}"

    @staticmethod
    def deal_won_key(deal_id: str) -> str:
        return f"deal_won_{deal_id}"

    @staticmethod
    def failure_key(event_id: str) -> str:
        return f"failure_{event_id}"

    # -- publish ------------------------------------------------------------
    def publish(
        self,
        kind: NotificationKind,
        delivery_key: str,
        payload: Dict[str, Any],
        channels: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> List[NotificationRecord]:
        """
        Publish a typed notification through every routed channel.
        Idempotent per (delivery_key, channel): repeated runs never duplicate.
        Adapter failures are captured per-channel and never raised to callers.
        """
        priority = self.router.route(kind)
        selected_channels = channels or self.router.default_channels(kind)

        results: List[NotificationRecord] = []
        for channel in selected_channels:
            adapter = self.adapters.get(channel)
            if not adapter:
                continue

            if self.state.already_delivered(delivery_key, channel):
                existing = self.state.get(delivery_key, channel)
                existing.status = DeliveryStatus.DUPLICATE_SKIPPED.value
                results.append(existing)
                continue

            previous = self.state.get(delivery_key, channel)
            record = NotificationRecord(
                event_id=f"notif_{uuid.uuid4().hex[:12]}",
                delivery_key=delivery_key,
                kind=kind.value,
                channel=channel,
                priority=priority.value,
                created_at=datetime.now(timezone.utc).isoformat(),
                status=DeliveryStatus.GENERATED.value,
                attempts=previous.attempts if previous else 0,
            )

            # Only telegram is gated by per-kind toggles; others deliver always.
            if channel == "telegram" and not adapter.kind_enabled(kind):
                record.status = DeliveryStatus.DUPLICATE_SKIPPED.value
                record.last_error = f"telegram toggle disabled for {kind.value}"
                self.state.upsert(record)
                results.append(record)
                continue

            if not adapter.is_configured():
                record.status = DeliveryStatus.FAILED.value
                record.last_error = "channel not configured"
                record.attempts = 1
                record.last_attempt_at = datetime.now(timezone.utc).isoformat()
                self.state.upsert(record)
                results.append(record)
                continue

            # Attempt delivery (dry-run previews do not send).
            if dry_run:
                record.status = DeliveryStatus.QUEUED.value
                record.last_error = "dry_run (not sent)"
                self.state.upsert(record)
                results.append(record)
                continue

            record.status = DeliveryStatus.QUEUED.value
            record.attempts += 1
            record.last_attempt_at = datetime.now(timezone.utc).isoformat()
            try:
                adapter.deliver(record, payload)
                if record.status == DeliveryStatus.GENERATED.value:
                    record.status = DeliveryStatus.SENT.value
            except Exception as e:  # noqa: BLE001 — failure isolation boundary
                record.status = DeliveryStatus.FAILED.value
                record.last_error = str(e)[:300]
            self.state.upsert(record)
            results.append(record)

        return results

    # -- convenience --------------------------------------------------------
    def send_daily_brief(self, dry_run: bool = False) -> List[NotificationRecord]:
        """Generate today's quick brief from real state and publish it (idempotent)."""
        from MBM.LeadEngine.gtm_quick_brief import GtmQuickBrief  # lazy: avoid circular import

        brief = GtmQuickBrief()
        daily = brief.generate_daily()
        payload = {
            "summary": f"MBM GTM Daily Brief {daily.get('date')}",
            "telegram_text": format_telegram_daily_brief(daily),
            "text": brief.render_email_daily(daily),
            "subject": f"MBM GTM Daily Brief — {daily.get('date')}",
            "data": daily,
        }
        return self.publish(
            NotificationKind.DAILY_BRIEF,
            self.daily_brief_key(),
            payload,
            dry_run=dry_run,
        )

    def send_meeting_booked(self, meeting: Dict[str, Any], dry_run: bool = False) -> List[NotificationRecord]:
        meeting_id = str(meeting.get("id") or meeting.get("company") or "unknown")
        payload = {
            "summary": f"Meeting booked: {meeting.get('company')}",
            "telegram_text": format_meeting_booked_message(meeting),
            "text": format_meeting_booked_message(meeting),
            "subject": f"[MBM GTM] Meeting booked — {meeting.get('company')}",
            "data": meeting,
        }
        return self.publish(
            NotificationKind.MEETING_BOOKED,
            self.meeting_key(meeting_id),
            payload,
            dry_run=dry_run,
        )

    def send_hot_buyer(self, buyer: Dict[str, Any], dry_run: bool = False) -> List[NotificationRecord]:
        opportunity_id = str(buyer.get("id") or buyer.get("entity_id") or buyer.get("company") or "unknown")
        payload = {
            "summary": f"HOT buyer: {buyer.get('company')}",
            "telegram_text": format_hot_buyer_message(buyer),
            "text": format_hot_buyer_message(buyer),
            "subject": f"[MBM GTM] HOT buyer — {buyer.get('company')}",
            "data": buyer,
        }
        return self.publish(
            NotificationKind.HOT_BUYER,
            self.hot_buyer_key(opportunity_id),
            payload,
            dry_run=dry_run,
        )

    def send_positive_reply(self, reply: Dict[str, Any], dry_run: bool = False) -> List[NotificationRecord]:
        message_id = str(reply.get("message_id") or reply.get("id") or "unknown")
        payload = {
            "summary": f"Positive reply: {reply.get('company')}",
            "telegram_text": format_positive_reply_message(reply),
            "text": format_positive_reply_message(reply),
            "subject": f"[MBM GTM] Positive reply — {reply.get('company')}",
            "data": reply,
        }
        return self.publish(
            NotificationKind.POSITIVE_REPLY,
            self.reply_key(message_id),
            payload,
            dry_run=dry_run,
        )

    def send_critical_failure(self, failure: Dict[str, Any], dry_run: bool = False) -> List[NotificationRecord]:
        event_id = str(failure.get("event_id") or "unknown")
        payload = {
            "summary": f"GTM failure: {failure.get('type')}",
            "telegram_text": format_failure_message(failure),
            "text": format_failure_message(failure),
            "subject": f"[MBM GTM] ⚠️ FAILURE — {failure.get('type')}",
            "data": failure,
        }
        return self.publish(
            NotificationKind.CRITICAL_FAILURE,
            self.failure_key(event_id),
            payload,
            dry_run=dry_run,
        )

    # -- test / preview -----------------------------------------------------
    def send_test_telegram(self) -> Dict[str, Any]:
        """Send a clearly-marked connectivity test. Never a sales notification."""
        adapter = self.adapters.get("telegram")
        validation = adapter.validate()
        if not validation["ok"]:
            return {"sent": False, "validation": validation, "message": "not configured"}

        record = NotificationRecord(
            event_id=f"test_{uuid.uuid4().hex[:8]}",
            delivery_key=f"test_telegram_{datetime.now(timezone.utc).isoformat()}",
            kind="TEST",
            channel="telegram",
            priority="P0",
            created_at=datetime.now(timezone.utc).isoformat(),
            status=DeliveryStatus.GENERATED.value,
        )
        record.attempts = 1
        record.last_attempt_at = datetime.now(timezone.utc).isoformat()
        try:
            adapter.deliver(record, {"text": TEST_TELEGRAM_MESSAGE})
            self.state.upsert(record)
            return {"sent": True, "status": record.status, "validation": validation, "record": record.to_dict()}
        except Exception as e:  # noqa: BLE001
            record.status = DeliveryStatus.FAILED.value
            record.last_error = str(e)[:300]
            self.state.upsert(record)
            return {"sent": False, "status": record.status, "validation": validation, "error": str(e)}

    def send_test_gmail(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Send a real authenticated test email through the Gmail adapter and verify status."""
        adapter: GmailDeliveryAdapter = self.adapters.get("gmail")  # type: ignore
        if not adapter:
            return {"sent": False, "error": "gmail adapter not registered"}

        validation = adapter.validate()
        target_to = recipient or adapter.owner_email()
        record = NotificationRecord(
            event_id=f"notif_{uuid.uuid4().hex[:12]}",
            delivery_key=f"test_gmail_{datetime.now(timezone.utc).isoformat()}",
            kind="TEST",
            channel="gmail",
            priority="P0",
            created_at=datetime.now(timezone.utc).isoformat(),
            status=DeliveryStatus.GENERATED.value,
        )
        record.attempts = 1
        record.last_attempt_at = datetime.now(timezone.utc).isoformat()
        try:
            adapter.deliver(record, {
                "email_subject": "🔔 [MBM GTM] Authenticated Gmail Transport Test",
                "email_text": (
                    "This is an automated connectivity test from MBM GTM Delivery Center.\n\n"
                    f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
                    f"Event ID: {record.event_id}\n"
                    "Status: AUTHENTICATED_TRANSPORT_VERIFIED\n"
                ),
                "recipient": target_to,
            })
            self.state.upsert(record)
            return {
                "sent": True,
                "status": record.status,
                "validation": validation,
                "recipient": target_to,
                "record": record.to_dict(),
            }
        except Exception as e:  # noqa: BLE001
            record.status = DeliveryStatus.FAILED.value
            record.last_error = str(e)[:300]
            self.state.upsert(record)
            return {
                "sent": False,
                "status": record.status,
                "validation": validation,
                "recipient": target_to,
                "error": str(e),
            }

    def check_gmail_inbound(self) -> Dict[str, Any]:
        """Check Gmail inbound unread messages and prospect replies via IMAP."""
        adapter: GmailDeliveryAdapter = self.adapters.get("gmail")  # type: ignore
        if not adapter:
            return {"ok": False, "error": "gmail adapter not registered"}
        try:
            replies = adapter.check_inbound_replies()
            return {"ok": True, "count": len(replies), "replies": replies}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------

def _build_preview(kind: NotificationKind) -> str:
    sample_payloads = {
        NotificationKind.HOT_BUYER: {
            "company": "Apex Mechanical & Air Solutions",
            "decision_maker": "Marcus Vance",
            "role": "Founder",
            "pain": "After-hours calls being missed",
            "ai_fit": "24/7 AI Emergency Call Answering & Dispatch",
            "expected_value_usd": 18000.0,
            "priority": 20.4,
        },
        NotificationKind.LEAD_WARMED: {
            "company": "Apex Mechanical & Air Solutions",
            "decision_maker": "Marcus Vance",
            "ai_fit": "24/7 AI Emergency Call Assistant",
            "signal": "Interested in seeing a live demo.",
        },
        NotificationKind.POSITIVE_REPLY: {
            "company": "Vanguard Commercial Roofing",
            "buyer": "Derek Holloway",
            "signal": "Interested in the AI follow-up workflow and requested pricing.",
            "next_action": "Send proposal & book 15-min walkthrough",
        },
        NotificationKind.MEETING_BOOKED: {
            "id": "preview",
            "company": "Premier Smile Partners",
            "buyer": "Dr. Sarah Lin",
            "date": "Tomorrow",
            "time": "10:30 AM",
            "ai_fit": "AI Recall + Front Desk Assistant",
            "brief_ready": True,
        },
        NotificationKind.DEAL_WON: {
            "company": "Apex Mechanical",
            "offer": "24/7 AI Emergency Call Agent",
            "value": "$4,000/mo ($48,000 ARR)",
        },
        NotificationKind.PROPOSAL_SENT: {
            "company": "Vanguard Commercial Roofing",
            "offer": "AI Lead Follow-Up Agent",
            "value": "$3,500/mo ($42,000 ARR)",
        },
        NotificationKind.CRITICAL_FAILURE: {
            "type": "Daily Lead Factory",
            "impact": "100 new leads were NOT delivered to the dialer.",
            "action": "Investigate immediately.",
        },
        NotificationKind.DAILY_BRIEF: {
            "date": "2026-08-16",
            "money": {
                "confirmed_revenue_usd": 4000.0,
                "new_pipeline_usd": 27500.0,
                "expected_value_usd": 18900.0,
                "proposals_count": 2,
                "deals_won_count": 1,
            },
            "progress": {
                "new_verified": 100,
                "contacted": 63,
                "connected": 31,
                "warmed": 18,
                "qualified": 9,
                "meetings_booked": 4,
                "proposals": 2,
                "deals_won": 1,
            },
            "meetings": {
                "booked": 4,
                "confirmed": 3,
                "today": 1,
                "tomorrow": 2,
                "briefs_ready": 4,
            },
            "outreach": {
                "positive_replies": 7,
                "demo_requests": 3,
                "pricing_requests": 2,
                "followups_due": 5,
            },
            "calling": {
                "connected": 31,
                "qualified": 9,
                "meetings_requested": 4,
            },
            "top_opportunities": [
                {
                    "company": "Apex Mechanical & Air Solutions",
                    "buyer": "Marcus Vance",
                    "role": "Founder",
                    "offer": "24/7 AI Emergency Call Agent",
                    "stage": "DEMO_BOOKED",
                    "expected_value_usd": 18000.0,
                    "next_action": "Prepare 15-min diagnostic demo",
                },
                {
                    "company": "Vanguard Commercial Roofing",
                    "buyer": "Derek Holloway",
                    "role": "Operations",
                    "offer": "AI Lead Follow-Up Agent",
                    "stage": "PROPOSAL",
                    "expected_value_usd": 8400.0,
                    "next_action": "Send Neteller retainer SOW",
                },
                {
                    "company": "Premier Smile Partners Dental Group",
                    "buyer": "Dr. Sarah Lin",
                    "role": "Practice Owner",
                    "offer": "AI Recall + Front Desk Assistant",
                    "stage": "ENGAGED",
                    "expected_value_usd": 6500.0,
                    "next_action": "Call to confirm demo slot",
                },
            ],
            "biggest_win": "Apex Mechanical converted from HOT lead → booked demo.",
            "next_moves": [
                "Prepare today's Apex demo (AI Emergency Call Agent)",
                "Follow up with Vanguard on AI Lead Follow-Up proposal",
                "Call Premier Smile Partners to confirm demo slot",
            ],
        },
    }
    payload = sample_payloads.get(kind, {})
    formatters = {
        NotificationKind.HOT_BUYER: format_hot_buyer_message,
        NotificationKind.LEAD_WARMED: format_lead_warmed_message,
        NotificationKind.POSITIVE_REPLY: format_positive_reply_message,
        NotificationKind.MEETING_BOOKED: format_meeting_booked_message,
        NotificationKind.DEAL_WON: format_deal_won_message,
        NotificationKind.PROPOSAL_SENT: format_proposal_message,
        NotificationKind.CRITICAL_FAILURE: format_failure_message,
        NotificationKind.DAILY_BRIEF: format_telegram_daily_brief,
    }
    fmt = formatters.get(kind, lambda p: str(p))
    return fmt(payload)


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Notification Bus")
    parser.add_argument("--test-telegram", action="store_true", help="Send a clearly-marked connectivity test message via Telegram")
    parser.add_argument("--test-gmail", action="store_true", help="Send a clearly-marked connectivity test email via Gmail SMTP")
    parser.add_argument("--check-inbound", action="store_true", help="Check inbound unread emails & detected replies via Gmail IMAP")
    parser.add_argument("--preview", type=str, choices=[k.value for k in NotificationKind], help="Render a message preview without sending")
    args = parser.parse_args()

    bus = NotificationBus()

    if args.test_telegram:
        result = bus.send_test_telegram()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("sent") else 1)

    if args.test_gmail:
        result = bus.send_test_gmail()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("sent") else 1)

    if args.check_inbound:
        result = bus.check_gmail_inbound()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("ok") else 1)

    if args.preview:
        kind = NotificationKind(args.preview)
        print(_build_preview(kind))
        return

    parser.print_help()


if __name__ == "__main__":
    main()