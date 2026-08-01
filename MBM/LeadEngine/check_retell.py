import requests, os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("RETELL_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}

# List phone numbers
r = requests.get("https://api.retellai.com/list-phone-numbers", headers=headers)
print("Phone Numbers Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print(f"  Found: {len(data)} numbers")
    for p in data:
        print(f"  {p.get('phone_number')} -> Agent: {p.get('agent_id', 'none')}")
else:
    print(f"  Error: {r.text[:200]}")

# List agents
r = requests.get("https://api.retellai.com/list-agents", headers=headers)
print("\nAgents Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print(f"  Found: {len(data)} agents")
    for a in data:
        print(f"  {a.get('agent_name')} -> {a.get('agent_id')}")
else:
    print(f"  Error: {r.text[:200]}")
