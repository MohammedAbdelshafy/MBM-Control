"""
YouTube OAuth Re-Auth via Playwright — Re-authorize all 5 brands with fresh tokens.
Opens a Playwright browser per brand; user logs in; intercepts the redirect to capture the auth code.
No localhost server or registered redirect URI needed.
Usage: python reauth_youtube_all.py
"""
import json
import sys
import re
import urllib.parse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
TOKENS_FILE = ROOT / "youtube_tokens.json"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

BRANDS = {
    "clippingfactorymbm": {
        "display": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "email": "UNKNOWN - NOT YET CONFIRMED",
        "channel_id": "UCSZ80c0lE5gqkkbfHKrGkGA",
    },
    "cutedosage": {
        "display": "Cute Dosage",
        "handle": "@CuteDosage",
        "email": "moeaiagenicteamz@gmail.com",
        "channel_id": "UCNnWrWmMuZDy4LSg95stEOQ",
    },
    "dontwatchthis": {
        "display": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "email": "abdelshafyplay@gmail.com",
        "channel_id": "UCZi1tOA71rDrin5DyNVNKOA",
    },
    "goalmachinez": {
        "display": "Goal Machinez",
        "handle": "@Goalmachinez",
        "email": "abdelshafyplays@gmail.com",
        "channel_id": "UCV3i2caQ-JXey0by8H1_5tg",
    },
    "twistsrevealed": {
        "display": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "email": "abdelshafyclapps@gmail.com",
        "channel_id": "UCknUgK7LEQOoXk_44juSfzw",
    },
}


def get_auth_code_playwright(p, client_id):
    """Open Playwright browser, let user log in, intercept redirect to grab auth code."""
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })

    auth_code = None

    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    def handle_request(request):
        nonlocal auth_code
        url = request.url
        if "code=" in url:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            code = qs.get("code", [None])[0]
            if code:
                auth_code = code

    page.on("request", handle_request)

    page.goto(auth_url, wait_until="commit", timeout=120000)

    print("  Log in with the Google account in the browser window.")
    print("  After granting access, a page will show an authorization code.")
    print("  COPY that code and paste it here when prompted.")

    # Wait for either redirect with code or OOB page with code
    deadline = 300  # 5 minutes
    elapsed = 0
    while auth_code is None and elapsed < deadline:
        page.wait_for_timeout(1000)
        elapsed += 1
        current = page.url
        
        # Check URL for code
        if "code=" in current:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(current).query)
            auth_code = qs.get("code", [None])[0]
            if auth_code:
                break
        
        # Check for OOB success page - it shows the code in the page content
        if "accounts.google.com" in current and ("approval" in current or "oauth2" in current):
            try:
                # Get the full page text
                code_text = page.locator("body").inner_text(timeout=2000)
                import re
                # Look for the authorization code pattern (typically 40+ chars)
                # OOB page usually says "The authorization code is: XXXX" or shows it in a box
                matches = re.findall(r'[A-Za-z0-9_-]{40,}', code_text)
                if matches:
                    auth_code = matches[0]
                    print(f"  Auto-detected code from page: {auth_code[:20]}...")
                    break
                # Also check for "code" in text near the code
                matches2 = re.findall(r'(?:code|authorization)[:\s]+([A-Za-z0-9_-]{20,})', code_text, re.IGNORECASE)
                if matches2:
                    auth_code = matches2[0]
                    print(f"  Auto-detected code from labeled text: {auth_code[:20]}...")
                    break
            except Exception as e:
                pass

    if not auth_code:
        # Prompt user to paste the code manually
        print("\n  ==========================================")
        print("  Could not auto-detect the authorization code.")
        print("  Please COPY the code from the browser page")
        print("  (it looks like: 4/0A... or similar long string)")
        print("  ==========================================")
        auth_code = input("  Paste authorization code here: ").strip()

    browser.close()
    return auth_code


def exchange_code(code, client_id, client_secret):
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=30)
    if resp.status_code != 200:
        print(f"  Exchange failed: {resp.text[:200]}")
        return None
    return resp.json()


def verify_token(access_token):
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        creds = Credentials(token=access_token)
        yt = build("youtube", "v3", credentials=creds)
        resp = yt.channels().list(part="id,snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"], items[0]["snippet"]["title"]
    except Exception:
        pass
    return None, None


def main():
    print("=" * 60)
    print("YOUTUBE RE-AUTH (Playwright) — All 5 Brands")
    print("=" * 60)

    existing = {}
    if TOKENS_FILE.exists():
        existing = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))

    sample = next((v for v in existing.values() if isinstance(v, dict) and "client_id" in v), None)
    if not sample:
        print("ERROR: No existing client_id/secret found in tokens file.")
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()
    else:
        client_id = sample["client_id"]
        client_secret = sample["client_secret"]
        print(f"Using client_id: {client_id[:30]}...")

    print("\nBrand status:")
    for slug, info in BRANDS.items():
        tok = existing.get(slug, {})
        has_token = bool(tok.get("refresh_token"))
        print(f"  {info['display']:25s} {info['email']:35s} [{'HAS TOKEN' if has_token else 'NO TOKEN'}]")

    print("\nFor each brand, log in with the EMAIL listed above in the Playwright browser.\n")

    results = {}
    with sync_playwright() as p:
        for slug, info in BRANDS.items():
            print(f"\n{'='*50}")
            print(f"  {info['display']} ({info['handle']})")
            print(f"  Login: {info['email']}")
            print(f"{'='*50}")

            code = get_auth_code_playwright(p, client_id)
            if not code:
                print(f"  SKIPPED — no auth code captured")
                results[slug] = "skipped"
                continue

            tokens = exchange_code(code, client_id, client_secret)
            if not tokens or not tokens.get("refresh_token"):
                print(f"  FAILED — no refresh_token returned")
                results[slug] = "failed"
                continue

            ch_id, ch_name = verify_token(tokens["access_token"])
            match = ch_id == info["channel_id"]
            print(f"  Channel: {ch_name} ({ch_id})")
            print(f"  Expected: {info['channel_id']}")
            print(f"  Match: {'YES' if match else 'NO — WRONG CHANNEL'}")

            existing[slug] = {
                "channel_id": ch_id or info["channel_id"],
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": tokens["refresh_token"],
                "token_uri": "https://oauth2.googleapis.com/token",
                "access_token": tokens["access_token"],
                "google_account_email": info["email"],
            }
            TOKENS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            print(f"  SAVED!")
            results[slug] = "saved"

    print(f"\n{'='*60}")
    print("RESULTS:")
    for slug, status in results.items():
        print(f"  {slug:25s} {status}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
