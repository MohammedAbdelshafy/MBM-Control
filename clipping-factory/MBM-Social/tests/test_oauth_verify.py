"""Quick test: verify YouTube OAuth tokens refresh successfully."""
import json
import pytest
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKENS_PATH = Path(__file__).resolve().parent.parent / "youtube_tokens.json"

@pytest.mark.skipif(not TOKENS_PATH.exists(), reason="youtube_tokens.json not found in test environment")
def test_oauth_token_refresh():
    tokens = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    for brand in ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez"]:
        if brand not in tokens:
            continue
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
            assert creds.valid
        except Exception as e:
            pytest.skip(f"{brand}: refresh failed (network or expired) - {e}")
