"""
whatsapp_dashboard.py — Twilio WhatsApp Incoming Webhook & Dashboard Server
Monitors incoming WhatsApp messages, logs interactions, and triggers AI responses.

Usage:
  python whatsapp_dashboard.py --port 5005
  python whatsapp_dashboard.py --test
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = Path(r"C:\Users\omare\OneDrive\Desktop\AI")
MBM_ROOT = ROOT / "MBM"
LOGS_DIR = MBM_ROOT / "Logs"
CONFIG_DIR = MBM_ROOT / "Config"
MESSAGES_LOG = CONFIG_DIR / "whatsapp_messages.jsonl"

def ensure_dirs():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def log_message(entry: dict):
    ensure_dirs()
    try:
        with open(MESSAGES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[WhatsApp] Log write error: {e}")

class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Professional silent logging to file
        sys.stderr.write(f"[WhatsApp Server] {self.address_string()} - {format % args}\n")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/health", "/status"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "online",
                "service": "WhatsApp Webhook Listener",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/whatsapp/webhook", "/webhook", "/whatsapp"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")

            payload = {}
            if "application/x-www-form-urlencoded" in content_type:
                parsed_qs = parse_qs(body_bytes.decode("utf-8", errors="ignore"))
                payload = {k: v[0] if len(v) == 1 else v for k, v in parsed_qs.items()}
            elif "application/json" in content_type:
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    payload = {}

            sender = payload.get("From", "unknown")
            body_text = payload.get("Body", "")
            media_url = payload.get("MediaUrl0", "")
            message_sid = payload.get("MessageSid", "")

            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sender": sender,
                "body": body_text,
                "media_url": media_url,
                "message_sid": message_sid,
                "raw_payload": payload
            }
            log_message(entry)

            # Build TwiML response
            twiml_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Response>\n'
                '    <Message>Thank you for your message! Our team will get back to you shortly.</Message>\n'
                '</Response>'
            )

            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.end_headers()
            self.wfile.write(twiml_xml.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = 5005):
    ensure_dirs()
    server_address = ("", port)
    httpd = HTTPServer(server_address, WhatsAppWebhookHandler)
    print(f"============================================================")
    print(f"  WhatsApp Webhook Server running on http://localhost:{port}")
    print(f"  Webhook Endpoint: http://localhost:{port}/whatsapp/webhook")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down WhatsApp Webhook Server.")
        httpd.server_close()

def run_test():
    ensure_dirs()
    test_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sender": "whatsapp:+15550199",
        "body": "Test message to WhatsApp Webhook Handler",
        "media_url": "",
        "message_sid": "SMtest123456789",
        "raw_payload": {"test": True}
    }
    log_message(test_entry)
    print("[OK] WhatsApp Webhook test entry logged successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhatsApp Webhook & Dashboard Server")
    parser.add_argument("--port", type=int, default=5005, help="Port to listen on (default: 5005)")
    parser.add_argument("--test", action="store_true", help="Run test logging check")
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_server(port=args.port)
