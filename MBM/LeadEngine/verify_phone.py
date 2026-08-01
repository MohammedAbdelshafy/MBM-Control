#!/usr/bin/env python3
"""
MBM LeadEngine — Real Phone Verification (Twilio Lookup v2)

Replaces the simulated random line-type "verification" in cold_calling_swarm_os.py
with real Twilio Lookup Line Type Intelligence (mobile / fixedLine / voip / nonFixedVoip).

Usage:
    python verify_phone.py --phone +14696584582
    python verify_phone.py --leads cold_calling_queue.json --dry-run
"""
import os
import json
import argparse
from pathlib import Path

import dotenv
from twilio.rest import Client

ROOT = Path(__file__).resolve().parent.parent.parent
dotenv.load_dotenv(ROOT / ".env")


def get_client():
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not tok:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN missing in AI/.env")
    return Client(sid, tok)


def normalize_phone(raw):
    """Normalize international phone numbers to E.164 (US +1 and UK +44 aware)."""
    if not raw:
        return None
    s = "".join(ch for ch in str(raw) if ch.isdigit() or ch == "+")
    if s.startswith("+"):
        s = "+" + s[1:]
        return s if 11 <= len(s) - 1 <= 15 else None
    if s.startswith("0") and len(s) in (10, 11):
        return "+44" + s[1:]
    if len(s) == 10:
        return "+1" + s
    if len(s) == 11 and s.startswith("1"):
        return "+" + s
    if len(s) >= 11:
        return "+" + s
    return None


def verify_phone(client, phone, fields="line_type_intelligence"):
    """Return {phone, verified, line_type, carrier}. verified=0 means invalid/unverifiable."""
    try:
        res = client.lookups.v2.phone_numbers(phone).fetch(fields=fields)
        lti = getattr(res, "line_type_intelligence", None) or {}
        lti = dict(lti) if not isinstance(lti, dict) else lti
        carrier = lti.get("carrier")
        if isinstance(carrier, dict):
            carrier = carrier.get("name")
        return {
            "phone": phone,
            "verified": 1,
            "line_type": lti.get("type", "unknown"),
            "carrier": carrier,
        }
    except Exception as e:
        if getattr(e, "status", None) == 404:
            return {"phone": phone, "verified": 0, "line_type": "invalid", "carrier": None}
        return {"phone": phone, "verified": 0, "line_type": "error", "carrier": str(e)[:100]}


def verify_leads_file(file_path, client=None, limit=None, simulate=False):
    """Verify every phone in a leads JSON/queue file; returns the annotated leads."""
    client = client or get_client()
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    leads = data if isinstance(data, list) else data.get("queue", data.get("leads", []))
    if limit:
        leads = leads[:limit]

    out = []
    for i, lead in enumerate(leads):
        phone = lead.get("verified_phone") or lead.get("phone") or lead.get("primary_phone")
        e164 = normalize_phone(phone)
        if not e164:
            lead["verification_status"] = "INVALID_NUMBER"
            lead["verified"] = 0
        else:
            lead["phone"] = e164
            if simulate:
                v = {"phone": e164, "verified": 1, "line_type": "mobile", "carrier": "simulated"}
            else:
                v = verify_phone(client, e164)
            lead["verified_phone"] = v["phone"]
            lead["verified"] = v["verified"]
            lead["line_type"] = v["line_type"]
            lead["carrier"] = v["carrier"]
            lead["verification_status"] = "VERIFIED_MOBILE" if v["line_type"] in ("mobile",) else (
                "VERIFIED_LANDLINE" if v["line_type"] in ("fixedLine", "premiumRate", "sharedCost", "tollFree") else (
                    "VERIFIED_VOIP" if v["line_type"] in ("voip", "nonFixedVoip", "personal", "pager") else (
                        "VERIFIED_OTHER" if v["verified"] else "UNVERIFIED")))
        out.append(lead)
        if (i + 1) % 10 == 0:
            print(f"  verified {i + 1}/{len(leads)}")

    if isinstance(data, list):
        result = out
    else:
        data["queue"] = out
        result = data
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone")
    ap.add_argument("--leads")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    if a.phone:
        c = get_client()
        print(json.dumps(verify_phone(c, normalize_phone(a.phone)), indent=2))
    elif a.leads:
        out = verify_leads_file(a.leads, limit=a.limit, simulate=a.dry_run)
        n = sum(1 for x in out if x.get("verified"))
        print(f"Verified {n}/{len(out)} leads in {a.leads}")
        from collections import Counter
        print("Line types:", dict(Counter(x.get("line_type", "?") for x in out)))
    else:
        ap.print_help()
