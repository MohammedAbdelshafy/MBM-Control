#!/usr/bin/env python3
"""
MBM Voice Agent Factory
Generates and deploys NEW voice agents to Retell AI.

Usage:
  python agent_factory.py --once
  python agent_factory.py --loop
  python agent_factory.py --deploy
  python agent_factory.py --status

Reliability contract (incident run 32863390319):
  - Retell returns a misleading generic HTTP 404 {"status":"error",
    "message":"Not Found"} when create-agent references a NONEXISTENT
    voice_id. It is NOT propagation delay: a valid voice attached to a
    seconds-old llm_id succeeds immediately (verified live 2026-08-25).
    => 404/4xx are PERMANENT errors: never retried; the just-created LLM
       is deleted (provable ownership: we hold its id from our own 201).
  - Only 429/5xx/network errors are retried (bounded, linear backoff).
  - The process exits non-zero unless EVERY requested creation succeeds,
    so CI cannot report a broken production cycle as green.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_FILE = LOGS_DIR / "factory_agents.json"
DEPLOYED_FILE = LOGS_DIR / "deployed_agents.json"
ATTEMPTS_FILE = LOGS_DIR / "factory_attempts.json"

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

RETELL_BASE = "https://api.retellai.com"
REQUEST_TIMEOUT = 30
AGENT_ATTEMPTS = 5
# Production cadence of the scheduled workflow (agent-factory.yml */5 cron).
CADENCE_SECONDS = 300

MAX_LEDGER_RECORDS = 250


class ConfigError(Exception):
    """Fatal configuration problem: production must not silently continue."""


# Keep this aligned with the last known-good production fix.
# NOTE: validated against GET /list-voices at startup (validate_voice_pool);
# entries absent from Retell are stripped before any create-agent call.
VOICE_IDS = [
    "retell-Willa",
    "retell-Cimo",
]

# Industry niches with scripts
NICHES = [
    {
        "name": "HVAC Repair",
        "persona": "Friendly HVAC service coordinator",
        "hook": "Hi! I'm calling about your heating and cooling system. Are you still experiencing issues with your HVAC?",
        "qualify": ["What's the issue?", "When did it start?", "What's your address?", "Is this residential or commercial?"],
        "close": "I'll have a technician call you within 30 minutes. What's the best number?",
        "rate": 0.35,
        "tags": ["hvac", "home-services", "repair"]
    },
    {
        "name": "Plumbing Emergency",
        "persona": "Calm, professional plumbing dispatcher",
        "hook": "Hi! I see you submitted a plumbing request. Is this still an emergency, or has the situation changed?",
        "qualify": ["What's the issue?", "Is water still running?", "What's your address?", "What's your timeline?"],
        "close": "A licensed plumber will call you within 15 minutes. Hang tight!",
        "rate": 0.35,
        "tags": ["plumbing", "emergency", "home-services"]
    },
    {
        "name": "Solar Panel Sales",
        "persona": "Energetic clean energy consultant",
        "hook": "Hi! I'm calling about solar panels for your home. Are you still interested in reducing your electricity bill by 30-50%?",
        "qualify": ["What's your monthly electric bill?", "Do you own your home?", "What's your roof direction?", "When are you looking to install?"],
        "close": "I'll send you a free solar estimate. What email works best?",
        "rate": 0.45,
        "tags": ["solar", "energy", "home-improvement"]
    },
    {
        "name": "Roofing Contractor",
        "persona": "Professional roofing consultant",
        "hook": "Hi! I'm following up on your roofing inquiry. Are you still looking to get your roof inspected or repaired?",
        "qualify": ["What's the issue?", "When was the last inspection?", "What type of roof?", "Is there visible damage?"],
        "close": "We can schedule a free inspection this week. What day works best?",
        "rate": 0.40,
        "tags": ["roofing", "contractor", "home-services"]
    },
    {
        "name": "Insurance Claims",
        "persona": "Empathetic insurance claim specialist",
        "hook": "Hi! I'm following up on your insurance claim. Do you still need assistance with the claims process?",
        "qualify": ["What type of claim?", "When did the incident occur?", "Have you filed yet?", "What's your policy number?"],
        "close": "I'll have an adjuster review your case within 24 hours. We'll call you back.",
        "rate": 0.50,
        "tags": ["insurance", "claims", "financial"]
    },
    {
        "name": "Legal Consultation",
        "persona": "Professional legal intake specialist",
        "hook": "Hi! I'm calling from the law office. You requested a consultation. Are you still looking for legal assistance?",
        "qualify": ["What type of case?", "When did this happen?", "Have you spoken to an attorney?", "What's your timeline?"],
        "close": "An attorney will call you within 2 hours for a free consultation.",
        "rate": 0.55,
        "tags": ["legal", "consultation", "professional"]
    },
    {
        "name": "Dental Appointment",
        "persona": "Warm dental office receptionist",
        "hook": "Hi! I'm calling about your upcoming dental appointment. Are you still able to make it?",
        "qualify": ["What procedure?", "Do you have insurance?", "Any preferences for date/time?", "Any anxiety concerns?"],
        "close": "I'll confirm your appointment and send a reminder. See you soon!",
        "rate": 0.30,
        "tags": ["dental", "healthcare", "appointment"]
    },
    {
        "name": "Auto Detailing",
        "persona": "Enthusiastic auto detailing coordinator",
        "hook": "Hi! I'm following up on your auto detailing request. Are you still looking to get your vehicle detailed?",
        "qualify": ["What type of vehicle?", "Interior, exterior, or both?", "Any special requests?", "When works for you?"],
        "close": "I'll book your detail slot. What day works best?",
        "rate": 0.35,
        "tags": ["auto", "detailing", "services"]
    },
    {
        "name": "Moving Company",
        "persona": "Organized moving coordinator",
        "hook": "Hi! I'm calling about your upcoming move. Are you still planning to relocate?",
        "qualify": ["When are you moving?", "What's the origin/destination?", "How many rooms?", "Any specialty items?"],
        "close": "I'll prepare a custom quote. When can we do a virtual walkthrough?",
        "rate": 0.40,
        "tags": ["moving", "logistics", "services"]
    },
]


def _ci_env(name):
    return os.environ.get(name, "") or ""


def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Failed reading {path.name}: {e}")
    return default


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_deployed():
    # Tolerate corrupt/empty state: the factory treats this file as a local
    # diagnostic record, never as a source of truth (runners are ephemeral).
    data = read_json(DEPLOYED_FILE, [])
    return data if isinstance(data, list) else []


def save_deployed(data):
    write_json(DEPLOYED_FILE, data)


def append_attempt(record):
    attempts = read_json(ATTEMPTS_FILE, [])
    if not isinstance(attempts, list):
        attempts = []
    record.setdefault("sha", _ci_env("GITHUB_SHA"))
    record.setdefault("run_id", _ci_env("GITHUB_RUN_ID"))
    record.setdefault("attempt", _ci_env("GITHUB_RUN_ATTEMPT"))
    attempts.append(record)
    # Keep the local diagnostic ledger bounded.
    write_json(ATTEMPTS_FILE, attempts[-MAX_LEDGER_RECORDS:])


def get_next_niche(offset=0):
    """Deterministic per-window niche selection.

    Keyed on (factory, UTC time slot) instead of ephemeral runner state, so
    every run/replay of the same 5-minute window rotates through the same
    niche sequence regardless of checkout freshness. Two agents requested in
    one batch use consecutive slots (offset 0 and 1).
    """
    slot = int(time.time()) // CADENCE_SECONDS
    return NICHES[(slot + offset) % len(NICHES)]


def validate_voice_pool():
    """Strip voice_ids Retell does not know about BEFORE creating anything.

    Live evidence (2026-08-25): create-agent answers a nonexistent voice_id
    with generic HTTP 404 {"status":"error","message":"Not Found"} — the exact
    signature that broke the 2026-08-25 production batch. Validation here is
    fail-safe: if the catalog cannot be fetched we keep the configured pool
    (production continues; retries remain bounded), but if the pool ends up
    empty we raise ConfigError because continuing would guarantee 404s.
    """
    headers = {"Authorization": f"Bearer {RETELL_API_KEY}"}
    try:
        r = requests.get(f"{RETELL_BASE}/list-voices", headers=headers, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[!] Voice catalog check skipped (network): {e}")
        return []
    if r.status_code != 200:
        print(f"[!] Voice catalog check skipped (HTTP {r.status_code}); keeping configured voices")
        return []

    try:
        known = {v.get("voice_id") for v in r.json()}
    except Exception as e:
        print(f"[!] Voice catalog unparseable ({e}); keeping configured voices")
        return []

    invalid = [v for v in VOICE_IDS if v not in known]
    for v in invalid:
        print(f"[!] Removing INVALID voice_id '{v}' (Retell /list-voices does not know it)")
        append_attempt({"status": "invalid_voice_removed", "voice_id": v})
    VOICE_IDS[:] = [v for v in VOICE_IDS if v in known]
    if not VOICE_IDS:
        raise ConfigError(
            "All configured voice_ids are invalid per Retell /list-voices. "
            "Fix VOICE_IDS in MBM/LeadEngine/agent_factory.py."
        )
    return invalid


def cleanup_orphan_llm(llm_id, reason):
    """Delete an LLM THIS process created (id captured from our own 201).

    Never called with an id we did not receive ourselves. If deletion fails,
    the id is quarantined in the attempt ledger so the resource stays
    traceable instead of silently accumulating.
    """
    if not llm_id:
        return False
    headers = {"Authorization": f"Bearer {RETELL_API_KEY}"}
    try:
        r = requests.delete(f"{RETELL_BASE}/delete-retell-llm/{llm_id}", headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code in (200, 201, 204):
            print(f"  [+] Orphan LLM cleaned up: {llm_id} ({reason})")
            append_attempt({"status": "orphan_llm_deleted", "llm_id": llm_id, "reason": reason})
            return True
        print(f"  [!] Could not delete orphan LLM {llm_id}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  [!] Could not delete orphan LLM {llm_id}: {e}")
    append_attempt({"status": "orphan_llm_quarantined", "llm_id": llm_id, "reason": reason})
    return False


def create_agent(niche):
    """Create a new Retell LLM and attach it to a voice agent."""
    started_at = datetime.now().isoformat()
    llm_id = None
    if not RETELL_API_KEY:
        raise ConfigError("RETELL_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json",
    }

    prompt = f"""You are {niche['persona']}.

