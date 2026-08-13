import urllib.parse

client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"
redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

brands = {
    "clippingfactorymbm": "abdelshafyclapps@gmail.com",
    "cutedosage": "moeaiagenticteamz@gmail.com",
    "dontwatchthis": "abdelshafyplay@gmail.com",
    "goalmachinez": "abdelshafyplays@gmail.com",
    "twistsrevealed": "bigmoeshafy@gmail.com"
}

print("=" * 80)
print("YOUTUBE OAUTH AUTHORIZATION LINKS - One per brand")
print("=" * 80)
print()
print("INSTRUCTIONS:")
print("1. Open each link in a NEW INCOGNITO/PRIVATE browser window")
print("2. Sign in with the EXACT email shown")
print("3. Grant permissions")
print("4. Copy the AUTHORIZATION CODE shown on the final page")
print("5. Paste each code below when prompted")
print()

auth_urls = {}
for brand, email in brands.items():
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": email,
    })
    auth_urls[brand] = auth_url
    print(f"--- {brand.upper()} ({email}) ---")
    print(auth_url)
    print()

print("=" * 80)
print("After getting all 5 codes, run this script again with codes to save tokens")
print("=" * 80)