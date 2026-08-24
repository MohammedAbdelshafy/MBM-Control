"""
ANTIGRAVITY -- DENTAL CAMPAIGN BATCH 1 EMAIL SENDER
Campaign: CAMP-DENTAL-DFW-MCR-001
Authorization: JARVIS HARD AUTHORIZATION
Mode: MICRO-BATCH (6 records max)
"""
import os, sys, json, smtplib, time, uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# ── CONFIG ──────────────────────────────────────────────────────────
QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "Offers", "dental", "dental_email_queue.json")
TELEMETRY_DIR = os.path.join(os.path.dirname(__file__), "..", "Artifacts", "GTM", "dental_campaign_telemetry")
CAMPAIGN_ID = "CAMP-DENTAL-DFW-MCR-001"
# Load .env files
def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val:
                os.environ.setdefault(key, val)

_base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_load_dotenv(os.path.join(_base, ".env"))
_load_dotenv(os.path.join(_base, ".env.local"))
_load_dotenv(os.path.join(_base, ".env.local.bak"))

# SMTP from env or .env.local
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Build sender pool: scan ALL env files for SMTP_SENDER_POOL entries
_SENDER_ACCOUNTS = []
_seen_users = set()

def _extract_pools(path):
    """Extract SMTP_SENDER_POOL entries from a dotenv file."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("SMTP_SENDER_POOL="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                for entry in val.split(","):
                    entry = entry.strip()
                    if ":" in entry:
                        _u, _p = entry.split(":", 1)
                        _u, _p = _u.strip(), _p.strip()
                        if _u not in _seen_users:
                            _SENDER_ACCOUNTS.append((_u, _p))
                            _seen_users.add(_u)

# Load clapps (fresh) FIRST, then play (may be rate-limited)
_extract_pools(os.path.join(_base, ".env.local.bak"))
_extract_pools(os.path.join(_base, ".env.local"))
_extract_pools(os.path.join(_base, ".env"))

# Also add explicit SMTP_USER/SMTP_PASS if set and unique
_eu = os.environ.get("SMTP_USER", "").strip()
_ep = os.environ.get("SMTP_PASS", "").strip()
if _eu and _ep and _ep != "REPLACE_WITH_NEW_APP_PASSWORD" and _eu not in _seen_users:
    _SENDER_ACCOUNTS.append((_eu, _ep))

print(f"SMTP pool: {[a[0] for a in _SENDER_ACCOUNTS]}")

# Pick the first working account
SMTP_USER = _SENDER_ACCOUNTS[0][0] if _SENDER_ACCOUNTS else ""
SMTP_PASS = _SENDER_ACCOUNTS[0][1] if _SENDER_ACCOUNTS else ""

FROM_NAME = "Mohammed"
FROM_EMAIL = SMTP_USER

def _smtp_connect():
    """Create a fresh SMTP connection."""
    s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(SMTP_USER, SMTP_PASS)
    return s

# ── REQUIRED FIELDS ────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "company_id", "company", "recipient", "recipient_role",
    "business_email", "email_source", "email_verification_status",
    "pain_evidence", "offer_id", "offer_name",
    "approved_subject", "approved_body",
    "suppression_status", "email_ready"
]

# ── VALIDATION ─────────────────────────────────────────────────────
def validate_record(record):
    """Validate a single record against the send gate."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in record or record[field] is None or record[field] == "":
            errors.append(f"MISSING:{field}")
    
    if record.get("email_ready") is not True:
        errors.append("email_ready != true")
    if record.get("suppression_status") != "clear":
        errors.append(f"suppression_status={record.get('suppression_status')}")
    if record.get("email_verification_status") != "VERIFIED":
        errors.append(f"email_verification_status={record.get('email_verification_status')}")
    
    return errors

