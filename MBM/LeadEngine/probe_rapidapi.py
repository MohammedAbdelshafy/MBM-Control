import http.client
import os

rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()
host = "skip-tracing-working-api.p.rapidapi.com"

endpoints = [
    "/search?phone=2124567890",
    "/reverse-phone?phone=2124567890",
    "/phone?number=2124567890",
    "/search?query=2124567890"
]

for endpoint in endpoints:
    print(f"Trying {endpoint}...")
    conn = http.client.HTTPSConnection(host)
    headers = {
        'x-rapidapi-key': rapidapi_key,
        'x-rapidapi-host': host
    }
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    print(f"Status: {res.status}")
    print(f"Body: {res.read().decode('utf-8')[:200]}")
