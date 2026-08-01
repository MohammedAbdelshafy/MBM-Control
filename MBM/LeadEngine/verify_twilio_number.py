"""
Twilio Caller ID Verification Assistant
=========================================
Mission: Helps you verify your personal phone number or upgrade your Twilio account
to dial any US or international number without restrictions.
"""

import os
import sys
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC03c0fb6f1a1775d7385c364af597c999")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "32b051acb02af4cbaad0fe0c1ca551a8")


def check_account_status():
    print("============================================================")
    print("[TWILIO CHECK] TWILIO ACCOUNT & VERIFIED NUMBERS STATUS CHECK")
    print("============================================================")

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        account = client.api.v2010.accounts(TWILIO_ACCOUNT_SID).fetch()
        
        print(f"Account Name: {account.friendly_name}")
        print(f"Account Status: {account.status}")
        print(f"Account Type: {account.type}")
        
        print("\nCurrently Verified Caller IDs on Your Twilio Account:")
        print("------------------------------------------------------------")
        count = 0
        for num in client.outgoing_caller_ids.list():
            count += 1
            print(f"  {count}. {num.friendly_name} ({num.phone_number})")
        
        if count == 0:
            print("  (No verified caller IDs found yet)")

        print("\n------------------------------------------------------------")
        print("CRITICAL TWILIO RULES:")
        print("1. In Trial Mode: Only YOUR personal phone (+201040404118) needs to be verified.")
        print("2. Prospects do NOT need verification if calling via Web Browser Dialer (http://localhost:5173/voice-agents).")
        print("3. To remove ALL verification limits for all phone numbers worldwide, add $20 to your Twilio balance at:")
        print("   https://console.twilio.com/us1/billing/payment-methods")
        print("============================================================")

    except Exception as e:
        print(f"Error checking Twilio status: {e}")


if __name__ == "__main__":
    check_account_status()
