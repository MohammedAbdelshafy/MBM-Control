#!/usr/bin/env python3
"""
MBM LeadEngine — Power Dialer (merged from standalone real-estate-dialer)

Rings your phone and the lead simultaneously. Human answers -> you are connected
in a conference. Voicemail / no-answer / busy -> auto-advances to the next lead.

No webhooks required: call status is tracked by polling the Twilio API, so this
runs entirely on your local machine (no ngrok, no public URL).

Usage:
    python power_dialer.py --help
    python power_dialer.py --leads cold_calling_queue.json --simulate --limit 2
    python power_dialer.py --leads cold_calling_queue.json --verify --limit 5
    python power_dialer.py --leads cold_calling_queue.json --start 3 --from-queue-id 90874020
    python power_dialer.py --phone +1... --name "PipHouse LLC" --my-phone +201103030360
"""
import os
import sys
import json
import time
import argparse
import datetime
import subprocess
from pathlib import Path

import dotenv
from twilio.rest import Client

ROOT = Path(__file__).resolve().parent.parent.parent
dotenv.load_dotenv(ROOT / ".env")

from verify_phone import normalize_phone, verify_phone  # noqa: E402

RING_TIME = int(os.getenv("RING_TIME", "30"))
AMD_TIMEOUT = int(os.getenv("AMD_TIMEOUT", "15"))
GAP_SECONDS = int(os.getenv("GAP_BETWEEN_CALLS", "3"))
POLL_SECONDS = 3


def get_client():
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not tok:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN missing in AI/.env")
    return Client(sid, tok)


def twilio_from():
    frm = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    if not frm:
        raise RuntimeError("TWILIO_PHONE_NUMBER missing in AI/.env")
    return frm


def agent_phone():
    phone = os.getenv("USER_MOBILE_PHONE", "").strip() or os.getenv("AGENT_NUMBER", "").strip()
    if not phone:
        raise RuntimeError("USER_MOBILE_PHONE missing in AI/.env")
    return normalize_phone(phone)


def conference_twiml(room, caller_id=None):
    dial = f'<Dial timeout="{RING_TIME}"'
    if caller_id:
        dial += f' callerId="{caller_id}"'
    dial += ">"
    return (f"<Response>{dial}"
            f'<Conference startConferenceOnEnter="true" endConferenceOnExit="true" beep="false" waitUrl="">{room}</Conference>'
            f"</Dial></Response>")


def load_leads(file_path=None, phone=None, name=None):
    """Load leads from a queue file, or build a single-lead list."""
    if phone:
        return [{"contact_name": name or phone, "phone": phone, "status": "manual"}]
    if not file_path:
        file_path = ROOT / "MBM" / "LeadEngine" / "cold_calling_queue.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    leads = data if isinstance(data, list) else data.get("queue", data.get("leads", []))
    if isinstance(data, dict) and "queue" in data and not isinstance(data.get("queue"), list):
        # allow {queue: {id: lead}} shape
        leads = list(data["queue"].values())
    return list(leads)


def save_queue(file_path, leads):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            data = leads
        else:
            data["queue"] = leads
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=2, default=str)


def place_calls(client, lead_phone, room):
    frm = twilio_from()
    lead_twiml = conference_twiml(room, caller_id=frm)
    agent_twiml = conference_twiml(room)
    lead_call = client.calls.create(
        to=lead_phone,
        from_=frm,
        twiml=lead_twiml,
        machine_detection="Enable",
        machine_detection_timeout=AMD_TIMEOUT,
    )
    agent_call = client.calls.create(to=agent_phone(), from_=frm, twiml=agent_twiml)
    return lead_call, agent_call


def classify(lead_call):
    """Classify a terminal lead call that never reached a live conversation."""
    status = lead_call.status
    answered_by = getattr(lead_call, "answered_by", None)
    if answered_by and str(answered_by).lower().startswith("machine"):
        return "voicemail"
    if status == "no-answer":
        return "no_answer"
    if status == "busy":
        return "busy"
    if status == "failed":
        return "failed"
    return "no_answer" if status == "completed" else status


