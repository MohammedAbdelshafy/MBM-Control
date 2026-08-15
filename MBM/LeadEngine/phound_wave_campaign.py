#!/usr/bin/env python3
"""
phound_wave_campaign.py — Phound Wave SMS Campaign Engine (Enterprise)
=====================================================================
Builds a compliant, personalized SMS blast for Contech AI consultancy
outreach and dispatches it through the **Phound** telephony layer.

WHY PHOUND:
  - Twilio is dead for this workflow (Lookup 401 + no app passwords).
  - Phound Wave is the account's bulk SMS tool: sends from YOUR Phound
    number, replies land back as normal conversations, TCR/opt-out managed.

MODES:
  native_app (default)  Build a ready-to-send campaign manifest (CSV + JSON)
                        + per-lead `https://web.phound.app/?phone=...` prefill
                        links so the operator sends from the Phound app.
  api                   When Phound provisions an official SMS endpoint + token
                        (PHOUND_SMS_ENDPOINT / PHOUND_API_TOKEN), POST each
                        message through the secure provider boundary. Defaults
                        to native_app until a real endpoint is configured.

DATA SOURCE:
  Reads the live dialer leads DB (mbm-dialer/app/public/leads_database.json)
  filtered to VERIFIED rows for the target vertical. No synthetic numbers —
  every row has a real E164 phone from the NPI registry / skip-trace.

COMPLIANCE (TCR):
  - Every message carries opt-out language + STOP keyword note.
  - Opted-out / STOP'd numbers are excluded (leads_database `sms_opted_out`).
  - Runs are written to logs/phound_wave_campaigns.json (Output Contract).

USAGE (safe by default — dry-run first):
  python MBM/LeadEngine/phound_wave_campaign.py --dry-run --limit 5
  python MBM/LeadEngine/phound_wave_campaign.py --apply --vertical "Clinics" --limit 25
  python MBM/LeadEngine/phound_wave_campaign.py --list --vertical "Clinics"
"""

import os
import sys
import json
import csv
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
CAMPAIGN_HISTORY = LOGS / "phound_wave_campaigns.json"
CAMPAIGN_EXPORT_DIR = LOGS / "phound_wave"
CAMPAIGN_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

LEADS_DB = BASE.parent.parent / "mbm-dialer" / "app" / "public" / "leads_database.json"

# Canonical Neteller rail (source of truth).
sys.path.insert(0, str(BASE.parent.parent))
try:
    from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID
except Exception:
    NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
    NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")

    def neteller_link(amount, item, currency="USD", **kw):
        base = "https://member.neteller.com/pay"
        return f"{base}?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}&amount={float(amount):.2f}&currency={currency}&item={item}"

# ─── AI consultancy offer (priced, scoped, deliverable) ────────────────────
OFFERS = {
    "Clinics": {
        "headline": "Patient-Growth AI Retainer",
        "price": 497,
        "neteller_item": "Clinic_AI_Retainer",
        "body": (
            "Hi {first_name}, it's Omar with Contech AI. We build an AI voice "
            "receptionist for medical practices that answers every call 24/7, "
            "fills cancellations, and delivers a weekly list of local patients "
            "actively looking to book. First onboarding call is on us — you see "
            "it work before paying. Reply READY and we'll send the setup link."
        ),
    },
    "Real Estate Sellers": {
        "headline": "Off-Market Wholesale Assignment Rights",
        "price": 5000,
        "neteller_item": "Wholesale_Deal_Rights",
        "body": (
            "Hi {first_name}, Contech Capital here. We have pre-vetted cash buyers "
            "actively acquiring off-market inventory this month. If you're selling "
            "or assigning any distressed/held property, reply YES and we'll send "
            "the terms + payout link. No fees until you approve."
        ),
    },
}

# Per-vertical fallback for everything else.
DEFAULT_OFFER = {
    "headline": "Contech AI Consultation",
    "price": 297,
    "neteller_item": "AI_Consultation",
    "body": (
        "Hi {first_name}, Omar from Contech AI. We automate outreach and operations "
        "for local businesses with AI voice + SMS agents. Happy to run a free "
        "10-min fit call to see if it makes sense — reply INTERESTED and we'll "
        "send a link to book it."
    ),
}

OPT_OUT_TAIL = " (Msg&data rates may apply. Reply STOP to opt out.)"
SMS_LIMIT = 160


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[PHOUND WAVE] {ts} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def load_leads(path=None):
    p = path or LEADS_DB
    if not p.exists():
        log(f"Leads DB not found: {p}")
        return []
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception as e:
        log(f"Failed to read leads DB: {e}")
        return []


