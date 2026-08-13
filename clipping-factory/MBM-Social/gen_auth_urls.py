import urllib.parse

client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"

# Try OOB flow (installed app)
auth_url_oob = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id,
    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
    "response_type": "code",
    "scope": scope,
    "access_type": "offline",
    "prompt": "consent",
})

# Try localhost without port
auth_url_localhost = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id,
    "redirect_uri": "http://localhost",
    "response_type": "code",
    "scope": scope,
    "access_type": "offline",
    "prompt": "consent",
})

# Try localhost:8080
auth_url_8080 = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id,
    "redirect_uri": "http://localhost:8080",
    "response_type": "code",
    "scope": scope,
    "access_type": "offline",
    "prompt": "consent",
})

print("OOB:")
print(auth_url_oob)
print()
print("localhost:")
print(auth_url_localhost)
print()
print("localhost:8080:")
print(auth_url_8080)