def dial_lead(client, lead, index, session_logs):
    """Dial one lead, wait for the outcome, return disposition."""
    raw_phone = lead.get("verified_phone") or lead.get("phone")
    e164 = normalize_phone(raw_phone)
    if not e164:
        lead["disposition"] = "invalid_number"
        lead["status"] = "failed"
        print(f"[{index}] SKIP {lead.get('contact_name') or lead.get('name') or '?'} — invalid number {raw_phone}")
        return "invalid_number"

    name = lead.get("contact_name") or lead.get("name") or lead.get("prospect_name") or "Lead"
    print(f"\n[{index}] Dialing {name} ({e164}) ...")
    room = f"mbm_{int(time.time())}_{index}"

    try:
        lead_call, agent_call = place_calls(client, e164, room)
    except Exception as e:
        msg = str(e)
        print(f"[{index}] ERROR placing call: {msg}")
        if "Trial" in msg or "unverified" in msg.lower():
            print("\n  BLOCKED BY TRIAL ACCOUNT. To dial real numbers you must UPGRADE your Twilio account:")
            print("    1. Go to https://console.twilio.com")
            print("    2. Add a payment method (billing) — converts Trial -> full, unlocks calling any number")
            print("    3. Run the dialer again.")
        lead["disposition"] = "failed"
        lead["status"] = "failed"
        return "failed"

    print(f"  call_sid={lead_call.sid}  agent_sid={agent_call.sid} — answer your phone!")
    lead["call_sid"] = lead_call.sid

    saw_live = False
    deadline = time.time() + RING_TIME + AMD_TIMEOUT + 120
    start = time.time()
    outcome = None
    duration = 0

    while time.time() < deadline:
        time.sleep(POLL_SECONDS)
        try:
            lc = client.calls(lead_call.sid).fetch()
            ac = client.calls(agent_call.sid).fetch()
        except Exception as e:
            print(f"  poll error: {e}")
            break

        if lc.status == "in-progress" and not saw_live:
            answered_by = getattr(lc, "answered_by", None)
            if answered_by and str(answered_by).lower().startswith("machine"):
                print(f"  VOICEMAIL detected ({name}) — moving on.")
                _cancel(client, agent_call.sid)
                _cancel(client, lead_call.sid)
                outcome = "voicemail"
                break
            saw_live = True
            print(f"  >>> HUMAN ANSWERED ({name}) — you are connected! Talk to them now.")
            lead["disposition"] = "live"

        # Lead call ended
        if lc.status in ("completed", "busy", "no-answer", "failed", "canceled"):
            duration = int((time.time() - start) / 60 * 100)  # placeholder
            if saw_live:
                print(f"  conversation ended ({lc.status}).")
                _cancel(client, agent_call.sid)
                outcome = "contacted"
            else:
                outcome = classify(lc)
                print(f"  no answer / not live ({lc.status}, answered_by={getattr(lc,'answered_by',None)}) -> {outcome}")
                _cancel(client, agent_call.sid)
            break

        # Agent leg ended first
        if ac.status in ("completed", "busy", "no-answer", "failed", "canceled"):
            if saw_live:
                print(f"  you hung up ({ac.status}). Conversation complete.")
                _cancel(client, lead_call.sid)
                outcome = "contacted"
            else:
                print(f"  agent call ended ({ac.status}) — nobody on the line.")
                _cancel(client, lead_call.sid)
                outcome = "agent_missed"
            break

    if outcome is None:
        print(f"  timeout after {(time.time() - start):.0f}s — cancelling.")
        _cancel(client, lead_call.sid)
        _cancel(client, agent_call.sid)
        outcome = "timeout"

    # duration in seconds from the call resource
    try:
        duration = int(getattr(client.calls(lead_call.sid).fetch(), "duration", 0) or 0)
    except Exception:
        pass

    lead["disposition"] = outcome
    lead["status"] = "called"
    lead["last_called"] = datetime.datetime.now().isoformat()
    lead["call_duration_seconds"] = duration
    lead["bridge_command"] = (
        f"python MBM/LeadEngine/call_bridge_to_phone.py --my-phone {agent_phone()} --prospect {e164}"
    )

    session_logs.append({
        "contact": name,
        "phone": e164,
        "call_sid": lead_call.sid,
        "disposition": outcome,
        "duration_seconds": duration,
    })
    return outcome


