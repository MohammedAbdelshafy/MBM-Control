#!/usr/bin/env python3
"""
Close-Queue Dialer — Call the Verified Real Leads (Twilio → Your Phone Bridge)
==============================================================================
WHAT IT DOES:
  Reads the NPI-verified call sheet (Track 2 output), ranks leads by priority,
  and places calls through the existing Twilio bridge (rings YOUR mobile first,
  then connects you to the prospect showing your Twilio number as Caller ID).

  Each call logs a REAL disposition (answered / voicemail / no-answer / bad).
  Only calls that make real contact can ever flip the revenue gate.

WHY THIS IS DIFFERENT:
  - Calls REAL businesses (NPI registry) with REAL phone lines.
  - Every lead is dialable — no synthetic numbers burning bridge time.
  - Dispositions are written to logs/close_dispositions.json which the
    revenue gate reads — so "made money" reflects reality.

USAGE (safe by default — dry-run first):
  python MBM/LeadEngine/close_queue_dialer.py --dry-run --limit 5
  python MBM/LeadEngine/close_queue_dialer.py --live --limit 10
  python MBM/LeadEngine/close_queue_dialer.py --list              # show ranked leads
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import csv
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE.parent.parent / "MBM" / "Artifacts"
LOGS = BASE / "logs"
CALLSHEET = ARTIFACTS / "npi_verified_callsheet.csv"
LOGS.mkdir(parents=True, exist_ok=True)

# Default operator mobile (the phone Twilio rings first). Override with --my-phone.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE.parent.parent / ".env")
except ImportError:
    pass
MY_PHONE = os.getenv("USER_MOBILE_PHONE") or os.getenv("OPERATOR_CELL") or ""

# A real, defined offer for a medical practice — priced, scoped, deliverable.
OFFER = {
    "name": "Patient-Growth Retainer",
    "price": 497,
    "what_they_get": (
        "1) Weekly qualified local patient-lead list (real contacts, verified) "
        "2) Done-for-you no-show reminder automation 3) Credentialing checklist "
        "4) One live onboarding call"
    ),
    "close_line": (
        "We only charge after the first onboarding call so you can see the "
        "system work before paying."
    ),
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[CLOSE DIALER] {ts} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def load_leads(path=None):
    p = path or CALLSHEET
    if not p.exists():
        log(f"Call sheet not found: {p}. Run npi_verified_callsheet.py first.")
        return []
    with open(p, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (int(r.get("priority", 9)), r.get("phone", "")))

    # ── Verification gate: only verified owner numbers pass ──
    try:
        from dialer_verification_gate import filter_for_dialer
        rows = filter_for_dialer(rows)
    except ImportError:
        log("WARNING: dialer_verification_gate not found — skipping verification")

    return rows


def display_leads(rows, limit=15):
    print(f"\n=== TOP {min(limit, len(rows))} DIALABLE LEADS ===")
    print(f"{'#':>3} {'prio':>4} {'vertical':<8} {'phone':<16} {'company':<34} {'contact'}")
    for i, r in enumerate(rows[:limit], 1):
        print(f"{i:>3} {r.get('priority',''):>4} {r.get('vertical_tag',''):<8} "
              f"{r.get('phone',''):<16} {(r.get('company_name','') or '')[:34]:<34} "
              f"{r.get('authorized_official_name','')}")


def place_call(row, my_phone, live, simulate_reason=""):
    """Place a call via Twilio bridge (or simulate). Returns (ok, detail)."""
    phone = row.get("phone", "").strip()
    if not phone.startswith("+"):
        log(f"SKIP {phone}: not E.164")
        return False, "bad_format"
    if not my_phone:
        log("No operator phone. Set USER_MOBILE_PHONE / OPERATOR_CELL or pass --my-phone.")
        return False, "no_operator"

    if not live:
        return True, "simulated"

    try:
        sys.path.insert(0, str(BASE))
        from twilio_client import get_client, twilio_from, require_live_calls
        client = get_client()
        twilio_from_num = os.getenv("TWILIO_PHONE_NUMBER", "") or twilio_from()
        if not twilio_from_num:
            log("Missing TWILIO_PHONE_NUMBER env var")
            return False, "no_twilio"
        require_live_calls(client, prospect=phone)
        twiml = (f'<Response><Say>Connecting your call...</Say>'
                 f'<Dial callerId="{twilio_from_num}">{phone}</Dial></Response>')
        call = client.calls.create(
            twiml=twiml, to=my_phone, from_=twilio_from_num)
        return True, call.sid
    except Exception as e:
        log(f"CALL ERROR {phone}: {e}")
        return False, f"error:{str(e)[:120]}"


def record_disposition(row, outcome, detail=""):
    path = LOGS / "close_dispositions.json"
    disp = []
    if path.exists():
        try:
            disp = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            disp = []
    disp.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phone": row.get("phone"),
        "company": row.get("company_name"),
        "vertical": row.get("vertical_tag"),
        "contact": row.get("authorized_official_name"),
        "outcome": outcome,
        "detail": detail,
    })
    path.write_text(json.dumps(disp, indent=2, default=str), encoding="utf-8")


def run(live=False, limit=None, my_phone=None, delay=8, path=None):
    rows = load_leads(path)
    if not rows:
        return
    my_phone = my_phone or MY_PHONE
    display_leads(rows, limit=limit or 15)
    target = rows[:limit] if limit else rows
    print(f"\n=== DIALING {len(target)} LEADS (live={live}) ===")

    for i, r in enumerate(target, 1):
        state = f"[{i}/{len(target)}]"
        print(f"\n{'-'*80}")
        print(f"{state} INITIATING TWILIO BRIDGE TO YOUR PHONE...")
        
        company = r.get('company_name', 'your practice').title()
        contact = r.get('authorized_official_name', 'Doctor').title()
        vertical = r.get('vertical_tag', 'medical practice').upper()
        
        script = f"""