def normalize_e164(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if digits.startswith("+"):
        return digits
    digits = digits.replace("+", "")
    if not digits:
        return ""
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    return f"+1{digits.lstrip('1')}" if not digits.startswith("1") else f"+{digits}"


def build_message(offer, lead):
    first = (lead.get("contact") or lead.get("npi_name") or "there").strip()
    if not first:
        first = "there"
    first_name = first.split()[0].title()
    company = lead.get("company") or lead.get("npi_name") or ""
    body = offer["body"].format(first_name=first_name)
    pay = neteller_link(offer["price"], offer["neteller_item"])
    msg = f"{body}\n\n{offer['headline']} — ${offer['price']:.0f}: {pay}{OPT_OUT_TAIL}"
    return msg


def select_leads(leads, vertical, limit, min_status=("VERIFIED", "ENRICHED")):
    picked = []
    for lead in leads:
        v = (lead.get("vertical") or "").strip()
        if vertical and v.lower() != vertical.lower():
            continue
        status = lead.get("skip_trace_status") or "UNVERIFIED"
        if status not in min_status:
            continue
        if str(lead.get("sms_opted_out", "")).strip().lower() in ("1", "true", "yes", "stop"):
            continue
        phone = normalize_e164(lead.get("phone"))
        if not phone:
            continue
        picked.append(lead)
    picked.sort(key=lambda r: int(r.get("motivation_score") or 0), reverse=True)
    return picked[:limit] if limit else picked


def write_export(runs, vertical, total):
    csv_path = CAMPAIGN_EXPORT_DIR / f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Contact_Name", "Company", "Phone", "Message", "Neteller_Paylink", "Phound_Prefill", "Offer", "Price_USD", "Send_Status"])
        for r in runs:
            w.writerow([
                r["contact"], r["company"], r["phone"], r["message"], r["paylink"],
                r["phound_prefill"], r["offer"], r["price"], r["send_status"],
            ])
    json_path = CAMPAIGN_EXPORT_DIR / f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": utcnow(), "vertical": vertical, "rows": total, "runs": runs}, f, indent=2, default=str)
    return csv_path, json_path


def record_history(entry):
    hist = []
    if CAMPAIGN_HISTORY.exists():
        try:
            hist = json.loads(CAMPAIGN_HISTORY.read_text(encoding="utf-8"))
        except Exception:
            hist = []
    hist.append(entry)
    with open(CAMPAIGN_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist[-200:], f, indent=2, default=str)


def dispatch_api(run):
    """POST a single message through the Phound SMS boundary (only when a real
    endpoint is configured). Falls back to native_app otherwise."""
    endpoint = os.getenv("PHOUND_SMS_ENDPOINT", "").strip()
    token = os.getenv("PHOUND_API_TOKEN", "").strip()
    if not endpoint:
        return {"status": "skipped", "reason": "PHOUND_SMS_ENDPOINT not configured; use native_app mode"}
    if not token:
        return {"status": "skipped", "reason": "PHOUND_API_TOKEN not configured"}
    try:
        import urllib.request
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"to": run["phone"], "message": run["message"], "campaign": run["offer"], "lead_id": run["id"]}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"status": "accepted", "http_status": resp.status}
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def main():
    ap = argparse.ArgumentParser(description="Phound Wave SMS campaign engine")
    ap.add_argument("--vertical", default="", help="Filter to one vertical (default: all)")
    ap.add_argument("--limit", type=int, default=0, help="Max leads (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="Build + validate without sending")
    ap.add_argument("--apply", action="store_true", help="Write campaign export + attempt dispatch")
    ap.add_argument("--mode", choices=["native_app", "api"], default="native_app", help="Dispatch mode")
    ap.add_argument("--list", action="store_true", help="Show selected leads only")
    args = ap.parse_args()

    leads = load_leads()
    if not leads:
        log("No leads loaded. Check mbm-dialer/app/public/leads_database.json")
        return

    selected = select_leads(leads, args.vertical, args.limit)
    log(f"Loaded {len(leads)} leads; {len(selected)} eligible (VERIFIED + not opted-out).")

    if args.list:
        for r in selected:
            print(f"  {r.get('id')} | {r.get('contact')} | {r.get('company')} | {normalize_e164(r.get('phone'))} | {r.get('skip_trace_status')}")
        return

    if not args.dry_run and not args.apply:
        log("No action requested. Use --dry-run (preview) or --apply (export + dispatch).")
        return

    runs = []
    for lead in selected:
        vertical = (lead.get("vertical") or "").strip()
        offer = OFFERS.get(vertical) or DEFAULT_OFFER
        message = build_message(offer, lead)
        phone = normalize_e164(lead.get("phone"))
        pay = neteller_link(offer["price"], offer["neteller_item"])
        run = {
            "id": lead.get("id"),
            "contact": lead.get("contact") or lead.get("npi_name") or "",
            "company": lead.get("company") or "",
            "phone": phone,
            "message": message,
            "paylink": pay,
            "offer": offer["headline"],
            "price": offer["price"],
            "segments": max(1, (len(message) + SMS_LIMIT - 1) // SMS_LIMIT),
            "chars": len(message),
            "phound_prefill": f"https://web.phound.app/?phone={phone}",
        }
        if args.apply and args.mode == "api":
            run["send_status"] = dispatch_api(run)
        elif args.apply:
            run["send_status"] = "native_app"
        else:
            run["send_status"] = "preview"
        runs.append(run)

    if args.apply:
        csv_path, json_path = write_export(runs, args.vertical or "all", len(selected))
        entry = {
            "status": "success",
            "inputs": {"vertical": args.vertical or "all", "limit": args.limit, "mode": args.mode, "eligible": len(selected), "sent": len(runs)},
            "outputs": {"csv": str(csv_path), "json": str(json_path), "runs": len(runs), "total_chars": sum(r["chars"] for r in runs)},
            "errors": [r.get("send_status", {}).get("error", "") for r in runs if isinstance(r.get("send_status"), dict) and r["send_status"].get("status") == "error"],
            "next_action": "Review campaign CSV, confirm Phound Wave plan/TCR, send from Phound app (native) or enable API endpoint.",
            "owner": "human",
            "timestamp": utcnow(),
        }
        record_history(entry)
        log(f"Wrote {len(runs)} messages -> {csv_path.name}")
        log(f"History: {CAMPAIGN_HISTORY}")
    else:
        log(f"[DRY-RUN] {len(runs)} messages ready (not sent). Sample:")
        for r in runs[:2]:
            log(f"  → {r['company']} ({r['phone']}): {r['message'][:120]}...")

    # Safety summary
    segs = sum(r["segments"] for r in runs)
    log(f"Total segments to send: {segs}")
    if runs:
        log("REMINDER: Phound Wave requires Pro/Business plan + TCR campaign registration. STOP/opt-outs are excluded.")


if __name__ == "__main__":
    main()