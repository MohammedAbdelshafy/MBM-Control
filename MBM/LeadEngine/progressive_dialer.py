#!/usr/bin/env python3
"""
Progressive Dialer — Twilio-based auto-dialer with machine detection,
call outcome tracking, lead status updates, campaign management,
and optional Retell AI agent bridge for AI-powered conversations.

Modes:
  Direct (default):     Dial and use Twilio demo TwiML or custom URL
  --bridge:             Bridge call to Retell AI agent for AI conversation

Usage:
  python progressive_dialer.py --start              # Start dialing (direct mode)
  python progressive_dialer.py --start --bridge     # Start with Retell AI agents
  python progressive_dialer.py --start --bridge --agent seller   # Force agent type
  python progressive_dialer.py --pause               # Pause dialer
  python progressive_dialer.py --resume              # Resume paused dialer
  python progressive_dialer.py --status              # Show dialer status + stats
  python progressive_dialer.py --campaign 10         # Dial only 10 leads
  python progressive_dialer.py --delay 5             # Set delay between calls
  python progressive_dialer.py --report              # Call summary report
  python progressive_dialer.py --dry-run             # Preview leads to be called
"""

import os
import sys
import json
import csv
import time
import signal
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    os.system(f"{sys.executable} -m pip install twilio -q")
    from twilio.rest import Client as TwilioClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = Path(__file__).resolve().parent / "logs"
PIPELINE_FILE = ROOT / "MBM" / "Pipeline" / "pipeline.csv"
STATE_FILE = LOGS_DIR / "dialer_state.json"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER", "+16619909068")
RETELL_API_KEY = os.getenv("RETELL_API_KEY")

AGENTS = {
    "seller": "agent_00bb14caed46feaddd75526ce2",
    "buyer": "agent_1cf38b194ed2d0cf9842ba82ee",
    "pre_foreclosure": "agent_3404c7c4a6f7b1448145fbbdd9",
    "commercial": "agent_ec2545ec4ba59441a07608623b",
    "referral": "agent_8e178801707abe5236c469cc00",
    "ecommerce": "agent_43b5f21d2663151d439c3c699d",
}

SCRIPTS = {
    "seller": {
        "greeting": "Hi, this is Sarah from MBM Property Solutions. I'm reaching out regarding your property. Are you still interested in selling?",
        "questions": ["What's the address?", "What's your timeline?", "Would you consider a cash offer?"],
    },
    "buyer": {
        "greeting": "Hi, this is James from MBM Property Solutions. I'm reaching out about your property search. Are you still looking to buy?",
        "questions": ["What's your budget?", "What area?", "Are you pre-approved?"],
    },
    "pre_foreclosure": {
        "greeting": "Hi, this is Maria from MBM Property Solutions. We help homeowners in pre-foreclosure. Are you still in need of assistance?",
        "questions": ["When is your auction date?", "How much do you owe?", "Would you accept a cash offer?"],
    },
}

OUTCOME_ORDER = ["answered", "voicemail", "busy", "no_answer", "failed"]

_running = True


def _log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {ts} | {msg}")


def _get_twilio_client():
    if not TWILIO_SID or not TWILIO_TOKEN:
        _log("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set in .env", "ERROR")
        return None
    return TwilioClient(TWILIO_SID, TWILIO_TOKEN)


def _load_pipeline():
    if not PIPELINE_FILE.exists():
        _log(f"Pipeline file not found: {PIPELINE_FILE}", "ERROR")
        return []
    with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_pipeline(leads):
    tmp = PIPELINE_FILE.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)
    shutil.move(str(tmp), str(PIPELINE_FILE))


def _load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"status": "idle", "paused": False, "index": 0, "total_dialed": 0,
            "outcomes": {}, "campaign_limit": 0, "delay": 3, "started_at": None,
            "last_call_at": None, "bridge_mode": False, "agent_type": None}


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _clean_phone(phone):
    phone = phone.strip().replace("-", "").replace("(", "").replace(")", "").replace(" ", "").replace(".", "")
    if not phone.startswith("+"):
        phone = "+1" + phone
    return phone


def _detect_agent_type(lead):
    notes = (lead.get("notes", "") + " " + lead.get("solution", "")).lower()
    if "sell" in notes or "foreclosure" in notes or "distressed" in notes:
        return "seller"
    if "buy" in notes or "commercial" in notes or "luxury" in notes:
        return "buyer"
    if "refer" in notes:
        return "referral"
    if "ecom" in notes or "plastic" in notes or "scrap" in notes:
        return "ecommerce"
    return "seller"