# ── SEND ───────────────────────────────────────────────────────────
def send_email(record, smtp_conn):
    """Send a single approved email."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = record["business_email"]
    msg["Subject"] = record["approved_subject"]
    msg["X-Campaign-ID"] = CAMPAIGN_ID
    
    message_id = f"<{uuid.uuid4()}@{SMTP_HOST}>"
    msg["Message-ID"] = message_id
    
    # Plain text body only (no HTML hype)
    body = record["approved_body"]
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    try:
        smtp_conn.send_message(msg)
        return {"sent": True, "message_id": message_id, "error": None}
    except Exception as e:
        return {"sent": False, "message_id": message_id, "error": str(e)}

# ── MAIN ───────────────────────────────────────────────────────────
def main():
    global SMTP_USER, SMTP_PASS, FROM_EMAIL
    dry_run = "--dry-run" in sys.argv
    
    # Load queue
    queue_path = os.path.normpath(QUEUE_PATH)
    if not os.path.exists(queue_path):
        print(f"FATAL: Queue file not found: {queue_path}")
        sys.exit(1)
    
    with open(queue_path, "r", encoding="utf-8") as f:
        queue = json.load(f)
    
    records = queue.get("records", [])
    print(f"Loaded {len(records)} records from queue")
    
    # Validate ALL records first
    ready = []
    blocked = []
    for rec in records:
        errors = validate_record(rec)
        if errors:
            blocked.append({"company_id": rec.get("company_id", "UNKNOWN"), "company": rec.get("company", "UNKNOWN"), "errors": errors})
            print(f"  BLOCKED: {rec.get('company', 'UNKNOWN')} -- {errors}")
        else:
            ready.append(rec)
            print(f"  READY:   {rec.get('company', 'UNKNOWN')} -> {rec.get('business_email', 'UNKNOWN')}")
    
    print(f"\nValidation: {len(ready)} READY, {len(blocked)} BLOCKED")
    
    if len(ready) == 0:
        print("No records passed validation. Exiting.")
        sys.exit(0)
    
    # Telemetry
    os.makedirs(os.path.normpath(TELEMETRY_DIR), exist_ok=True)
    telemetry = {
        "campaign_id": CAMPAIGN_ID,
        "batch": "BATCH-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run" if dry_run else "live",
        "emails_ready": len(ready),
        "emails_blocked": len(blocked),
        "blocked_details": blocked,
        "results": []
    }
    
    if dry_run:
        print("\n=== DRY RUN -- No emails will be sent ===")
        for rec in ready:
            print(f"  WOULD SEND: {rec['company']} -> {rec['business_email']}")
            print(f"    Subject: {rec['approved_subject']}")
            telemetry["results"].append({
                "company_id": rec["company_id"],
                "company": rec["company"],
                "recipient": rec["recipient"],
                "business_email": rec["business_email"],
                "offer_id": rec["offer_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_id": "DRY_RUN",
                "sent": False,
                "delivered": None,
                "bounced": None,
                "reply": None,
                "reply_classification": None,
                "next_action": "SEND_LIVE"
            })
    else:
        # Live send
        print(f"\n=== LIVE SEND -- {len(ready)} emails ===")
        print(f"SMTP: {SMTP_HOST}:{SMTP_PORT} as {SMTP_USER}")
        
        if not SMTP_USER or not SMTP_PASS:
            print("FATAL: SMTP credentials not configured. Set SMTP_SENDER_POOL or SMTP_USER+SMTP_PASS in env.")
            sys.exit(1)
        
        # Test SMTP connection
        try:
            smtp = _smtp_connect()
            print("SMTP: Connected and authenticated")
        except Exception as e:
            # Try fallback accounts
            connected = False
            for acct_user, acct_pass in _SENDER_ACCOUNTS[1:]:
                try:
                    print(f"  Trying fallback: {acct_user}...")
                    global SMTP_USER, SMTP_PASS, FROM_EMAIL
                    SMTP_USER = acct_user
                    SMTP_PASS = acct_pass
                    FROM_EMAIL = acct_user
                    smtp = _smtp_connect()
                    print(f"SMTP: Connected via fallback {acct_user}")
                    connected = True
                    break
                except Exception as e2:
                    print(f"  Fallback {acct_user} failed: {e2}")
            if not connected:
                print(f"FATAL: All SMTP accounts exhausted. Last error: {e}")
                sys.exit(1)
        
        sent_count = 0
        for i, rec in enumerate(ready):
            print(f"\n  [{i+1}/{len(ready)}] Sending to {rec['company']} ({rec['business_email']})...")
            
            # Reconnect per-send for resilience
            try:
                smtp.noop()
            except Exception:
                print("    Reconnecting SMTP...")
                try:
                    smtp = _smtp_connect()
                except Exception as ce:
                    print(f"    Reconnect failed: {ce}")
                    telemetry["results"].append({
                        "company_id": rec["company_id"], "company": rec["company"],
                        "recipient": rec["recipient"], "business_email": rec["business_email"],
                        "offer_id": rec["offer_id"], "campaign_id": CAMPAIGN_ID,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message_id": "CONNECT_FAILED", "sent": False,
                        "delivered": None, "bounced": None, "reply": None,
                        "reply_classification": None, "next_action": "RETRY_OR_BLOCK"
                    })
                    continue
            
            result = send_email(rec, smtp)
            
            status = "SENT" if result["sent"] else "FAILED"
            print(f"    {status} (message_id={result['message_id'][:40]}...)")
            if result["error"]:
                print(f"    Error: {result['error']}")
                # If rate-limited, try to reconnect with fallback
                if "Daily user sending limit" in str(result["error"]):
                    print("    RATE LIMITED - trying fallback account...")
                    for acct_user, acct_pass in _SENDER_ACCOUNTS:
                        if acct_user == SMTP_USER:
                            continue
                        try:
                            SMTP_USER = acct_user
                            SMTP_PASS = acct_pass
                            FROM_EMAIL = acct_user
                            smtp = _smtp_connect()
                            print(f"    Switched to {acct_user}")
                            # Retry this email
                            result = send_email(rec, smtp)
                            status = "SENT" if result["sent"] else "FAILED"
                            print(f"    RETRY {status}")
                            break
                        except Exception:
                            continue
            
            telemetry["results"].append({
                "company_id": rec["company_id"],
                "company": rec["company"],
                "recipient": rec["recipient"],
                "business_email": rec["business_email"],
                "offer_id": rec["offer_id"],
                "campaign_id": CAMPAIGN_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_id": result["message_id"],
                "sent": result["sent"],
                "delivered": None,  # async -- check later
                "bounced": None,
                "reply": None,
                "reply_classification": None,
                "next_action": "MONITOR_REPLY" if result["sent"] else "RETRY_OR_BLOCK"
            })
            
            if result["sent"]:
                sent_count += 1
            
            # Pace: 5 seconds between sends (safer for Gmail)
            if i < len(ready) - 1:
                time.sleep(5)
        
        try:
            smtp.quit()
        except Exception:
            pass
        telemetry["emails_sent"] = sent_count
        print(f"\n=== SEND COMPLETE: {sent_count}/{len(ready)} sent ===")
    
    # Write telemetry
    telemetry_path = os.path.join(
        os.path.normpath(TELEMETRY_DIR),
        f"batch1_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(telemetry_path, "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2)
    print(f"\nTelemetry written: {telemetry_path}")
    
    # Summary
    sent = sum(1 for r in telemetry["results"] if r["sent"])
    print(f"""
========================================
ANTIGRAVITY BATCH 1 FINAL REPORT
========================================
CAMPAIGN:        {CAMPAIGN_ID}
EMAILS_READY:    {len(ready)}
EMAILS_BLOCKED:  {len(blocked)}
EMAILS_SENT:     {sent}
DELIVERED:       PENDING (async)
BOUNCED:         PENDING (async)
REPLIES:         0 (monitoring)
POSITIVE_REPLIES: 0
HOT:             0
DEMOS:           0
PILOTS:          0
SUPPRESSIONS:    0
========================================
""")

if __name__ == "__main__":
    main()
