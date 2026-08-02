"""
whop_lifecycle_engage.py — Lifecycle Engagement & Churn Defense Automation
===========================================================================
Subsystem: MBM Whop Monetization (Automation #2)

Listens to `MBM/Whop/logs/whop_memberships.json` ledger (populated by `whop_monetize.py monitor`).
Processes automated retention & engagement lifecycle flows:
- `new`       -> Welcome Email + Quickstart Guide + Telegram Alert
- `at_risk`   -> Retention & Churn-Defense Email (30% Discount) + Telegram Alert
- `dormant`   -> Re-engagement Campaign + Feature Spotlight
- `churned`   -> Reactivation Offer ($50 Bonus Credit)

Output contract follows AGENTS.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

REPO_ROOT = BASE_DIR.parent.parent

DRY_RUN = False

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LEDGER_FILE = LOGS_DIR / "whop_memberships.json"
ENGAGE_LOG_FILE = LOGS_DIR / "whop_engage_log.json"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SUPABASE_URL = "https://prgmwljhbjtcjmwnjaao.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Load .env / .env.local (matching the pattern used across MBM scripts)
for name in (".env", ".env.local"):
    env_file = REPO_ROOT / name
    if not env_file.exists():
        continue
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key.startswith("SUPABASE_SERVICE_ROLE_KEY"):
            SUPABASE_SERVICE_ROLE_KEY = val
        elif key == "TELEGRAM_BOT_TOKEN" and not TELEGRAM_BOT_TOKEN:
            TELEGRAM_BOT_TOKEN = val
        elif key == "TELEGRAM_CHAT_ID" and not TELEGRAM_CHAT_ID:
            TELEGRAM_CHAT_ID = val


def _send_telegram(text: str) -> bool:
    """Send formatted Telegram alert."""
    global DRY_RUN
    if DRY_RUN:
        print(f"[ENGAGE TELEGRAM DRY-RUN] {text[:120]}")
        return True
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[ENGAGE TELEGRAM WARN] {e}")
        return False


def _queue_email(to_email: str, subject: str, body: str) -> bool:
    """Queue an outreach email into the Supabase email_queue table (drained by
    server/emailSender.js). Falls back to a local JSON queue if no service role key."""
    global DRY_RUN
    if DRY_RUN:
        print(f"[ENGAGE EMAIL DRY-RUN] -> {to_email} ({subject})")
        return True
    if not to_email or to_email == "customer@contecai.com":
        return False

    if SUPABASE_SERVICE_ROLE_KEY:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }
        payload = [{
            "recipient_email": to_email,
            "subject": subject,
            "body": body,
            "status": "qued",
        }]
        try:
            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/email_queue",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    print(f"[ENGAGE EMAIL QUEUED] -> {to_email} ({subject})")
                    return True
                print(f"[ENGAGE EMAIL QUEUE WARN] HTTP {resp.status} for {to_email}")
                return False
        except Exception as e:
            print(f"[ENGAGE EMAIL QUEUE WARN] {e}")
            return False

    # Fallback: local JSON queue (only used if no Supabase service key available)
    queue_file = BASE_DIR.parent / "Logs" / "email_queue.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_data = []
    if queue_file.exists():
        try:
            queue_data = json.loads(queue_file.read_text(encoding="utf-8"))
        except Exception:
            queue_data = []
    msg_id = f"whop_engage_{int(time.time())}_{len(queue_data)+1}"
    queue_data.append({
        "id": msg_id,
        "to": to_email,
        "subject": subject,
        "body": body,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    queue_file.write_text(json.dumps(queue_data, indent=2), encoding="utf-8")
    print(f"[ENGAGE EMAIL QUEUED (local)] -> {to_email} ({subject})")
    return True


def run_lifecycle_engage() -> dict:
    """Read whop_memberships.json ledger and execute lifecycle actions."""
    print("=== EXECUTING WHOP LIFECYCLE ENGAGE & CHURN DEFENSE ===")
    
    if not LEDGER_FILE.exists():
        LEDGER_FILE.write_text(json.dumps({"records": []}, indent=2), encoding="utf-8")

    try:
        ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
        records = ledger.get("records", [])
    except Exception as e:
        return _contract("failure", {"error": f"Failed reading ledger: {e}"})

    already_processed = set()
    if ENGAGE_LOG_FILE.exists():
        try:
            history = json.loads(ENGAGE_LOG_FILE.read_text(encoding="utf-8"))
            already_processed = set(history.get("processed_ids", []))
        except Exception:
            pass

    processed = []
    actions_taken = {"welcome": 0, "retention_discount": 0, "reactivation": 0, "reengage": 0}

    for rec in records:
        mid = rec.get("membership_id") or rec.get("user_id") or f"m_{rec.get('scanned_at')}"
        stage = rec.get("stage", "stable")
        user_email = rec.get("email") or "customer@contecai.com"

        if mid in already_processed:
            continue

        if stage == "new":
            # Welcome Flow
            subject = "🚀 Welcome to Contec AI Agentic Teamz — Your AI Skills Are Ready!"
            body = (
                "Hi there,\n\n"
                "Welcome to Contec AI Agentic Teamz! Your Whop membership is active.\n\n"
                "Here is your Quickstart Guide:\n"
                "1. Access your AI Skills Storefront: https://whop.com/checkout/plan_ContecAI\n"
                "2. Join our VIP Telegram Community\n"
                "3. Contact Support 24/7 on +1 (661) 990-9068\n\n"
                "Let's build your revenue engine!\n"
                "— Contec AI Team"
            )
            _queue_email(user_email, subject, body)
            _send_telegram(f"<b>🎉 New Whop Member Welcomed!</b>\nEmail: {user_email}\nMembership: {mid}")
            actions_taken["welcome"] += 1

        elif stage in ("at_risk", "dormant"):
            # Retention & Churn-Defense Flow
            subject = "🎁 Exclusive 30% Discount + Dedicated AI Agent Setup for You"
            body = (
                "Hi there,\n\n"
                "We noticed you haven't used your AI Skills suite recently.\n"
                "To make sure you get maximum ROI, we're giving you a 30% Lifetime Discount on your next renewal + 1-on-1 AI Setup session!\n\n"
                "Claim your 30% discount here: https://whop.com/checkout/plan_ContecAI\n\n"
                "Best,\n— Contec AI Team"
            )
            _queue_email(user_email, subject, body)
            _send_telegram(f"<b>🛡️ Whop Churn Defense Triggered!</b>\nStage: {stage}\nEmail: {user_email}")
            actions_taken["retention_discount"] += 1

        elif stage == "churned":
            # Reactivation Flow
            subject = "We Miss You! Get $50 Bonus Credit to Reactivate Your Whop Membership"
            body = (
                "Hi there,\n\n"
                "We miss having you in Contec AI Agentic Teamz!\n"
                "Reactivate your account today and receive $50 bonus credit towards any AI Agent skill.\n\n"
                "Reactivate now: https://whop.com/checkout/plan_ContecAI\n\n"
                "— Contec AI Team"
            )
            _queue_email(user_email, subject, body)
            actions_taken["reactivation"] += 1

        already_processed.add(mid)
        processed.append(rec)

    # Save engagement history
    ENGAGE_LOG_FILE.write_text(
        json.dumps({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed_ids": list(already_processed)[-2000:],
            "actions_summary": actions_taken
        }, indent=2),
        encoding="utf-8"
    )

    outputs = {
        "processed_count": len(processed),
        "actions_summary": actions_taken,
        "status": "LIFECYCLE_ENGAGE_COMPLETE"
    }

    print(f"WHOP LIFECYCLE ENGAGE: Processed {len(processed)} memberships -> {json.dumps(actions_taken)}")
    result = _contract("success", outputs)
    print(json.dumps(result))
    return result


def _contract(status: str, outputs: dict, next_action: str = "continue", owner: str = "system") -> dict:
    return {
        "status": status,
        "inputs": {"ledger_file": str(LEDGER_FILE)},
        "outputs": outputs,
        "errors": outputs.get("errors") or [],
        "next_action": next_action,
        "owner": owner,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Whop lifecycle engagement & churn defense")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without queueing emails or sending Telegram")
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    run_lifecycle_engage()
