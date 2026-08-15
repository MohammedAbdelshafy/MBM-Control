"""
high_ticket_sales_engine.py — JARVIS OS High-Ticket B2B Sales & Closing Engine.
================================================================================
Generates dynamic, 12-point high-conviction sales execution blueprints:
  1. WHY THIS LEAD
  2. OWNER / DECISION MAKER
  3. COMPANY
  4. VERTICAL
  5. PAIN POINT
  6. PRIMARY OFFER
  7. PATTERN INTERRUPT OPENER
  8. 3x TARGETED DISCOVERY QUESTIONS
  9. VALUE FRAME
  10. 5x BULLETPROOF OBJECTION REBUTTALS
  11. TRIAL CLOSE
  12. FINAL CLOSE & INSTANT FOLLOW-UP CADENCE (SMS + Email + Neteller Link)

Closing Framework:
  HOOK → DISCOVERY → PAIN → COST OF INACTION → SOLUTION → VALUE → DEMO → CLOSE
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from MBM.LeadEngine.canonical_deal_engine import CanonicalDeal, CanonicalDealMemory


def generate_12_point_sales_blueprint(deal: CanonicalDeal) -> Dict[str, Any]:
    """Generates the full 12-point sales blueprint for any CanonicalDeal."""
    first_name = deal.owner_name.split()[0] if deal.owner_name and " " in deal.owner_name else (deal.owner_name or "Partner")
    company = deal.company_name or "Your Firm"
    vertical = deal.vertical or "Enterprise Services"
    neteller_url = deal.neteller_link or "https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=2500.00&currency=USD&item=AI-ONBOARDING"

    # Opener
    opener = (
        f"\"Hey {first_name}! Good morning—this is Omar from MBM Systems. "
        f"I know I’m catching you right in the middle of operations, but I’m reaching out specifically because we engineered "
        f"an automated workflow system for {vertical} companies like {company} that eliminates manual bottleneck hours. "
        f"Do you have just 45 seconds to chat?\""
    )

    # 3 Discovery Questions
    discovery = [
        f"1. When your team is running at peak volume, what percentage of inbound calls or estimate requests end up sitting unanswered for more than 15 minutes?",
        f"2. Right now, how much administrative time is your team spending manually re-typing job data and following up on unclosed proposals each week?",
        f"3. If you could capture 100% of after-hours leads and automate client onboarding without hiring extra staff, what would that do for your monthly bottom line?"
    ]

    # Value Frame & Cost of Inaction
    value_frame = (
        f"\"Look {first_name}, the math is straightforward: Most {vertical} operators lose between $15,000 to $40,000 every single month simply from slow lead response times and administrative friction. "
        f"Our autonomous engine deploys in 48 hours, connects directly to your existing workflow, and guarantees zero missed revenue opportunities.\""
    )

    # 5 Objections Matrix
    objections = {
        "1_too_busy": (
            f"\"I completely understand you're busy, {first_name}—in fact, that is exactly why I called. "
            f"If your team is too busy to manage incoming leads, you are leaving thousands on the table. "
            f"Our AI runs 24/7 in the background so you don't have to lift a finger. Can I send you a 60-second interactive demo video?\""
        ),
        "2_too_expensive": (
            f"\"I respect budget conscious operators, {first_name}. But let's look at the ROI: "
            f"If our system captures just ONE extra closed client or recovers ONE lost project per month, that pays for our entire fee 4 times over. "
            f"This isn't an expense—it is a net-positive revenue generator from day one.\""
        ),
        "3_already_have_software": (
            f"\"That’s fantastic! We don't ask you to replace your software—our engine layers directly on top of your existing tools via API to supercharge them. "
            f"We fill the gap between raw data and actual client conversions.\""
        ),
        "4_send_email_first": (
            f"\"I’d be glad to email you our 1-page executive brief, {first_name}. What’s the best email for you? ... Perfect! "
            f"If what you see aligns with your growth goals for {company}, would you be open to a 10-minute walkthrough this Thursday at 2 PM?\""
        ),
        "5_need_to_consult_partner": (
            f"\"100%, {first_name}. Big decisions require team alignment. I will email you our exact ROI breakdown and live demo credentials right now so you both have real numbers in front of you. "
            f"Let’s pencil in a quick 10-minute debrief on Friday.\""
        )
    }

    # Trial Close
    trial_close = (
        f"\"Based on what you’ve shared about {company}'s current volume, if we could deploy this system to capture all after-hours leads starting next Monday with zero disruption, "
        f"would you be open to running a 14-day live proof of concept?\""
    )

    # Final Close & Neteller Rail
    final_close = (
        f"\"{first_name}, let’s do this: I am sending over our official onboarding agreement and secure checkout link right now ({neteller_url}). "
        f"We will have your custom AI workflow calibrated and live within 48 hours. Let’s get your revenue engine locked in today!\""
    )

    # Follow-Up SMS
    followup_sms = (
        f"Hey {first_name}! Great connecting today. Here is the 1-page summary & demo link for {company}: "
        f"Let me know what time works best tomorrow for your 10-min live demo! - Omar (+1 661-990-9068)"
    )

    # Follow-Up Email
    followup_email = {
        "subject": f"Executive AI Growth Brief for {company} — Next Steps",
        "body": f"""Hi {first_name},

It was a pleasure speaking with you today regarding {company}.

As discussed, attached is our Executive Brief outlining how our Autonomous Workflow Engine eliminates operational bottlenecks and captures high-ticket revenue across {vertical}.

Key Deliverables:
- 24/7 Instant Lead Qualification & Recovery
- Automated Proposal & Booking Workflow
- Direct Integration with your existing tech stack
- Guaranteed ROI within the first 14 days

You can review the agreement and activate deployment directly via our secure checkout:
{neteller_url}

Best regards,
Omar Shafy
Director of AI Acquisitions | JARVIS OS
Direct: +1 (661) 990-9068
"""
    }

    blueprint = {
        "1_why_this_lead": deal.why_this_deal or f"High-value {vertical} company with identified operational bottleneck.",
        "2_decision_maker": deal.owner_name or "Owner / Managing Director",
        "3_company": company,
        "4_vertical": vertical,
        "5_pain_point": deal.risks or "Manual operational friction and missed inbound client response times.",
        "6_primary_offer": deal.primary_offer or f"Autonomous Workflow Engine ({deal.neteller_link or 'Neteller Rail'})",
        "7_opener": opener,
        "8_discovery_questions": discovery,
        "9_value_frame": value_frame,
        "10_objection_matrix": objections,
        "11_trial_close": trial_close,
        "12_final_close": final_close,
        "followup_sms": followup_sms,
        "followup_email": followup_email
    }

    return blueprint


def enrich_memory_with_sales_blueprints():
    """Enriches all CanonicalDeals in memory with complete 12-point sales blueprints."""
    memory = CanonicalDealMemory()
    print(f"\n[SALES ENGINE] Generating 12-point high-ticket sales blueprints for {len(memory.deals)} deals...")

    for deal_id, deal in memory.deals.items():
        bp = generate_12_point_sales_blueprint(deal)
        deal.sales_script = bp["7_opener"]
        deal.objection_handling = bp["10_objection_matrix"]
        deal.why_this_deal = bp["1_why_this_lead"]
        deal.economic_thesis = bp["9_value_frame"]

    memory.save()
    print(f"  ✓ Saved enriched blueprints to Canonical Deal Memory: {memory.storage_path}")


if __name__ == "__main__":
    enrich_memory_with_sales_blueprints()
