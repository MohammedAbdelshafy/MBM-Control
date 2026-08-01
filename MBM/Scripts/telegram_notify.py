import os, sys, json, urllib.request, urllib.parse, mimetypes, time
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "..", "Config", "telegram_chat_id.txt")

def api_call(method, data=None):
    url = f"{API}/{method}"
    if data:
        data = urllib.parse.urlencode(data).encode()
    try:
        r = urllib.request.urlopen(url, data=data, timeout=10)
        return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_chat_id():
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE) as f:
            cid = f.read().strip()
            if cid: return cid
    updates = api_call("getUpdates", {"timeout": 2, "limit": 1})
    if updates.get("ok") and updates.get("result"):
        cid = str(updates["result"][-1]["message"]["chat"]["id"])
        os.makedirs(os.path.dirname(CHAT_ID_FILE), exist_ok=True)
        with open(CHAT_ID_FILE, "w") as f:
            f.write(cid)
        print(f"Chat ID detected: {cid}")
        return cid
    return None

def send_message(text, cid=None):
    if not cid: cid = get_chat_id()
    if not cid:
        print("No chat ID available. Message the bot @Kyle500_bot on Telegram first.")
        return False
    data = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
    r = api_call("sendMessage", data)
    return r.get("ok", False)

def send_file(filepath, caption="", cid=None):
    if not cid: cid = get_chat_id()
    if not cid: return False
    if not os.path.exists(filepath):
        send_message(f"File not found: {filepath}", cid)
        return False
    try:
        import http.client
        boundary = "----" + str(time.time()).replace(".", "")
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            file_data = f.read()
        body = []
        body.append(f"--{boundary}")
        body.append(f'Content-Disposition: form-data; name="chat_id"')
        body.append("")
        body.append(str(cid))
        body.append(f"--{boundary}")
        body.append(f'Content-Disposition: form-data; name="caption"')
        body.append("")
        body.append(caption)
        body.append(f"--{boundary}")
        body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"')
        body.append("Content-Type: application/octet-stream")
        body.append("")
        body.append("")
        body_bytes = "\r\n".join(body).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        parsed = urllib.parse.urlparse(f"{API}/sendDocument")
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=30)
        conn.request("POST", parsed.path, body=body_bytes, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        resp = conn.getresponse()
        return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        send_message(f"Send file failed: {e}", cid)
        return False

def notify_pipeline_start():
    send_message(f"*MBM Pipeline* \U0001f504 Starting run at {datetime.now().strftime('%H:%M')}")

def notify_pipeline_result(log_path, buyer_count, distressed_count, match_count=0, scored_count=0, buyer_csv="", seller_csv=""):
    lines = [
        f"*MBM Pipeline Complete* \u2705",
        f"Buyer Contacts: {buyer_count}",
        f"Distressed Properties: {distressed_count}",
    ]
    if match_count:
        lines.append(f"Property-Buyer Matches: {match_count}")
    if scored_count:
        lines.append(f"Leads Scored: {scored_count}")
    lines.append(f"Log: `{os.path.basename(log_path)}`")
    send_message("\n".join(lines))
    if buyer_csv and os.path.exists(buyer_csv):
        send_file(buyer_csv, f"Buyer Contacts ({buyer_count})")
    if seller_csv and os.path.exists(seller_csv):
        send_file(seller_csv, f"Distressed Sellers ({distressed_count})")

def notify_error(step, msg):
    send_message(f"\u26a0\ufe0f *MBM Pipeline Error* - {step}\n`{msg[:200]}`")

def daily_digest():
    """Compile all engine runs from the past 24 hours and send a summary."""
    import glob
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "Logs")
    heartbeat_file = os.path.join(os.path.dirname(__file__), "..", "Config", "heartbeat.json")
    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "Artifacts")
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "LeadPacks")

    now = datetime.now()
    cutoff = now.timestamp() - 86400  # 24h ago

    # Count engine runs in last 24h
    engine_logs = sorted(glob.glob(os.path.join(logs_dir, "engine_*.log")))
    recent_runs = []
    for lf in engine_logs:
        if os.path.getmtime(lf) >= cutoff:
            recent_runs.append(lf)

    pipeline_logs = sorted(glob.glob(os.path.join(logs_dir, "pipeline_*.log")))
    recent_pipelines = [lf for lf in pipeline_logs if os.path.getmtime(lf) >= cutoff]

    total_runs = len(recent_runs) + len(recent_pipelines)

    # Check heartbeat
    hb_status = "unknown"
    hb_leads = 0
    hb_error = ""
    if os.path.exists(heartbeat_file):
        try:
            with open(heartbeat_file) as f:
                hb = json.load(f)
            hb_status = hb.get("status", "unknown")
            hb_leads = hb.get("leads_found", 0)
            hb_error = hb.get("error", "")
        except Exception:
            pass

    # Count latest leads
    lead_files = sorted(glob.glob(os.path.join(artifacts_dir, "ALL_LEADS_*.csv")), key=os.path.getmtime, reverse=True)
    latest_lead_count = 0
    if lead_files:
        try:
            import csv as csv_mod
            with open(lead_files[0], 'r', encoding='utf-8') as f:
                latest_lead_count = sum(1 for _ in csv_mod.reader(f)) - 1  # minus header
        except Exception:
            pass

    # Count today's packs
    today_str = now.strftime('%Y-%m-%d')
    pack_dir = os.path.join(packs_dir, f"Pack_{today_str}")
    pack_exists = os.path.isdir(pack_dir)

    # Build digest
    status_icon = "\u2705" if hb_status in ("healthy", "running") else "\u26a0\ufe0f"
    lines = [
        f"*MBM Daily Digest* \U0001f4ca  {now.strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"*Engine Status:* {status_icon} {hb_status}",
        f"*Runs (24h):* {total_runs}",
        f"*Latest Leads in DB:* {latest_lead_count}",
        f"*Heartbeat Leads:* {hb_leads}",
    ]
    if pack_exists:
        lines.append(f"*Today's Pack:* \u2705 Built")
    else:
        lines.append(f"*Today's Pack:* \u274c Not yet")
    if hb_error:
        lines.append(f"*Last Error:* {hb_error[:100]}")
    lines.append(f"")
    lines.append(f"_Engine runs every 4h. Watchdog checks every 30min._")

    send_message("\n".join(lines))

    # Send the latest lead file if recent
    if lead_files and os.path.getmtime(lead_files[0]) >= cutoff:
        send_file(lead_files[0], f"Latest leads ({latest_lead_count})")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "test":
        send_message("MBM Pipeline notification system is online! \u2705")
    elif cmd == "start":
        notify_pipeline_start()
    elif cmd == "notify_result":
        log_path = sys.argv[2] if len(sys.argv) > 2 else ""
        buyer_count = sys.argv[3] if len(sys.argv) > 3 else "?"
        distressed_count = sys.argv[4] if len(sys.argv) > 4 else "?"
        match_count = sys.argv[5] if len(sys.argv) > 5 else 0
        scored_count = sys.argv[6] if len(sys.argv) > 6 else 0
        buyer_csv = sys.argv[7] if len(sys.argv) > 7 else ""
        seller_csv = sys.argv[8] if len(sys.argv) > 8 else ""
        notify_pipeline_result(log_path, buyer_count, distressed_count, match_count, scored_count, buyer_csv, seller_csv)
    elif cmd == "notify_error":
        step = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
        msg = sys.argv[3] if len(sys.argv) > 3 else ""
        notify_error(step, msg)
    elif cmd == "file":
        f = sys.argv[2] if len(sys.argv) > 2 else ""
        send_file(f, sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "daily_digest":
        daily_digest()
    else:
        print("Usage: telegram_notify.py [test|start|notify_result|notify_error|file|daily_digest]")
