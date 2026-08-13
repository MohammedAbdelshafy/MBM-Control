import http.client
import os

rapidapi_key = os.getenv("RAPIDAPI_KEY", "572a857767mshe9f183ef86f1060p15ee07jsn900c90701df8")
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
