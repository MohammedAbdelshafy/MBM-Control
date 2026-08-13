#!/usr/bin/env python3
"""
MBM Voice Agent Factory
Generates and deploys NEW voice agents every 15 minutes to Retell AI.
Each agent targets a different niche/industry for maximum coverage.

Usage:
  python agent_factory.py --once        # Generate 1 agent now
  python agent_factory.py --loop        # Generate every 15 min (runs forever)
  python agent_factory.py --deploy      # Deploy all agents to Retell
  python agent_factory.py --status      # Show all deployed agents
"""

import json
import os
import sys
import time
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_FILE = LOGS_DIR / "factory_agents.json"
DEPLOYED_FILE = LOGS_DIR / "deployed_agents.json"

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

# Voice IDs for variety (Retell native voices — only verified working IDs)
VOICE_IDS = [
    "retell-Willa",
    "retell-Cimo",
    "retell-Alejandro",
    "retell-Nico",
    "retell-Cleo",
    "retell-Adam",
    "retell-Hailey",
    "retell-Brian",
]

# Industry niches with scripts
NICHES = [
    {
        "name": "HVAC Repair",
        "persona": "Friendly HVAC service coordinator",
        "hook": "Hi! I'm calling about your heating and cooling system. Are you still experiencing issues with your HVAC?",
        "qualify": ["What's the issue?", "When did it start?", "What's your address?", "Is this residential or commercial?"],
        "close": "I'll have a technician call you within 30 minutes. What's the best number?",
        "rate": 0.35,
        "tags": ["hvac", "home-services", "repair"]
    },
    {
        "name": "Plumbing Emergency",
        "persona": "Calm, professional plumbing dispatcher",
        "hook": "Hi! I see you submitted a plumbing request. Is this still an emergency, or has the situation changed?",
        "qualify": ["What's the issue?", "Is water still running?", "What's your address?", "What's your timeline?"],
        "close": "A licensed plumber will call you within 15 minutes. Hang tight!",
        "rate": 0.35,
        "tags": ["plumbing", "emergency", "home-services"]
    },
    {
        "name": "Solar Panel Sales",
        "persona": "Energetic clean energy consultant",
        "hook": "Hi! I'm calling about solar panels for your home. Are you still interested in reducing your electricity bill by 30-50%?",
        "qualify": ["What's your monthly electric bill?", "Do you own your home?", "What's your roof direction?", "When are you looking to install?"],
        "close": "I'll send you a free solar estimate. What email works best?",
        "rate": 0.45,
        "tags": ["solar", "energy", "home-improvement"]
    },
    {
        "name": "Roofing Contractor",
        "persona": "Professional roofing consultant",
        "hook": "Hi! I'm following up on your roofing inquiry. Are you still looking to get your roof inspected or repaired?",
        "qualify": ["What's the issue?", "When was the last inspection?", "What type of roof?", "Is there visible damage?"],
        "close": "We can schedule a free inspection this week. What day works best?",
        "rate": 0.40,
        "tags": ["roofing", "contractor", "home-services"]
    },
    {
        "name": "Insurance Claims",
        "persona": "Empathetic insurance claim specialist",
        "hook": "Hi! I'm following up on your insurance claim. Are you still need assistance with the claims process?",
        "qualify": ["What type of claim?", "When did the incident occur?", "Have you filed yet?", "What's your policy number?"],
        "close": "I'll have an adjuster review your case within 24 hours. We'll call you back.",
        "rate": 0.50,
        "tags": ["insurance", "claims", "financial"]
    },
    {
        "name": "Legal Consultation",
        "persona": "Professional legal intake specialist",
        "hook": "Hi! I'm calling from the law office. You requested a consultation. Are you still looking for legal assistance?",
        "qualify": ["What type of case?", "When did this happen?", "Have you spoken to an attorney?", "What's your timeline?"],
        "close": "An attorney will call you within 2 hours for a free consultation.",
        "rate": 0.55,
        "tags": ["legal", "consultation", "professional"]
    },
    {
        "name": "Dental Appointment",
        "persona": "Warm dental office receptionist",
        "hook": "Hi! I'm calling about your upcoming dental appointment. Are you still able to make it?",
        "qualify": ["What procedure?", "Do you have insurance?", "Any preferences for date/time?", "Any anxiety concerns?"],
        "close": "I'll confirm your appointment and send a reminder. See you soon!",
        "rate": 0.30,
        "tags": ["dental", "healthcare", "appointment"]
    },
    {
        "name": "Auto Detailing",
        "persona": "Enthusiastic auto detailing coordinator",
        "hook": "Hi! I'm following up on your auto detailing request. Are you still looking to get your vehicle detailed?",
        "qualify": ["What type of vehicle?", "Interior, exterior, or both?", "Any special requests?", "When works for you?"],
        "close": "I'll book your detail slot. What day works best?",
        "rate": 0.35,
        "tags": ["auto", "detailing", "services"]
    },
    {
        "name": "Moving Company",
        "persona": "Organized moving coordinator",
        "hook": "Hi! I'm calling about your upcoming move. Are you still planning to relocate?",
        "qualify": ["When are you moving?", "What's the origin/destination?", "How many rooms?", "Any specialty items?"],
        "close": "I'll prepare a custom quote. When can we do a virtual walkthrough?",
        "rate": 0.40,
        "tags": ["moving", "logistics", "services"]
    },
    {
        "name": "Pest Control",
        "persona": "Knowledgeable pest control specialist",
        "hook": "Hi! I'm following up on your pest control request. Are you still experiencing pest issues?",
        "qualify": ["What type of pests?", "How long have you noticed them?", "What's your home size?", "Any pets or children?"],
        "close": "We can treat your home this week. What day works best?",
        "rate": 0.35,
        "tags": ["pest-control", "home-services", "maintenance"]
    },
    {
        "name": "Landscaping",
        "persona": "Creative landscaping consultant",
        "hook": "Hi! I'm calling about your landscaping project. Are you still looking to improve your outdoor space?",
        "qualify": ["What services needed?", "What's your budget?", "What's your yard size?", "Any specific ideas?"],
        "close": "I'll design a custom proposal. Can we schedule a site visit this week?",
        "rate": 0.40,
        "tags": ["landscaping", "outdoor", "home-improvement"]
    },
    {
        "name": "Pool Service",
        "persona": "Friendly pool maintenance coordinator",
        "hook": "Hi! I'm following up on your pool service request. Is your pool still needing maintenance or repair?",
        "qualify": ["What's the issue?", "Pool size?", "How often do you use it?", "Last time it was serviced?"],
        "close": "A pool tech will call you within 1 hour. What's the best number?",
        "rate": 0.35,
        "tags": ["pool", "maintenance", "home-services"]
    },
    {
        "name": "Window Cleaning",
        "persona": "Efficient window cleaning dispatcher",
        "hook": "Hi! I'm calling about your window cleaning request. Are you still looking to get your windows cleaned?",
        "qualify": ["How many windows?", "Interior, exterior, or both?", "Any high or hard-to-reach?", "When works for you?"],
        "close": "I'll book your cleaning slot. What day works best?",
        "rate": 0.30,
        "tags": ["cleaning", "window", "services"]
    },
    {
        "name": "Painting Contractor",
        "persona": "Detail-oriented painting consultant",
        "hook": "Hi! I'm following up on your painting project. Are you still looking to get your space painted?",
        "qualify": ["Interior or exterior?", "What areas need painting?", "What colors?", "Any prep needed?"],
        "close": "I'll prepare a free estimate. Can we do a walkthrough this week?",
        "rate": 0.40,
        "tags": ["painting", "contractor", "home-improvement"]
    },
    {
        "name": "Electrical Services",
        "persona": "Licensed electrical coordinator",
        "hook": "Hi! I'm calling about your electrical issue. Are you still experiencing problems?",
        "qualify": ["What's the issue?", "Is it urgent?", "What's your address?", "Any safety concerns?"],
        "close": "A licensed electrician will call you within 30 minutes.",
        "rate": 0.45,
        "tags": ["electrical", "home-services", "emergency"]
    },
    {
        "name": "Concrete & Foundation",
        "persona": "Structural foundation specialist",
        "hook": "Hi! I'm following up on your foundation inquiry. Are you noticing any cracks or settling?",
        "qualify": ["What issues do you see?", "When did you first notice?", "What type of foundation?", "How old is the property?"],
        "close": "We'll schedule a free inspection this week. What day works best?",
        "rate": 0.50,
        "tags": ["concrete", "foundation", "contractor"]
    },
    {
        "name": "Fence Installation",
        "persona": "Friendly fencing coordinator",
        "hook": "Hi! I'm calling about your fence project. Are you still looking to install or repair a fence?",
        "qualify": ["What type of fence?", "Linear footage needed?", "Any HOA restrictions?", "What's your timeline?"],
        "close": "I'll prepare a custom quote. Can we measure your yard this week?",
        "rate": 0.35,
        "tags": ["fencing", "contractor", "home-improvement"]
    },
    {
        "name": "Garage Door",
        "persona": "Quick garage door specialist",
        "hook": "Hi! I'm calling about your garage door issue. Is it still not working properly?",
        "qualify": ["What's the issue?", "Manual or automatic?", "When did it stop working?", "What brand?"],
        "close": "A tech will call you within 20 minutes. We offer same-day repair.",
        "rate": 0.35,
        "tags": ["garage-door", "repair", "home-services"]
    },
    {
        "name": "Gutter Cleaning",
        "persona": "Efficient gutter service coordinator",
        "hook": "Hi! I'm following up on your gutter cleaning request. Are you still looking to get your gutters cleaned?",
        "qualify": ["How many linear feet?", "Any visible damage?", "When was the last cleaning?", "Are you noticing overflow?"],
        "close": "I'll book your gutter cleaning this week. What day works?",
        "rate": 0.30,
        "tags": ["gutter", "cleaning", "home-services"]
    },
    {
        "name": "Handyman Services",
        "persona": "Versatile handyman coordinator",
        "hook": "Hi! I'm calling about your handyman request. What repairs or projects do you need help with?",
        "qualify": ["What's the project?", "How urgent?", "What's your budget?", "Any specific skills needed?"],
        "close": "I'll match you with the right handyman. What day works for the job?",
        "rate": 0.35,
        "tags": ["handyman", "repairs", "general"]
    },
    {
        "name": "Carpet Cleaning",
        "persona": "Professional carpet cleaning dispatcher",
        "hook": "Hi! I'm following up on your carpet cleaning request. Are you still looking to get your carpets cleaned?",
        "qualify": ["How many rooms?", "Any stains or pet damage?", "What type of carpet?", "When works for you?"],
        "close": "I'll book your carpet cleaning. What day works best?",
        "rate": 0.30,
        "tags": ["carpet", "cleaning", "home-services"]
    },
    {
        "name": "Appliance Repair",
        "persona": "Knowledgeable appliance repair coordinator",
        "hook": "Hi! I'm calling about your appliance issue. Is it still malfunctioning?",
        "qualify": ["What appliance?", "What's the issue?", "Brand and model?", "Still under warranty?"],
        "close": "A tech will call you within 1 hour. Same-day repair available.",
        "rate": 0.40,
        "tags": ["appliance", "repair", "home-services"]
    },
    {
        "name": "Home Inspection",
        "persona": "Thorough home inspection coordinator",
        "hook": "Hi! I'm calling about your home inspection. Are you still looking to schedule one?",
        "qualify": ["Buying or selling?", "What's the address?", "When's the deadline?", "Any known issues?"],
        "close": "I'll book your inspection. What day works for the walkthrough?",
        "rate": 0.45,
        "tags": ["inspection", "real-estate", "professional"]
    },
    {
        "name": "Tree Service",
        "persona": "Experienced tree care specialist",
        "hook": "Hi! I'm following up on your tree service request. Do you still need tree work done?",
        "qualify": ["What service needed?", "How many trees?", "Any emergency?", "Access to the area?"],
        "close": "We can have a crew out this week. What day works?",
        "rate": 0.40,
        "tags": ["tree", "landscaping", "home-services"]
    },
    {
        "name": "Pressure Washing",
        "persona": "Energetic pressure washing coordinator",
    "hook": "Hi! I'm calling about pressure washing your property. Are you still looking to get it cleaned?",
        "qualify": ["What areas?", "How many sq ft?", "Any delicate surfaces?", "When works for you?"],
        "close": "I'll book your pressure wash this week. What day works?",
        "rate": 0.30,
        "tags": ["pressure-washing", "cleaning", "exterior"]
    },
    {
        "name": "Flooring Installation",
        "persona": "Professional flooring consultant",
        "hook": "Hi! I'm following up on your flooring project. Are you still looking to install new flooring?",
        "qualify": ["What type of flooring?", "Which rooms?", "What's your budget?", "When do you want it done?"],
        "close": "I'll prepare a custom estimate. Can we measure your space this week?",
        "rate": 0.45,
        "tags": ["flooring", "installation", "home-improvement"]
    },
    {
        "name": "Smart Home Setup",
        "persona": "Tech-savvy smart home specialist",
        "hook": "Hi! I'm calling about setting up your smart home. Are you still interested in automation?",
        "qualify": ["What devices?", "What's your budget?", "What platform (Alexa/Google)?", "Any specific goals?"],
        "close": "I'll design a custom setup. Can we do a virtual consult this week?",
        "rate": 0.50,
        "tags": ["smart-home", "technology", "installation"]
    },
    {
        "name": "Water Heater",
        "persona": "Quick water heater specialist",
        "hook": "Hi! I'm calling about your water heater. Is it still not working properly?",
        "qualify": ["Gas or electric?", "What's the issue?", "How old is it?", "Tank or tankless?"],
        "close": "We can install a new unit tomorrow. What time works?",
        "rate": 0.40,
        "tags": ["water-heater", "plumbing", "repair"]
    },
    {
        "name": "Attic Insulation",
        "persona": "Energy efficiency specialist",
        "hook": "Hi! I'm following up on your insulation inquiry. Are you still looking to improve your home's energy efficiency?",
        "qualify": ["What's your current insulation?", "What's your energy bill?", "What's your home size?", "Any cold spots?"],
        "close": "We can insulate your attic this week. What day works?",
        "rate": 0.40,
        "tags": ["insulation", "energy", "home-improvement"]
    },
    {
        "name": "Commercial Roofing",
        "persona": "Professional commercial roofing estimator",
        "hook": "Hi! I'm calling about your commercial roofing maintenance. Are you still interested in scheduling an inspection before the next storm season?",
        "qualify": ["What type of building?", "Flat or sloped roof?", "Any known leaks?", "Who handles your property maintenance?"],
        "close": "I'll have our estimator call you within 1 hour with inspection times. What's the best number?",
        "rate": 0.55,
        "tags": ["commercial", "roofing", "b2b"]
    },
    {
        "name": "Commercial HVAC Maintenance",
        "persona": "Experienced commercial HVAC account manager",
        "hook": "Hi! I'm following up on your commercial HVAC service request. Are you still looking for a maintenance plan?",
        "qualify": ["How many units?", "What type of building?", "Are you on a current maintenance plan?", "Who's your facility manager?"],
        "close": "I'll send over a preventative maintenance quote today. What email works best?",
        "rate": 0.55,
        "tags": ["commercial", "hvac", "b2b"]
    },
    {
        "name": "Medical Billing Services",
        "persona": "Knowledgeable medical billing consultant",
        "hook": "Hi! I'm calling about your practice's medical billing. Are you still looking to improve your claim approval rates?",
        "qualify": ["What specialty is the practice?", "What's your current approval rate?", "How many providers?", "Which billing software do you use?"],
        "close": "I'll schedule a free revenue cycle review. When works for you?",
        "rate": 0.60,
        "tags": ["healthcare", "billing", "b2b"]
    },
    {
        "name": "Dental Practice Growth",
        "persona": "Dental practice growth specialist",
        "hook": "Hi! I'm following up on your dental practice inquiry. Are you still looking to fill more appointments?",
        "qualify": ["How many chairs?", "Which services are underbooked?", "What's your current no-show rate?", "Who handles scheduling now?"],
        "close": "I'll put together a growth plan for your practice. Can we do a 15-minute call?",
        "rate": 0.60,
        "tags": ["dental", "healthcare", "b2b"]
    },
    {
        "name": "Commercial Janitorial Contracts",
        "persona": "Facilities services account executive",
        "hook": "Hi! I'm calling about your office cleaning service. Are you still looking for a commercial janitorial provider?",
        "qualify": ["What's your square footage?", "How often do you need service?", "What industry is the facility?", "Do you need daily or nightly cleaning?"],
        "close": "I'll prepare a custom cleaning proposal today. What's the best email?",
        "rate": 0.55,
        "tags": ["janitorial", "facilities", "b2b"]
    },
    {
        "name": "IT Managed Services",
        "persona": "IT solutions consultant",
        "hook": "Hi! I'm following up on your IT support inquiry. Are you still looking for managed IT services?",
        "qualify": ["How many employees?", "Who handles your IT now?", "Any compliance requirements?", "What's your biggest IT pain point?"],
        "close": "I'll schedule a free IT assessment. When works for a quick call?",
        "rate": 0.65,
        "tags": ["it-services", "msp", "b2b"]
    },
    {
        "name": "Industrial Recycling & Waste",
        "persona": "Industrial waste management specialist",
        "hook": "Hi! I'm calling about your facility's recycling program. Are you still looking to reduce waste disposal costs?",
        "qualify": ["What materials do you generate?", "What's your monthly volume?", "Who's your current hauler?", "Any hauling contracts expiring?"],
        "close": "I'll put together a savings estimate. What's the best email?",
        "rate": 0.65,
        "tags": ["recycling", "industrial", "b2b"]
    },
    {
        "name": "Freight & Logistics Brokerage",
        "persona": "Freight brokerage account manager",
        "hook": "Hi! I'm following up on your shipping needs. Are you still looking for reliable freight carriers?",
        "qualify": ["What do you ship?", "What's your monthly volume?", "What are your current lanes?", "Any recurring pain points?"],
        "close": "I'll match you with vetted carriers this week. What lane should we start with?",
        "rate": 0.65,
        "tags": ["logistics", "freight", "b2b"]
    },
    {
        "name": "Restaurant Equipment Repair",
        "persona": "Commercial kitchen service coordinator",
        "hook": "Hi! I'm calling about your commercial kitchen equipment. Are you still looking for repair service?",
        "qualify": ["What equipment needs service?", "Gas, electric, or refrigeration?", "Do you have a service contract?", "When does the issue occur?"],
        "close": "A certified tech will call you within 30 minutes. What's the best number?",
        "rate": 0.55,
        "tags": ["restaurant", "equipment", "b2b"]
    },
    {
        "name": "Commercial Refrigeration",
        "persona": "Commercial refrigeration specialist",
        "hook": "Hi! I'm following up on your refrigeration service request. Are you still having temperature issues?",
        "qualify": ["What type of unit?", "What temperature issue?", "Walk-in or reach-in?", "Is product at risk?"],
        "close": "I'll dispatch a tech today. What's the best number?",
        "rate": 0.60,
        "tags": ["refrigeration", "commercial", "b2b"]
    },
    {
        "name": "Warehouse Staffing",
        "persona": "Staffing agency account manager",
        "hook": "Hi! I'm calling about your hiring needs. Are you still looking to fill warehouse positions?",
        "qualify": ["How many positions?", "What are the shift requirements?", "What's the pay range?", "When do you need them?"],
        "close": "I'll send over qualified candidates this week. How many do you need?",
        "rate": 0.55,
        "tags": ["staffing", "warehouse", "b2b"]
    },
    {
        "name": "Fulfillment & 3PL Services",
        "persona": "E-commerce fulfillment consultant",
        "hook": "Hi! I'm following up on your fulfillment inquiry. Are you still looking for a 3PL partner?",
        "qualify": ["What's your monthly order volume?", "What are your product dimensions?", "Any kitting or returns?", "What's your current pick-and-pack cost?"],
        "close": "I'll prepare a fulfillment rate sheet today. What email works best?",
        "rate": 0.60,
        "tags": ["fulfillment", "ecommerce", "b2b"]
    },
    {
        "name": "Merchant Services & Payments",
        "persona": "Payments solutions advisor",
        "hook": "Hi! I'm calling about your payment processing. Are you still looking to lower your card processing fees?",
        "qualify": ["What's your average ticket?", "What's your monthly volume?", "Who's your current processor?", "Any chargeback issues?"],
        "close": "I'll run a no-obligation rate comparison. What's the best email?",
        "rate": 0.65,
        "tags": ["payments", "merchant-services", "b2b"]
    },
    {
        "name": "Payroll & HR Services",
        "persona": "Payroll services consultant",
        "hook": "Hi! I'm following up on your payroll inquiry. Are you still looking to streamline payroll and HR?",
        "qualify": ["How many employees?", "Who's your current payroll provider?", "Weekly, bi-weekly, or monthly?", "Any HR compliance needs?"],
        "close": "I'll schedule a free payroll audit. When works for you?",
        "rate": 0.65,
        "tags": ["payroll", "hr", "b2b"]
    },
    {
        "name": "Fire & Life Safety Inspection",
        "persona": "Fire safety compliance specialist",
        "hook": "Hi! I'm calling about your fire and life safety inspection. Are you still looking to schedule one?",
        "qualify": ["What type of facility?", "When does your inspection expire?", "Which systems need testing?", "Who handles compliance now?"],
        "close": "I'll book your inspection this week. What day works best?",
        "rate": 0.60,
        "tags": ["fire-safety", "compliance", "b2b"]
    },
    {
        "name": "Commercial Security Systems",
        "persona": "Commercial security consultant",
        "hook": "Hi! I'm following up on your security system inquiry. Are you still looking to upgrade your surveillance?",
        "qualify": ["What type of facility?", "What's your current camera system?", "How many entry points?", "Any alarm monitoring?"],
        "close": "I'll prepare a security proposal today. What's the best email?",
        "rate": 0.60,
        "tags": ["security", "surveillance", "b2b"]
    },
    {
        "name": "Parking Lot Maintenance",
        "persona": "Parking lot maintenance coordinator",
        "hook": "Hi! I'm calling about your parking lot. Are you still looking for striping and sealcoating services?",
        "qualify": ["What's the lot size?", "Any cracking or faded lines?", "Do you need ADA compliance?", "When was the last sealcoat?"],
        "close": "I'll send over a quote this week. What's the best email?",
        "rate": 0.55,
        "tags": ["parking-lot", "maintenance", "b2b"]
    },
    {
        "name": "Water Damage Restoration",
        "persona": "Emergency restoration coordinator",
        "hook": "Hi! I'm following up on your water damage claim. Is the situation still active?",
        "qualify": ["Where's the damage?", "How long has it been wet?", "Have you contacted your insurer?", "What materials were affected?"],
        "close": "A restoration crew can be dispatched today. What's the best number?",
        "rate": 0.55,
        "tags": ["restoration", "emergency", "home-services"]
    },
    {
        "name": "Mold Remediation",
        "persona": "Mold remediation specialist",
        "hook": "Hi! I'm calling about the mold issue you reported. Are you still looking to get it remediated?",
        "qualify": ["Where's the mold?", "Any visible growth?", "Has it been tested?", "What's the affected area size?"],
        "close": "I'll schedule a free inspection this week. What day works best?",
        "rate": 0.60,
        "tags": ["mold", "remediation", "home-services"]
    },
    {
        "name": "Elevator & Escalator Maintenance",
        "persona": "Vertical transportation service manager",
        "hook": "Hi! I'm calling about your elevator service. Are you still looking for a maintenance contract?",
        "qualify": ["How many elevators?", "Who's your current service provider?", "Any code violations?", "What's the building height and usage?"],
        "close": "I'll prepare a maintenance proposal. What's the best email?",
        "rate": 0.65,
        "tags": ["elevator", "commercial", "b2b"]
    },
    {
        "name": "Off-Market Real Estate Acquisition",
        "persona": "Real estate acquisitions specialist",
        "hook": "Hi! I'm following up on your property inquiry. Are you still looking to sell?",
        "qualify": ["What's the property address?", "What's your timeline?", "Any liens or tenants?", "What's the current condition?"],
        "close": "We can make a cash offer this week. What's the best number?",
        "rate": 0.75,
        "tags": ["real-estate", "acquisitions", "high-ticket"]
    },
    {
        "name": "Business Working Capital",
        "persona": "Business funding advisor",
        "hook": "Hi! I'm calling about your business financing inquiry. Are you still looking for working capital?",
        "qualify": ["What's your monthly revenue?", "How long in business?", "What's the funding amount?", "What will the capital be used for?"],
        "close": "I'll check today's pre-qualification rates. What's the best email?",
        "rate": 0.70,
        "tags": ["financing", "working-capital", "b2b"]
    },
    {
        "name": "Commercial Solar",
        "persona": "Commercial solar development consultant",
        "hook": "Hi! I'm following up on your commercial solar inquiry. Are you still exploring solar for your facility?",
        "qualify": ["What's your monthly utility spend?", "What's your facility square footage?", "Roof or ground-mount?", "Any energy goals or rebates?"],
        "close": "I'll prepare a commercial solar savings model. What email works best?",
        "rate": 0.65,
        "tags": ["solar", "commercial", "energy"]
    },
    {
        "name": "Home Warranty Claims",
        "persona": "Home warranty claims coordinator",
        "hook": "Hi! I'm calling about your home warranty claim. Are you still needing service on your covered system?",
        "qualify": ["What's your policy number?", "Which system failed?", "Have you filed a claim yet?", "What's the model and age?"],
        "close": "I'll escalate your claim for faster service. What's the best number?",
        "rate": 0.50,
        "tags": ["home-warranty", "insurance", "home-services"]
    },
]


