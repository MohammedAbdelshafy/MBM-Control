import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MBM AI Realtime Objection Handling Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        pass

gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        pass


class ObjectionRequest(BaseModel):
    objection: str
    script: str = "Standard cold call pitch"
    lead_name: str = "Prospect"
    company: str = "Company"


@app.post("/api/objection")
async def handle_objection(req: ObjectionRequest):
    prompt = f"""
    You are an elite, high-ticket cold calling sales closer (Jordan Belfort + Chris Voss caliber).
    You are on a live phone call with prospect {req.lead_name} from {req.company}.

    Current pitch: "{req.script}"
    Prospect objection: "{req.objection}"

    Give me the EXACT, 1-2 sentence conversational response to say out loud right now to overcome this objection, pattern-interrupt them, and secure the next micro-commitment.
    NO fluff, NO greetings, NO quotation marks. Just the exact conversational words to speak.
    """

    # 1. Try Groq LPU (Sub-second latency)
    if groq_client:
        try:
            chat = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a master cold calling tele-closer. Output only the exact words to say."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=150
            )
            return {"response": chat.choices[0].message.content.strip().strip('"')}
        except Exception as ge:
            print(f"[WARN] Groq error: {ge}")

    # 2. Try NVIDIA NIM (TensorRT-LLM accelerated Llama-3.3-70B / Nemotron)
    if NVIDIA_API_KEY and not NVIDIA_API_KEY.startswith("nvapi-demo"):
        try:
            import urllib.request
            import json
            payload = {
                "model": "meta/llama-3.3-70b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a master cold calling tele-closer. Output only the exact words to say."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 150
            }
            req_nv = urllib.request.Request(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_nv, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"response": data["choices"][0]["message"]["content"].strip().strip('"')}
        except Exception as nve:
            print(f"[WARN] NVIDIA NIM error: {nve}")

    # 3. Fallback to Gemini
    if gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return {"response": response.text.strip().strip('"')}
        except Exception as gme:
            print(f"[WARN] Gemini error: {gme}")

    # 3. Rule-based offline fallback
    obj_lower = req.objection.lower()
    if "not interested" in obj_lower or "not selling" in obj_lower:
        return {"response": f"Totally understand {req.lead_name}. Just so I update our records, are you holding onto it long term, or is there a specific number down the road where letting it go would make sense?"}
    elif "offer" in obj_lower or "price" in obj_lower or "how much" in obj_lower:
        return {"response": f"Because we pay cash and cover all closing fees as-is, my offer depends on current condition. If we closed next week with zero fees, what ballpark number were you hoping to walk away with?"}
    elif "email" in obj_lower or "mail" in obj_lower:
        return {"response": f"I'd be glad to send an email! What's the best address for you? If our cash terms meet your expectations, would you be ready to review the contract this week?"}
    elif "who" in obj_lower or "number" in obj_lower:
        return {"response": f"We pull public county tax assessor records and cross-reference with local business registries. I'm a real private buyer, not a call center."}

    return {"response": f"I completely understand {req.lead_name}. If I could show you how we can close in 7 days with zero fees, would you be open to a 30-second summary?"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3005)
