import json
with open('youtube_tokens.json') as f:
    tokens = json.load(f)
for brand, info in tokens.items():
    if isinstance(info, dict):
        print(f'{brand}: keys={list(info.keys())}, has_refresh={"refresh_token" in info}')