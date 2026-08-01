"""
YouTube OAuth Setup — generates youtube_tokens.json for the PublishingAgent.

Run this once to configure YouTube publishing:
    cd clipping-factory/backend
    .venv\Scripts\python.exe scripts\youtube_oauth_setup.py

You need:
1. A Google Cloud Console project with YouTube Data API v3 enabled
2. OAuth 2.0 credentials (client_id, client_secret) from the Credentials page
3. A refresh_token (obtained via the OAuth consent flow)

If you already have a refresh_token from a previous setup, you can provide
the client_id and client_secret that generated it and this script will
validate and save them.
"""
import json
import sys
from pathlib import Path

TOKENS_FILE = Path(__file__).parent.parent.parent / "youtube_tokens.json"


def main():
    print("=" * 60)
    print("YouTube OAuth Setup")
    print("=" * 60)
    print()
    print(f"Tokens will be saved to: {TOKENS_FILE}")
    print()

    # Collect credentials
    channel_id = input("Channel ID (or 'default'): ").strip() or "default"
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    refresh_token = input("Refresh Token: ").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("\nERROR: All fields are required.")
        sys.exit(1)

    # Test the credentials by refreshing the token
    print("\nTesting credentials...")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds.refresh(Request())
        print(f"Token refresh OK. Access token: {creds.token[:20]}...")

        # Verify we can access the YouTube API
        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(part="snippet", mine=True).execute()
        if response.get("items"):
            channel = response["items"][0]
            print(f"Channel verified: {channel['snippet']['title']}")
            print(f"Channel ID: {channel['id']}")
            # Use actual channel ID if user provided 'default'
            if channel_id == "default":
                channel_id = channel["id"]
        else:
            print("WARNING: No channel found for this credential. Saving anyway.")

    except Exception as e:
        print(f"\nERROR: Credential test failed: {e}")
        print("Check your client_id, client_secret, and refresh_token.")
        sys.exit(1)

    # Save tokens
    tokens = {
        channel_id: {
            "access_token": creds.token,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    }

    TOKENS_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    print(f"\nTokens saved to {TOKENS_FILE}")
    print("YouTube publishing is now configured.")


if __name__ == "__main__":
    main()
