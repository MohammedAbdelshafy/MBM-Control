#!/usr/bin/env python3
import urllib.request
import json

print("=" * 60)
print("VERIFYING RUNTIME HTTP ENDPOINTS")
print("=" * 60)

# 1. Check Dialer Vite Dev Server on port 5173
try:
    with urllib.request.urlopen("http://localhost:5173") as res:
        print(f"http://localhost:5173/ -> HTTP {res.status} OK")
except Exception as e:
    print(f"http://localhost:5173/ -> Error: {e}")

# 2. Check Backend Agent API on port 3005
try:
    with urllib.request.urlopen("http://localhost:3005/docs") as res:
        print(f"http://localhost:3005/docs -> HTTP {res.status} OK")
except Exception as e:
    print(f"http://localhost:3005/docs -> Error: {e}")

# 3. Check Session Scoreboard API
try:
    with urllib.request.urlopen("http://localhost:3005/api/session-scoreboard") as res:
        data = json.loads(res.read().decode())
        print(f"http://localhost:3005/api/session-scoreboard -> HTTP {res.status} OK: {data}")
except Exception as e:
    print(f"http://localhost:3005/api/session-scoreboard -> Error: {e}")

print("=" * 60)
