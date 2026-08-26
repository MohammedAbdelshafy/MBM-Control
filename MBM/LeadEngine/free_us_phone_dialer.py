"""
US Outbound Dial Bridge (Twilio) — HONEST STATUS ONLY
=====================================================
ZERO-SIMULATION LAW:
  This module places REAL calls via the Twilio SDK when credentials exist.
  Without credentials it returns TELEPHONY_BLOCKED. It NEVER fabricates a
  connected/minutes-used outcome, and never invents free-minute balances.

Canonical dispositions belong in MBM/LeadEngine/outreach_event.py — a call
placed here is only an ATTEMPT until a human records what actually happened
on the bridge (see close_queue_dialer.py for the operator flow).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent.resolve()

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()


def telephony_status() -> dict:
    """Report REAL bridge configuration. No invented balances or minutes."""
    configured = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)
    return {
        "status": "READY" if configured else "TELEPHONY_BLOCKED",
        "provider": "twilio",
        "caller_id": TWILIO_PHONE_NUMBER if configured else None,
        "credentials_present": {
            "TWILIO_ACCOUNT_SID": bool(TWILIO_ACCOUNT_SID),
            "TWILIO_AUTH_TOKEN": bool(TWILIO_AUTH_TOKEN),
            "TWILIO_PHONE_NUMBER": bool(TWILIO_PHONE_NUMBER),
        },
        "required_integration": (
            "Set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER "
            "in .env (or use the close_queue_dialer.py operator bridge)."
            if not configured else ""
        ),
    }


def place_outbound_call(to_number: str, prospect_name: str = "Prospect") -> dict:
    """
    Place ONE real outbound call. Returns the provider's actual result.

    Never simulates. Without credentials -> {"status": "TELEPHONY_BLOCKED"}.
    A dispatched call is still only an attempt until a human disposition
    is recorded via outreach_event.record_event(...).
    """
    status = telephony_status()
    if status["status"] != "READY":
        return {
            **status,
            "to": to_number,
            "prospect_name": prospect_name,
            "call_placed": False,
        }

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # Operator-bridge pattern: ring our own console first so a human
        # speaks; TwiML then dials the prospect with our caller ID.
        my_phone = os.getenv("USER_MOBILE_PHONE") or os.getenv("OPERATOR_CELL") or ""
        if not my_phone:
            return {
                **status,
                "status": "TELEPHONY_BLOCKED",
                "required_integration": "Set USER_MOBILE_PHONE / OPERATOR_CELL for the operator bridge.",
                "to": to_number,
                "prospect_name": prospect_name,
                "call_placed": False,
            }
        twiml = (
            f'<Response><Say>Connecting your call...</Say>'
            f'<Dial callerId="{TWILIO_PHONE_NUMBER}">{to_number}</Dial></Response>'
        )
        call = client.calls.create(twiml=twiml, to=my_phone, from_=TWILIO_PHONE_NUMBER)
        return {
            **status,
            "status": "DISPATCHED_TO_OPERATOR_BRIDGE",
            "call_sid": call.sid,
            "to": to_number,
            "prospect_name": prospect_name,
            "call_placed": True,
            "note": "Outcome pending human disposition — not counted as contact.",
        }
    except Exception as e:
        return {
            **status,
            "status": "CALL_ERROR",
            "error": str(e)[:200],
            "to": to_number,
            "prospect_name": prospect_name,
            "call_placed": False,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(telephony_status(), indent=2))
