import os
import json
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AgencyProspector:
    """
    B2B Outreach Agent for the AI Clipping & Voice Agency.
    Targets YouTubers and Podcasters, analyzes their content, and drafts 
    hyper-personalized pitch emails offering free AI-generated clips as a lead magnet.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logging.error("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def find_prospects(self, niche="Business Podcasts"):
        """Mock scraping YouTube or podcast directories for ideal clients."""
        logging.info(f"Scanning for ideal targets in niche: {niche}...")
        # In a real system, this would use the YouTube Data API or SerpApi
        return [
            {
                "name": "Alex Entrepreneur",
                "channel": "The Builder's Journey",
                "subscribers": 45000,
                "latest_video": "How to scale your SaaS to $10M",
                "email": "alex@example.com"
            },
            {
                "name": "Sarah Tech",
                "channel": "Tech Founder Insights",
                "subscribers": 12000,
                "latest_video": "The future of AI engineering",
                "email": "sarah@example.com"
            }
        ]

    def draft_pitch(self, prospect):
        if not self.client:
            return "Mock Pitch due to missing API key."

        prompt = f"""
        You are the founder of an elite AI Clipping & Voice Agency.
        Write a highly personalized, concise cold email to this podcaster:
        Name: {prospect['name']}
        Channel: {prospect['channel']}
        Latest Video: {prospect['latest_video']}

        The pitch: We ran your latest episode through our proprietary AI engine. 
        It found 4 viral hooks. We completely edited, captioned, and color-graded one of them for you.
        It's attached below, completely free for you to post.
        Call to action: Let's automate this for every episode. Do you have 10 mins next week?
        Keep it under 150 words. No corporate jargon. Sound like a peer.
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            logging.error(f"Failed to generate pitch: {e}")
            return "Error generating pitch."

    def run(self):
        prospects = self.find_prospects()
        for p in prospects:
            logging.info(f"Drafting pitch for {p['name']} ({p['channel']})...")
            pitch = self.draft_pitch(p)
            print("-" * 50)
            print(f"To: {p['email']}")
            print(f"Subject: I made a viral short from '{p['latest_video']}'")
            print("-" * 50)
            print(pitch)
            print("=" * 50)

if __name__ == "__main__":
    prospector = AgencyProspector()
    prospector.run()
