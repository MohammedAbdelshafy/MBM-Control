"""
CGPT Script Generator — creates / refreshes a personalized call script for a
dialer lead using OpenAI's ChatGPT (chat.completions). Quietly falls back to the
lead's existing Call_Script, or a vertical template, if no API key is present.

Credential (add to .env / .env.local):
    OPENAI_API_KEY = sk-...

Usage:
    python cgpt_script_generator.py --id Clinics-24
    python cgpt_script_generator.py --lead '{"company":"...","contact":"..."}'
    python cgpt_script_generator.py --refresh-missing   # backfill leads with no Call_Script
    python cgpt_script_generator.py --update-json       # write generated scripts back to leads_database.json
"""
import os
import io
import sys
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIALER_LEADS = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
ENV_FILES = [ROOT / ".env", ROOT / ".env.local"]

MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"


def _load_env():
    for env_path in ENV_FILES:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _tty(text: str) -> str:
    try:
        text.encode(sys.stdout.encoding or "utf-8")
        return text
    except Exception:
        return text.encode("ascii", errors="replace").decode("ascii")


OFFER_BY_VERTICAL = {
    "Real Estate Sellers": "We buy houses as-is with a 7-day cash close, zero agent fees, "
                          "and we cover all closing costs.",
    "Texas Real Estate": "We buy houses as-is with a 7-day cash close, zero agent fees, "
                         "and we cover all closing costs.",
    "Master Catch-All": "firm cash offer on the property with a 7-day close and zero fees.",
}
DEFAULT_OFFER = ("A patient-growth retainer that drops pre-qualified, cash-ready patients "
                 "into this office's schedule, with a pay-zero-until-you-see-it risk reversal "
                 "at $497/mo.")


def _build_prompt(lead: dict) -> str:
    d = lead.get("details") or {}
    vertical = (lead.get("vertical") or "").strip()
    offer = OFFER_BY_VERTICAL.get(vertical, DEFAULT_OFFER)
    return (
        "Write a short, natural, human-sounding cold call script (5-7 spoken paragraphs). "
        "Use the prospect's real first name. Do NOT sound like a robot or a pitch deck. "
        "One clear purpose: get them to agree to a short follow-up conversation. "
        "Context:\n"
        f"- Contact: {lead.get('contact') or 'unknown'}\n"
        f"- Company: {lead.get('company') or 'unknown'}\n"
        f"- Vertical: {vertical or 'unknown'}\n"
        f"- Taxonomy / specialty: {d.get('taxonomy') or 'unknown'}\n"
        f"- City / State: {d.get('city') or ''} {d.get('state') or ''}\n"
        f"- Offer: {offer}\n"
        "Return ONLY the script text, no preamble, no quotes around the whole block."
    )


def _template_fallback(lead: dict) -> str:
    d = lead.get("details") or {}
    v = (lead.get("vertical") or "").lower()
    if "estate" in v:
        return (f"Hi {lead.get('contact')}, this is Mohammed. I know I'm catching you out of the "
                f"blue, do you have 30 seconds? I'm calling about {d.get('address') or 'your property'}. "
                f"We buy homes as-is with a 7-day cash close and zero fees. Are you open to a quick "
                f"cash offer?")
    return (f"Hi {lead.get('contact')}, this is Mohammed. I know this is out of the blue, do you "
            f"have 30 seconds? I run a patient-acquisition engine and I have a list of verified, "
            f"cash-ready patients looking for {d.get('taxonomy') or 'treatment'} in "
            f"{d.get('city') or 'your area'}, and my current partner clinic is full. Are you taking "
            f"new patients at {lead.get('company')}?")


