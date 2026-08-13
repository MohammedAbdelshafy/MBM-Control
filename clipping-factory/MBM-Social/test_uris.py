import urllib.parse

client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"

brands = {
    "clippingfactorymbm": {"email": "abdelshafyclapps@gmail.com"},
    "cutedosage": {"email": "moeaiagenticteamz@gmail.com"},
    "dontwatchthis": {"email": "abdelshafyplay@gmail.com"},
    "goalmachinez": {"email": "abdelshafyplays@gmail.com"},
    "twistsrevealed": {"email": "bigmoeshafy@gmail.com"},
}

# Try different redirect URI options
redirect_options = [
    "http://localhost:8090",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:5000",
    "http://localhost:3000",
]

for redirect_uri in redirect_options:
    print(f"\n--- Testing redirect_uri: {redirect_uri} ---")
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": brands["clippingfactorymbm"]["email"],
    })
    print(auth_url)