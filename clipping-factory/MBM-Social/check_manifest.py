import json
with open('social_media_accounts_manifest.json') as f:
    manifest = json.load(f)
for m in manifest:
    print(f'Brand: {m["brand"]}')
    print(f'  Email: {m["email"]}')
    print(f'  TikTok: {m["tiktok"]}')
    print()