"""
Generate Permanent Refresh Token for YouTube Uploads
=====================================================
Obtains a permanent offline refresh_token using Desktop App OAuth credentials
and saves it to youtube_tokens.json and .env.

Run:
  python clipping-factory/generate_permanent_refresh_token.py
"""

import json
import os
import sys
import io
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent
TOKENS_PATH = BASE_DIR / "MBM-Social" / "youtube_tokens.json"

CLIENT_ID = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
CLIENT_SECRET = "GOOGLE_OAUTH_CLIENT_SECRET_REDACTED"


def main():
    print("==========================================================")
    print("  YOUTUBE DATA API PERMANENT REFRESH TOKEN GENERATOR      ")
    print("==========================================================")

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    print("\nStarting local server for OAuth flow on http://localhost:8095/ ...")
    try:
        creds = flow.run_local_server(port=8095, prompt="consent", access_type="offline")
        print("\n[OK] Authorization Successful!")
        print(f"Permanent Refresh Token: {creds.refresh_token}")

        # Save to youtube_tokens.json
        if TOKENS_PATH.exists():
            tokens_data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
            for brand in ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]:
                if brand in tokens_data:
                    tokens_data[brand]["client_id"] = CLIENT_ID
                    tokens_data[brand]["client_secret"] = CLIENT_SECRET
                    tokens_data[brand]["refresh_token"] = creds.refresh_token
                    tokens_data[brand]["access_token"] = creds.token
            TOKENS_PATH.write_text(json.dumps(tokens_data, indent=2), encoding="utf-8")
            print(f"[OK] Saved permanent refresh token to {TOKENS_PATH.name} across all 5 brands")

        # Save to .env files
        for env_path in [ROOT_DIR / ".env", BASE_DIR / "MBM-Social" / ".env"]:
            if env_path.exists():
                text = env_path.read_text(encoding="utf-8", errors="ignore")
                lines = [l for l in text.splitlines() if not l.startswith("YOUTUBE_REFRESH_TOKEN=")]
                lines.append(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                print(f"[OK] Saved YOUTUBE_REFRESH_TOKEN to {env_path.name}")

        print("\n==========================================================")
        print("  YOUTUBE DATA API V3 AUTHORIZATION FULLY COMPLETE!       ")
        print("==========================================================")
    except Exception as e:
        print(f"\n[ERROR] Flow error: {e}")


if __name__ == "__main__":
    main()
