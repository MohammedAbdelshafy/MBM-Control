#!/usr/bin/env python3
"""Local test harness emulating the Meta WhatsApp Cloud API webhook contract.

Stdlib only — no pip installs required.

Contract implemented (documented Meta behaviour, nothing invented):
  GET  /webhook?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=CHALLENGE
        -> 200 with the challenge string if TOKEN == VERIFY_TOKEN, else 403.
  POST /webhook  with a WhatsApp-style JSON payload
        -> parses sender + message text, runs the front-desk qualification
           state machine (front_desk_logic.py), and:
             * DRY_RUN=1 (default, no keys needed): writes the would-be
               Graph API reply payload to stdout and to `dry_run_outbox.jsonl`.
             * DRY_RUN=0 with real WHATSAPP_TOKEN + PHONE_NUMBER_ID:
               POSTs the reply to https://graph.facebook.com/v21.0/<id>/messages.
               Never run this without real credentials and explicit intent.

Env:
  VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID, PORT, DRY_RUN (default 1)
"""

import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from front_desk_logic import new_session, process_message

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"
PORT = int(os.environ.get("PORT", "8765"))
OUTBOX_FILE = os.environ.get("OUTBOX_FILE", "dry_run_outbox.jsonl")

GRAPH_BASE = "https://graph.facebook.com/v21.0"

# sender -> session state (in-memory; a real deployment persists this)
sessions = {}


def extract_messages(payload: dict):
    """Parse a Meta-style webhook payload into (sender, text, message_id) tuples."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                text = (msg.get("text") or {}).get("body", "")
                out.append((msg.get("from", ""), text, msg.get("id", "")))
    return out


def build_reply_payload(to: str, body: str) -> dict:
    """The Graph API payload used to send a WhatsApp text message."""
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }


def send_or_dry_run(to: str, body: str) -> dict:
    """Send via Graph API if live credentials are configured, else dry-run."""
    payload = build_reply_payload(to, body)
    if DRY_RUN or not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        with open(OUTBOX_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "payload": payload}) + "\n")
        print("DRY-RUN reply ->", json.dumps(payload))
        return {"dry_run": True, "payload": payload}
    url = "%s/%s/messages" % (GRAPH_BASE, PHONE_NUMBER_ID)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + WHATSAPP_TOKEN,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return {"dry_run": False, "status": resp.status, "body": resp.read().decode("utf-8")}


class Handler(BaseHTTPRequestHandler):
    server_version = "WhatsAppHarness/1.0"

    def _send(self, status: int, body: bytes, ctype="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        if parsed.path != "/webhook":
            return self._send(404, b"not found")
        mode = q.get("hub.mode", [""])[0]
        token = q.get("hub.verify_token", [""])[0]
        challenge = q.get("hub.challenge", [""])[0]
        if mode == "subscribe" and token and token == VERIFY_TOKEN:
            return self._send(200, challenge.encode("utf-8"))
        return self._send(403, b"verification failed")

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/webhook":
            return self._send(404, b"not found")
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._send(400, b"bad json")
        results = []
        for sender, text, msg_id in extract_messages(payload):
            state = sessions.get(sender) or new_session(sender)
            state, reply, escalate, stage = process_message(state, text)
            sessions[sender] = state
            sent = send_or_dry_run(sender, reply)
            results.append({
                "sender": sender,
                "message_id": msg_id,
                "stage": stage,
                "escalate": escalate,
                "reply": reply,
                "sent": sent,
            })
        return self._send(200, json.dumps({"ok": True, "results": results}).encode("utf-8"),
                          "application/json")

    def log_message(self, fmt, *args):  # quieter logs
        print("harness:", fmt % args)


def main():
    print("DRY_RUN =", DRY_RUN, "| VERIFY_TOKEN set =", bool(VERIFY_TOKEN))
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print("listening on 127.0.0.1:%d" % PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
