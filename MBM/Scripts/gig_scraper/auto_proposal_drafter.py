import os
import requests
import json

# Uses the litellm gateway or direct API
# Assuming you use OpenRouter as configured in fcc-server
API_KEY = os.getenv("OPENROUTER_API_KEY", "your_openrouter_key")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def draft_proposal(job_title: str, job_description: str) -> str:
    """
    Takes a job description and uses Claude 3.5 Sonnet to draft a highly customized, winning proposal.
    """
    system_prompt = """
    You are an expert AI Automation Engineer and a top-rated freelancer on Upwork.
    Your goal is to write a short, punchy, and highly persuasive proposal for the given job.
    
    Rules for the proposal:
    1. Start with a direct, custom hook (no "Dear Hiring Manager").
    2. Acknowledge their specific problem from the job description.
    3. Briefly mention your relevant tech stack (FastAPI, Vapi, LangGraph, Python).
    4. Provide a 2-step plan of how you will solve it.
    5. Call to action to jump on a quick 10-minute discovery call.
    6. Keep it under 200 words.
    """
    
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Job Title: {job_title}\n\nJob Description: {job_description}\n\nDraft the proposal:"}
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response_data = response.json()
        
        if "choices" in response_data:
            return response_data["choices"][0]["message"]["content"]
        else:
            return f"Error drafting proposal: {response_data}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    # Test the drafter
    sample_title = "Need an AI Voice Agent for my Dental Clinic"
    sample_desc = "We miss a lot of calls when the receptionist is busy. We want an AI to answer the phone, answer basic questions like our hours and pricing, and book appointments in our Google Calendar."
    
    print("Drafting proposal for:", sample_title)
    print("-" * 50)
    proposal = draft_proposal(sample_title, sample_desc)
    print(proposal)
