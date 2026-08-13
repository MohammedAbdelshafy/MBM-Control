from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from google import genai
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MBM Gemini Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is missing!")
    
client = genai.Client(api_key=api_key)

class ObjectionRequest(BaseModel):
    objection: str
    script: str
    lead_name: str
    company: str

@app.post("/api/objection")
async def handle_objection(req: ObjectionRequest):
    prompt = f"""
    You are an expert, world-class cold calling sales closer. 
    You are currently on the phone with a prospect named {req.lead_name} from {req.company}.
    
    Here is the script you were using:
    "{req.script}"
    
    The prospect just gave you this objection:
    "{req.objection}"
    
    Give me the EXACT, 1-2 sentence conversational response I should say right now to overcome this objection and keep the call moving forward. 
    Do NOT include any greetings or commentary. Just the exact words to say out loud. Be persuasive, confident, and empathetic.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"response": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3005)
