import requests, os, json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("RETELL_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Step 1: Create a web call (no phone number needed, completely free)
print("[1] Creating web call for Seller Qualifier agent...")
r = requests.post("https://api.retellai.com/v2/create-web-call", headers=headers, json={
    "agent_id": "agent_00bb14caed46feaddd75526ce2"
})
print(f"    Status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    print(f"    Call ID: {data.get('call_id')}")
    print(f"    Agent: Seller Qualifier")
    
    # Save the web call details
    with open("MBM/LeadEngine/logs/web_call.json", "w") as f:
        json.dump(data, f, indent=2)
    
    # Get the web call URL
    web_call_url = data.get("web_call_url") or data.get("call_url") or data.get("url")
    if web_call_url:
        print(f"\n    [!] OPEN THIS URL TO TEST THE CALL:")
        print(f"    {web_call_url}")
    else:
        print(f"\n    Full response: {json.dumps(data, indent=2)}")
else:
    print(f"    Error: {r.text[:300]}")

# Step 2: Also try list existing web calls
print("\n[2] Checking existing calls...")
r = requests.post("https://api.retellai.com/list-calls", headers=headers, json={
    "limit": 5
})
print(f"    Status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    calls = data.get("calls", data) if isinstance(data, dict) else data
    if isinstance(calls, list):
        for c in calls[:3]:
            print(f"    - {c.get('call_id','')} | {c.get('call_type','')} | {c.get('status','')}")
    else:
        print(f"    Response: {str(data)[:200]}")
