"""Hermetic tests for the Telegram delivery adapter (formatting, config, delivery state)."""

import os
import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_notification_bus import (
    TelegramDeliveryAdapter,
    NotificationKind,
    DeliveryStatus,
    TEST_TELEGRAM_MESSAGE,
    format_telegram_daily_brief,
    format_hot_buyer_message,
    format_positive_reply_message,
    format_meeting_booked_message,
    format_failure_message,
)


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("GTM_TELEGRAM_BOT_TOKEN", "123456:ABCdef_xyz")
    monkeypatch.setenv("GTM_TELEGRAM_CHAT_ID", "-1001234567890")
    return TelegramDeliveryAdapter()


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def test_validation_ok(adapter):
    v = adapter.validate()
    assert v["ok"] is True
    assert v["enabled"] is True
    assert v["errors"] == []


def test_validation_missing_token(adapter, monkeypatch):
    monkeypatch.delenv("GTM_TELEGRAM_BOT_TOKEN")
    v = adapter.validate()
    assert v["ok"] is False
    assert any("GTM_TELEGRAM_BOT_TOKEN" in e for e in v["errors"])


def test_validation_missing_chat_id(adapter, monkeypatch):
    monkeypatch.delenv("GTM_TELEGRAM_CHAT_ID")
    v = adapter.validate()
    assert v["ok"] is False
    assert any("GTM_TELEGRAM_CHAT_ID" in e for e in v["errors"])


def test_validation_disabled_is_not_error(monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_ENABLED", "false")
    a = TelegramDeliveryAdapter()
    v = a.validate()
    assert v["ok"] is False  # not ready to send
    assert v["errors"] == []  # but not a misconfiguration


def test_not_configured_when_disabled(monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_ENABLED", "false")
    assert TelegramDeliveryAdapter().is_configured() is False


# ---------------------------------------------------------------------------
# Delivery state semantics
# ---------------------------------------------------------------------------

class FakeHTTPPost:
    def __init__(self, response):
        self.calls = []
        self.response = response

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.response


def test_delivered_when_message_id_returned(adapter, monkeypatch):
    from MBM.LeadEngine.gtm_notification_bus import NotificationRecord
    fake = FakeHTTPPost({"ok": True, "result": {"message_id": 42}})
    adapter._http_post = fake
    rec = NotificationRecord(
        event_id="e1", delivery_key="hot_buyer_x", kind="HOT_BUYER",
        channel="telegram", priority="P1",
        created_at="2026-08-16T00:00:00Z",
    )
    ok = adapter.deliver(rec, {"text": "hello"})
    assert ok is True
    assert rec.status == DeliveryStatus.DELIVERED.value


def test_rejected_is_failed_not_delivered(adapter, monkeypatch):
    from MBM.LeadEngine.gtm_notification_bus import NotificationRecord, DeliveryError
    fake = FakeHTTPPost({"ok": False, "description": "chat not found"})
    adapter._http_post = fake
    rec = NotificationRecord(
        event_id="e2", delivery_key="hot_buyer_y", kind="HOT_BUYER",
        channel="telegram", priority="P1",
        created_at="2026-08-16T00:00:00Z",
    )
    with pytest.raises(DeliveryError):
        adapter.deliver(rec, {"text": "hello"})
    assert rec.status == DeliveryStatus.GENERATED.value  # bus flips to FAILED


def test_kind_toggles(adapter, monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_POSITIVE_REPLIES", "false")
    assert adapter.kind_enabled(NotificationKind.POSITIVE_REPLY) is False
    assert adapter.kind_enabled(NotificationKind.MEETING_BOOKED) is True


# ---------------------------------------------------------------------------
# Message formatting (canonical Telegram layouts)
# ---------------------------------------------------------------------------

def test_test_message_clearly_marked():
    assert "MBM GTM TEST" in TEST_TELEGRAM_MESSAGE
    assert "No production action was triggered." in TEST_TELEGRAM_MESSAGE
    assert "🧪" in TEST_TELEGRAM_MESSAGE


def test_daily_brief_formatting():
    brief = {
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
    }
    text = format_telegram_daily_brief(brief)
    assert "🚀 MBM GTM DAILY" in text
    assert "127 new verified leads" in text
    assert "34 HOT · 46 HIGH · 47 WARM" in text
    assert "14 replies · 7 positive" in text
    assert "19 conversations · 8 qualified" in text
    assert "3 meetings" in text
    assert "5 active opportunities" in text
    assert "Dialer: ✅" in text
    assert "Duplicates: 0" in text


def test_hot_buyer_formatting():
    text = format_hot_buyer_message({
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Founder",
        "pain": "After-hours calls being missed",
        "ai_fit": "24/7 AI Emergency Call Answering & Dispatch",
        "priority": 20.4,
    })
    assert "🔥 HOT AI BUYER" in text
    assert "Apex Mechanical & Air Solutions" in text
    assert "Marcus Vance" in text
    assert "20.4" in text
    assert "📞 CALL" in text


def test_positive_reply_formatting():
    text = format_positive_reply_message({
        "company": "Vanguard Commercial Roofing",
        "buyer": "Derek Holloway",
        "signal": "Interested in the AI follow-up workflow.",
    })
    assert "🔥 POSITIVE REPLY" in text
    assert "Vanguard Commercial Roofing" in text
    assert "Derek Holloway" in text
    assert "📅 BOOK MEETING" in text


def test_meeting_booked_formatting():
    text = format_meeting_booked_message({
        "company": "Premier Smile Partners",
        "buyer": "Dr. Sarah Lin",
        "date": "Tomorrow",
        "time": "10:30 AM",
        "ai_fit": "AI Recall / Front Desk Assistant",
        "brief_ready": True,
    })
    assert "📅 MEETING BOOKED" in text
    assert "Premier Smile Partners" in text
    assert "Dr. Sarah Lin" in text
    assert "Tomorrow 10:30 AM" in text
    assert "✅ Ready" in text


def test_failure_formatting():
    text = format_failure_message({
        "type": "Dialer Sync",
        "status": "FAILED",
        "impact": "Today's new leads were not delivered.",
    })
    assert "🚨 GTM FAILURE" in text
    assert "Dialer Sync" in text
    assert "Investigate immediately." in text