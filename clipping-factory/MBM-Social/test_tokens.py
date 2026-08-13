from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import json

with open('youtube_tokens.json') as f:
    tokens = json.load(f)

for brand, info in tokens.items():
    if not isinstance(info, dict) or 'client_id' not in info:
        continue
    try:
        creds = Credentials(
            token=info.get('access_token'),
            refresh_token=info.get('refresh_token'),
            token_uri=info.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=info['client_id'],
            client_secret=info['client_secret'],
            scopes=['https://www.googleapis.com/auth/youtube.upload']
        )
        if creds.expired or not creds.token:
            creds.refresh(Request())
            print(f'{brand}: REFRESHED OK')
        else:
            print(f'{brand}: VALID (not expired)')
        
        # Test API call
        youtube = build('youtube', 'v3', credentials=creds)
        resp = youtube.channels().list(part='id,snippet', mine=True).execute()
        items = resp.get('items', [])
        if items:
            print(f'  -> Channel: {items[0]["snippet"]["title"]} ({items[0]["id"]})')
        else:
            print(f'  -> NO CHANNELS FOUND (token may be revoked)')
    except Exception as e:
        print(f'{brand}: ERROR - {e}')