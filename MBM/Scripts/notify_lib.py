#!/usr/bin/env python3
"""
notify_lib.py — Telegram + Supabase notification persistence (stdlib only)
==========================================================================
Every alert the control plane fires should survive a fresh CI checkout.
This module sends the Telegram message AND durably inserts a record into the
Supabase `notifications` table (service-role REST insert).

Behaviors:
  - Safe no-op when secrets are unset (local dev / missing env).
  - Exits 1 only when Telegram is configured but the send fails (fail loud).
  - File paths are repo-root relative so workflows can call it directly.

Usage (CLI):
  python MBM/Scripts/notify_lib.py --event "ci:overnight" --message "text..."

Usage (import):
  from notify_lib import send_and_log, log_notification
"""

import json
import os
import sys
import urllib.parse
import urllib.request

TELEGRAM_API = "https://api.telegram.org/bot"


def _env(name):
    return os.environ.get(name, "").strip()


def send_telegram(text, token=None, chat_id=None):
    token = token or _env("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(f"{TELEGRAM_API}{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status < 300
    except Exception as exc:
        print(f"send_telegram error: {exc}")
        return False


def log_notification(event, message, status="sent"):
    """Insert a durable record into Supabase `notifications`. No-op w/o creds."""
    url = _env("VITE_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return False
    payload = json.dumps({
        "event": (event or "notification")[:200],
        "channel": "telegram",
        "message": (message or "")[:4000],
        "status": status,
        "repo": _env("GITHUB_REPOSITORY"),
        "workflow": _env("GITHUB_WORKFLOW"),
        "run_id": _env("GITHUB_RUN_ID"),
    }).encode()
    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/notifications",
            data=payload,
            method="POST",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status < 300
    except Exception as exc:
        print(f"log_notification error: {exc}")
        return False


def send_and_log(event, message):
    ok = send_telegram(message)
    logged = log_notification(event, message, status="sent" if ok else "failed")
    print(f"telegram={'OK' if ok else 'skipped/failed'} supabase={'OK' if logged else 'skipped'}")
    return ok


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send + durably log a notification")
    parser.add_argument("--event", default="ci:notification")
    parser.add_argument("--message", required=True)
    args = parser.parse_args()

    delivered = send_and_log(args.event, args.message)
    # No-op (not configured) = success. Configured but undelivered = failure.
    if not delivered and _env("TELEGRAM_BOT_TOKEN"):
        sys.exit(1)
    sys.exit(0)
