"""Hermetic unit tests for GTM Gmail Delivery Adapter and transport isolation."""

import os
import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_notification_bus import (
    GmailDeliveryAdapter,
    NotificationBus,
    NotificationKind,
    NotificationRecord,
    DeliveryStatus,
    PriorityLevel,
    PriorityRouter,
)


class MockSMTPSender:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.sent_messages = []

    def __call__(self, to_addr: str, subject: str, body_text: str, html_body=None):
        if self.should_fail:
            raise RuntimeError("535 5.7.8 Username and Password not accepted")
        self.sent_messages.append({"to": to_addr, "subject": subject, "body": body_text})
        return {"sent": True, "to": to_addr, "subject": subject, "message_id": "<test-msg-1@mbm-gtm.local>"}


class MockIMAPClient:
    def __init__(self, sample_replies=None):
        self.sample_replies = sample_replies or [
            {
                "from": "Marcus Vance <marcus@apexmechanical.com>",
                "subject": "Re: AI Call Answering Demo",
                "date": "Sun, 16 Aug 2026 14:22:00 +0000",
            }
        ]

    def __call__(self, query="UNSEEN"):
        return self.sample_replies


@pytest.fixture
def mock_gmail_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("GTM_GMAIL_ENABLED", "true")
    monkeypatch.setenv("GTM_GMAIL_USER", "abdelshafyclapps@gmail.com")
    monkeypatch.setenv("GTM_GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("OWNER_EMAIL", "abdelshafyclapps@gmail.com")


def test_gmail_adapter_account_resolution(mock_gmail_env):
    adapter = GmailDeliveryAdapter()
    assert adapter.account_user() == "abdelshafyclapps@gmail.com"
    # Whitespace stripped from app password
    assert adapter.account_password() == "abcdefghijklmnop"
    assert adapter.owner_email() == "abdelshafyclapps@gmail.com"
    assert adapter.is_enabled() is True
    assert adapter.is_configured() is True


def test_gmail_adapter_validation_missing_credentials(monkeypatch):
    monkeypatch.delenv("GTM_GMAIL_USER", raising=False)
    monkeypatch.delenv("MASTER_GMAIL", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("GTM_GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)

    adapter = GmailDeliveryAdapter()
    v = adapter.validate()
    assert v["has_password"] is False
    assert any("App Password" in err for err in v["errors"])
    assert any("Google App Password" in hint for hint in v["hints"])


def test_gmail_adapter_send_success(mock_gmail_env):
    mock_smtp = MockSMTPSender()
    adapter = GmailDeliveryAdapter(smtp_sender=mock_smtp)

    record = NotificationRecord(
        event_id="evt_001",
        delivery_key="hot_buyer_opp_123",
        kind="HOT_BUYER",
        channel="gmail",
        priority="P1",
        created_at="2026-08-16T12:00:00Z",
    )

    payload = {
        "email_subject": "🔥 HOT BUYER ALERT: Apex Mechanical",
        "email_text": "Marcus Vance is interested in 24/7 AI Receptionist.",
        "recipient": "abdelshafyclapps@gmail.com",
    }

    ok = adapter.deliver(record, payload)
    assert ok is True
    assert record.status == DeliveryStatus.DELIVERED.value
    assert len(mock_smtp.sent_messages) == 1
    assert mock_smtp.sent_messages[0]["to"] == "abdelshafyclapps@gmail.com"
    assert "HOT BUYER" in mock_smtp.sent_messages[0]["subject"]


def test_gmail_adapter_failure_isolated(mock_gmail_env):
    mock_smtp = MockSMTPSender(should_fail=True)
    adapter = GmailDeliveryAdapter(smtp_sender=mock_smtp)

    record = NotificationRecord(
        event_id="evt_002",
        delivery_key="hot_buyer_opp_456",
        kind="HOT_BUYER",
        channel="gmail",
        priority="P1",
        created_at="2026-08-16T12:00:00Z",
    )

    payload = {
        "email_subject": "🔥 HOT BUYER",
        "email_text": "Test body",
    }

    with pytest.raises(Exception) as exc_info:
        adapter.deliver(record, payload)
    assert "Username and Password not accepted" in str(exc_info.value)


def test_gmail_inbound_replies_detection(mock_gmail_env):
    mock_imap = MockIMAPClient()
    adapter = GmailDeliveryAdapter(imap_client=mock_imap)

    replies = adapter.check_inbound_replies()
    assert len(replies) == 1
    assert "Marcus Vance" in replies[0]["from"]
    assert "AI Call Answering" in replies[0]["subject"]


def test_notification_bus_send_test_gmail(tmp_path, mock_gmail_env):
    mock_smtp = MockSMTPSender()
    adapter = GmailDeliveryAdapter(smtp_sender=mock_smtp)

    bus = NotificationBus(
        state_path=tmp_path / "delivery_state.json",
        adapters={"gmail": adapter},
    )

    result = bus.send_test_gmail()
    assert result["sent"] is True
    assert result["status"] == DeliveryStatus.DELIVERED.value
    assert result["recipient"] == "abdelshafyclapps@gmail.com"
    assert len(mock_smtp.sent_messages) == 1


def test_notification_bus_check_gmail_inbound(tmp_path, mock_gmail_env):
    mock_imap = MockIMAPClient()
    adapter = GmailDeliveryAdapter(imap_client=mock_imap)

    bus = NotificationBus(
        state_path=tmp_path / "delivery_state.json",
        adapters={"gmail": adapter},
    )

    result = bus.check_gmail_inbound()
    assert result["ok"] is True
    assert result["count"] == 1
    assert "Marcus Vance" in result["replies"][0]["from"]


def test_gmail_delivery_idempotency(tmp_path, mock_gmail_env):
    mock_smtp = MockSMTPSender()
    adapter = GmailDeliveryAdapter(smtp_sender=mock_smtp)

    bus = NotificationBus(
        state_path=tmp_path / "delivery_state.json",
        adapters={"gmail": adapter},
    )

    # First publish: delivers
    recs1 = bus.publish(
        NotificationKind.DAILY_BRIEF,
        "daily_brief_2026-08-16",
        {"email_subject": "Daily Brief", "email_text": "All metrics green"},
        channels=["gmail"],
    )
    assert recs1[0].status == DeliveryStatus.DELIVERED.value
    assert len(mock_smtp.sent_messages) == 1

    # Second publish with identical delivery_key: idempotent skip
    recs2 = bus.publish(
        NotificationKind.DAILY_BRIEF,
        "daily_brief_2026-08-16",
        {"email_subject": "Daily Brief", "email_text": "All metrics green"},
        channels=["gmail"],
    )
    assert recs2[0].status == DeliveryStatus.DUPLICATE_SKIPPED.value
    # No second email sent
    assert len(mock_smtp.sent_messages) == 1


def test_all_seven_gtm_alert_kinds_route_to_gmail():
    expected_kinds = [
        NotificationKind.DAILY_BRIEF,
        NotificationKind.HOT_BUYER,
        NotificationKind.POSITIVE_REPLY,
        NotificationKind.MEETING_BOOKED,
        NotificationKind.MEETING_WITHIN_1H,
        NotificationKind.DEAL_WON,
        NotificationKind.CRITICAL_FAILURE,
    ]

    for kind in expected_kinds:
        channels = PriorityRouter.default_channels(kind)
        assert "gmail" in channels, f"Kind {kind} missing gmail channel routing"
