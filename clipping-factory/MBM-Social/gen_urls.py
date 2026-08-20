import urllib.parse
CLIENT_ID = '708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com'
SCOPE = 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube'
REDIRECT = 'http://localhost:8090'
brands = {
    'cutedosage': 'moeaiagenticteamz@gmail.com',
    'dontwatchthis': 'abdelshafyplay@gmail.com',
    'goalmachinez': 'abdelshafyplays@gmail.com',
}
for brand, email in brands.items():
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': CLIENT_ID, 'redirect_uri': REDIRECT, 'response_type': 'code',
        'scope': SCOPE, 'access_type': 'offline', 'prompt': 'consent',
        'login_hint': email, 'state': brand,
    })
    print(f'=== {brand} ({email}) ===')
    print(url)
    print()
