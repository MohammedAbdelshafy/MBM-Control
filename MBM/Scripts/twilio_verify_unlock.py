"""Twilio Unlock Verification — Check if free minutes are active.

After running twilio_unlock_guide.py, run this to confirm:
  - Payment method is on file
  - Account is upgraded from trial
  - Free $15.50 credit is available
  - Outbound calling is enabled

Usage:
    python MBM/Scripts/twilio_verify_unlock.py
    python MBM/Scripts/twilio_verify_unlock.py --test-call 4155551234
"""

import os
import sys
import json
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATUS_FILE = os.path.join(ROOT, "MBM", "Artifacts", "twilio_unlock_status.json")
LOGS_DIR = os.path.join(ROOT, "MBM", "LeadEngine", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


def ensure_twilio():
    try:
        from twilio.rest import Client
        return Client
    except ImportError:
        print("Installing twilio SDK...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "twilio", "-q"])
        from twilio.rest import Client
        return Client


def verify():
    Client = ensure_twilio()

    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

    if not sid or not token:
        # Try loading from .env
        env_path = os.path.join(ROOT, "AI.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TWILIO_ACCOUNT_SID="):
                        sid = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("TWILIO_AUTH_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not sid or not token:
        print("❌ TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not found.")
        print("   Set them in AI/.env or as environment variables.")
        return False

    print("=" * 60)
    print("  TWILIO UNLOCK VERIFICATION")
    print("=" * 60)

    client = Client(sid, token)
    results = {}

    # 1. Account Status
    print("\n📌 Account Status:")
    try:
        account = client.api.v2010.accounts(sid).fetch()
        results["account_name"] = account.friendly_name
        results["account_status"] = account.status
        results["account_type"] = account.type
        print(f"  Name:   {account.friendly_name}")
        print(f"  Status: {account.status}")
        print(f"  Type:   {account.type}")

        if account.type == "Full" or account.status == "active":
            print("  ✅ Account is FULL (not trial)")
            results["unlocked"] = True
        elif account.type == "Trial":
            print("  ⚠️  Account is still TRIAL — payment method may not have registered")
            results["unlocked"] = False
        else:
            print(f"  ⚠️  Account type: {account.type}, status: {account.status}")
            results["unlocked"] = False
    except Exception as e:
        print(f"  ❌ Error checking account: {e}")
        results["unlocked"] = False

    # 2. Balance
    print("\n📌 Balance:")
    try:
        balance = client.api.v2010.accounts(sid).balance.fetch()
        amount = balance.balance
        currency = balance.currency
        results["balance"] = f"{amount} {currency}"
        print(f"  Balance: ${amount} {currency}")
        if float(amount) > 0:
            print("  ✅ Credit available — calling should work")
        else:
            print("  ⚠️  Zero balance — add payment method first")
    except Exception as e:
        print(f"  ⚠️  Could not fetch balance: {e}")

    # 3. Verified Caller IDs
    print("\n📌 Verified Caller IDs:")
    try:
        caller_ids = client.outgoing_caller_ids.list()
        results["verified_numbers"] = len(caller_ids)
        for i, cid in enumerate(caller_ids, 1):
            print(f"  {i}. {cid.phone_number} ({cid.friendly_name})")
        if len(caller_ids) == 0:
            print("  (None)")
    except Exception as e:
        print(f"  ⚠️  Could not list caller IDs: {e}")

    # 4. Phone Numbers
    print("\n📌 Purchased Phone Numbers:")
    try:
        numbers = client.incoming_phone_numbers.list()
        results["phone_numbers"] = len(numbers)
        for i, num in enumerate(numbers, 1):
            print(f"  {i}. {num.phone_number} ({num.friendly_name})")
        if len(numbers) == 0:
            print("  (None — using Twilio free number)")
    except Exception as e:
        print(f"  ⚠️  Could not list numbers: {e}")

    # 5. Test Call (optional)
    test_number = None
    if "--test-call" in sys.argv:
        idx = sys.argv.index("--test-call")
        if idx + 1 < len(sys.argv):
            test_number = sys.argv[idx + 1]

    if test_number:
        print(f"\n📌 Test Call to {test_number}:")
        try:
            call = client.calls.create(
                to=test_number,
                from_="+12183930474",  # Our Twilio number
                url="http://demo.twilio.com/docs/voice.xml",
                timeout=15,
            )
            print(f"  ✅ Call initiated: {call.sid}")
            print(f"  Status: {call.status}")
            results["test_call"] = {"sid": call.sid, "status": call.status, "to": test_number}
        except Exception as e:
            print(f"  ❌ Test call failed: {e}")
            results["test_call"] = {"error": str(e)}

    # 6. Save results
    results["timestamp"] = datetime.now().isoformat()
    with open(STATUS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    # Also save to logs
    log_file = os.path.join(LOGS_DIR, f"twilio_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(log_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    if results.get("unlocked"):
        print("  ✅ TWILIO IS UNLOCKED — Ready to make calls!")
        print("  Next: python MBM/LeadEngine/progressive_dialer.py --start --bridge --campaign 50")
    else:
        print("  ⚠️  Twilio may still be in trial mode.")
        print("  Run: python MBM/Scripts/twilio_unlock_guide.py")
    print("=" * 60)

    return results.get("unlocked", False)


if __name__ == "__main__":
    verify()
