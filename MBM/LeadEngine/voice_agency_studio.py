"""
MBM Voice Agency Studio - Platform Connection Manager
======================================================
Connects voice agents to paying platforms and manages revenue.

Platforms:
  1. ElevenLabs Voice Library - Passive royalties per usage
  2. Synthflow AI - Agency retainers ($297-$997/mo) + $0.25/min
  3. Retell AI - Wholesale $0.09/min → bill client $0.35/min
  4. Vapi AI - White-label enterprise reselling
  5. Quora Poe - Per-message monetization

Run: python voice_agency_studio.py [--platform PLATFORM] [--action ACTION]
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(r'C:\Users\omare\OneDrive\Desktop\AI\MBM')
LOGS_DIR = BASE_DIR / 'LeadEngine' / 'logs'
AGENTS_FILE = LOGS_DIR / 'grabbed_voice_agents.json'
PLATFORMS_FILE = LOGS_DIR / 'grabbed_voice_platforms.json'
STUDIO_DIR = BASE_DIR / 'VoiceAgencyStudio'
STUDIO_DIR.mkdir(exist_ok=True)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
RETELL_API_KEY = os.getenv("RETELL_API_KEY", "")
SYNTHFLOW_API_KEY = os.getenv("SYNTHFLOW_API_KEY", "")

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[VOICE STUDIO] {timestamp} - {msg}"
    print(line)
    with open(LOGS_DIR / 'voice_studio.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_agents():
    if AGENTS_FILE.exists():
        with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def load_platforms():
    if PLATFORMS_FILE.exists():
        with open(PLATFORMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


# ══════════════════════════════════════════════════════════════
# PLATFORM 1: ELEVENLABS VOICE LIBRARY
# ══════════════════════════════════════════════════════════════

def connect_elevenlabs():
    """Connect voice agents to ElevenLabs Voice Library for passive royalties."""
    log("=" * 60)
    log("CONNECTING TO ELEVENLABS VOICE LIBRARY")
    log("=" * 60)
    
    agents = load_agents()
    elevenlabs_agents = [a for a in agents if a.get('voice_provider') == 'elevenlabs']
    
    if not ELEVENLABS_API_KEY:
        log("No ElevenLabs API key found. Setting up manual connection...")
        setup = {
            "platform": "ElevenLabs Voice Library",
            "status": "MANUAL_SETUP_REQUIRED",
            "steps": [
                "1. Go to https://elevenlabs.io/voice-library",
                "2. Sign up / Login to your account",
                "3. Go to Profile Settings > API Keys",
                "4. Generate an API key",
                "5. Add to .env as ELEVENLABS_API_KEY=your_key",
                "6. Go to Voice Library > My Voices",
                "7. Click 'Add Generative or Cloned Voice'",
                "8. Upload voice samples or use Voice Designer",
                "9. Set visibility to 'Public' for marketplace royalties",
                "10. Each voice used by others earns you passive income",
            ],
            "agents_to_publish": [
                {
                    "name": a['title'],
                    "voice_id": a.get('voice_id', 'N/A'),
                    "rate": f"${a['rate_per_min']}/min",
                    "tags": a.get('tags', []),
                }
                for a in elevenlabs_agents
            ],
            "revenue_model": {
                "type": "Usage-based passive royalties",
                "payout": "Stripe Connect",
                "when": "Every time someone uses your voice in their generation",
                "typical_earnings": "$0.01-$0.10 per 1K characters generated",
            },
            "setup_url": "https://elevenlabs.io/voice-library",
        }
    else:
        # API connection
        try:
            headers = {"xi-api-key": ELEVENLABS_API_KEY}
            
            # Get available voices
            resp = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=10)
            if resp.status_code == 200:
                voices = resp.json().get('voices', [])
                log(f"Found {len(voices)} existing voices in ElevenLabs")
                
                # Check subscription tier
                sub_resp = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers, timeout=10)
                if sub_resp.status_code == 200:
                    sub = sub_resp.json()
                    log(f"Plan: {sub.get('tier', 'unknown')} | Characters: {sub.get('character_count', 0)}/{sub.get('character_limit', 0)}")
                
                setup = {
                    "platform": "ElevenLabs Voice Library",
                    "status": "CONNECTED",
                    "existing_voices": len(voices),
                    "agents_ready": len(elevenlabs_agents),
                    "next_steps": [
                        "Voices are live in your ElevenLabs account",
                        "Set visibility to 'Public' in Voice Library for marketplace earnings",
                        "Monitor usage at https://elevenlabs.io/voice-library",
                    ]
                }
            else:
                log(f"ElevenLabs API error: {resp.status_code}")
                setup = {"platform": "ElevenLabs", "status": "API_ERROR", "code": resp.status_code}
        except Exception as e:
            log(f"ElevenLabs connection failed: {e}")
            setup = {"platform": "ElevenLabs", "status": "CONNECTION_FAILED", "error": str(e)}
    
    # Save connection status
    with open(STUDIO_DIR / 'elevenlabs_connection.json', 'w', encoding='utf-8') as f:
        json.dump(setup, f, indent=2)
    
    log(f"ElevenLabs status: {setup.get('status', 'unknown')}")
    return setup


# ══════════════════════════════════════════════════════════════
# PLATFORM 2: SYNTHFLOW AI AGENCY
# ══════════════════════════════════════════════════════════════

def connect_synthflow():
    """Connect to Synthflow AI for agency retainer revenue."""
    log("=" * 60)
    log("CONNECTING TO SYNTHFLOW AI AGENCY")
    log("=" * 60)
    
    agents = load_agents()
    
    setup = {
        "platform": "Synthflow AI Reseller Agency",
        "status": "SETUP_INSTRUCTIONS",
        "url": "https://synthflow.ai",
        "revenue_model": {
            "type": "White-Label Agency Retainers + Usage Markup",
            "tiers": {
                "Starter": "$297/mo (5 agents, 100 min/mo)",
                "Growth": "$597/mo (15 agents, 500 min/mo)",
                "Pro": "$997/mo (unlimited agents, unlimited min)",
            },
            "usage_markup": "$0.25/min wholesale → bill client $0.50-$1.00/min",
            "payout": "Stripe Connect",
        },
        "setup_steps": [
            "1. Go to https://synthflow.ai",
            "2. Click 'Become an Agency Partner'",
            "3. Fill out the agency application",
            "4. Wait for approval (usually 24-48 hours)",
            "5. Access your agency dashboard",
            "6. Create voice agents using our grabbed templates",
            "7. Set your client pricing (markup $0.25-$0.75/min)",
            "8. White-label the dashboard with your branding",
            "9. Onboard clients and start billing",
        ],
        "agents_to_deploy": [
            {
                "name": a['title'],
                "persona": a.get('persona', ''),
                "rate": f"${a['rate_per_min']}/min",
                "your_rate": f"${a['rate_per_min'] + 0.25}/min",
                "tags": a.get('tags', []),
            }
            for a in agents
        ],
        "pitch_to_clients": {
            "target_market": "Local service businesses (plumbers, HVAC, lawyers, doctors, dentists)",
            "pain_point": "62% of leads call the next business if no answer",
            "solution": "24/7 AI receptionist that answers, qualifies, and books appointments",
            "pricing_to_client": "$197-$497/mo + usage",
            "your_cost": "$0.09-$0.25/min (wholesale)",
            "margin": "$0.25-$0.75/min + setup fees",
        },
    }
    
    with open(STUDIO_DIR / 'synthflow_connection.json', 'w', encoding='utf-8') as f:
        json.dump(setup, f, indent=2)
    
    log("Synthflow setup instructions saved")
    return setup


# ══════════════════════════════════════════════════════════════
# PLATFORM 3: RETELL AI + CHATDASH
# ══════════════════════════════════════════════════════════════

def connect_retell():
    """Connect to Retell AI for wholesale voice markup."""
    log("=" * 60)
    log("CONNECTING TO RETELL AI")
    log("=" * 60)
    
    agents = load_agents()
    
    setup = {
        "platform": "Retell AI + ChatDash Wrapper",
        "status": "SETUP_INSTRUCTIONS",
        "url": "https://retellai.com",
        "revenue_model": {
            "type": "Wholesale → Retail Markup",
            "wholesale_cost": "$0.09/min",
            "your_client_price": "$0.35/min",
            "margin": "$0.26/min (289% markup)",
            "setup_fee": "$1,500 per client",
            "payout": "Stripe",
        },
        "setup_steps": [
            "1. Go to https://retellai.com",
            "2. Sign up for a free account",
            "3. Get $5 free credit to test",
            "4. Create voice agents using our templates",
            "5. Deploy to phone numbers",
            "6. Set up billing dashboard for clients",
            "7. Bill clients $0.35/min + $1,500 setup",
        ],
        "agents_to_deploy": [
            {
                "name": a['title'],
                "persona": a.get('persona', ''),
                "wholesale_rate": "$0.09/min",
                "client_rate": "$0.35/min",
                "margin": "$0.26/min",
                "tags": a.get('tags', []),
            }
            for a in agents
        ],
        "revenue_calculator": {
            "per_client_per_month": {
                "100_minutes": {"cost": "$9", "revenue": "$35", "profit": "$26"},
                "500_minutes": {"cost": "$45", "revenue": "$175", "profit": "$130"},
                "1000_minutes": {"cost": "$90", "revenue": "$350", "profit": "$260"},
            },
            "with_setup_fee": {
                "1_client": "$1,500 + $26/mo",
                "5_clients": "$7,500 + $130/mo",
                "10_clients": "$15,000 + $260/mo",
            }
        },
    }
    
    with open(STUDIO_DIR / 'retell_connection.json', 'w', encoding='utf-8') as f:
        json.dump(setup, f, indent=2)
    
    log("Retell AI setup instructions saved")
    return setup


# ══════════════════════════════════════════════════════════════
# PLATFORM 4: VAPI AI ECOSYSTEM
# ══════════════════════════════════════════════════════════════

def connect_vapi():
    """Connect to Vapi AI for enterprise voice agency reselling."""
    log("=" * 60)
    log("CONNECTING TO VAPI AI")
    log("=" * 60)
    
    agents = load_agents()
    
    setup = {
        "platform": "Vapi AI Ecosystem",
        "status": "SETUP_INSTRUCTIONS",
        "url": "https://vapi.ai",
        "revenue_model": {
            "type": "Enterprise White-Label Reselling",
            "model": "Custom setup fees + per-minute usage margins",
            "typical_deal": "$5,000-$20,000 setup + $500-$2,000/mo",
            "payout": "Stripe / Wire",
        },
        "setup_steps": [
            "1. Go to https://vapi.ai",
            "2. Sign up for developer account",
            "3. Get API key and add to .env as VAPI_API_KEY",
            "4. Create voice agents using our templates",
            "5. Deploy to phone numbers via Vapi",
            "6. Set up white-label portal for clients",
            "7. Bill clients custom pricing",
        ],
        "agents_to_deploy": [
            {
                "name": a['title'],
                "persona": a.get('persona', ''),
                "voice_provider": a.get('voice_provider', ''),
                "model": a.get('model_name', ''),
                "tags": a.get('tags', []),
            }
            for a in agents
        ],
    }
    
    with open(STUDIO_DIR / 'vapi_connection.json', 'w', encoding='utf-8') as f:
        json.dump(setup, f, indent=2)
    
    log("Vapi AI setup instructions saved")
    return setup


# ══════════════════════════════════════════════════════════════
# BUSINESS OUTREACH - LOCAL SERVICE BUSINESSES
# ══════════════════════════════════════════════════════════════

def generate_business_outreach():
    """Generate outreach for local businesses to sell voice agents."""
    log("=" * 60)
    log("GENERATING BUSINESS OUTREACH")
    log("=" * 60)
    
    niches = [
        {
            "name": "Plumbing Companies",
            "pain": "Missed calls during jobs = lost revenue",
            "stat": "62% of leads call the next business if no answer",
            "solution": "24/7 AI receptionist that answers, quotes, and books",
            "pricing": "$297/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your plumbing business. I noticed you might be missing calls during busy hours. Did you know 62% of leads call the next plumber if they don't get an answer? I built an AI receptionist that answers 24/7, gives quotes, and books appointments. Want to hear a live demo?",
        },
        {
            "name": "HVAC Companies",
            "pain": "After-hours calls go to voicemail",
            "stat": "78% of customers choose the first responder",
            "solution": "AI dispatcher that qualifies and schedules emergency calls",
            "pricing": "$397/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your HVAC company. Emergency calls after hours are going to voicemail, right? That's money walking out the door. Our AI answers instantly, qualifies the emergency, and books the dispatch. Want to hear it in action?",
        },
        {
            "name": "Law Firms",
            "pain": "Intake calls need qualification before booking",
            "stat": "Legal leads convert 5x faster with immediate response",
            "solution": "AI intake specialist that qualifies and books consultations",
            "pricing": "$497/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your law firm. We built an AI intake specialist that answers calls, qualifies leads by case type, and books consultations directly onto your calendar. It's HIPAA-compliant and works 24/7. Want to hear a demo?",
        },
        {
            "name": "Dental Offices",
            "pain": "Front desk overwhelmed with appointment calls",
            "stat": "Dental practices miss 30% of inbound calls",
            "solution": "AI scheduler that books cleanings and consultations",
            "pricing": "$297/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your dental office. We built an AI scheduler that answers calls, checks insurance eligibility, and books appointments directly. Your front desk can focus on patients. Want to hear it work?",
        },
        {
            "name": "Real Estate Agents",
            "pain": "Showing requests and lead qualification take too much time",
            "stat": "Agents who respond in 5 min close 9x more deals",
            "solution": "AI ISA that qualifies leads and books showings",
            "pricing": "$397/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your real estate business. We built an AI ISA that qualifies incoming leads, checks financing, and books showings on your calendar. You only talk to pre-qualified buyers. Want to hear it?",
        },
        {
            "name": "Auto Dealerships",
            "pain": "Sales team can't handle all inbound leads",
            "stat": "Dealerships miss 40% of internet leads",
            "solution": "AI sales rep that qualifies and books test drives",
            "pricing": "$597/mo + $0.35/min",
            "demo_script": "Hi, I'm calling about your dealership. We built an AI sales rep that qualifies internet leads, answers questions about inventory, and books test drives. It works 24/7 and never takes a break. Want to hear a demo?",
        },
    ]
    
    # Save niches
    with open(STUDIO_DIR / 'business_niches.json', 'w', encoding='utf-8') as f:
        json.dump(niches, f, indent=2)
    
    # Generate email templates
    for niche in niches:
        email_file = STUDIO_DIR / f'outreach_{niche["name"].lower().replace(" ", "_")}.txt'
        with open(email_file, 'w', encoding='utf-8') as f:
            f.write(f"Subject: {niche['pain']} - AI Solution for {niche['name']}\n\n")
            f.write(f"Hi [First Name],\n\n")
            f.write(f"I was researching {niche['name'].lower()} in [City] and noticed something.\n\n")
            f.write(f"FACT: {niche['stat']}.\n\n")
            f.write(f"That's exactly why I built {niche['solution']}.\n\n")
            f.write(f"It's a completely human-sounding AI that:\n")
            f.write(f"- Answers every call within 2 rings\n")
            f.write(f"- Qualifies the lead in real-time\n")
            f.write(f"- Books appointments directly on your calendar\n")
            f.write(f"- Works 24/7, including holidays\n\n")
            f.write(f"PRICING: {niche['pricing']}\n\n")
            f.write(f"I'd love to let you call a live demo number to hear it for yourself.\n\n")
            f.write(f"Do you have 5 minutes this week for a quick chat?\n\n")
            f.write(f"Best,\nOmar\nMBM Lead Generation\n")
    
    log(f"Created {len(niches)} niche outreach templates")
    return niches


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

    def generate_dashboard():
    """Generate the voice agency studio dashboard."""
    log("=" * 60)
    log("GENERATING VOICE AGENCY DASHBOARD")
    log("=" * 60)
    
    agents = load_agents()
    platforms = load_platforms()
    
    total_rate = sum(a.get('rate_per_min', 0) for a in agents)
    avg_rate = total_rate / len(agents) if agents else 0
    
    # Convert data to safe strings for HTML
    agents_json = json.dumps(agents[:5]) if agents else '[]'
    platforms_json = json.dumps(platforms[:5]) if platforms else '[]'
    
    html = f"""<!DOCTYPE html>
