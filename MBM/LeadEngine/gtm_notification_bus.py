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
    POSITIVE_REPLY = "POSITIVE_REPLY"
    MEETING_BOOKED = "MEETING_BOOKED"
    MEETING_WITHIN_1H = "MEETING_WITHIN_1H"
    DEAL_WON = "DEAL_WON"
    REVENUE_RECEIVED = "REVENUE_RECEIVED"
    CRITICAL_FAILURE = "CRITICAL_FAILURE"
    QUALIFIED_CONVERSATION = "QUALIFIED_CONVERSATION"
    NEW_LEADS = "NEW_LEADS"
    WARM_SIGNAL = "WARM_SIGNAL"
    ROUTINE_FOLLOWUP = "ROUTINE_FOLLOWUP"


class PriorityLevel(str, Enum):
    P0 = "P0"  # immediate — critical failure / deal won / revenue / meeting within 1h
    P1 = "P1"  # near-immediate — meeting booked / positive reply / HOT buyer / qualified conversation
    P2 = "P2"  # daily digest — new leads / warm signals / routine follow-ups / statistics


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
    NotificationKind.POSITIVE_REPLY: "GTM_TELEGRAM_POSITIVE_REPLIES",
    NotificationKind.MEETING_BOOKED: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.MEETING_WITHIN_1H: "GTM_TELEGRAM_MEETINGS",
    NotificationKind.DEAL_WON: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.REVENUE_RECEIVED: "GTM_TELEGRAM_HOT_BUYERS",
    NotificationKind.CRITICAL_FAILURE: "GTM_TELEGRAM_FAILURES",
    NotificationKind.QUALIFIED_CONVERSATION: "GTM_TELEGRAM_POSITIVE_REPLIES",
    NotificationKind.NEW_LEADS: "GTM_TELEGRAM_DAILY_BRIEF",
    NotificationKind.WARM_SIGNAL: "GTM_TELEGRAM_DAILY_BRIEF",
    NotificationKind.ROUTINE_FOLLOWUP: "GTM_TELEGRAM_DAILY_BRIEF",
}


