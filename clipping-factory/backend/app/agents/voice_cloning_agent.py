import os
import json
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VoiceCloningAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logging.error("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def generate_voiceover(self, script, output_path="voiceover.mp3"):
        """
        Uses Gemini 2.5 Flash Audio capabilities to generate a voiceover for the given script.
        """
        if not self.client:
            logging.error("Agent not initialized properly.")
            return False
            
        logging.info(f"Generating voiceover for script: {script[:50]}...")
        
        try:
            # We use the Audio modality of Gemini 2.5
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Read the following script with high energy and professionalism:\n\n{script}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    temperature=0.3
                )
            )
            
            # The response will contain an inline audio blob
            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                if part.inline_data:
                    audio_data = part.inline_data.data
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    logging.info(f"Successfully wrote audio to {output_path}")
                    return True
            
            logging.error("No audio returned in the response.")
            return False
            
        except Exception as e:
            logging.error(f"Failed to generate voiceover: {e}")
            return False

if __name__ == "__main__":
    agent = VoiceCloningAgent()
    script = "Hi there! I'm calling about the property at 123 Main Street. Are you the owner?"
    agent.generate_voiceover(script, output_path="test_intro.mp3")
