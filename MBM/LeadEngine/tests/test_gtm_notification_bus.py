"""Hermetic tests for the GTM Notification Bus (routing, state, idempotency, failure isolation)."""

import os
import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_notification_bus import (
    NotificationBus,
    NotificationKind,
    PriorityRouter,
    PriorityLevel,
    DeliveryStatus,
    TelegramDeliveryAdapter,
    InAppDeliveryAdapter,
    EmailDeliveryAdapter,
    GmailDeliveryAdapter,
    WebhookDeliveryAdapter,
    NotificationRecord,
)


class FakeHTTPPost:
    """Injected transport so tests are hermetic (no network)."""

    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"ok": True, "result": {"message_id": 1}}

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.response


@pytest.fixture
def bus_env(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.setenv("GTM_TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("GTM_TELEGRAM_BOT_TOKEN", "123456:ABCdef_xyz")
    monkeypatch.setenv("GTM_TELEGRAM_CHAT_ID", "-1001234567890")
    monkeypatch.setenv("GTM_WEBHOOK_URL", "https://example.com/hook")
    fake = FakeHTTPPost()
    fake_gmail_sends = []
    fake_gmail_sender = lambda to, sub, body: fake_gmail_sends.append((to, sub, body)) or {"sent": True, "to": to, "subject": sub}
    bus = NotificationBus(
        state_path=tmp_path / "delivery_state.json",
        adapters={
            "in_app": InAppDeliveryAdapter(tmp_path / "feed.jsonl"),
            "email": EmailDeliveryAdapter(tmp_path / "outbox"),
            "gmail": GmailDeliveryAdapter(smtp_sender=fake_gmail_sender),
            "telegram": TelegramDeliveryAdapter(http_post=fake),
            "webhook": WebhookDeliveryAdapter(http_post=fake),
        },
    )
    bus._fake = fake
    bus._fake_gmail_sends = fake_gmail_sends
    return bus


def payload():
    return {"text": "hello", "telegram_text": "hello", "data": {}}


# ---------------------------------------------------------------------------
# Priority routing
# ---------------------------------------------------------------------------

def test_priority_routing():
    assert PriorityRouter.route(NotificationKind.CRITICAL_FAILURE) == PriorityLevel.P0
    assert PriorityRouter.route(NotificationKind.DEAL_WON) == PriorityLevel.P0
    assert PriorityRouter.route(NotificationKind.MEETING_WITHIN_1H) == PriorityLevel.P0
    assert PriorityRouter.route(NotificationKind.MEETING_BOOKED) == PriorityLevel.P1
    assert PriorityRouter.route(NotificationKind.POSITIVE_REPLY) == PriorityLevel.P1
    assert PriorityRouter.route(NotificationKind.HOT_BUYER) == PriorityLevel.P1
    assert PriorityRouter.route(NotificationKind.DAILY_BRIEF) == PriorityLevel.P2
    assert PriorityRouter.route(NotificationKind.NEW_LEADS) == PriorityLevel.P2


def test_p0_uses_all_channels(bus_env):
    recs = bus_env.publish(NotificationKind.CRITICAL_FAILURE, "failure_evt1", payload())
    channels = {r.channel for r in recs}
    assert {"telegram", "email", "in_app", "webhook"} <= channels


def test_p1_uses_telegram_inapp_email(bus_env):
    recs = bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_opp1", payload())
    channels = {r.channel for r in recs}
    assert {"telegram", "in_app", "email"} <= channels


def test_p2_digest_is_opt_in_for_telegram(bus_env):
    # P2 digest kinds do not spam telegram unless explicitly enabled.
    recs = bus_env.publish(NotificationKind.DAILY_BRIEF, "daily_brief_2026-01-01", payload())
    channels = {r.channel for r in recs}
    assert "in_app" in channels and "email" in channels
    # telegram record is produced but gated (toggle off) — tracked, never sent.
    tg = next(r for r in recs if r.channel == "telegram")
    assert tg.status == DeliveryStatus.DUPLICATE_SKIPPED.value
    assert bus_env._fake.calls == []


def test_p2_digest_telegram_enabled_when_flag_set(bus_env, monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_DAILY_BRIEF", "true")
    recs = bus_env.publish(NotificationKind.DAILY_BRIEF, "daily_brief_2026-01-02", payload())
    channels = {r.channel for r in recs}
    assert "telegram" in channels


# ---------------------------------------------------------------------------
# Delivery state lifecycle
# ---------------------------------------------------------------------------

def test_delivery_state_transitions(bus_env):
    recs = bus_env.publish(NotificationKind.MEETING_BOOKED, "meeting_booked_m1", payload())
    in_app = next(r for r in recs if r.channel == "in_app")
    assert in_app.status == DeliveryStatus.DELIVERED.value
    assert in_app.attempts == 1
    assert in_app.created_at
    assert in_app.event_id


def test_telegram_delivered_when_message_id(bus_env):
    recs = bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_opp2", payload())
    tg = next(r for r in recs if r.channel == "telegram")
    assert tg.status == DeliveryStatus.DELIVERED.value


def test_telegram_rejected_is_failed_not_delivered(bus_env, monkeypatch):
    bus_env.adapters["telegram"]._http_post = FakeHTTPPost({"ok": False, "description": "chat not found"})
    recs = bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_opp3", payload())
    tg = next(r for r in recs if r.channel == "telegram")
    assert tg.status == DeliveryStatus.FAILED.value
    assert "chat not found" in tg.last_error


# ---------------------------------------------------------------------------
# Idempotency — repeated runs never duplicate
# ---------------------------------------------------------------------------

def test_no_duplicate_notifications_on_repeat(bus_env):
    # P1 kinds deliver on telegram by default; repeated runs must not duplicate.
    key = "hot_buyer_opp-repeat"
    bus_env.publish(NotificationKind.HOT_BUYER, key, payload())
    bus_env.publish(NotificationKind.HOT_BUYER, key, payload())
    sent = len(bus_env._fake.calls)
    assert sent == 1  # telegram called exactly once


def test_partial_failure_retries_only_failed_channel(bus_env):
    bus_env.adapters["telegram"]._http_post = FakeHTTPPost({"ok": False, "description": "boom"})
    key = "hot_buyer_opp4"
    first = bus_env.publish(NotificationKind.HOT_BUYER, key, payload())
    assert next(r for r in first if r.channel == "telegram").status == DeliveryStatus.FAILED.value
    assert next(r for r in first if r.channel == "in_app").status == DeliveryStatus.DELIVERED.value

    # Fix telegram and re-run: telegram retried, in_app NOT duplicated.
    bus_env.adapters["telegram"]._http_post = FakeHTTPPost({"ok": True, "result": {"message_id": 9}})
    second = bus_env.publish(NotificationKind.HOT_BUYER, key, payload())
    tg = next(r for r in second if r.channel == "telegram")
    in_app = next(r for r in second if r.channel == "in_app")
    assert tg.status == DeliveryStatus.DELIVERED.value
    assert tg.attempts == 2  # retried once
    assert in_app.status == DeliveryStatus.DUPLICATE_SKIPPED.value


def test_distinct_delivery_keys_both_deliver(bus_env):
    bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_a", payload())
    bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_b", payload())
    tg = bus_env.adapters["telegram"]
    assert len(tg._http_post.calls) == 2


# ---------------------------------------------------------------------------
# Failure isolation — Telegram failing never breaks GTM
# ---------------------------------------------------------------------------

def test_telegram_failure_isolated(bus_env, monkeypatch):
    def boom(url, body):
        raise RuntimeError("network down")
    bus_env.adapters["telegram"]._http_post = boom
    recs = bus_env.publish(NotificationKind.CRITICAL_FAILURE, "failure_iso1", payload())
    tg = next(r for r in recs if r.channel == "telegram")
    in_app = next(r for r in recs if r.channel == "in_app")
    assert tg.status == DeliveryStatus.FAILED.value
    assert "network down" in tg.last_error
    # Other channels still delivered.
    assert in_app.status == DeliveryStatus.DELIVERED.value


# ---------------------------------------------------------------------------
# Missing configuration
# ---------------------------------------------------------------------------

def test_missing_config_returns_failed_record(bus_env, monkeypatch):
    monkeypatch.delenv("GTM_TELEGRAM_BOT_TOKEN")
    recs = bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_noconfig", payload())
    tg = next(r for r in recs if r.channel == "telegram")
    assert tg.status == DeliveryStatus.FAILED.value
    assert "not configured" in tg.last_error


def test_telegram_kind_toggle_disables_kind(bus_env, monkeypatch):
    monkeypatch.setenv("GTM_TELEGRAM_POSITIVE_REPLIES", "false")
    recs = bus_env.publish(NotificationKind.POSITIVE_REPLY, "positive_reply_msg1", payload())
    tg = next(r for r in recs if r.channel == "telegram")
    assert tg.status == DeliveryStatus.DUPLICATE_SKIPPED.value
    assert "toggle disabled" in tg.last_error


# ---------------------------------------------------------------------------
# Dry run / preview
# ---------------------------------------------------------------------------

def test_dry_run_queues_without_sending(bus_env):
    recs = bus_env.publish(NotificationKind.DAILY_BRIEF, "daily_brief_2026-02-02", payload(), dry_run=True)
    for r in recs:
        if r.channel == "telegram":
            assert r.status == DeliveryStatus.DUPLICATE_SKIPPED.value  # digest gated in dry-run too
        else:
            assert r.status == DeliveryStatus.QUEUED.value
    assert bus_env._fake.calls == []


def test_delivery_key_generators(bus_env):
    assert bus_env.daily_brief_key("2026-08-16") == "daily_brief_2026-08-16"
    assert bus_env.meeting_key("m1") == "meeting_booked_m1"
    assert bus_env.reply_key("r1") == "positive_reply_r1"
    assert bus_env.hot_buyer_key("o1") == "hot_buyer_o1"
    assert bus_env.deal_won_key("d1") == "deal_won_d1"
    assert bus_env.failure_key("e1") == "failure_e1"


def test_delivery_state_persists(bus_env, tmp_path):
    bus_env.publish(NotificationKind.HOT_BUYER, "hot_buyer_persist", payload())
    state_file = tmp_path / "delivery_state.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert any("hot_buyer_persist" in k for k in data)


def test_webhook_delivers_on_2xx(bus_env):
    recs = bus_env.publish(NotificationKind.CRITICAL_FAILURE, "failure_wh1", payload())
    wh = next(r for r in recs if r.channel == "webhook")
    assert wh.status == DeliveryStatus.DELIVERED.value


def test_webhook_not_configured_is_failed(bus_env, monkeypatch):
    monkeypatch.delenv("GTM_WEBHOOK_URL")
    recs = bus_env.publish(NotificationKind.CRITICAL_FAILURE, "failure_wh2", payload())
    wh = next(r for r in recs if r.channel == "webhook")
    assert wh.status == DeliveryStatus.FAILED.value