def _cancel(client, sid):
    try:
        client.calls(sid).update(status="canceled")
    except Exception:
        pass


def prompt_deal_outcome(name):
    """Ask the user how the call ended. Returns 'closed' | 'interest' | 'no'."""
    try:
        ans = input(f"\n  Outcome for {name}? [closed/acquired | interest | no] > ").strip().lower()
        if ans.startswith(("c", "a")):
            return "closed"
        if ans.startswith("i"):
            return "interest"
        return "no"
    except (EOFError, KeyboardInterrupt):
        return "no"


def dial_pool(client, leads, session_logs, summary, start_idx=1, ask_outcome=False, wholesaler_pool=None,
              wholesalers_per_deal=3):
    """Dial leads in order. If ask_outcome and a deal closes, inject N wholesalers to dial next."""
    w_idx = 0
    deals_closed = 0
    i = start_idx
    queue = list(leads)
    trigger_map = {}

    while queue:
        lead = queue.pop(0)
        origin = lead.get("_pool", "lead")
        outcome = dial_lead(client, lead, i, session_logs)
        summary["dispositions"][outcome] = summary["dispositions"].get(outcome, 0) + 1

        if ask_outcome and origin == "buyer":
            verdict = prompt_deal_outcome(lead.get("contact_name") or "buyer")
            lead["deal_verdict"] = verdict
            if verdict == "closed":
                deals_closed += 1
                added = 0
                while added < wholesalers_per_deal and w_idx < len(wholesaler_pool):
                    w = dict(wholesaler_pool[w_idx])
                    w_idx += 1
                    w["_pool"] = "wholesaler"
                    w["triggered_by"] = lead.get("contact_name")
                    trigger_map[w["phone"]] = lead.get("contact_name")
                    queue.append(w)
                    added += 1
                print(f"\n  >>> DEAL CLOSED ({lead.get('contact_name')}) -> adding {added} wholesaler(s) to dial next")

        if queue:
            print(f"  ... {GAP_SECONDS}s pause before next call")
            time.sleep(GAP_SECONDS)
        i += 1

    summary["deals_closed"] = deals_closed
    return w_idx, deals_closed


