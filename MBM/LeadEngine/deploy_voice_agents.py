#!/usr/bin/env python3
"""
MBM Voice Agent Deployer
Deploys voice agents to Retell AI, Synthflow, Vapi, and ElevenLabs.
Usage: python deploy_voice_agents.py --platform retell|synthflow|vapi|elevenlabs|all
"""

import json
import os
import sys
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_FILE = ROOT / "MBM" / "voice_agent_scripts.json"
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_scripts():
    with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["agents"]


def deploy_retell(agents):
    api_key = os.getenv("RETELL_API_KEY")
    if not api_key:
        print("[!] RETELL_API_KEY not set in .env")
        print("    Sign up at https://retellai.com -> Dashboard -> API Keys")
        return False

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    results = []

    for agent in agents:
        # Step 1: Create the LLM first
        llm_prompt = agent["script"]["greeting"] + "\n\n" + \
            "Script flow:\n" + \
            f"If YES: {agent['script']['if_yes']}\n" + \
            f"If NO: {agent['script']['if_no']}\n" + \
            f"If needs time: {agent['script'].get('if_needs_time', 'Would you like me to check back later?')}\n" + \
            f"Closing: {agent['script']['closing']}\n\n" + \
            "Qualification questions:\n" + \
            "\n".join(f"- {q}" for q in agent["script"]["qualification_questions"])

        llm_payload = {
            "model": "gemini-2.0-flash",
            "general_prompt": llm_prompt
        }

        try:
            r = requests.post("https://api.retellai.com/create-retell-llm", headers=headers, json=llm_payload, timeout=30)
            if r.status_code not in (200, 201):
                results.append({"name": agent["name"], "status": "failed", "error": f"LLM creation failed: {r.text[:100]}"})
                print(f"  [-] Failed LLM: {agent['name']} -> {r.status_code}: {r.text[:100]}")
                continue
            llm_data = r.json()
            llm_id = llm_data.get("llm_id")
            print(f"  [+] Created LLM: {llm_id}")
        except Exception as e:
            results.append({"name": agent["name"], "status": "error", "error": str(e)})
            print(f"[!] Error creating LLM: {agent['name']} -> {e}")
            continue

        # Step 2: Create the agent with the LLM
        agent_payload = {
            "agent_name": agent["name"],
            "voice_id": agent["voice_id"],
            "response_engine": {
                "type": "retell-llm",
                "llm_id": llm_id
            }
        }

        try:
            r = requests.post("https://api.retellai.com/create-agent", headers=headers, json=agent_payload, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                agent_id = data.get("agent_id", "unknown")
                results.append({"name": agent["name"], "retell_agent_id": agent_id, "llm_id": llm_id, "status": "deployed"})
                print(f"  [+] Deployed: {agent['name']} -> {agent_id}")
            else:
                results.append({"name": agent["name"], "status": "failed", "error": r.text[:200]})
                print(f"  [-] Failed: {agent['name']} -> {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results.append({"name": agent["name"], "status": "error", "error": str(e)})
            print(f"  [!] Error: {agent['name']} -> {e}")

    with open(LOGS_DIR / "retell_deployments.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Results saved to logs/retell_deployments.json")
    return True


def deploy_synthflow(agents):
    api_key = os.getenv("SYNTHFLOW_API_KEY") or os.getenv("SYNTHFLOW_TOKEN")
    if not api_key:
        print("[!] SYNTHFLOW_API_KEY not set in .env")
        print("    Sign up at https://synthflow.ai - Settings - API Keys")
        return False

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    results = []

    for agent in agents:
        payload = {
            "name": agent["name"],
            "prompt": agent["script"]["greeting"] + "\n\n" +
                "Qualification flow:\n" +
                f"Yes path: {agent['script']['if_yes']}\n" +
                f"No path: {agent['script']['if_no']}\n" +
                f"Close: {agent['script']['closing']}"
        }

        try:
            r = requests.post("https://api.synthflow.ai/v1/agents", headers=headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                agent_id = data.get("id", "unknown")
                results.append({"name": agent["name"], "synthflow_agent_id": agent_id, "status": "deployed"})
                print(f"[+] Deployed: {agent['name']} - {agent_id}")
            else:
                results.append({"name": agent["name"], "status": "failed", "error": r.text[:200]})
                print(f"[-] Failed: {agent['name']} - {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results.append({"name": agent["name"], "status": "error", "error": str(e)})
            print(f"[!] Error: {agent['name']} - {e}")

    with open(LOGS_DIR / "synthflow_deployments.json", "w") as f:
        json.dump(results, f, indent=2)
    return True


def deploy_vapi(agents):
    api_key = os.getenv("VAPI_API_KEY") or os.getenv("VAPI_TOKEN")
    if not api_key:
        print("[!] VAPI_API_KEY not set in .env")
        print("    Sign up at https://vapi.ai - Dashboard - API Keys")
        return False

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    results = []

    for agent in agents:
        payload = {
            "name": agent["name"],
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": agent["script"]["greeting"] + "\n\n" +
                        "You are confirming if the lead is still interested.\n" +
                        f"If YES: {agent['script']['if_yes']}\n" +
                        f"If NO: {agent['script']['if_no']}\n" +
                        f"Close: {agent['script']['closing']}"}
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId": agent["voice_id"]
            }
        }

        try:
            r = requests.post("https://api.vapi.ai/assistant", headers=headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                assistant_id = data.get("id", "unknown")
                results.append({"name": agent["name"], "vapi_assistant_id": assistant_id, "status": "deployed"})
                print(f"[+] Deployed: {agent['name']} - {assistant_id}")
            else:
                results.append({"name": agent["name"], "status": "failed", "error": r.text[:200]})
                print(f"[-] Failed: {agent['name']} - {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results.append({"name": agent["name"], "status": "error", "error": str(e)})
            print(f"[!] Error: {agent['name']} - {e}")

    with open(LOGS_DIR / "vapi_deployments.json", "w") as f:
        json.dump(results, f, indent=2)
    return True


def deploy_elevenlabs(agents):
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[!] ELEVENLABS_API_KEY not set in .env")
        print("    Sign up at https://elevenlabs.io - Profile - API Keys")
        return False

    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    results = []

    for agent in agents:
        payload = {
            "name": agent["name"],
            "description": f"MBM Voice Agent - {agent['purpose']}",
            "prompt": agent["script"]["greeting"],
            "first_message": agent["script"]["greeting"]
        }

        try:
            r = requests.post("https://api.elevenlabs.io/v1/convai/agents", headers=headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                agent_id = data.get("agent_id", "unknown")
                results.append({"name": agent["name"], "elevenlabs_agent_id": agent_id, "status": "deployed"})
                print(f"[+] Deployed: {agent['name']} - {agent_id}")
            else:
                results.append({"name": agent["name"], "status": "failed", "error": r.text[:200]})
                print(f"[-] Failed: {agent['name']} - {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results.append({"name": agent["name"], "status": "error", "error": str(e)})
            print(f"[!] Error: {agent['name']} - {e}")

    with open(LOGS_DIR / "elevenlabs_deployments.json", "w") as f:
        json.dump(results, f, indent=2)
    return True


DEPLOYERS = {
    "retell": deploy_retell,
    "synthflow": deploy_synthflow,
    "vapi": deploy_vapi,
    "elevenlabs": deploy_elevenlabs,
}


def main():
    parser = argparse.ArgumentParser(description="Deploy MBM voice agents to platforms")
    parser.add_argument("--platform", "-p", required=True, choices=list(DEPLOYERS.keys()) + ["all"])
    args = parser.parse_args()

    agents = load_scripts()
    print(f"[*] Loaded {len(agents)} voice agent scripts")

    if args.platform == "all":
        for name, deployer in DEPLOYERS.items():
            print(f"\n{'='*50}")
            print(f"  Deploying to {name.upper()}")
            print(f"{'='*50}")
            deployer(agents)
    else:
        DEPLOYERS[args.platform](agents)


if __name__ == "__main__":
    main()
