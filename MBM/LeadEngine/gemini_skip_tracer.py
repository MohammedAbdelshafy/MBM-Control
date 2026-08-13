import os
import json
import logging
from google import genai
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure we have the API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your .env file.")

client = genai.Client(api_key=api_key)

def autonomous_skip_trace(name, address, city):
    """
    Uses Gemini 2.5 Flash with native Google Search grounding to autonomously 
    skip trace a property owner when free scrapers fail.
    """
    query = f"Find the real personal phone number and email address for {name} who owns property at {address}, {city}. Search public records, real estate directories, or business registrations."
    
    try:
        logging.info(f"Initiating autonomous Gemini search for {name}...")
        
        # We use generate_content with google_search tool for live web access
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=query,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], # Enable native search grounding
                temperature=0.1,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "phone": {"type": "STRING", "description": "The exact phone number found, or null if absolutely not found."},
                        "email": {"type": "STRING", "description": "The email address found, or null."},
                        "confidence": {"type": "STRING", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "sources_used": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "URLs or domains where this was found."}
                    }
                }
            )
        )
        
        # Parse the structured JSON response
        data = json.loads(response.text)
        return data

    except Exception as e:
        logging.error(f"Gemini Skip Trace Failed: {e}")
        return None

if __name__ == "__main__":
    # Test the agent
    print("Testing Autonomous Gemini Skip Tracer...")
    result = autonomous_skip_trace(name="Charles Brown", address="12124 SCHROEDER RD", city="DALLAS")
    print(json.dumps(result, indent=2))