def main():
    ap = argparse.ArgumentParser(description="MBM Power Dialer")
    ap.add_argument("--leads", help="Path to leads JSON/queue file")
    ap.add_argument("--buyers", help="Path to buyer leads JSON (US cash buyers)")
    ap.add_argument("--wholesalers", help="Path to wholesaler leads JSON (dialed after a closed/acquired deal)")
    ap.add_argument("--wholesalers-per-deal", type=int, default=3,
                    help="Wholesalers to call for every closed/acquired deal (default 3)")
    ap.add_argument("--phone", help="Single phone to dial")
    ap.add_argument("--name", help="Name for single phone")
    ap.add_argument("--verify", action="store_true", help="Run real Twilio Lookup verification before dialing")
    ap.add_argument("--simulate", action="store_true", help="Dry run — verify and plan, no calls")
    ap.add_argument("--limit", type=int, help="Max leads to process")
    ap.add_argument("--start", type=int, default=0, help="Skip first N leads")
    a = ap.parse_args()

    client = get_client()
    frm = twilio_from()
    my_phone = agent_phone()

    # Build the lead plan
    buyers = []
    wholesalers = []
    if a.buyers:
        buyers = load_leads(a.buyers)
        for b in buyers:
            b["_pool"] = "buyer"
    if a.wholesalers:
        wholesalers = load_leads(a.wholesalers)
    leads = load_leads(a.leads, a.phone, a.name)
    for l in leads:
        l["_pool"] = "lead"

    leads = leads[a.start:] or buyers[a.start:]
    if a.limit:
        leads = leads[:a.limit]
        buyers = buyers[:a.limit]

    print(f"Power Dialer — From {frm} -> Your phone {my_phone}")
    print(f"Plan: {len(buyers)} buyers + {len(leads if not a.buyers else [])} direct | "
          f"ring={RING_TIME}s | amd={AMD_TIMEOUT}s | gap={GAP_SECONDS}s | wholesalers/deal={a.wholesalers_per_deal}")

    if a.simulate:
        print("\n=== SIMULATE MODE (no calls placed) ===")
        for i, lead in enumerate(buyers[:len(buyers)] if buyers else leads, 1):
            p = normalize_phone(lead.get("verified_phone") or lead.get("phone"))
            print(f"  [{i}] BUYER: {lead.get('contact_name') or lead.get('name') or '?'} ({p})")
        if wholesalers:
            print("  [*] WHOLESALERS (dialed after each closed/acquired deal):")
            for w in wholesalers[:a.wholesalers_per_deal * 2]:
                print(f"      - {w.get('contact_name','?')} ({normalize_phone(w.get('phone'))})")
        print("No live calls placed. Run without --simulate to dial for real.")
        return

    session_logs = []
    summary = {
        "platform": "MBM Power Dialer",
        "timestamp": datetime.datetime.now().isoformat(),
        "twilio_caller_id": frm,
        "user_mobile_phone": my_phone,
        "workflow": "buyers-first; wholesalers dialed per closed deal",
        "dispositions": {},
        "deals_closed": 0,
        "wholesalers_dialed": [],
    }

    print(f"\n{'='*60}\nSTARTING POWER DIAL SESSION — answer your phone!\n{'='*60}")

    # Verify buyers + wholesalers with real Twilio Lookup
    if a.verify and not a.simulate:
        from verify_phone import verify_leads_file
        tmp = ROOT / "MBM" / "LeadEngine" / "_dialer_verify_tmp.json"
        for pool in (buyers, wholesalers):
            if not pool:
                continue
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(pool, f, indent=2)
            pool[:] = verify_leads_file(str(tmp), client)
            os.remove(tmp)

    # Dial buyers (ask deal outcome after each); closed deals inject wholesalers
    ask = bool(a.wholesalers)
    w_idx, deals_closed = dial_pool(
        client, buyers if buyers else leads, session_logs, summary,
        start_idx=1, ask_outcome=ask,
        wholesaler_pool=wholesalers, wholesalers_per_deal=a.wholesalers_per_deal,
    )
    summary["deals_closed"] = deals_closed
    summary["wholesalers_dialed"] = [
        {"contact_name": l.get("contact_name"), "phone": l.get("phone"),
         "disposition": l.get("disposition"), "triggered_by": l.get("triggered_by")}
        for l in (buyers + wholesalers) if l.get("_pool") == "wholesaler"
    ]

    summary["session_logs"] = session_logs
    summary["hot_leads_for_user_close"] = [
        {
            "prospect_name": l.get("contact_name") or l.get("prospect_name"),
            "phone": l.get("verified_phone") or l.get("phone"),
            "bridge_command": l.get("bridge_command"),
        }
        for l in (buyers + wholesalers) if l.get("disposition") in ("contacted", "live")
    ]

    desktop = Path(r"C:\Users\omare\Desktop\power_dialer_report.json")
    try:
        with open(desktop, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"\nReport saved to {desktop}")
    except Exception as e:
        print(f"Could not save desktop report: {e}")

    print("\n=== SESSION SUMMARY ===")
    print(json.dumps(summary["dispositions"], indent=2))
    print(f"Deals closed: {deals_closed} | Wholesalers dialed: {len(summary['wholesalers_dialed'])}")
    contacted = [l for l in (buyers + wholesalers) if l.get("disposition") in ("contacted", "live")]
    if contacted:
        print("\nHot leads ready for you to close:")
        for l in contacted:
            print(f"  - {l.get('contact_name')} ({l.get('verified_phone') or l.get('phone')})")


if __name__ == "__main__":
    main()
