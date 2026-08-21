import requests
import json
import os

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()

# Test address: 12124 SCHROEDER RD, DALLAS, TX, 75243
url = "https://skip-tracing-working-api.p.rapidapi.com/search"
headers = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "skip-tracing-working-api.p.rapidapi.com"
}
params = {"address": "12124 SCHROEDER RD, DALLAS, TX 75243"}

print("Querying RapidAPI Skip Tracing...")
try:
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    print("Status:", resp.status_code)
    print("Response:", resp.text[:500])
except Exception as e:
    print("Error:", e)