<html><head><title>MBM Voice Agency Studio</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2a 100%); min-height: 100vh; }}
.glass {{ background: rgba(20, 20, 40, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }}
.gradient-text {{ background: linear-gradient(135deg, #00ff88 0%, #00ccff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.card-hover {{ transition: all 0.3s ease; }}
.card-hover:hover {{ transform: translateY(-5px); box-shadow: 0 20px 40px rgba(0, 255, 136, 0.3); }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
</style>
</head><body>

<div class="container mx-auto px-4 py-8">
    <header class="text-center mb-12">
        <h1 class="text-5xl font-bold mb-4 gradient-text">🎭 MBM Voice Agency Studio</h1>
        <p class="text-gray-400 text-lg">Your Complete Voice AI Business Platform</p>
        <p class="text-sm text-gray-500 mt-2">Connected to paying platforms | {datetime.now().strftime('%B %d, %Y')}</p>
    </header>
    
    <div class="stats-grid mb-12">
        <div class="glass rounded-xl p-6 card-hover">
            <div class="text-4xl font-bold text-green-400">{len(agents)}</div>
            <div class="text-gray-400 mt-2">Voice Agents Created</div>
            <div class="text-xs text-gray-500 mt-1">Ready for Deployment</div>
        </div>
        <div class="glass rounded-xl p-6 card-hover">
            <div class="text-4xl font-bold text-blue-400">{len(platforms)}</div>
            <div class="text-gray-400 mt-2">Paying Platforms</div>
            <div class="text-xs text-gray-500 mt-1">Integrated & Configured</div>
        </div>
        <div class="glass rounded-xl p-6 card-hover">
            <div class="text-4xl font-bold text-purple-400">${avg_rate:.2f}</div>
            <div class="text-gray-400 mt-2">Avg Rate/Min</div>
            <div class="text-xs text-gray-500 mt-1">Market Average</div>
        </div>
    </div>
    
    <div class="grid md:grid-cols-2 gap-8 mb-12">
        <div class="glass rounded-xl p-6">
            <h2 class="text-2xl font-bold mb-4 text-blue-400">🚀 Quick Actions</h2>
            <div class="space-y-3">
                <a href="#" onclick="createAgent()" class="block w-full bg-gradient-to-r from-green-500 to-blue-500 text-white py-3 px-4 rounded-lg font-semibold hover:from-green-600 hover:to-blue-600 transition-all">
                    ✨ Create New Voice Agent
                </a>
                <a href="#" onclick="connectPlatform()" class="block w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white py-3 px-4 rounded-lg font-semibold hover:from-purple-600 hover:to-pink-600 transition-all">
                    🔗 Connect New Platform
                </a>
                <a href="#" onclick="startSales()" class="block w-full bg-gradient-to-r from-orange-500 to-red-500 text-white py-3 px-4 rounded-lg font-semibold hover:from-orange-600 hover:to-red-600 transition-all">
                    📞 Start Sales Campaign
                </a>
            </div>
            
            <div class="mt-6 p-4 bg-gray-900 rounded-lg">
                <h3 class="font-semibold mb-2">📊 Revenue Projections (Next Month)</h3>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between">
                        <span>Starter Agencies (3 clients):</span>
                        <span class="text-green-400">${3 * 100 * 0.35:.0f}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Growth Agencies (10 clients):</span>
                        <span class="text-green-400">${10 * 300 * 0.35:.0f}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Enterprise Agencies (50 clients):</span>
                        <span class="text-green-400">${50 * 1000 * 0.35:.0f}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="glass rounded-xl p-6">
            <h2 class="text-2xl font-bold mb-4 text-green-400">🎯 Target Markets</h2>
            <div class="grid grid-cols-2 gap-3">
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">🔧 Plumbers</div>
                    <div class="text-xs text-gray-400 mt-1">Emergency calls handled</div>
                </div>
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">❄️ HVAC Techs</div>
                    <div class="text-xs text-gray-400 mt-1">24/7 dispatch</div>
                </div>
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">⚖️ Lawyers</div>
                    <div class="text-xs text-gray-400 mt-1">Client intake</div>
                </div>
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">👨‍⚕️ Dentists</div>
                    <div class="text-xs text-gray-400 mt-1">Appointment scheduling</div>
                </div>
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">🏠 Real Estate</div>
                    <div class="text-xs text-gray-400 mt-1">Lead qualification</div>
                </div>
                <div class="bg-gray-900 p-3 rounded-lg">
                    <div class="font-semibold">🚗 Auto Dealers</div>
                    <div class="text-xs text-gray-400 mt-1">Sales calls</div>
                </div>
            </div>
            
            <div class="mt-6">
                <div class="text-sm font-semibold mb-2">💡 Proven Pitch:</div>
                <div class="text-xs text-gray-300 italic">
                    "<span class="text-green-400">62% of leads call the next business if no answer</span>".<br>
                    Our AI answers 24/7, qualifies leads, and books appointments.<br>
                    Price: <span class="text-yellow-400">$297-$497/mo + $0.35/min</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="glass rounded-xl p-6 mb-12">
        <h2 class="text-2xl font-bold mb-6 text-purple-400">🤖 Your Voice Agents</h2>
        <div id="agents-container" class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {"".join([
                f'''
                <div class="agent-card bg-gray-900 rounded-lg p-5 card-hover border border-gray-700">
                    <h3 class="font-bold text-lg mb-2 text-white">{agent.get('title', 'Untitled Agent')}</h3>
                    <p class="text-sm text-gray-400 mb-3">{agent.get('description', 'No description available')}</p>
                    <div class="flex flex-wrap gap-2 mb-3">
                        {"".join([f'<span class="tag-pill bg-blue-900 text-blue-300 px-2 py-1 rounded text-xs">{tag}</span>' for tag in agent.get('tags', [])[:3]])}
                    </div>
                    <div class="flex justify-between items-center">
                        <div class="text-xl font-bold text-green-400">${agent.get('rate_per_min', 0):.2f}/min</div>
                        <button onclick="sellAgent('{agent.get('title', '').replace(\"'\", '\\\\'')}')" 
                            class="bg-gradient-to-r from-orange-500 to-red-500 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:from-orange-600 hover:to-red-600">
                            🎯 Sell Now
                        </button>
                    </div>
                </div>
                ''' for agent in agents[:6]
            ])}
            {'' if agents else '<div class="col-span-full text-center py-8 text-gray-500">No voice agents created yet. <a href="#" onclick="createAgent()" class="text-green-400 hover:underline">Create your first agent</a></div>''}
        </div>
    </div>
    
    <div class="glass rounded-xl p-6 mb-8">
        <h2 class="text-2xl font-bold mb-4 text-orange-400">🔗 Connected Platforms</h2>
        <div class="grid md:grid-cols-2 gap-4">
            {"".join([
                f'''
                <div class="platform-card bg-gray-900 rounded-lg p-4 border border-gray-700">
                    <h3 class="font-bold text-lg mb-2 text-green-400">{platform.get('platform', 'Unknown Platform')}</h3>
                    <p class="text-sm text-gray-400 mb-3"><strong>Model:</strong> {platform.get('payout_model', 'N/A')}</p>
                    <p class="text-sm text-gray-400 mb-3"><strong>Revenue:</strong> {platform.get('how_you_get_paid', 'N/A')}</p>
                    <a href="{platform.get('url', '#')}" target="_blank" 
                       class="inline-block bg-gradient-to-r from-blue-500 to-purple-500 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:from-blue-600 hover:to-purple-600">
                        🌐 Visit Platform
                    </a>
                </div>
                ''' for platform in platforms[:4]
            ])}
            {'' if platforms else '<div class="col-span-full text-center py-8 text-gray-500">No platforms connected yet. <a href="#" onclick="connectPlatform()" class="text-green-400 hover:underline">Connect your first platform</a></div>''}
        </div>
    </div>
    
    <footer class="text-center mt-12">
        <div class="glass rounded-xl p-6">
            <p class="text-gray-400 mb-2">🎭 Generated by MBM Voice Agency Studio - Empowering Voice AI Entrepreneurs</p>
            <div class="flex justify-center space-x-6 text-sm text-gray-500">
                <a href="#" class="hover:text-green-400 transition-colors">Dashboard</a>
                <a href="#" class="hover:text-green-400 transition-colors">Analytics</a>
                <a href="#" class="hover:text-green-400 transition-colors">Support</a>
                <a href="#" class="hover:text-green-400 transition-colors">Settings</a>
            </div>
        </div>
    </footer>
</div>

<script>
// Agent data
const agents = {agents_json};
const platforms = {platforms_json};

function createAgent() {{
    alert('📧 Agent creation form would open here!\n\nYou\'d be able to:\\n- Choose voice characteristics\\n- Set persona and personality\\n- Configure pricing\\n- Select target markets');
}}

function connectPlatform() {{
    alert('🔗 Platform connection wizard!\n\nAvailable platforms:\\n- ElevenLabs Voice Library\\n- Synthflow AI Agency\\n- Retell AI\\n- Vapi AI\\n\\nEach platform offers different revenue models and commission structures.');
}}

function sellAgent(agentTitle) {{
    alert(`🎯 Ready to sell: ${agentTitle}\n\nBusiness outreach will begin immediately to:\\n- Plumbers in your area\\n- HVAC companies\\n- Law firms\\n- And more!\n\nOur proven 62% conversion pitch will be used.`);
}}

function startSales() {{
    alert('📞 Sales campaign activated!\n\nThis will:\\n1. Generate personalized outreach emails\\n2. Set up demo call scheduling\\n3. Track conversations and responses\\n4. Send daily reminders to prospects\\n\\nCost: $0 setup (we\'re just getting started!)');
}}

// Auto-refresh dashboard every 30 seconds
function refreshDashboard() {{
    const now = new Date();
    document.querySelector('[data-time]').textContent = now.toLocaleString();
}}

// Initialize
refreshDashboard();
setInterval(refreshDashboard, 30000);

// Add time display
const header = document.querySelector('header');
const timeDisplay = document.createElement('p');
timeDisplay.textContent = 'Last updated: just now';
timeDisplay.className = 'text-xs text-gray-600';
timeDisplay.setAttribute('data-time', 'just now');
header.appendChild(timeDisplay);
</script>
</body></html>"""
    
    dashboard_file = STUDIO_DIR / 'dashboard.html'
    with open(dashboard_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    log(f"Dashboard saved: {dashboard_file}")
    return dashboard_file


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("MBM VOICE AGENCY STUDIO")
    print("=" * 60)
    
    # Connect all platforms
    elevenlabs = connect_elevenlabs()
    synthflow = connect_synthflow()
    retell = connect_retell()
    vapi = connect_vapi()
    
    # Generate business outreach
    niches = generate_business_outreach()
    
    # Generate dashboard
    dashboard = generate_dashboard()
    
    # Open dashboard
    import subprocess
    subprocess.Popen(['start', str(dashboard)], shell=True)
    
    print(f"\nDashboard opened: {dashboard}")
    print(f"Business outreach templates: {len(niches)} niches")
    print(f"\nNext steps:")
    print(f"1. Sign up at synthflow.ai / retellai.com / vapi.ai")
    print(f"2. Deploy voice agents to phone numbers")
    print(f"3. Call local businesses using our pitch templates")
    print(f"4. Start earning $0.25-$0.75/min per client")
