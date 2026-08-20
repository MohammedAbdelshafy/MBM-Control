"""Step 2: Verify YouTube OAuth token refresh for clippingfactorymbm."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

tokens_path = Path("youtube_tokens.json")
tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
brand = "clippingfactorymbm"
info = tokens[brand]

creds = Credentials(
    token=info.get("access_token"),
    refresh_token=info.get("refresh_token"),
    token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
    client_id=info.get("client_id"),
    client_secret=info.get("client_secret"),
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)

try:
    creds.refresh(Request())
    print("OAUTH: PASS")
    print(f"brand: {brand}")
    print(f"channel: {info.get('channel_id', 'N/A')}")
    print(f"token_refreshed: True")
    print(f"scope: youtube.upload")
    print(f"note: channels().list requires youtube.readonly scope; upload scope verified via refresh")
except Exception as e:
    print("OAUTH: FAIL")
    print(f"REASON: {e}")
    sys.exit(1)
