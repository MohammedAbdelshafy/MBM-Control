import urllib.parse
import http.server
import threading
import webbrowser
import requests
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
client_secret = "GOOGLE_OAUTH_CLIENT_SECRET_REDACTED"
redirect_uri = "http://localhost:8090"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"

TOKENS_FILE = Path(__file__).resolve().parent / "youtube_tokens.json"

brands = {
    "clippingfactorymbm": {"email": "abdelshafyclapps@gmail.com", "channel_id": "UCSZ80c0lE5gqkkbfHKrGkGA"},
    "cutedosage": {"email": "moeaiagenticteamz@gmail.com", "channel_id": "UCNnWrWmMuZDy4LSg95stEOQ"},
    "dontwatchthis": {"email": "abdelshafyplay@gmail.com", "channel_id": "UCZi1tOA71rDrin5DyNVNKOA"},
    "goalmachinez": {"email": "abdelshafyplays@gmail.com", "channel_id": "UCV3i2caQ-JXey0by8H1_5tg"},
    "twistsrevealed": {"email": "bigmoeshafy@gmail.com", "channel_id": "UCknUgK7LEQOoXk_44juSfzw"},
}

auth_codes = {}
server_shutdown = None

class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_codes, server_shutdown
        parsed = urlparse(self.path)
        if parsed.path == "/oauth2callback":
            qs = parse_qs(parsed.query)
            if "code" in qs:
                code = qs["code"][0]
                # Determine brand from state parameter
                state = qs.get("state", [""])[0]
                auth_codes[state] = code
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization successful! You can close this window.</h1>")
                # Shutdown server after a delay
                threading.Timer(0.5, lambda: server_shutdown()).start()
                return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress log messages

def run_server():
    global server_shutdown
    server = http.server.HTTPServer(("localhost", 8090), OAuthHandler)
    server_shutdown = server.shutdown
    server.serve_forever()

# Start server in background
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

import time
time.sleep(0.5)  # Let server start

print("=" * 60)
print("OAUTH FLOW - Opening browser for each brand")
print("=" * 60)
print("A browser window will open for each brand.")
print("Sign in with the correct email, grant access.")
print("The code will be captured automatically.")
print()

for brand, info in brands.items():
    print(f"\n--- {brand} ({info['email']}) ---")
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": info["email"],
        "state": brand,
    })
    
    print(f"Opening browser...")
    webbrowser.open(auth_url)
    
    # Wait for code
    deadline = time.time() + 300  # 5 minutes
    while brand not in auth_codes and time.time() < deadline:
        time.sleep(0.5)
    
    if brand in auth_codes:
        print(f"  Got code: {auth_codes[brand][:20]}...")
    else:
        print(f"  TIMEOUT - no code received")

print("\n" + "=" * 60)
print("Exchanging codes for tokens...")
print("=" * 60)

existing = {}
if TOKENS_FILE.exists():
    existing = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))

for brand, code in auth_codes.items():
    info = brands[brand]
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    
    if resp.status_code != 200:
        print(f"  {brand}: FAILED - {resp.text[:200]}")
        continue
    
    tokens = resp.json()
    if not tokens.get("refresh_token"):
        print(f"  {brand}: FAILED - no refresh_token")
        continue
    
    # Verify
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(token=tokens["access_token"])
        yt = build("youtube", "v3", credentials=creds)
        ch_resp = yt.channels().list(part="id,snippet", mine=True).execute()
        items = ch_resp.get("items", [])
        if items:
            ch_id = items[0]["id"]
            ch_name = items[0]["snippet"]["title"]
            expected = info["channel_id"]
            match = "OK" if ch_id == expected else "WRONG CHANNEL"
            print(f"  {brand}: SUCCESS - {ch_name} ({ch_id}) [{match}]")
        else:
            print(f"  {brand}: SUCCESS - no channel found")
    except Exception as e:
        print(f"  {brand}: TOKEN SAVED but verify failed: {e}")
    
    existing[brand] = {
        "channel_id": info["channel_id"],
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
        "token_uri": "https://oauth2.googleapis.com/token",
        "access_token": tokens["access_token"],
        "google_account_email": info["email"],
    }

TOKENS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
print(f"\nSaved {len(auth_codes)} tokens to {TOKENS_FILE}")
print("Done! Run the publisher now.")