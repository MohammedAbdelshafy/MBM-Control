"""
B2B Cold Email Outreach & Client Acquisition Engine
====================================================
Mission: Target high-value businesses (agencies, SaaS, real estate firms)
with personalized cold email sequences to sell AI agent services.

Target Segments:
  1. Marketing Agencies ($2K - $10K/mo retainers)
  2. Real Estate Brokerages ($3K - $15K setup)
  3. Solar/HVAC Companies ($1.5K - $5K setup)
  4. Insurance Agencies ($2K - $8K setup)
  5. SaaS Startups ($5K - $20K project)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

OUTREACH_FILE = LOGS_DIR / 'b2b_outreach_targets.json'
SEQUENCES_FILE = LOGS_DIR / 'cold_email_sequences.json'


TARGET_SEGMENTS = [
    {
        "segment": "Marketing Agencies",
        "search_queries": [
            "digital marketing agency",
            "social media marketing agency",
            "lead generation agency",
        ],
        "ideal_client_size": "5-50 employees",
        "pain_points": [
            "Manual lead qualification eats up SDR time",
            "High cost per lead from paid ads",
            "Clients demanding faster response times",
        ],
        "solution_pitch": "AI Voice Agent that qualifies leads 24/7, cutting cost-per-lead by 70%",
        "price_point": "$2,500/mo retainer",
        "monthly_revenue_potential": "$25,000 (10 clients)",
    },
    {
        "segment": "Real Estate Brokerages",
        "search_queries": [
            "real estate brokerage",
            "property management company",
            "real estate investing group",
        ],
        "ideal_client_size": "10-100 agents",
        "pain_points": [
            "Agents waste hours cold calling unqualified leads",
            "Missed calls from motivated sellers",
            "No automated follow-up system",
        ],
        "solution_pitch": "AI calling swarm that pre-qualifies sellers and books appointments",
        "price_point": "$5,000 setup + $1,500/mo",
        "monthly_revenue_potential": "$50,000 (5 setups + 10 retainers)",
    },
    {
        "segment": "Solar & HVAC Companies",
        "search_queries": [
            "solar installation company",
            "hvac contractor",
            "home services company",
        ],
        "ideal_client_size": "10-30 employees",
        "pain_points": [
            "High cost per appointment ($200-$500)",
            "Low answer rates on cold calls",
            "Long sales cycles",
        ],
        "solution_pitch": "AI appointment setter that books qualified site surveys at 1/3 the cost",
        "price_point": "$3,000 setup + $1,000/mo",
        "monthly_revenue_potential": "$30,000 (3 setups + 15 retainers)",
    },
    {
        "segment": "Insurance Agencies",
        "search_queries": [
            "insurance agency",
            "independent insurance agent",
            "insurance broker",
        ],
        "ideal_client_size": "5-25 employees",
        "pain_points": [
            "Policy renewal follow-ups are manual",
            "New lead quote turnaround too slow",
            "High churn from lack of engagement",
        ],
        "solution_pitch": "AI agent that handles quote requests, renewal reminders, and cross-sells",
        "price_point": "$2,000 setup + $800/mo",
        "monthly_revenue_potential": "$20,000 (5 setups + 15 retainers)",
    },
]


COLD_EMAIL_SEQUENCES = [
    {
        "name": "Agency Owner Outreach",
        "sequence": [
            {
                "day": 0,
                "subject": "Quick question about your lead flow",
                "body": "Hi {name},\n\nI noticed {company} is doing great work in {city}. Quick question — how are you currently handling inbound lead qualification?\n\nWe built an AI voice agent that qualifies leads 24/7 and books demos automatically. Clients typically see 3x more qualified meetings.\n\nWorth a 10-min chat?\n\nBest,\nMoe Shafy\nContech AI Agentic Teamz",
            },
            {
                "day": 3,
                "subject": "Re: Quick question about your lead flow",
                "body": "Hi {name},\n\nJust following up on my note about AI lead qualification. We helped a similar agency in Miami cut their cost-per-lead from $45 to $12.\n\nWould a quick demo be useful?\n\n— Moe",
            },
            {
                "day": 7,
                "subject": "Last note — free AI agent audit",
                "body": "Hi {name},\n\nLast touch from me. I'm offering a free AI agent audit — I'll analyze your current lead flow and show exactly where automation can save you time and money.\n\nNo strings attached. Interested?\n\n— Moe",
            },
        ],
    },
    {
        "name": "Real Estate Brokerage Outreach",
        "sequence": [
            {
                "day": 0,
                "subject": "Your agents are losing deals to missed calls",
                "body": "Hi {name},\n\nI work with real estate brokerages that are tired of losing motivated sellers to voicemail. Our AI calling agent dials, pre-qualifies, and books appointments — even at 2 AM.\n\nCan I show you how it works?\n\nBest,\nMoe Shafy",
            },
            {
                "day": 4,
                "subject": "Re: Your agents are losing deals",
                "body": "Hi {name},\n\nQuick stat: our AI agent books 3-5 qualified appointments per day per market. That's 90+ extra seller conversations/month.\n\nWorth 15 minutes to see the demo?\n\n— Moe",
            },
        ],
    },
]


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[B2B OUTREACH] {timestamp} - {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))


def build_target_list():
    """Build targeted prospect list across segments."""
    log("Building B2B target list...")
    
    all_targets = []
    for segment in TARGET_SEGMENTS:
        target = {
            "segment": segment["segment"],
            "ideal_client_size": segment["ideal_client_size"],
            "pain_points": segment["pain_points"],
            "solution_pitch": segment["solution_pitch"],
            "price_point": segment["price_point"],
            "monthly_revenue_potential": segment["monthly_revenue_potential"],
            "status": "ready_for_outreach",
        }
        all_targets.append(target)
    
    with open(OUTREACH_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_targets, f, indent=2)
    
    with open(SEQUENCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(COLD_EMAIL_SEQUENCES, f, indent=2)
    
    log(f"Built target list: {len(all_targets)} segments")
    print(json.dumps({"targets": len(all_targets), "segments": [t["segment"] for t in all_targets]}, indent=2))
    
    return all_targets


if __name__ == "__main__":
    build_target_list()