class PriorityRouter:
    """Routes notification kinds to priority levels and default channel sets."""

    DEFAULT_CHANNELS = {
        PriorityLevel.P0: ["telegram", "email", "in_app", "webhook"],
        PriorityLevel.P1: ["telegram", "in_app", "email"],
        PriorityLevel.P2: ["in_app", "email", "telegram"],
    }

    KIND_PRIORITY = {
        NotificationKind.CRITICAL_FAILURE: PriorityLevel.P0,
        NotificationKind.DEAL_WON: PriorityLevel.P0,
        NotificationKind.REVENUE_RECEIVED: PriorityLevel.P0,
        NotificationKind.MEETING_WITHIN_1H: PriorityLevel.P0,
        NotificationKind.MEETING_BOOKED: PriorityLevel.P1,
        NotificationKind.POSITIVE_REPLY: PriorityLevel.P1,
        NotificationKind.HOT_BUYER: PriorityLevel.P1,
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
        return os.environ.get("GTM_TELEGRAM_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

    def bot_token(self) -> str:
        return os.environ.get("GTM_TELEGRAM_BOT_TOKEN", "").strip()

    def chat_id(self) -> str:
        return os.environ.get("GTM_TELEGRAM_CHAT_ID", "").strip()

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
    """Compact 10-second daily brief in the canonical Telegram format."""
    d = brief.get("daily", {})
    leads = d.get("leads", {})
    email = d.get("email", {})
    calling = d.get("calling", {})
    meetings = d.get("meetings", {})
    pipeline = d.get("pipeline", {})
    alerts = d.get("alerts", {})

    lines = [
        "🚀 MBM GTM DAILY",
        "",
        f"{leads.get('verified', 0)} new verified leads",
        f"{leads.get('hot', 0)} HOT · {leads.get('high', 0)} HIGH · {leads.get('warm', 0)} WARM",
        "",
        f"📧 {email.get('replies', 0)} replies · {email.get('positive', 0)} positive",
        f"📞 {calling.get('connected', 0)} conversations · {calling.get('qualified', 0)} qualified",
        f"📅 {meetings.get('booked', 0)} meetings",
        f"💰 {pipeline.get('active_opportunities', 0)} active opportunities",
    ]
    for i, action in enumerate(brief.get("top_actions", [])[:3], start=1):
        lines.append(f"🎯 NEXT {i}: {action.get('action', '')[:48]} {action.get('company', '')}")
    lines.append("")
    lines.append(f"Dialer: {'✅' if calling.get('dialer_ok', True) else '⚠️'}")
    lines.append(f"Verification: {'✅' if alerts.get('verification_failures', 0) == 0 else '⚠️'}")
    lines.append(f"Duplicates: {alerts.get('duplicates', 0)}")
    return "\n".join(lines)


def format_hot_buyer_message(buyer: Dict[str, Any]) -> str:
    priority = buyer.get("priority", buyer.get("priority_score", "—"))
    return (
        "🔥 HOT AI BUYER\n\n"
        f"{buyer.get('company', '—')}\n"
        f"{buyer.get('decision_maker', buyer.get('buyer', '—'))} · {buyer.get('role', '—')}\n\n"
        f"Pain:\n{buyer.get('pain', buyer.get('pain_point', '—'))}\n\n"
        f"AI Fit:\n{buyer.get('ai_fit', buyer.get('recommended_ai_assistant', '—'))}\n\n"
        f"Priority:\n{priority}\n\n"
        "Next:\n📞 CALL"
    )


def format_positive_reply_message(reply: Dict[str, Any]) -> str:
    return (
        "🔥 POSITIVE REPLY\n\n"
        f"{reply.get('company', '—')}\n\n"
        f"Buyer:\n{reply.get('buyer', reply.get('decision_maker', '—'))}\n\n"
        f"Signal:\n{reply.get('signal', reply.get('summary', '—'))}\n\n"
        "Next:\n📅 BOOK MEETING"
    )


def format_meeting_booked_message(meeting: Dict[str, Any]) -> str:
    when = meeting.get("date", "") or meeting.get("when", "TBD")
    if meeting.get("time"):
        when = f"{when} {meeting['time']}"
    brief_ready = meeting.get("brief_ready", False)
    return (
        "📅 MEETING BOOKED\n\n"
        f"{meeting.get('company', '—')}\n\n"
        f"Buyer:\n{meeting.get('buyer', meeting.get('decision_maker', '—'))}\n\n"
        f"When:\n{when}\n\n"
        f"AI Fit:\n{meeting.get('ai_fit', meeting.get('recommended_ai_assistant', '—'))}\n\n"
        f"Brief:\n{'✅ Ready' if brief_ready else '⚠️ Not ready'}\n\n"
        "Next:\nPrepare demo"
    )


def format_failure_message(failure: Dict[str, Any]) -> str:
    return (
        "🚨 GTM FAILURE\n\n"
        f"Type:\n{failure.get('type', 'Unknown')}\n\n"
        f"Status:\n{failure.get('status', 'FAILED')}\n\n"
        f"Impact:\n{failure.get('impact', '—')}\n\n"
        "Action:\nInvestigate immediately."
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
            "priority": 20.4,
        },
        NotificationKind.POSITIVE_REPLY: {
            "company": "Vanguard Commercial Roofing",
            "buyer": "Derek Holloway",
            "signal": "Interested in the AI follow-up workflow.",
        },
        NotificationKind.MEETING_BOOKED: {
            "id": "preview",
            "company": "Premier Smile Partners",
            "buyer": "Dr. Sarah Lin",
            "date": "Tomorrow",
            "time": "10:30 AM",
            "ai_fit": "AI Recall / Front Desk Assistant",
            "brief_ready": True,
        },
        NotificationKind.CRITICAL_FAILURE: {
            "type": "Dialer Sync",
            "status": "FAILED",
            "impact": "Today's new leads were not delivered.",
        },
        NotificationKind.DAILY_BRIEF: {
            "daily": {
                "leads": {"verified": 127, "hot": 34, "high": 46, "warm": 47},
                "email": {"replies": 14, "positive": 7},
                "calling": {"connected": 19, "qualified": 8},
                "meetings": {"booked": 3},
                "pipeline": {"active_opportunities": 5},
                "alerts": {"verification_failures": 0, "duplicates": 0},
            },
            "top_actions": [
                {"action": "CALL_DISCOVERY", "company": "Apex Mechanical"},
                {"action": "SEND_COLD_EMAIL", "company": "Vanguard"},
                {"action": "BOOK_MEETING", "company": "Premier Smile"},
            ],
        },
    }
    payload = sample_payloads.get(kind, {})
    formatters = {
        NotificationKind.HOT_BUYER: format_hot_buyer_message,
        NotificationKind.POSITIVE_REPLY: format_positive_reply_message,
        NotificationKind.MEETING_BOOKED: format_meeting_booked_message,
        NotificationKind.CRITICAL_FAILURE: format_failure_message,
        NotificationKind.DAILY_BRIEF: format_telegram_daily_brief,
    }
    fmt = formatters.get(kind, lambda p: str(p))
    return fmt(payload)


def main():
    parser = argparse.ArgumentParser(description="MBM GTM Notification Bus")
    parser.add_argument("--test-telegram", action="store_true", help="Send a clearly-marked connectivity test message")
    parser.add_argument("--preview", type=str, choices=[k.value for k in NotificationKind], help="Render a message preview without sending")
    args = parser.parse_args()

    bus = NotificationBus()

    if args.test_telegram:
        result = bus.send_test_telegram()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("sent") else 1)

    if args.preview:
        kind = NotificationKind(args.preview)
        print(_build_preview(kind))
        return

    parser.print_help()


if __name__ == "__main__":
    main()