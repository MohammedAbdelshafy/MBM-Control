import json, requests, os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("RETELL_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

with open("MBM/LeadEngine/logs/retell_deployments.json") as f:
    deployments = json.load(f)

deployed_names = {d["name"] for d in deployments if d["status"] == "deployed"}

with open("MBM/voice_agent_scripts.json") as f:
    agents = json.load(f)["agents"]

voice_map = {
    "Buyer Qualifier": "retell-Willa",
    "Commercial Lead Qualifier": "retell-Alejandro",
    "E-Commerce Upsell": "retell-Nico"
}

for agent in agents:
    if agent["name"] in deployed_names:
        print(f"Skipping {agent['name']} - already deployed")
        continue

    voice_id = voice_map.get(agent["name"], "retell-Willa")

    prompt = agent["script"]["greeting"] + "\n\nScript flow:\n"
    prompt += f"If YES: {agent['script']['if_yes']}\n"
    prompt += f"If NO: {agent['script']['if_no']}\n"
    prompt += f"Closing: {agent['script']['closing']}\n\n"
    prompt += "Qualification questions:\n"
    prompt += "\n".join("- " + q for q in agent["script"]["qualification_questions"])

    r = requests.post("https://api.retellai.com/create-retell-llm", headers=headers, json={"model": "gemini-2.0-flash", "general_prompt": prompt})
    if r.status_code not in (200, 201):
        print(f"Failed LLM for {agent['name']}: {r.status_code}")
        continue
    llm_id = r.json()["llm_id"]
    print(f"Created LLM: {llm_id}")

    r = requests.post("https://api.retellai.com/create-agent", headers=headers, json={
        "agent_name": agent["name"],
        "voice_id": voice_id,
        "response_engine": {"type": "retell-llm", "llm_id": llm_id}
    })
    if r.status_code in (200, 201):
        agent_id = r.json()["agent_id"]
        deployments.append({"name": agent["name"], "retell_agent_id": agent_id, "llm_id": llm_id, "status": "deployed"})
        print(f"Deployed: {agent['name']} -> {agent_id}")
    else:
        print(f"Failed: {agent['name']} -> {r.status_code}: {r.text[:100]}")

with open("MBM/LeadEngine/logs/retell_deployments.json", "w") as f:
    json.dump(deployments, f, indent=2)

print(f"\nTotal deployed: {sum(1 for d in deployments if d['status']=='deployed')}")
