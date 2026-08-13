#!/usr/bin/env python3
"""
Twilio Client Helper — Single Source of Truth for Twilio Auth + Preflight
=========================================================================
WHY THIS FILE EXISTS:
  The dialers were using TWILIO_AUTH_TOKEN which is rejected (HTTP 401) — the
  account's API key (SK...) authenticates fine. This helper:
    1. Builds a Twilio client trying (in order):
       a. API key (TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET)  <- known-good
       b. Account SID + auth token (legacy)
    2. Runs a preflight that tells you EXACTLY why a live call will/won't work
       (account type, verified numbers, trial restrictions).

USAGE:
  from twilio_client import get_client, preflight, twilio_from

  client = get_client()          # raises with clear message if none work
  print(preflight(client))       # dict of what the account can/cannot do
"""

import os
import json
import base64
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass


def _env(name):
    v = os.getenv(name, "").strip()
    return v or None


def account_sid():
    return _env("TWILIO_ACCOUNT_SID")


def api_key_creds():
    return (_env("TWILIO_API_KEY_SID") or _env("TWILIO_API_KEY"),
            _env("TWILIO_API_KEY_SECRET"))


def token_creds():
    return (_env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN"))


def _basic_auth(creds):
    user, pw = creds
    if not user or not pw:
        return None
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def _authed_request(path, creds, timeout=15):
    """Raw REST call with a specific credential pair. Returns (json, err)."""
    auth = _basic_auth(creds)
    if not auth:
        return None, "missing creds"
    url = f"https://api.twilio.com/2010-04-01{path}"
    req = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            return None, body.get("message") or body.get("code") or str(e.code)
        except Exception:
            return None, str(e)
    except Exception as e:
        return None, str(e)


def find_working_creds():
    """Return the first credential pair that authenticates, else raise."""
    # 1) API key (known good on this account)
    data, err = _authed_request("/Accounts.json", api_key_creds())
    if data and not err:
        return api_key_creds(), "api_key"
    # 2) Account token
    data, err = _authed_request(f"/Accounts/{account_sid()}.json", token_creds())
    if data and not err:
        return token_creds(), "account_token"
    raise RuntimeError(
        "No working Twilio credentials. API key and account token both rejected. "
        "Check .env TWILIO_API_KEY_SID / TWILIO_API_KEY_SECRET / TWILIO_AUTH_TOKEN."
    )


def get_client():
    """Return a configured twilio.rest.Client using working creds."""
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        os.system(f"{os.sys.executable} -m pip install twilio -q")
        from twilio.rest import Client as TwilioClient

    creds, kind = find_working_creds()
    user, pw = creds
    return TwilioClient(user, pw)


def twilio_from():
    """The outbound caller-id / owned number."""
    frm = _env("TWILIO_PHONE_NUMBER") or _env("TWILIO_CALLER_ID")
    if not frm:
        raise RuntimeError("TWILIO_PHONE_NUMBER missing in .env")
    return frm


def preflight(client=None):
    """Diagnose what this Twilio account can actually do."""
    sid = account_sid()
    client = client or get_client()
    creds, kind = find_working_creds()
    out = {
        "auth": kind,
        "account_sid": sid,
        "account_type": "unknown",
        "account_status": "unknown",
        "owned_numbers": [],
        "verified_caller_ids": [],
        "live_calls_unlocked": None,
        "reason": "",
    }
    data, err = _authed_request(f"/Accounts/{sid}.json", creds)
    if data:
        out["account_type"] = data.get("type", "unknown")
        out["account_status"] = data.get("status", "unknown")

    nums, _ = _authed_request(
        f"/Accounts/{sid}/IncomingPhoneNumbers.json?PageSize=50", creds)
    if nums:
        out["owned_numbers"] = [
            n.get("phone_number") for n in nums.get("incoming_phone_numbers", [])
        ]

    vids, _ = _authed_request(
        f"/Accounts/{sid}/OutgoingCallerIds.json?PageSize=50", creds)
    if vids:
        out["verified_caller_ids"] = [
            n.get("phone_number") for n in vids.get("outgoing_caller_ids", [])
        ]

    trial = out["account_type"].lower() == "trial"
    if trial:
        out["live_calls_unlocked"] = False
        out["reason"] = (
            "TRIAL account: can only call numbers in verified_caller_ids. "
            "Upgrade billing at console.twilio.com to call any US number."
        )
    else:
        out["live_calls_unlocked"] = True
        out["reason"] = "Full account: live calls to any number allowed."

    return out


def require_live_calls(client=None, prospect=None):
    """Raise a clear error if the account can't place live calls to a prospect."""
    info = preflight(client)
    if not info["live_calls_unlocked"]:
        if prospect:
            vids = info["verified_caller_ids"]
            if prospect in vids:
                return info  # calling a verified number is fine even on trial
        raise RuntimeError(info["reason"])
    return info


if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2))