Opening: "{niche['hook']}"

Qualification questions:
{chr(10).join('- ' + q for q in niche['qualify'])}

Closing: "{niche['close']}"

If they say NO: "No problem. If you need {niche['name'].lower()} services in the future, we're here to help. Have a great day!"
If they say NOT NOW: "Totally understand. Should I check back in a week or two?"
If they say ALREADY DONE: "Great! If you need anything else, don't hesitate to reach out."
If they're BUSY: "I understand. When would be a better time for a quick 2-minute call?"

Be natural, empathetic, and professional. Never be pushy. Log the outcome."""

    voice_id = random.choice(VOICE_IDS)
    llm_payload = {
        "model": "gemini-2.5-flash-lite",
        "general_prompt": prompt,
        "start_speaker": "agent",
        "begin_message": niche["hook"],
    }

    try:
        r = requests.post(
            f"{RETELL_BASE}/create-retell-llm",
            headers=headers,
            json=llm_payload,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code not in (200, 201):
            print(f"  [-] LLM creation failed: {r.status_code} - {r.text[:500]}")
            append_attempt({"niche": niche["name"], "status": "llm_failed", "http": r.status_code, "at": started_at, "body": r.text[:500]})
            return None
        try:
            llm_id = r.json().get("llm_id")
        except Exception:
            llm_id = None
        if not llm_id:
            print(f"  [-] LLM creation returned no llm_id: {r.text[:500]}")
            append_attempt({"niche": niche["name"], "status": "llm_missing_id", "at": started_at, "body": r.text[:500]})
            return None
        print(f"  [+] Created LLM: {llm_id}")
    except Exception as e:
        print(f"  [!] Error creating LLM: {e}")
        append_attempt({"niche": niche["name"], "status": "llm_exception", "error": str(e)[:500], "at": started_at})
        return None

    # Retell may not expose the newly-created response engine immediately.
    time.sleep(5)

    agent_payload = {
        "agent_name": f"MBM-{niche['name'].replace(' ', '-')}-{datetime.now().strftime('%H%M%S')}",
        "voice_id": voice_id,
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
    }

    for attempt in range(AGENT_ATTEMPTS):
        try:
            r = requests.post(
                f"{RETELL_BASE}/create-agent",
                headers=headers,
                json=agent_payload,
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code in (200, 201):
                try:
                    data = r.json()
                except Exception:
                    print(f"  [-] create-agent returned malformed JSON: {r.text[:1000]}")
                    append_attempt({"niche": niche["name"], "status": "agent_malformed_response", "llm_id": llm_id, "at": started_at, "body": r.text[:1000]})
                    cleanup_orphan_llm(llm_id, "malformed_create_agent_response")
                    return None
                agent_id = data.get("agent_id")
                if not agent_id:
                    print(f"  [-] create-agent returned no agent_id: {r.text[:1000]}")
                    append_attempt({"niche": niche["name"], "status": "agent_missing_id", "llm_id": llm_id, "at": started_at, "body": r.text[:1000]})
                    cleanup_orphan_llm(llm_id, "missing_agent_id")
                    return None
                return {
                    "niche": niche["name"],
                    "agent_id": agent_id,
                    "llm_id": llm_id,
                    "voice_id": voice_id,
                    "rate_per_min": niche["rate"],
                    "tags": niche["tags"],
                    "deployed_at": datetime.now().isoformat(),
                    "status": "deployed",
                }

            # Permanent client-side/reference failures: retrying can never
            # succeed (404 on create-agent == unknown voice_id/llm reference;
            # verified live 2026-08-25). Fail fast, keep evidence, clean up.
            if r.status_code in (400, 401, 403, 404, 405, 422):
                print(f"  [-] create-agent PERMANENT failure {r.status_code} "
                      f"(voice_id={voice_id}, llm_id={llm_id}): {r.text[:500]}")
                append_attempt({
                    "niche": niche["name"],
                    "status": "agent_failed_permanent",
                    "http": r.status_code,
                    "llm_id": llm_id,
                    "voice_id": voice_id,
                    "at": started_at,
                    "body": r.text[:1000],
                })
                cleanup_orphan_llm(llm_id, f"permanent_http_{r.status_code}")
                return None

            if r.status_code in (429, 500, 502, 503, 504) and attempt < AGENT_ATTEMPTS - 1:
                wait = 5 * (attempt + 1)
                print(f"  [~] Retell create-agent transient {r.status_code} "
                      f"(attempt {attempt + 1}/{AGENT_ATTEMPTS}), retrying in {wait}s")
                time.sleep(wait)
                continue

            print(f"  [-] create-agent failed: {r.status_code} - {r.text[:1000]}")
            append_attempt({
                "niche": niche["name"],
                "status": "agent_failed_transient_exhausted" if r.status_code in (429, 500, 502, 503, 504) else "agent_failed",
                "http": r.status_code,
                "llm_id": llm_id,
                "at": started_at,
                "body": r.text[:1000],
            })
            cleanup_orphan_llm(llm_id, f"http_{r.status_code}_after_retries")
            return None
        except Exception as e:
            if attempt < AGENT_ATTEMPTS - 1:
                wait = 5 * (attempt + 1)
                print(f"  [~] create-agent exception: {e}; retrying in {wait}s")
                time.sleep(wait)
                continue
            print(f"  [!] create-agent exhausted retries: {e}")
            append_attempt({"niche": niche["name"], "status": "agent_exception", "llm_id": llm_id, "error": str(e)[:500], "at": started_at})
            cleanup_orphan_llm(llm_id, "exception_after_retries")
            return None

    return None


def generate_one(niche=None, offset=0):
    if niche is None:
        niche = get_next_niche(offset=offset)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating agent for: {niche['name']}")
    result = create_agent(niche)
    if result:
        deployed = load_deployed()
        deployed.append(result)
        save_deployed(deployed)
        print(f"  [+] Deployed: {result['agent_id']} (${result['rate_per_min']}/min)")
        print(f"  [+] Total deployed: {len(deployed)}")
        append_attempt({"niche": niche["name"], "status": "deployed", "agent_id": result["agent_id"], "llm_id": result["llm_id"], "at": result["deployed_at"]})
        return result
    return None


def run_loop():
    print("\n" + "=" * 50)
    print("  MBM VOICE AGENT FACTORY")
    print("  Generating new agent every 15 minutes")
    print("=" * 50 + "\n")
    while True:
        result = generate_one()
        if result:
            time.sleep(900)
        else:
            time.sleep(300)


def show_status():
    deployed = load_deployed()
    if not deployed:
        print("[!] No agents deployed yet")
        return
    total_rate = 0
    for i, agent in enumerate(deployed, 1):
        print(f"{i}. {agent['niche']} | {agent['agent_id']} | ${agent['rate_per_min']}/min | {agent['deployed_at']}")
        total_rate += agent['rate_per_min']
    print(f"Total agents: {len(deployed)}")
    print(f"Combined rate: ${total_rate:.2f}/min")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args(argv)

    if args.status:
        show_status()
        return 0

    if not RETELL_API_KEY:
        print("[FATAL] RETELL_API_KEY not set; refusing to run a no-op batch")
        return 2

    try:
        validate_voice_pool()
    except ConfigError as e:
        print(f"[FATAL] {e}")
        return 2

    made = 0
    failed = 0
    for i in range(max(1, args.count)):
        try:
            result = generate_one(offset=i)
        except ConfigError as e:
            print(f"[FATAL] {e}")
            return 2
        if result:
            made += 1
        else:
            failed += 1

    print(f"\nSUMMARY: made={made} failed={failed} requested={max(1, args.count)} "
          f"revision={_ci_env('GITHUB_SHA') or 'local'} run={_ci_env('GITHUB_RUN_ID') or 'local'}")

    # Strict gate: a partial or total batch failure must turn the workflow red
    # so the Telegram alert fires. Silent-green degradation is how the
    # 2026-08-25 incident stayed invisible until a manual inspection.
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
