import os
import json
import logging
from google import genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PainPointAppGenerator:
    """
    Automated Lead Magnet Generator.
    Scrapes a target company, identifies an operational inefficiency,
    and uses Gemini to write a functioning micro-app prototype that solves it.
    The prototype is then sent to the company as an irresistible B2B pitch.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logging.error("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def analyze_company(self, domain: str):
        """Mock analyzing a company's public presence to find inefficiencies."""
        logging.info(f"Scanning {domain} for operational pain points...")
        # In a real scenario, this would use Firecrawl to read their site/careers page
        return {
            "company": domain,
            "pain_point": "High customer support volume for basic pricing and policy questions.",
            "proposed_solution": "An automated AI Support Agent trained specifically on their docs."
        }

    def generate_app_code(self, analysis: dict):
        """Uses Gemini to generate the actual code for the prototype app."""
        if not self.client:
            return "// Mock Code: API Key Missing"

        logging.info(f"Generating micro-app code to solve: {analysis['proposed_solution']}")
        prompt = f"""
        You are an elite AI agency developer.
        A prospective client ({analysis['company']}) has this pain point: {analysis['pain_point']}
        We are proposing this solution: {analysis['proposed_solution']}
        
        Write a single-file React component (using Tailwind CSS) that acts as a sleek, 
        functioning UI for this solution. Make it look premium. 
        Only output the code, no markdown wrapping.
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text.replace("```jsx", "").replace("```", "").strip()
        except Exception as e:
            logging.error(f"Failed to generate app code: {e}")
            return "// Error generating code."

    def build_pitch(self, analysis: dict, code: str):
        """Saves the prototype to disk and drafts the cold email."""
        output_dir = "generated_apps"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{analysis['company'].replace('.', '_')}_prototype.jsx"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(code)
            
        pitch = f"""
Subject: I built an AI agent to fix your support volume

Hi Team at {analysis['company']},

I noticed you might be dealing with {analysis['pain_point']}.
Instead of a long pitch, I just went ahead and built a custom AI micro-app to solve this for you. 

I've attached the working prototype code ({filename}).
Let's get on a 10-minute call next week, and I'll show you how we can deploy this live on your site to automate your workflow.

Best,
MBM AI Agency
"""
        logging.info(f"Saved prototype to {filepath}")
        return pitch

    def run(self, target_domain="example.com"):
        print(f"=== Starting Pain-Point App Generation for {target_domain} ===")
        analysis = self.analyze_company(target_domain)
        code = self.generate_app_code(analysis)
        pitch = self.build_pitch(analysis, code)
        
        print("\n" + "="*50)
        print("READY TO SEND PITCH:")
        print("="*50)
        print(pitch)
        print("="*50)
        
        self.dispatch_email(analysis, pitch)
        
    def dispatch_email(self, analysis: dict, pitch: str):
        """Finds the CEO via FreeSkipTracer and queues the email."""
        try:
            from free_skip_tracer import FreeSkipTracer
            import requests
            
            tracer = FreeSkipTracer()
            # Mocking CEO lookup for demo. In reality, we'd use a LinkedIn API here.
            ceo_name = "Alex Founder"
            print(f"[Executive Targeting] Found CEO: {ceo_name}")
            
            # Use skip tracer to try and find the email
            # FreeSkipTracer primarily uses physical addresses, but we can mock an email hit
            result = tracer.find_contact(name=ceo_name, address=analysis['company'], city="Remote")
            
            target_email = "ceo@" + analysis['company']
            if result and result.get('email'):
                target_email = result['email']
                
            print(f"[Executive Targeting] Resolved Email: {target_email}")
            
            # Send to backend
            payload = {
                "recipient_email": target_email,
                "subject": f"I built an AI agent to fix your support volume",
                "body": pitch
            }
            
            resp = requests.post("http://localhost:3002/api/email-queue", json=payload)
            if resp.status_code == 200:
                print(f"[Email Dispatch] Successfully queued pitch to {target_email} in backend.")
            else:
                print(f"[Email Dispatch] Failed to queue email: {resp.text}")
                
        except Exception as e:
            print(f"[Email Dispatch] Error: {e}")

if __name__ == "__main__":
    generator = PainPointAppGenerator()
    generator.run(target_domain="acme-corp.com")
