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
    format_lead_warmed_message,
    format_positive_reply_message,
    format_meeting_booked_message,
    format_deal_won_message,
    format_proposal_message,
    format_failure_message,
)


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
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


def test_validation_legacy_credentials_fallback(monkeypatch):
    monkeypatch.delenv("GTM_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("GTM_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("GTM_TELEGRAM_ENABLED", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABCdef_xyz")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
    a = TelegramDeliveryAdapter()
    v = a.validate()
    assert v["ok"] is True
    assert v["enabled"] is True
    assert v["token_set"] is True
    assert v["chat_id_set"] is True


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
# Message formatting (Executive Money + Progress Telegram layouts)
# ---------------------------------------------------------------------------

def test_test_message_clearly_marked():
    assert "MBM GTM TEST" in TEST_TELEGRAM_MESSAGE
    assert "No production action was triggered." in TEST_TELEGRAM_MESSAGE
    assert "🧪" in TEST_TELEGRAM_MESSAGE


def test_daily_brief_money_and_progress_formatting():
    brief = {
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
        ],
        "biggest_win": "Apex Mechanical converted from HOT lead → booked demo.",
        "next_moves": [
            "Prepare today's Apex demo (AI Emergency Call Agent)",
            "Follow up with Vanguard on AI Lead Follow-Up proposal",
            "Call Premier Smile Partners to confirm demo slot",
        ],
    }
    text = format_telegram_daily_brief(brief)
    assert "🚀 MBM GTM DAILY REVENUE BRIEF" in text
    assert "💰 MONEY" in text
    assert "Confirmed Revenue: $4,000" in text
    assert "New Pipeline: $27,500" in text
    assert "Expected Value: $18,900" in text
    assert "Proposals: 2" in text
    assert "Deals Won: 1" in text

    assert "🔥 PROGRESS" in text
    assert "New Verified Leads: 100" in text
    assert "Contacted: 63" in text
    assert "Connected: 31" in text
    assert "Warmed: 18" in text
    assert "Qualified: 9" in text

    assert "📅 MEETINGS" in text
    assert "Booked: 4" in text
    assert "Confirmed: 3" in text
    assert "Today: 1" in text
    assert "Tomorrow: 2" in text

    assert "📧 OUTREACH" in text
    assert "Positive Replies: 7" in text
    assert "Demo Requests: 3" in text
    assert "Pricing Requests: 2"

    assert "🎯 TOP OPPORTUNITIES" in text
    assert "Apex Mechanical & Air Solutions" in text
    assert "Vanguard Commercial Roofing" in text

    assert "🏆 BIGGEST WIN" in text
    assert "Apex Mechanical converted from HOT lead → booked demo." in text

    assert "➡️ NEXT BEST MOVES" in text
    assert "Prepare today's Apex demo" in text


def test_zero_technical_diagnostics_in_telegram_brief():
    brief = {
        "date": "2026-08-16",
        "money": {"confirmed_revenue_usd": 0.0, "new_pipeline_usd": 10000.0, "expected_value_usd": 5000.0, "proposals_count": 0, "deals_won_count": 0},
        "progress": {"new_verified": 100, "contacted": 20, "connected": 10, "warmed": 5, "qualified": 3, "meetings_booked": 1, "proposals": 0, "deals_won": 0},
        "meetings": {"booked": 1, "confirmed": 1, "today": 0, "tomorrow": 1},
        "outreach": {"positive_replies": 2, "demo_requests": 1, "pricing_requests": 1, "followups_due": 0},
        "calling": {"connected": 10, "qualified": 3, "meetings_requested": 1},
        "top_opportunities": [{"company": "Acme Industrial", "buyer": "John Doe", "offer": "AI Receptionist", "stage": "HOT", "expected_value_usd": 5000.0, "next_action": "Call"}],
        "biggest_win": "First meeting booked",
        "next_moves": ["Move 1", "Move 2", "Move 3"],
    }
    text = format_telegram_daily_brief(brief)
    # Strict check: zero technical leakages
    forbidden_terms = ["cpu", "ram", "git commit", "git branch", "pytest", "typecheck", "process id", "build status", "daemon", "docker", "port 5173", "stack trace"]
    for term in forbidden_terms:
        assert term not in text.lower(), f"Found forbidden technical term '{term}' in Telegram brief!"


def test_hot_buyer_formatting():
    text = format_hot_buyer_message({
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Founder",
        "pain": "After-hours calls being missed",
        "ai_fit": "24/7 AI Emergency Call Answering & Dispatch",
        "expected_value_usd": 18000.0,
    })
    assert "🔥 HOT BUYER" in text
    assert "Apex Mechanical & Air Solutions" in text
    assert "Marcus Vance · Founder" in text
    assert "$18,000" in text
    assert "📞 Call discovery" in text


def test_lead_warmed_formatting():
    text = format_lead_warmed_message({
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "offer": "24/7 AI Emergency Call Assistant",
        "signal": "Interested in seeing a live demo.",
    })
    assert "🔥 LEAD WARMED" in text
    assert "Apex Mechanical & Air Solutions" in text
    assert "Marcus Vance" in text
    assert "24/7 AI Emergency Call Assistant" in text
    assert "📅 Book meeting" in text


def test_positive_reply_formatting():
    text = format_positive_reply_message({
        "company": "Vanguard Commercial Roofing",
        "buyer": "Derek Holloway",
        "signal": "Interested in the AI follow-up workflow and requested pricing.",
        "next_action": "Send proposal & book 15-min walkthrough",
    })
    assert "🔥 POSITIVE REPLY" in text
    assert "Vanguard Commercial Roofing" in text
    assert "Buyer: Derek Holloway" in text
    assert "📅 Send proposal & book 15-min walkthrough" in text


def test_meeting_booked_formatting():
    text = format_meeting_booked_message({
        "company": "Premier Smile Partners",
        "buyer": "Dr. Sarah Lin",
        "date": "Tomorrow",
        "time": "10:30 AM",
        "ai_fit": "AI Recall + Front Desk Assistant",
        "why_agreed": "Overdue hygiene recalls causing $15k/mo uncollected revenue.",
        "next_action": "Prepare 15-min ROI demo",
        "brief_ready": True,
    })
    assert "📅 MEETING BOOKED" in text
    assert "Premier Smile Partners" in text
    assert "Buyer: Dr. Sarah Lin" in text
    assert "Tomorrow · 10:30 AM" in text
    assert "Why They Agreed:" in text
    assert "Overdue hygiene recalls" in text
    assert "✅ Ready" in text
    assert "Next Action:\nPrepare 15-min ROI demo" in text


def test_deal_won_formatting():
    text = format_deal_won_message({
        "company": "Apex Mechanical",
        "offer": "24/7 AI Emergency Call Agent",
        "value": "$4,000/mo ($48,000 ARR)",
        "revenue_state": "CONFIRMED (Neteller)",
        "next_step": "Onboarding kickoff & client setup",
    })
    assert "💰 DEAL WON" in text
    assert "Apex Mechanical" in text
    assert "$4,000/mo ($48,000 ARR)" in text
    assert "Revenue State:\nCONFIRMED (Neteller)" in text
    assert "Next Step:\nOnboarding kickoff & client setup" in text


def test_proposal_sent_formatting():
    text = format_proposal_message({
        "company": "Vanguard Commercial Roofing",
        "offer": "AI Lead Follow-Up Agent",
        "value": "$3,500/mo ($42,000 ARR)",
    })
    assert "📑 PROPOSAL" in text
    assert "Vanguard Commercial Roofing" in text
    assert "$3,500/mo ($42,000 ARR)" in text
    assert "Awaiting decision" in text


def test_failure_formatting():
    text = format_failure_message({
        "type": "Daily Lead Factory",
        "impact": "100 new leads were NOT delivered to the dialer.",
        "action": "Investigate immediately.",
    })
    assert "🚨 GTM BLOCKER" in text
    assert "Daily Lead Factory" in text
    assert "Investigate immediately." in text