def _get_next_leads(state, count=50):
    leads = _load_pipeline()
    available = []
    for i, lead in enumerate(leads):
        if i < state.get("index", 0):
            continue
        stage = lead.get("stage", "").lower()
        phone = lead.get("phone", "").strip()
        if stage in ("converted", "closed_won", "closed_lost", "unqualified", "do_not_call"):
            continue
        if not phone:
            continue
        available.append((i, lead))
        if len(available) >= count:
            break
    return available, leads


def _build_bridge_twiml(agent_type, lead):
    agent_id = AGENTS.get(agent_type, AGENTS["seller"])
    script = SCRIPTS.get(agent_type, SCRIPTS["seller"])
    greeting = script.get("greeting", "Hello!")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Matthew">{greeting}</Say>
    <Pause length="2"/>
    <Connect>
        <Sip>sip:{agent_id}@sip.retellai.com</Sip>
    </Connect>
</Response>"""
    return twiml


def make_call(lead, index, twilio_client, bridge=False, agent_type=None):
    phone = _clean_phone(lead.get("phone", ""))
    company = lead.get("company", "Unknown")

    try:
        if bridge:
            detected = agent_type or _detect_agent_type(lead)
            twiml = _build_bridge_twiml(detected, lead)
            call = twilio_client.calls.create(
                to=phone,
                from_=TWILIO_FROM,
                twiml=twiml,
                timeout=60,
                record=True,
                machine_detection="Enable",
                machine_detection_timeout=8,
                status_callback_event=["initiated", "ringing", "answered", "completed", "busy", "no-answer", "failed"],
                status_callback=f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json",
            )
            _log(f"[{index}] Bridged {company} ({phone}) via Retell {detected} — SID: {call.sid}", "CALL")
            return {
                "call_sid": call.sid,
                "company": company,
                "phone": phone,
                "agent_type": detected,
                "status": call.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            call = twilio_client.calls.create(
                to=phone,
                from_=TWILIO_FROM,
                url="http://demo.twilio.com/docs/voice.xml",
                timeout=30,
                machine_detection="Enable",
                machine_detection_timeout=8,
                status_callback_event=["initiated", "ringing", "answered", "completed", "busy", "no-answer", "failed"],
                status_callback=f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json",
            )
            _log(f"[{index}] Called {company} ({phone}) — SID: {call.sid}", "CALL")
            return {
                "call_sid": call.sid,
                "company": company,
                "phone": phone,
                "status": call.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        _log(f"[{index}] Failed {company} ({phone}): {e}", "ERROR")
        return {
            "call_sid": None,
            "company": company,
            "phone": phone,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _get_call_outcome(call_sid, twilio_client, max_retries=8):
    for attempt in range(max_retries):
        time.sleep(2)
        try:
            call = twilio_client.calls(call_sid).fetch()
            status = call.status.lower()
            if status == "completed":
                duration = int(call.duration) if call.duration else 0
                if call.answered_by:
                    if "machine" in call.answered_by.lower():
                        return "voicemail", duration
                    return "answered", duration
                return "answered" if duration > 5 else "voicemail", duration
            elif status == "busy":
                return "busy", 0
            elif status == "no-answer":
                return "no_answer", 0
            elif status == "failed":
                return "failed", 0
            elif status in ("ringing", "initiated", "queued"):
                continue
        except Exception:
            continue
    return "no_answer", 0


def run_dialer(state):
    global _running
    twilio_client = _get_twilio_client()
    if not twilio_client:
        return

    state["status"] = "running"
    state["started_at"] = state.get("started_at") or datetime.now(timezone.utc).isoformat()
    _save_state(state)

    total_dialed = state.get("total_dialed", 0)
    outcomes = state.get("outcomes", {})
    campaign_limit = state.get("campaign_limit", 0)
    delay = state.get("delay", 3)
    bridge = state.get("bridge_mode", False)
    agent_type = state.get("agent_type")
    call_log = []

    mode = "BRIDGE" if bridge else "DIRECT"
    _log(f"Progressive Dialer started ({mode}) — press Ctrl+C to pause", "START")
    _log(f"State file: {STATE_FILE}", "INFO")

    while _running:
        if state.get("paused", False):
            _log("Dialer is paused — waiting...", "PAUSE")
            time.sleep(5)
            state = _load_state()
            continue

        if campaign_limit > 0 and total_dialed >= campaign_limit:
            _log(f"Campaign limit reached ({campaign_limit} calls)", "DONE")
            state["status"] = "completed"
            break

        available, all_leads = _get_next_leads(state)
        if not available:
            _log("No more leads to dial — pipeline exhausted", "DONE")
            state["status"] = "completed"
            break

        idx, lead = available[0]
        result = make_call(lead, idx + 1, twilio_client, bridge=bridge, agent_type=agent_type)

        if result["call_sid"]:
            outcome, duration = _get_call_outcome(result["call_sid"], twilio_client)
            result["outcome"] = outcome
            result["duration_seconds"] = duration
            _log(f"[{idx + 1}] Outcome: {outcome} ({duration}s)", "RESULT")

            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            total_dialed += 1

            all_leads[idx]["stage"] = {
                "answered": "contacted",
                "voicemail": "voicemail_left",
                "busy": "busy",
                "no_answer": "no_answer",
                "failed": "failed",
            }.get(outcome, all_leads[idx].get("stage", ""))
            all_leads[idx]["last_touch"] = datetime.now().strftime("%Y-%m-%d")
            method = "bridge" if bridge else "direct"
            all_leads[idx]["notes"] = (all_leads[idx].get("notes", "") +
                                       f" | Called {datetime.now().strftime('%Y-%m-%d %H:%M')} [{method}]: {outcome} ({duration}s)")
            _save_pipeline(all_leads)
        else:
            outcomes["failed"] = outcomes.get("failed", 0) + 1
            total_dialed += 1

        call_log.append(result)
        state["index"] = idx + 1
        state["total_dialed"] = total_dialed
        state["outcomes"] = outcomes
        state["last_call_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

        if _running and not state.get("paused", False):
            _log(f"Waiting {delay}s before next call...", "INFO")
            for _ in range(delay):
                if not _running or state.get("paused", False):
                    break
                time.sleep(1)

    log_file = LOGS_DIR / f"dialer_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w") as f:
        json.dump(call_log, f, indent=2, default=str)
    _log(f"Call log saved: {log_file.name}", "INFO")
    state["status"] = "completed" if state["status"] != "paused" else "paused"
    _save_state(state)

    _print_summary(outcomes, total_dialed)


# ── CLI Commands ───────────────────────────────────────────────────────

def cmd_start(args):
    state = _load_state()
    if state.get("status") == "running" and not state.get("paused", False):
        _log("Dialer is already running. Use --pause or --resume", "WARN")
        return
    if args.campaign:
        state["campaign_limit"] = args.campaign
    if args.delay:
        state["delay"] = args.delay
    state["bridge_mode"] = args.bridge
    if args.agent:
        state["agent_type"] = args.agent
    state["paused"] = False
    run_dialer(state)


def cmd_pause():
    state = _load_state()
    state["paused"] = True
    state["status"] = "paused"
    _save_state(state)
    _log("Dialer paused. Use --resume to continue.", "PAUSE")


def cmd_resume():
    state = _load_state()
    if state.get("status") not in ("paused", "idle"):
        cmd_start(argparse.Namespace(campaign=state.get("campaign_limit", 0),
                                     delay=state.get("delay", 3),
                                     bridge=state.get("bridge_mode", False),
                                     agent=state.get("agent_type", None)))
        return
    state["paused"] = False
    state["status"] = "running"
    _save_state(state)
    _log("Dialer resumed.", "INFO")
    run_dialer(state)


def cmd_status():
    state = _load_state()
    total_leads = len(_load_pipeline())
    available = sum(1 for l in _load_pipeline()
                    if l.get("stage", "").lower() not in ("converted", "closed_won", "closed_lost", "unqualified", "do_not_call")
                    and l.get("phone", "").strip())
    outcomes = state.get("outcomes", {})
    total = state.get("total_dialed", 0)
    delay = state.get("delay", 3)
    limit = state.get("campaign_limit", 0)
    idx = state.get("index", 0)
    status = state.get("status", "idle")
    bridge = state.get("bridge_mode", False)

    mode_str = "BRIDGE (Retell AI)" if bridge else "DIRECT"
    print(f"\n{'='*50}")
    print(f"  PROGRESSIVE DIALER STATUS")
    print(f"{'='*50}")
    print(f"  Status:           {status.upper()}")
    print(f"  Mode:             {mode_str}")
    print(f"  Agent type:       {state.get('agent_type', 'auto-detect')}")
    print(f"  Paused:           {state.get('paused', False)}")
    print(f"  Delay:            {delay}s")
    print(f"  Campaign limit:   {limit if limit else 'unlimited'}")
    print(f"  Index:            {idx}")
    print(f"  Total dialed:     {total}")
    print(f"  Pipeline leads:   {total_leads}")
    print(f"  Available to call: {available}")
    if outcomes:
        print(f"\n  Outcomes:")
        for o in OUTCOME_ORDER:
            if o in outcomes:
                pct = outcomes[o] / total * 100 if total else 0
                print(f"    {o:12s}: {outcomes[o]:4d} ({pct:.0f}%)")
    if state.get("started_at"):
        print(f"\n  Started:   {state['started_at']}")
    if state.get("last_call_at"):
        print(f"  Last call: {state['last_call_at']}")
    print(f"  State file: {STATE_FILE}")
    print(f"{'='*50}\n")


def cmd_report():
    log_files = sorted(LOGS_DIR.glob("dialer_calls_*.json"))
    if not log_files:
        _log("No dialer call logs found", "INFO")
        return

    all_outcomes = {}
    total_calls = 0
    total_duration = 0
    recent = log_files[-1]

    with open(recent) as f:
        calls = json.load(f)

    for c in calls:
        outcome = c.get("outcome", "unknown")
        all_outcomes[outcome] = all_outcomes.get(outcome, 0) + 1
        total_calls += 1
        total_duration += c.get("duration_seconds", 0)

    mode = "bridge" if calls and "agent_type" in calls[0] else "direct"
    print(f"\n{'='*50}")
    print(f"  DIALER REPORT — {mode.upper()} — {recent.stem}")
    print(f"{'='*50}")
    print(f"  Total calls:      {total_calls}")
    print(f"  Total talk time:  {total_duration // 60}m {total_duration % 60}s")
    print(f"  Avg call length:  {total_duration // max(total_calls, 1)}s")
    print(f"\n  Outcomes:")
    for o in OUTCOME_ORDER:
        if o in all_outcomes:
            pct = all_outcomes[o] / total_calls * 100
            print(f"    {o:12s}: {all_outcomes[o]:4d} ({pct:.0f}%)")
    print(f"\n  File: {recent}")
    print(f"{'='*50}\n")


def cmd_dry_run(args):
    leads = _load_pipeline()
    available = []
    for i, lead in enumerate(leads):
        stage = lead.get("stage", "").lower()
        phone = lead.get("phone", "").strip()
        if stage in ("converted", "closed_won", "closed_lost", "unqualified", "do_not_call"):
            continue
        if not phone:
            continue
        detected = _detect_agent_type(lead)
        available.append((i, lead, detected))

    mode = "BRIDGE" if args.bridge else "DIRECT"
    print(f"\n{'='*50}")
    print(f"  DRY RUN — {mode} — {len(available)} leads")
    print(f"{'='*50}")
    for i, (idx, lead, agent) in enumerate(available[:20], 1):
        phone = _clean_phone(lead.get("phone", ""))
        agent_tag = f" [{agent}]" if args.bridge else ""
        print(f"  {i:3d}. {lead.get('company','?'):30s} {phone}{agent_tag}")
    if len(available) > 20:
        print(f"  ... and {len(available) - 20} more")
    print(f"{'='*50}\n")


def _print_summary(outcomes, total):
    print(f"\n{'='*50}")
    print(f"  DIALER SESSION COMPLETE")
    print(f"{'='*50}")
    print(f"  Total dialed: {total}")
    for o in OUTCOME_ORDER:
        if o in outcomes:
            pct = outcomes[o] / total * 100 if total else 0
            print(f"    {o:12s}: {outcomes[o]:4d} ({pct:.0f}%)")
    print(f"{'='*50}\n")


def signal_handler(sig, frame):
    global _running
    _running = False
    _log("Interrupt received — pausing dialer...", "SIG")
    cmd_pause()


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Progressive Dialer — Twilio auto-dialer with Retell AI bridge")
    parser.add_argument("--start", action="store_true", help="Start progressive dialing")
    parser.add_argument("--pause", action="store_true", help="Pause dialer")
    parser.add_argument("--resume", action="store_true", help="Resume paused dialer")
    parser.add_argument("--status", action="store_true", help="Show dialer status + stats")
    parser.add_argument("--campaign", type=int, default=0, help="Dial only N leads")
    parser.add_argument("--delay", type=int, default=3, help="Delay between calls (seconds)")
    parser.add_argument("--report", action="store_true", help="Generate call summary report")
    parser.add_argument("--dry-run", action="store_true", help="Preview which leads will be called")
    parser.add_argument("--bridge", action="store_true", help="Use Retell AI agent bridge")
    parser.add_argument("--agent", choices=list(AGENTS.keys()), help="Force Retell agent type (auto-detected by default)")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.report:
        cmd_report()
    elif args.dry_run:
        cmd_dry_run(args)
    elif args.pause:
        cmd_pause()
    elif args.resume:
        cmd_resume()
    elif args.start:
        cmd_start(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