def _salvage_json_array(raw):
    """Recover the last complete JSON array from corrupt/concatenated data."""
    idx = raw.rfind("]")
    while idx != -1:
        try:
            data = json.loads(raw[: idx + 1])
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        idx = raw.rfind("]", 0, idx)
    return None


def load_deployed():
    if DEPLOYED_FILE.exists():
        try:
            with open(DEPLOYED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            raw = DEPLOYED_FILE.read_text(encoding="utf-8", errors="replace")
            salvaged = _salvage_json_array(raw)
            if salvaged is not None:
                corrupt_bak = DEPLOYED_FILE.with_suffix(".corrupt.json")
                if not corrupt_bak.exists():
                    corrupt_bak.write_text(raw, encoding="utf-8")
                save_deployed(salvaged)
                print(f"[!] Repaired corrupt {DEPLOYED_FILE.name}: recovered {len(salvaged)} agent(s), backup saved")
                return salvaged
            print(f"[!] {DEPLOYED_FILE.name} is unreadable; starting fresh")
            return []
    return []


def save_deployed(deployed):
    with open(DEPLOYED_FILE, "w", encoding="utf-8") as f:
        json.dump(deployed, f, indent=2)


def get_next_niche(exclude=None):
    """Pick a niche that hasn't been deployed yet, or cycle back"""
    deployed = load_deployed()
    deployed_names = {d["niche"] for d in deployed}
    exclude = exclude or set()
    deployed_names = deployed_names | set(exclude)

    available = [n for n in NICHES if n["name"] not in deployed_names]
    if not available:
        # All deployed, pick random one (still avoid within-batch repeats)
        available = [n for n in NICHES if n["name"] not in exclude]
    if not available:
        available = NICHES

    return random.choice(available)


def resolve_niche(value):
    """Resolve a niche selector (0-based index or exact name) to a NICHES entry."""
    try:
        idx = int(value)
        if 0 <= idx < len(NICHES):
            return NICHES[idx]
        return None
    except ValueError:
        pass
    for n in NICHES:
        if n["name"].lower() == str(value).strip().lower():
            return n
    return None


def create_agent(niche):
    """Create a new voice agent for a niche and deploy to Retell"""
    if not RETELL_API_KEY:
        print("[!] RETELL_API_KEY not set")
        return None

    headers = {"Authorization": f"Bearer {RETELL_API_KEY}", "Content-Type": "application/json"}

    prompt = f"""You are {niche['persona']}. 

Opening: "{niche['hook']}"

Qualification questions:
{chr(10).join('- ' + q for q in niche['qualify'])}

Closing: "{niche['close']}"

If they say NO: "No problem. If you need {niche['name'].lower()} services in the future, we're here to help. Have a great day!"
If they say NOT NOW: "Totally understand. Should I check back in a week or two?"
If they say ALREADY DONE: "Great! If you need anything else, don't hesitate to reach out."
If they're BUSY: "I understand. When would be a better time for a quick 2-minute call?"

Be natural, empathetic, and professional. Never be pushy. Log the outcome."""

    voice_id = random.choice(VOICE_IDS)

    # Step 1: Create LLM first
    llm_payload = {
        "model": "gemini-2.0-flash",
        "general_prompt": prompt
    }

    try:
        r = requests.post("https://api.retellai.com/create-retell-llm", headers=headers, json=llm_payload, timeout=30)
        if r.status_code not in (200, 201):
            print(f"  [-] LLM creation failed: {r.status_code} - {r.text[:100]}")
            return None
        llm_data = r.json()
        llm_id = llm_data.get("llm_id")
        print(f"  [+] Created LLM: {llm_id}")
    except Exception as e:
        print(f"  [!] Error creating LLM: {e}")
        return None

    # Step 2: Create agent with LLM
    agent_payload = {
        "agent_name": f"MBM-{niche['name'].replace(' ', '-')}-{datetime.now().strftime('%H%M%S')}",
        "voice_id": voice_id,
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
            return {
                "niche": niche["name"],
                "agent_id": agent_id,
                "llm_id": llm_id,
                "voice_id": voice_id,
                "rate_per_min": niche["rate"],
                "tags": niche["tags"],
                "deployed_at": datetime.now().isoformat(),
                "status": "deployed"
            }
        else:
            print(f"  [-] Failed: {r.status_code} - {r.text[:100]}")
            return None
    except Exception as e:
        print(f"  [!] Error: {e}")
        return None


def generate_one(niche=None):
    """Generate and deploy one agent (optionally pinned to a specific niche)"""
    if niche is None:
        niche = get_next_niche()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating agent for: {niche['name']}")

    result = create_agent(niche)
    if result:
        deployed = load_deployed()
        deployed.append(result)
        save_deployed(deployed)
        print(f"  [+] Deployed: {result['agent_id']} (${result['rate_per_min']}/min)")
        print(f"  [+] Total deployed: {len(deployed)}")
        return result
    return None


def run_loop():
    """Generate agents every 15 minutes"""
    print(f"\n{'='*50}")
    print(f"  MBM VOICE AGENT FACTORY")
    print(f"  Generating new agent every 15 minutes")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    while True:
        result = generate_one()
        if result:
            print(f"  Next agent in 15 minutes...\n")
        else:
            print(f"  Retrying in 5 minutes...\n")
            time.sleep(300)
            continue

        time.sleep(900)  # 15 minutes


def show_status():
    """Show all deployed agents"""
    deployed = load_deployed()
    if not deployed:
        print("[!] No agents deployed yet")
        return

    print(f"\n{'='*60}")
    print(f"  MBM DEPLOYED VOICE AGENTS ({len(deployed)} total)")
    print(f"{'='*60}\n")

    total_rate = 0
    for i, agent in enumerate(deployed, 1):
        print(f"  {i}. {agent['niche']}")
        print(f"     ID: {agent['agent_id']}")
        print(f"     Rate: ${agent['rate_per_min']}/min")
        print(f"     Tags: {', '.join(agent['tags'])}")
        print(f"     Deployed: {agent['deployed_at']}")
        print()
        total_rate += agent['rate_per_min']

    print(f"{'='*60}")
    print(f"  Total agents: {len(deployed)}")
    print(f"  Combined rate: ${total_rate:.2f}/min")
    print(f"  Hourly potential: ${total_rate * 60:.2f}/hr (if all active)")
    print(f"{'='*60}")


def generate_all():
    """Generate agents for ALL available niches (skips already-deployed ones)."""
    print(f"\n[+] Generating voice agents for all {len(NICHES)} industry niches...")
    deployed = load_deployed()
    existing = {d["niche"] for d in deployed}
    created = 0
    for idx, niche in enumerate(NICHES):
        if niche["name"] in existing:
            print(f"  [{idx+1}/{len(NICHES)}] Skipped (already deployed): {niche['name']}")
            continue
        agent = create_agent(niche)
        if agent:
            deployed.append(agent)
            created += 1
            print(f"  [{idx+1}/{len(NICHES)}] Deployed: {niche['name']} (${niche['rate']}/min)")
        else:
            print(f"  [{idx+1}/{len(NICHES)}] Failed: {niche['name']}")
    if created:
        save_deployed(deployed)
    print(f"[+] Batch complete: {created} new agent(s) deployed")
    show_status()

def main():
    parser = argparse.ArgumentParser(description="MBM Voice Agent Factory")
    parser.add_argument("--once", action="store_true", help="Generate 1 agent now")
    parser.add_argument("--all", action="store_true", help="Generate agents for ALL niches")
    parser.add_argument("--count", type=int, default=1, help="Number of agents to generate")
    parser.add_argument("--niche", help="Generate a specific niche (index or name)")
    parser.add_argument("--loop", action="store_true", help="Generate every 15 minutes")
    parser.add_argument("--status", action="store_true", help="Show deployed agents")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.loop:
        run_loop()
        return

    if args.niche:
        niche = resolve_niche(args.niche)
        if not niche:
            print(f"[!] Niche not found: {args.niche}")
            sys.exit(1)
        result = generate_one(niche=niche)
        sys.exit(0 if result else 1)

    if args.all:
        generate_all()
        return

    # default / --once / --count batch
    made = 0
    for _ in range(max(1, args.count)):
        if generate_one():
            made += 1
    if made:
        print(f"[+] Batch complete: {made} agent(s) deployed this run")
    sys.exit(0 if made else 1)


if __name__ == "__main__":
    main()