def generate_script(lead: dict) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            from MBM.LeadEngine.nvidia_model_registry import NVIDIAModelRegistry
            nvr = NVIDIAModelRegistry()
            res = nvr.query_model(
                model_id="nvidia/llama-3.3-70b-instruct",
                prompt=_build_prompt(lead),
                system_prompt="You write concise, human, high-converting cold call scripts for sales outreach."
            )
            script_text = res.get("message", "").strip()
            if script_text:
                return {
                    "lead": lead.get("id"),
                    "model": "nvidia/llama-3.3-70b-instruct",
                    "generated": True,
                    "script": script_text
                }
        except Exception:
            pass
        script = _template_fallback(lead)
        return {"lead": lead.get("id"), "model": "template-fallback", "generated": True, "script": script}

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You write concise, human, high-converting cold call scripts."},
            {"role": "user", "content": _build_prompt(lead)},
        ],
        "temperature": 0.7,
        "max_tokens": 350,
    }
    try:
        r = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=40,
        )
        if r.status_code == 200:
            script = r.json()["choices"][0]["message"]["content"].strip()
            return {"lead": lead.get("id"), "model": MODEL, "generated": True, "script": script}
    except Exception:
        pass

    # Fallback to NVIDIA NIM on OpenAI error or quota exhaustion
    try:
        from MBM.LeadEngine.nvidia_model_registry import NVIDIAModelRegistry
        nvr = NVIDIAModelRegistry()
        res = nvr.query_model(
            model_id="nvidia/llama-3.3-70b-instruct",
            prompt=_build_prompt(lead),
            system_prompt="You write concise, human, high-converting cold call scripts for sales outreach."
        )
        script_text = res.get("message", "").strip()
        if script_text:
            return {
                "lead": lead.get("id"),
                "model": "nvidia/llama-3.3-70b-instruct",
                "generated": True,
                "script": script_text
            }
    except Exception:
        pass

    script = _template_fallback(lead)
    return {"lead": lead.get("id"), "model": "template-fallback", "generated": True, "script": script}


def _load_leads():
    data = json.loads(DIALER_LEADS.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("leads", data.get("data", []))


def main():
    _load_env()
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print(_tty("[CGPT] WARNING: OPENAI_API_KEY not set — will use template fallbacks. "
                   "Add it to .env to enable ChatGPT-generated scripts."))

    if "--lead" in sys.argv:
        idx = sys.argv.index("--lead")
        lead = json.loads(sys.argv[idx + 1])
        res = generate_script(lead)
        print(res["script"])
        return

    if "--id" in sys.argv:
        idx = sys.argv.index("--id")
        lead_id = sys.argv[idx + 1]
        leads = _load_leads()
        lead = next((l for l in leads if l.get("id") == lead_id), None)
        if not lead:
            print(_tty(f"[CGPT] No lead with id {lead_id}"))
            sys.exit(1)
        res = generate_script(lead)
        print(res["script"])
        return

    if "--refresh-missing" in sys.argv:
        leads = _load_leads()
        missing = [l for l in leads if not ((l.get("details") or {}).get("Call_Script"))]
        print(_tty(f"[CGPT] {len(leads)} leads, {len(missing)} missing a Call_Script. Generating..."))
        written = 0
        for i, lead in enumerate(missing[:50], 1):
            details = lead.setdefault("details", {})
            details["Call_Script"] = generate_script(lead)["script"]
            written += 1
            if i % 10 == 0:
                print(_tty(f"  ... {i}/{min(len(missing), 50)} done"))
        if "--update-json" in sys.argv:
            sys.path.insert(0, str(ROOT))
            from MBM.LeadEngine.dialer_gateway import commit_dialer_db
            commit_dialer_db(leads, reason="cgpt_script_generator", author="CGPT_SCRIPT_GENERATOR")
            print(_tty(f"[CGPT] Wrote {written} updated scripts back to leads_database.json"))
        else:
            print(_tty(f"[CGPT] Generated {written} scripts in memory (add --update-json to persist)."))
        return

    print(_tty("Usage: see module docstring. Try --id <lead_id> or --refresh-missing."))


if __name__ == "__main__":
    main()
