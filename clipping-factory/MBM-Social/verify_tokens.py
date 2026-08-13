import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

tokens = json.load(open('youtube_tokens.json'))
results = {}
for brand, tok in tokens.items():
    if brand == '_comment':
        continue
    try:
        creds = Credentials(
            token=tok.get('access_token'),
            refresh_token=tok['refresh_token'],
            token_uri=tok['token_uri'],
            client_id=tok['client_id'],
            client_secret=tok['client_secret'],
        )
        creds.refresh(Request())
        yt = build('youtube', 'v3', credentials=creds)
        r = yt.channels().list(part='id,snippet', mine=True).execute()
        items = r.get('items', [])
        if items:
            ch = items[0]
            ch_id = ch['id']
            ch_name = ch['snippet']['title']
            expected = tok['channel_id']
            match = ch_id == expected
            status = 'OK' if match else f'WRONG (expected {expected})'
            print(f'{brand:25s} {ch_id:25s} {ch_name:30s} {status}')
            results[brand] = match
        else:
            print(f'{brand:25s} NO CHANNEL FOUND')
            results[brand] = False
    except Exception as e:
        print(f'{brand:25s} ERROR: {e}')
        results[brand] = False

print()
ok = sum(1 for v in results.values() if v)
print(f'Result: {ok}/{len(results)} channels verified')
