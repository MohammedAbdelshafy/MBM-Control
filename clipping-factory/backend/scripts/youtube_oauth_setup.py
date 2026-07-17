"""
YouTube OAuth2 Setup — one-time auth to get refresh tokens for upload access.

Usage:
  cd clipping-factory/backend
  .venv\Scripts\python.exe scripts\youtube_oauth_setup.py

Steps:
  1. Create a Google Cloud project at https://console.cloud.google.com
  2. Enable YouTube Data API v3
  3. Create OAuth 2.0 Client ID (Desktop App type)
  4. Download client_secrets.json → place in clipping-factory/backend/
  5. Run this script → browser opens → log into each channel → authorize
  6. Tokens saved to youtube_tokens.json

For multiple channels: run once per channel, each gets its own token set.
"""
import json
import sys
from pathlib import Path

SECRETS_PATH = Path(__file__).parent.parent / "client_secrets.json"
TOKENS_PATH = Path(__file__).parent.parent / "youtube_tokens.json"
REDIRECT_URI = "http://localhost:8090"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def load_secrets():
    if not SECRETS_PATH.exists():
        print(f"ERROR: {SECRETS_PATH} not found.")
        print()
        print("Setup steps:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project (or use existing)")
        print("  3. Enable YouTube Data API v3:")
        print("     https://console.cloud.google.com/apis/library/youtube.googleapis.com")
        print("  4. Create OAuth 2.0 credentials:")
        print("     APIs & Services → Credentials → Create Credentials → OAuth client ID")
        print("     Type: Desktop App")
        print("  5. Download the JSON and save as:")
        print(f"     {SECRETS_PATH}")
        print()
        sys.exit(1)

    with open(SECRETS_PATH) as f:
        data = json.load(f)

    # Handle both 'web' and 'installed' client types
    if "installed" in data:
        client = data["installed"]
    elif "web" in data:
        client = data["web"]
    else:
        print("ERROR: Invalid client_secrets.json format")
        sys.exit(1)

    return client["client_id"], client["client_secret"]


def get_auth_url(client_id):
    from urllib.parse import urlencode
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_code(client_id, client_secret, code):
    import urllib.request
    import urllib.parse

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def get_channel_info(access_token):
    import urllib.request

    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp = urllib.request.urlopen(req)
    items = json.loads(resp.read()).get("items", [])
    if items:
        return items[0]["id"], items[0]["snippet"]["title"]
    return None, None


def start_local_server():
    """Start a temporary HTTP server to capture the OAuth redirect."""
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    code_holder = {"code": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "code=" in self.path:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                code_holder["code"] = qs.get("code", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization complete! You can close this tab.</h1>")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", 8090), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server, code_holder


def main():
    client_id, client_secret = load_secrets()
    auth_url = get_auth_url(client_id)

    print("=" * 60)
    print("YouTube OAuth2 Setup")
    print("=" * 60)
    print()
    print("A browser will open for authorization.")
    print("Log into the YouTube channel you want to connect.")
    print()

    # Try to open browser
    import webbrowser
    webbrowser.open(auth_url)
    print(f"If the browser didn't open, visit:\n{auth_url}")
    print()

    # Start local server to capture redirect
    server, code_holder = start_local_server()
    print("Waiting for authorization on http://localhost:8090 ...")

    # Wait for the code
    import time
    while code_holder["code"] is None:
        time.sleep(0.5)

    server.server_close()
    code = code_holder["code"]

    print("Exchanging code for tokens...")
    tokens = exchange_code(client_id, client_secret, code)

    # Get channel info
    channel_id, channel_name = get_channel_info(tokens["access_token"])
    print(f"Connected channel: {channel_name} ({channel_id})")

    # Load existing tokens
    existing = {}
    if TOKENS_PATH.exists():
        existing = json.loads(TOKENS_PATH.read_text())

    # Add / update this channel
    existing[channel_id] = {
        "channel_name": channel_name,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
        "access_token": tokens.get("access_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    TOKENS_PATH.write_text(json.dumps(existing, indent=2))
    print()
    print(f"Tokens saved to: {TOKENS_PATH}")
    print(f"Channels configured: {len(existing)}")
    for cid, info in existing.items():
        print(f"  - {info.get('channel_name', cid)}: {cid}")
    print()
    print("Done! You can now upload videos to this channel.")
    print("To add another channel, run this script again and log into a different channel.")


if __name__ == "__main__":
    main()
