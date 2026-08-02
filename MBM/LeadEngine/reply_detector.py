"""
Reply Detector + Follow-up Engine
=================================
The missing money loop: emails are sent (emailSender.js) but nobody ever reads
the replies. This script scans the Gmail inbox every hour, matches replies back
to the sent emails in `email_queue`, classifies intent, and:

  - Marks the original email_queue row as replied (dedup stored in `error`)
  - Queues a MEETING-REQUEST email for interested replies
  - Queues a FOLLOW-UP email for sent emails with no reply after N days
  - Writes logs/reply_log.json (append) + logs/reply_summary.json (fresh)

Only the existing `email_queue` table is used (no migration needed).
Cross-run dedup lives in the sent row's `error` column:
  {"reply_detected": true, "reply_class": "...", "replied_at": "..."}

Output contract follows AGENTS.md.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

REPLY_LOG = LOGS_DIR / "reply_log.json"
REPLY_SUMMARY = LOGS_DIR / "reply_summary.json"

IMAP_HOST = os.getenv("SMTP_IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("SMTP_IMAP_PORT", "993"))
SCAN_DAYS = int(os.getenv("REPLY_SCAN_DAYS", "7"))
FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "3"))
MAX_SENT = int(os.getenv("MAX_SENT_LOOKUP", "1000"))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent.parent / ".env.local")
except Exception:
    pass

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "https://prgmwljhbjtcjmwnjaao.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
EMAIL_USER = os.getenv("SMTP_USER", "")
EMAIL_PASS = os.getenv("SMTP_PASS", "").strip()

DRY_RUN = "--dry-run" in sys.argv

# ─── Classification keywords ───
INTERESTED = [
    "interested", "yes", "yeah", "sounds good", "looks good", "lets talk",
    "let's talk", "let’s talk", "book", "schedule", "demo", "call me",
    "call you", "price", "pricing", "quote", "how much", "more info",
    "send details", "set up", "meet", "availability", "please call",
    "what do you", "i'd like", "i would like", "want to", "start",
]
NOT_INTERESTED = [
    "not interested", "no thanks", "no thank", "unsubscribe", "remove me",
    "stop email", "don't contact", "dont contact", "opt out", "please remove",
    "this is spam", "do not email", "take me off", "not for us",
]
OOO = [
    "out of office", "on vacation", "annual leave", "away from",
    "auto-reply", "autoreply", "automated reply", "automatic reply",
]


def log(msg):
    line = f"[REPLY DETECTOR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))
    with open(LOGS_DIR / "reply_detector.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ─── Supabase REST helpers ───
def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def sb_get(path, params):
    import requests
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path}: {r.status_code} {r.text[:200]}")
    return r.json()


def sb_patch(path, params, body):
    import requests
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.patch(url, headers=sb_headers(), params=params, json=body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"PATCH {path}: {r.status_code} {r.text[:200]}")
    return r


def sb_post(path, body):
    import requests
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.post(url, headers=sb_headers(), json=body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path}: {r.status_code} {r.text[:200]}")
    return r


# ─── Email parsing helpers ───
def normalize_subject(s):
    if not s:
        return ""
    s = re.sub(r"^(re|fw|fwd|res|aw)\s*:", "", str(s).strip(), flags=re.I)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def decode_header_value(raw):
    from email.header import decode_header, make_header
    try:
        return str(make_header(decode_header(raw or "")))
    except Exception:
        return raw or ""


def parse_address(raw):
    from email.utils import parseaddr
    _, addr = parseaddr(raw or "")
    return (addr or "").strip().lower()


def strip_html(text):
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def message_body(msg, limit=500):
    """Return a plain-text snippet of an email message."""
    if msg.is_multipart():
        parts = [p for p in msg.walk() if p.get_content_type() == "text/plain"]
        if parts:
            return strip_html(parts[0].get_payload(decode=True).decode(
                parts[0].get_content_charset() or "utf-8", errors="ignore"))[:limit]
        html = [p for p in msg.walk() if p.get_content_type() == "text/html"]
        if html:
            return strip_html(html[0].get_payload(decode=True).decode(
                html[0].get_content_charset() or "utf-8", errors="ignore"))[:limit]
        return ""
    try:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def classify(text):
    t = (text or "").lower()
    if any(k in t for k in OOO):
        return "out_of_office"
    if any(k in t for k in NOT_INTERESTED):
        return "not_interested"
    if any(k in t for k in INTERESTED):
        return "interested"
    return "undecided"


def extract_dsn_recipients(body):
    """Extract failed recipient addresses from a delivery-status notification."""
    if not body:
        return []
    found = set()
    for pat in [
        r"rfc822;[\s\S]*?([\w.+-]+@[\w.-]+)",
        r"to:\s*<([\w.+-]+@[\w.-]+)>",
        r"couldn't be delivered[\s\S]*?<([\w.+-]+@[\w.-]+)>",
    ]:
        for m in re.finditer(pat, body, flags=re.I):
            found.add(m.group(1).strip("> ").lower())
    # Final fallback: any bare email after "deliver to"
    for m in re.finditer(r"(?:deliver(?:ed)? to|to the following|recipient)[^\n]*?<([\w.+-]+@[\w.-]+)>", body, flags=re.I):
        found.add(m.group(1).strip().lower())
    return list(found)


# ─── IMAP ───
MAX_SCAN = int(os.getenv("MAX_SCAN", "200"))


def fetch_recent_inbox(days=SCAN_DAYS):
    """Return (headers, get_body, close) — bulk header fetch, lazy body fetch."""
    import imaplib
    import email as emaillib
    from email.utils import parsedate_to_datetime

    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
    M.login(EMAIL_USER, EMAIL_PASS)
    M.select("INBOX")

    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    typ, data = M.search(None, f'(SINCE "{since_date}")')
    nums = data[0].split() if data and data[0] else []
    nums = nums[-MAX_SCAN:]
    log(f"IMAP: {len(nums)} messages in INBOX since {since_date} (scanning last {len(nums)})")

    def close():
        try:
            M.logout()
        except Exception:
            pass

    if not nums:
        close()
        return [], lambda n: "", close

    # 1. Bulk-fetch headers only
    try:
        typ, hdr_data = M.fetch(
            b",".join(nums),
            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
        )
    except Exception as e:
        close()
        raise RuntimeError(f"header fetch failed: {e}")

    headers = []
    for resp in hdr_data or []:
        if not isinstance(resp, tuple):
            continue
        try:
            raw = resp[0].decode().split(" ", 1)[0].strip("()")
            num = raw
            msg = emaillib.message_from_bytes(resp[1])
        except Exception:
            continue
        subject = decode_header_value(msg.get("Subject", ""))
        if not subject or not normalize_subject(subject):
            continue
        try:
            dt = parsedate_to_datetime(msg.get("Date", "")).replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
        headers.append({
            "num": num,
            "from": parse_address(msg.get("From", "")),
            "from_display": decode_header_value(msg.get("From", "")),
            "subject": subject,
            "date": dt.isoformat(),
            "message_id": msg.get("Message-ID", ""),
        })

    # 2. Lazy body fetch on demand
    def get_body(num):
        try:
            typ, bdata = M.fetch(num, "(BODY.PEEK[TEXT])")
            if bdata and bdata[0] and isinstance(bdata[0], tuple):
                return bdata[0][1].decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    return headers, get_body, close


# ─── Main ───
def main():
    started = datetime.now(timezone.utc).isoformat()
    errors = []

    if not SUPABASE_KEY:
        errors.append("SUPABASE_SERVICE_ROLE_KEY not set")
        log("FATAL: no SUPABASE_SERVICE_ROLE_KEY")
        print(json.dumps(_contract("failure", started, {}, errors, "fix_env", owner="human")))
        sys.exit(1)
    if not EMAIL_USER or not EMAIL_PASS:
        errors.append("SMTP_USER/SMTP_PASS not set")
        log("FATAL: no IMAP credentials")
        print(json.dumps(_contract("failure", started, {}, errors, "fix_env", owner="human")))
        sys.exit(1)

    # 1. Load sent emails from Supabase
    try:
        sent = sb_get("email_queue", {
            "select": "id,recipient_email,subject,sent_at,error",
            "status": "eq.sent",
            "order": "created_at.desc",
            "limit": str(MAX_SENT),
        })
    except Exception as e:
        errors.append(f"failed to load sent emails: {e}")
        log(f"ERROR loading sent emails: {e}")
        print(json.dumps(_contract("failure", started, {}, errors, "retry")))
        sys.exit(1)
    log(f"Loaded {len(sent)} sent emails from email_queue")

    sent_by_subject = {}
    for row in sent:
        key = normalize_subject(row.get("subject"))
        sent_by_subject.setdefault(key, []).append(row)
    sent_ids = set()
    for rows in sent_by_subject.values():
        for r in rows:
            sent_ids.add(r["id"])

    # 2. Scan inbox
    try:
        inbox, get_body, close_imap = fetch_recent_inbox()
    except Exception as e:
        errors.append(f"IMAP failed: {e}")
        log(f"ERROR IMAP: {e}")
        print(json.dumps(_contract("failure", started, {}, errors, "check_imap", owner="human")))
        sys.exit(1)

    # 3. Match replies + collect delivery-failure (bounce) notifications
    matched = []
    dsn_events = []
    seen_message_ids = set()
    try:
        for m in inbox:
            subj = (m["subject"] or "").lower()
            if "delivery status notification" in subj and (
                "failure" in subj or "delay" in subj
            ):
                dsn_events.append({"subject": m["subject"], "body": get_body(m["num"])})
                continue
            if m["message_id"] and m["message_id"] in seen_message_ids:
                continue
            seen_message_ids.add(m["message_id"])
            key = normalize_subject(m["subject"])
            candidates = sent_by_subject.get(key, [])
            if not candidates:
                continue
            # Prefer from-address match; fall back to subject-only if unique
            row = next((c for c in candidates if parse_address(c.get("recipient_email")) == m["from"]), None)
            if row is None and len(candidates) == 1:
                row = candidates[0]
            if row is None:
                continue
            m["body"] = get_body(m["num"])
            matched.append({"inbox": m, "row": row})
    finally:
        close_imap()

    log(f"Matched {len(matched)} inbox replies, {len(dsn_events)} bounce notifications")

    # 3b. Mark hard bounces on sent rows so they are never followed up again
    by_email = {}
    for row in sent:
        by_email.setdefault(parse_address(row.get("recipient_email")), row)
    bounces_matched = 0
    for dsn in dsn_events:
        recipients = extract_dsn_recipients(dsn["body"])
        for rec in recipients:
            row = by_email.get(rec)
            if not row:
                continue
            try:
                err = json.loads(row.get("error") or "{}")
            except Exception:
                err = {}
            if err.get("bounce_detected") or err.get("reply_detected"):
                continue
            err.update({"bounce_detected": True, "bounce_kind": "hard", "detected_at": started})
            if not DRY_RUN:
                try:
                    sb_patch("email_queue", {"id": f"eq.{row['id']}"}, {"error": json.dumps(err)})
                    bounces_matched += 1
                except Exception as e:
                    errors.append(f"failed to mark bounce on {row['id']}: {e}")
            else:
                bounces_matched += 1

    # Load existing active queue rows once for in-memory dedup (avoids N REST calls)
    existing_active = []
    try:
        existing_active = sb_get("email_queue", {
            "select": "recipient_email,subject",
            "status": "in.(qued,queo,sent)",
            "limit": "5000",
        })
    except Exception as e:
        errors.append(f"failed to load active queue rows: {e}")
    meeting_sent = {
        (r.get("recipient_email"), "let's find 15 min")
        for r in existing_active
        if "let's find 15 min" in (r.get("subject") or "").lower()
    }
    followup_sent = {
        (r.get("recipient_email"), "following up:")
        for r in existing_active
        if "following up:" in (r.get("subject") or "").lower()
    }

    # 4. Process each matched reply (dedup via error column)
    summary = {
        "timestamp": started,
        "new_replies": 0,
        "already_seen": 0,
        "interested_replies": 0,
        "not_interested": 0,
        "out_of_office": 0,
        "undecided": 0,
        "meetings_requested": 0,
        "followups_queued": 0,
        "bounces_detected": len(dsn_events),
        "bounces_matched": bounces_matched,
        "total_replies": len(matched),
    }
    reply_log = _load_json(REPLY_LOG, [])
    if not isinstance(reply_log, list):
        reply_log = []

    for m in matched:
        row = m["row"]
        # dedup: sent row already marked replied
        try:
            err = json.loads(row.get("error") or "{}")
        except Exception:
            err = {}
        if err.get("reply_detected"):
            summary["already_seen"] += 1
            continue

        cls = classify(m["inbox"]["body"])
        summary["new_replies"] += 1
        summary[{
            "interested": "interested_replies",
            "not_interested": "not_interested",
            "out_of_office": "out_of_office",
        }.get(cls, "undecided")] += 1

        meta = {
            "reply_detected": True,
            "reply_class": cls,
            "replied_at": m["inbox"]["date"],
            "from": m["inbox"]["from"],
            "from_display": m["inbox"]["from_display"],
            "message_id": m["inbox"]["message_id"],
            "snippet": m["inbox"]["body"][:200],
        }
        log(f"Reply from {m['inbox']['from']} on '{row.get('subject','')[:50]}' -> {cls}")

        # Persist dedup marker + reply metadata on the sent row
        if not DRY_RUN:
            try:
                sb_patch("email_queue", {"id": f"eq.{row['id']}"}, {"error": json.dumps(meta)})
            except Exception as e:
                errors.append(f"failed to mark reply on {row['id']}: {e}")
                continue

        reply_log.append({
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "sent_email_id": row["id"],
            "recipient_email": row.get("recipient_email"),
            "original_subject": row.get("subject"),
            **meta,
        })

        # Interested -> queue a meeting-request email
        if cls == "interested":
            queued = _queue_meeting(row, summary, meeting_sent)
            if queued:
                summary["meetings_requested"] += 1

    # 5. Follow-ups for sent-but-unanswered emails
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=FOLLOWUP_DAYS)).isoformat()
    max_age = (now - timedelta(days=int(os.getenv("FOLLOWUP_MAX_AGE_DAYS", "30")))).isoformat()
    followup_budget = int(os.getenv("FOLLOWUP_BATCH", "150"))
    for row in sent:
        if summary["followups_queued"] >= followup_budget:
            break
        sent_at = row.get("sent_at")
        if not sent_at or sent_at < cutoff or sent_at > max_age:
            continue
        try:
            err = json.loads(row.get("error") or "{}")
        except Exception:
            err = {}
        if err.get("reply_detected") or err.get("bounce_detected"):
            continue
        if _queue_followup(row, followup_sent):
            summary["followups_queued"] += 1

    # 6. Write logs
    reply_log = reply_log[-500:]
    if not DRY_RUN:
        _save_json(REPLY_LOG, reply_log)
    _save_json(REPLY_SUMMARY, summary)

    print(f"REPLY SUMMARY: {json.dumps(summary, default=str)}")
    print(json.dumps(_contract(
        "success" if not errors else "failure",
        started,
        summary,
        errors,
        "next_hour_scan",
    )))


def _queue_meeting(row, summary, meeting_sent):
    """Queue a meeting-request email for an interested replier (dedup by subject)."""
    recipient = row.get("recipient_email")
    subject = f"Re: {row.get('subject','')[:60]} — let's find 15 min"
    body = (
        f"Hi,\n\nThanks for getting back to us. Let's find 15 minutes to walk through "
        f"what we can do for you — what time works this week?\n\n"
        f"Pick a slot and we'll confirm right away.\n\nBest,\nContech AI Team"
    )
    if (recipient, "let's find 15 min") in meeting_sent:
        return False
    if DRY_RUN:
        return True
    try:
        sb_post("email_queue", {
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
            "status": "qued",
        })
        meeting_sent.add((recipient, "let's find 15 min"))
        log(f"Queued MEETING request -> {recipient}")
        return True
    except Exception as e:
        log(f"ERROR queuing meeting for {recipient}: {e}")
        return False


def _queue_followup(row, followup_sent):
    """Queue a gentle follow-up for an unanswered sent email (dedup by subject)."""
    recipient = row.get("recipient_email")
    original = row.get("subject", "")
    subject = f"Following up: {original[:70]}"
    body = (
        f"Hi,\n\nJust following up on my last email — wanted to make sure it landed. "
        f"If this isn't a fit right now, no problem at all.\n\n"
        f"Happy to answer any questions.\n\nBest,\nContech AI Team"
    )
    if (recipient, "following up:") in followup_sent:
        return False
    if DRY_RUN:
        return True
    try:
        sb_post("email_queue", {
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
            "status": "qued",
        })
        followup_sent.add((recipient, "following up:"))
        log(f"Queued FOLLOW-UP -> {recipient}")
        return True
    except Exception as e:
        log(f"ERROR queuing follow-up for {recipient}: {e}")
        return False


def _contract(status, timestamp, outputs, errors, next_action, owner="system"):
    return {
        "status": status,
        "inputs": {"scan_days": SCAN_DAYS, "followup_days": FOLLOWUP_DAYS, "dry_run": DRY_RUN},
        "outputs": outputs,
        "errors": errors,
        "next_action": next_action,
        "owner": owner,
        "timestamp": timestamp,
    }


if __name__ == "__main__":
    main()
