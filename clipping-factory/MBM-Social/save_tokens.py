import json
import requests
from pathlib import Path

TOKENS_FILE = Path(__file__).resolve().parent / "youtube_tokens.json"
client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
client_secret = "GOOGLE_OAUTH_CLIENT_SECRET_REDACTED"
redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

brands = {
    "clippingfactorymbm": {"email": "abdelshafyclapps@gmail.com", "channel_id": "UCSZ80c0lE5gqkkbfHKrGkGA"},
    "cutedosage": {"email": "moeaiagenticteamz@gmail.com", "channel_id": "UCNnWrWmMuZDy4LSg95stEOQ"},
    "dontwatchthis": {"email": "abdelshafyplay@gmail.com", "channel_id": "UCZi1tOA71rDrin5DyNVNKOA"},
    "goalmachinez": {"email": "abdelshafyplays@gmail.com", "channel_id": "UCV3i2caQ-JXey0by8H1_5tg"},
    "twistsrevealed": {"email": "bigmoeshafy@gmail.com", "channel_id": "UCknUgK7LEQOoXk_44juSfzw"},
}

print("=" * 60)
print("PASTE AUTHORIZATION CODES (one per line)")
print("=" * 60)
print("Format: brand=CODE")
print("Example: clippingfactorymbm=4/0A...")
print("Press ENTER on empty line when done")
print()

codes = {}
while True:
    line = input("> ").strip()
    if not line:
        break
    if "=" in line:
        brand, code = line.split("=", 1)
        codes[brand.strip()] = code.strip()
        print(f"  Saved code for {brand.strip()}")

if not codes:
    print("No codes entered. Exiting.")
    exit(0)

print("\nExchanging codes for tokens...")
existing = {}
if TOKENS_FILE.exists():
    existing = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))

for brand, code in codes.items():
    if brand not in brands:
        print(f"  Unknown brand: {brand}")
        continue
    
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    
    if resp.status_code != 200:
        print(f"  {brand}: FAILED - {resp.text[:200]}")
        continue
    
    tokens = resp.json()
    if not tokens.get("refresh_token"):
        print(f"  {brand}: FAILED - no refresh_token in response")
        continue
    
    # Verify the token works
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(token=tokens["access_token"])
        yt = build("youtube", "v3", credentials=creds)
        ch_resp = yt.channels().list(part="id,snippet", mine=True).execute()
        items = ch_resp.get("items", [])
        if items:
            ch_id = items[0]["id"]
            ch_name = items[0]["snippet"]["title"]
            expected = brands[brand]["channel_id"]
            match = "✓" if ch_id == expected else "✗ WRONG CHANNEL"
            print(f"  {brand}: SUCCESS - {ch_name} ({ch_id}) {match}")
        else:
            print(f"  {brand}: SUCCESS - but no channel found")
    except Exception as e:
        print(f"  {brand}: TOKEN SAVED but verify failed: {e}")
    
    existing[brand] = {
        "channel_id": brands[brand]["channel_id"],
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
        "token_uri": "https://oauth2.googleapis.com/token",
        "access_token": tokens["access_token"],
        "google_account_email": brands[brand]["email"],
    }

TOKENS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
print(f"\nSaved {len(codes)} tokens to {TOKENS_FILE}")