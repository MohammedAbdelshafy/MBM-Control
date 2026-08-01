import requests, os, json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("RETELL_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Step 1: Buy a phone number ($2/mo from free credits)
print("[1] Buying phone number...")
r = requests.post("https://api.retellai.com/create-phone-number", headers=headers, json={
    "area_code": 214,
    "friendly_name": "MBM Lead Caller"
})
print(f"    Status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    phone_number = data.get("phone_number")
    phone_id = data.get("phone_number_id")
    print(f"    Phone: {phone_number}")
    print(f"    ID: {phone_id}")
    
    # Save for later
    with open("MBM/LeadEngine/logs/retell_phone.json", "w") as f:
        json.dump({"phone_number": phone_number, "phone_id": phone_id, "agent_id": "agent_00bb14caed46feaddd75526ce2"}, f, indent=2)
    
    # Step 2: Assign Seller Qualifier agent to this number
    print("\n[2] Assigning Seller Qualifier agent...")
    r = requests.patch(f"https://api.retellai.com/update-phone-number/{phone_number}", headers=headers, json={
        "agent_id": "agent_00bb14caed46feaddd75526ce2"
    })
    print(f"    Status: {r.status_code}")
    if r.status_code in (200, 201):
        print(f"    Agent assigned!")
    else:
        print(f"    Error: {r.text[:200]}")
else:
    print(f"    Error: {r.text[:200]}")

# Step 3: Test outbound call
print("\n[3] Testing outbound call to your Twilio number...")
r = requests.post("https://api.retellai.com/create-phone-call", headers=headers, json={
    "from_number": phone_number,
    "to_number": "+16619909068",  # User's Twilio number
    "override_agent_id": "agent_00bb14caed46feaddd75526ce2"
})
print(f"    Status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    print(f"    Call ID: {data.get('call_id')}")
    print(f"    [!] You should receive a test call on your Twilio number!")
else:
    print(f"    Error: {r.text[:200]}")
