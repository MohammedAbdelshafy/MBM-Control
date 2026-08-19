"""Quick test: verify YouTube OAuth tokens refresh successfully."""
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

tokens = json.loads(open("youtube_tokens.json", encoding="utf-8").read())
for brand in ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez"]:
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
        print(f"{brand}: refresh OK, token expires_in={creds.expiry}")
    except Exception as e:
        print(f"{brand}: refresh FAILED - {e}")