================================================================================
⭐ THE MASTER SCRIPT: {company} ⭐
================================================================================
[PROSPECT DETAILS]
👤 Name: {contact}
🏥 Practice: {company}
📞 Phone: {r.get('phone')}
💉 Niche: {vertical}

[1. THE PATTERN INTERRUPT]
"Hey {contact}, this is Mohammed. I know I'm catching you entirely off guard right now... do you have 30 seconds for me to tell you why I called, and you can hang up if you hate it?"

[2. THE HOOK]
"I run a patient-acquisition engine specifically for {vertical} clinics in your area. I have a list of verified local patients looking for treatment, but my current partner clinic is fully booked. Are you currently taking on new patients at {company}?"

[3. THE QUALIFICATION]
"Perfect. We don't sell marketing. We physically drop pre-qualified, cash-ready patients directly into your schedule, and we handle all the no-show follow-ups."

[4. THE CLOSE (RISK REVERSAL)]
"Our Patient-Growth Retainer is $497, but here's the catch: I don't want you to pay me a single cent until after our first onboarding call, when you physically see the system working. 
If it doesn't make sense, we walk away. Sound fair enough to just take a look?"
================================================================================
"""
        print(script)
        
        if live:
            ok, call_sid = place_call(r, my_phone, live)
            if ok:
                print(f"📞 Twilio is ringing your phone NOW. Answer it to connect to {contact}.")
            else:
                print(f"❌ Twilio Call Failed: {call_sid}")
                
            print("\nSelect Outcome:")
            print("  a = Answered / Pitched")
            print("  v = Voicemail")
            print("  n = No Answer")
            print("  b = Bad Number")
            print("  s = Skip")
            print("  q = Quit Dialer")
            
            choice = input("\nOutcome [a/v/n/b/s/q]: ").strip().lower()
            if choice == 'q':
                print("Exiting dialer...")
                break
                
            outcome_map = {
                'a': 'answered',
                'v': 'voicemail',
                'n': 'no-answer',
                'b': 'bad-number',
                's': 'skipped'
            }
            outcome = outcome_map.get(choice, 'skipped')
            record_disposition(r, outcome, "Live Twilio Dial")
            print(f"Logged disposition: {outcome}")
        else:
            print(f"{state} DRY RUN -> {r['phone']} (queued, not dialed)")

    print(f"\nDone. Dispositions -> {LOGS / 'close_dispositions.json'}")
    print(f"OFFER to pitch: {OFFER['name']} ${OFFER['price']} | {OFFER['what_they_get']}")


def main():
    ap = argparse.ArgumentParser(description="Close-Queue Dialer (verified leads)")
    ap.add_argument("--dry-run", action="store_true", help="queue only (default)")
    ap.add_argument("--live", action="store_true", help="run interactive manual dialer for Phound")
    ap.add_argument("--limit", type=int, default=None, help="max leads to dial")
    ap.add_argument("--list", action="store_true", help="show ranked leads and exit")
    ap.add_argument("--delay", type=int, default=8, help="seconds between live calls")
    ap.add_argument("--sheet", default=None, help="override call sheet path")
    args = ap.parse_args()

    if args.list:
        display_leads(load_leads(args.sheet))
        return
    run(live=args.live, limit=args.limit,
        delay=args.delay, path=args.sheet)


if __name__ == "__main__":
    main()
