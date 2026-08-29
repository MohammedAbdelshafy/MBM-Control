"""
MBM Dialer Script Engine & Segment-Aware Dialogue Playbook Generator
=====================================================================
Generates high-conversion, natural, evidence-backed call scripts across
all 15 canonical segments:
  1. DISTRESSED_SELLER
  2. ABSENTEE_OWNER
  3. VACANT_PROPERTY
  4. HIGH_EQUITY
  5. FREE_AND_CLEAR
  6. TIRED_LANDLORD
  7. OUT_OF_STATE_OWNER
  8. SENIOR_OWNER
  9. LIKELY_TO_MOVE
 10. COMMERCIAL
 11. CONTRACTOR
 12. AI_CONSULTANCY
 13. WEBSITE_DESIGN
 14. MOBILE_APPS
 15. B2B_AGENCY

Script Philosophy:
  - Natural, conversational 10-step dialogue ladder (Permission -> Context -> Interest -> Motivation -> Timing -> Condition/Pain -> Price/Value -> Next Step -> Objections -> Polite Exit).
  - ZERO robotic phrasing, ZERO accusations of distress/bankruptcy/foreclosure.
  - Never forces real estate scripts onto business leads or agency scripts onto home owners.
  - Generates immutable `script_id` and complete `Call_Script` for 100% of leads.
"""

from __future__ import annotations

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from MBM.Scripts.neteller_config import neteller_link
except Exception:
    def neteller_link(amount: float, item: str, currency: str = "USD") -> str:
        import urllib.parse
        return f"https://member.neteller.com/pay?email={urllib.parse.quote('abdelshafyclapps@gmail.com')}&account=4599228811&amount={amount:.2f}&currency={currency}&item={urllib.parse.quote(item)}"


# ══════════════════════════════════════════════════════════════════════════════
# SEGMENT TAXONOMY
# ══════════════════════════════════════════════════════════════════════════════

SUPPORTED_SEGMENTS = [
    "DISTRESSED_SELLER",
    "ABSENTEE_OWNER",
    "VACANT_PROPERTY",
    "HIGH_EQUITY",
    "FREE_AND_CLEAR",
    "TIRED_LANDLORD",
    "OUT_OF_STATE_OWNER",
    "SENIOR_OWNER",
    "LIKELY_TO_MOVE",
    "COMMERCIAL",
    "CONTRACTOR",
    "AI_CONSULTANCY",
    "WEBSITE_DESIGN",
    "MOBILE_APPS",
    "B2B_AGENCY",
    "HEALTHCARE_CLINIC",
]


class SegmentClassifier:
    """Classifies a lead entity into one of the 15 segments based on verified signals."""

    @staticmethod
    def classify_segment(lead: Dict[str, Any]) -> str:
        vertical = str(lead.get("vertical") or "").lower()
        company = str(lead.get("company") or "").lower()
        contact = str(lead.get("contact") or "")
        details = lead.get("details") or {}
        signals = [str(s).lower() for s in (lead.get("motivation_signals") or [])]
        distress_reason = str(details.get("distress_reason") or "").lower()
        owner_status = str(lead.get("owner_status") or "").lower()
        sales_lane = str(lead.get("sales_lane") or "").upper()

        # 1. B2B / Technology / Contractor Segments
        if any(k in vertical for k in ["contractor", "contech", "hvac", "electric", "plumbing", "roofing", "civil"]):
            return "CONTRACTOR"
        if any(k in vertical for k in ["ai consultancy", "automation", "cognitive", "machine learning", "rpa"]):
            return "AI_CONSULTANCY"
        if any(k in vertical for k in ["website", "web design", "shopify", "wordpress", "frontend", "web studio"]):
            return "WEBSITE_DESIGN"
        if any(k in vertical for k in ["mobile app", "ios", "android", "flutter", "react native", "app studio"]):
            return "MOBILE_APPS"
        if any(k in vertical for k in ["professional services", "b2b", "advisory", "growth agency", "management consulting"]):
            return "B2B_AGENCY"
        if any(k in vertical for k in ["clinic", "dental", "medical", "spa", "therapy", "orthodontic", "health", "doctor", "npi"]):
            return "HEALTHCARE_CLINIC"
        if any(k in vertical for k in ["commercial", "industrial", "warehouse", "retail"]):
            return "COMMERCIAL"

        # 2. Real Estate Seller Segments (Dissecting signals)
        if any("vacant" in s for s in signals) or "vacant" in distress_reason:
            return "VACANT_PROPERTY"
        if any("absentee" in s for s in signals) or "absentee" in owner_status:
            return "ABSENTEE_OWNER"
        if any("out_of_state" in s for s in signals) or "out of state" in distress_reason:
            return "OUT_OF_STATE_OWNER"
        if any("landlord" in s for s in signals) or "tired landlord" in distress_reason or "eviction" in distress_reason:
            return "TIRED_LANDLORD"
        if any("free_and_clear" in s for s in signals) or "free & clear" in distress_reason:
            return "FREE_AND_CLEAR"
        if any("high_equity" in s for s in signals) or "equity" in distress_reason:
            return "HIGH_EQUITY"
        if any("senior" in s for s in signals) or "probate" in distress_reason or "estate" in company:
            return "SENIOR_OWNER"
        if any("distress" in s for s in signals) or any(k in distress_reason for k in ["tax", "code", "auction", "pre-foreclosure", "repairs", "distress"]):
            return "DISTRESSED_SELLER"
        if any("move" in s for s in signals) or "downsizing" in distress_reason:
            return "LIKELY_TO_MOVE"

        # Fallbacks based on sales lane or company
        if sales_lane == "REAL_ESTATE_WHOLESALE" or "seller" in vertical:
            return "DISTRESSED_SELLER"
        if "buyer" in vertical or sales_lane == "CASH_BUYER":
            return "COMMERCIAL"

        return "AI_CONSULTANCY"


# ══════════════════════════════════════════════════════════════════════════════
# 10-STEP CONVERSATIONAL SCRIPT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

class DialerScriptEngine:
    """Generates structured 10-step dialogue trees and Call_Script text."""

    @classmethod
    def generate_playbook(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        segment = SegmentClassifier.classify_segment(lead)
        contact_name = str(lead.get("contact") or "").strip()
        first_name = contact_name.split()[0] if contact_name and contact_name.lower() not in ("unknown", "n/a") else "there"
        company = str(lead.get("company") or "your business").strip()
        details = lead.get("details") or {}
        address = str(details.get("address") or details.get("Property_Address") or lead.get("address") or company or "the property").strip()
        city = str(details.get("city") or lead.get("city") or "the area").strip()

        script_id = f"SCRIPT-{segment}-{lead.get('id', 'TEMP')}"

        if segment in (
            "DISTRESSED_SELLER", "ABSENTEE_OWNER", "VACANT_PROPERTY",
            "HIGH_EQUITY", "FREE_AND_CLEAR", "TIRED_LANDLORD",
            "OUT_OF_STATE_OWNER", "SENIOR_OWNER", "LIKELY_TO_MOVE"
        ):
            playbook = cls._build_real_estate_playbook(segment, first_name, address, city, lead)
        elif segment in ("CONTRACTOR", "COMMERCIAL"):
            playbook = cls._build_contractor_playbook(segment, first_name, company, city, lead)
        elif segment in ("AI_CONSULTANCY", "WEBSITE_DESIGN", "MOBILE_APPS", "B2B_AGENCY"):
            playbook = cls._build_b2b_tech_playbook(segment, first_name, company, city, lead)
        else:
            playbook = cls._build_healthcare_playbook(segment, first_name, company, city, lead)

        playbook["script_id"] = script_id
        playbook["segment"] = segment
        playbook["neteller_checkout_link"] = playbook.get("offer", {}).get("neteller_checkout_link", "")

        return playbook

    @classmethod
    def _build_real_estate_playbook(
        cls, segment: str, first_name: str, address: str, city: str, lead: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Builds a natural seller-first conversation for property owners.
        Strictly prohibits accusatory, robotic, or presumptuous language.
        """
        openings = {
            "DISTRESSED_SELLER": f"Hi {first_name}, my name is Mohammed. I know this call is out of the blue, but I was looking at properties around {city} and was hoping to speak with the owner of {address}. Do you have 30 seconds?",
            "ABSENTEE_OWNER": f"Hi {first_name}, this is Mohammed. I'm reaching out regarding your property on {address} in {city}. Have you ever considered what an off-market cash offer might look like for it?",
            "VACANT_PROPERTY": f"Hi {first_name}, Mohammed here. I'm an active local investor buying homes in {city}. I came across {address} and wanted to see if you'd be open to a straightforward cash offer with no agent fees?",
            "TIRED_LANDLORD": f"Hi {first_name}, this is Mohammed. I work with private investors acquiring rental portfolios in {city}. I was calling about {address} - are you planning to keep holding it, or would you be open to an offer?",
            "HIGH_EQUITY": f"Hi {first_name}, my name is Mohammed. I'm looking for single-family homes around {city} to purchase for cash as-is. Have you thought about selling {address} at all this year?",
            "FREE_AND_CLEAR": f"Hi {first_name}, Mohammed calling. We're actively buying residential properties in {city} with zero commissions or closing costs. Would you consider an offer on {address} if the numbers made sense?",
            "OUT_OF_STATE_OWNER": f"Hi {first_name}, this is Mohammed. I specialize in buying Texas properties directly from out-of-state owners with full remote closing. Are you open to discussing a cash offer on {address}?",
            "SENIOR_OWNER": f"Hi {first_name}, Mohammed here. I'm reaching out respectfully about {address} in {city}. We help homeowners transition properties as-is without doing any cleanups or repairs. Would that be of any interest to you?",
            "LIKELY_TO_MOVE": f"Hi {first_name}, my name is Mohammed. I'm reaching out to see if you might be considering selling {address} in the coming months? We purchase homes directly with flexible move-out timelines.",
        }

        opening = openings.get(segment, openings["DISTRESSED_SELLER"])
        checkout_link = neteller_link(5000.0, f"Wholesale Deal Assignment Deposit - {address}")

        call_script = (
            f"{opening}\n\n"
            f"1. CONTEXT: Confirming I have the right person - are you still the owner of {address}?\n\n"
            f"2. OPEN TO SELLING: We buy properties strictly as-is for cash, meaning you don't pay any agent fees, make any repairs, or pay closing costs. If we could agree on a fair price, would you consider selling?\n\n"
            f"3. MOTIVATION: What would be the main goal for you if you did decide to part with it? Are you looking to reinvest, cash out, or just avoid future headaches?\n\n"
            f"4. TIMELINE: In an ideal world, how quickly would you want to close? We can close in 7 days or give you up to 60 days if you need time.\n\n"
            f"5. PROPERTY CONDITION: How would you describe the overall condition? Any major updates to the roof, HVAC, or plumbing needed, or is it move-in ready?\n\n"
            f"6. PRICE EXPECTATION: Ballpark figure, what kind of number would you need to see to make selling today make complete sense for you?\n\n"
            f"7. NEXT STEP: Let's do this: I'll run our comps and prepare a formal written cash offer for you by this afternoon. What's the best email address to send that over to?\n\n"
            f"8. POLITE EXIT (If Not Interested): Understood {first_name}, I completely respect that. If anything changes down the road, feel free to keep my number. Have a great day!"
        )

        return {
            "sales_lane": "REAL_ESTATE_WHOLESALE",
            "opening": opening,
            "context_confirmation": f"Confirm ownership of {address}",
            "open_to_selling": "Confirm if owner would review a direct as-is cash offer with zero closing fees.",
            "motivation_discovery": "Discover primary motivation: cashing out, simplifying, downsizing, or eliminating maintenance.",
            "timing_discovery": "Discover target closing window (7 days to 60 days flexible).",
            "condition_discovery": "Ask about roof, foundation, mechanicals, and cosmetic updates without assuming disrepair.",
            "price_expectation": "Discover owner target number and walk-away expectations.",
            "next_step": "Send written 7-day as-is purchase agreement and schedule 10-minute offer review call.",
            "objection_handlers": {
                "NOT_SELLING": "Completely understand! Would you mind if I check back in 6 months just in case your plans evolve?",
                "LOW_OFFER_FEAR": "We base our numbers transparently on recent neighborhood sales and subtract zero agent commissions. You'll see the exact math before deciding.",
                "NEED_MORE_MONEY": "We can structure creative options or cover 100% of your closing fees and moving expenses to put maximum cash in your pocket.",
                "HOW_DID_YOU_GET_NUMBER": "I work directly with public county appraisal and ownership records to reach out to neighborhood owners directly.",
                "ALREADY_HAVE_AGENT": "Understood. If you're not locked into an exclusive listing agreement yet, our cash offer saves you the full 6% broker commission.",
            },
            "polite_exit": "Thank you for your time, have a wonderful day!",
            "offer": {
                "name": "As-Is Cash Acquisition & 7-Day Close",
                "tier": "WHOLESALE_ASSIGNMENT",
                "estimated_deal_value_usd": 5000.0,
                "neteller_checkout_link": checkout_link,
            },
            "Call_Script": call_script,
        }

    @classmethod
    def _build_contractor_playbook(
        cls, segment: str, first_name: str, company: str, city: str, lead: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Builds tailored ConTech trade contractor operational workflow pitch — estimate recovery, dispatch, scheduling."""
        opening = f"Hi {first_name}, Mohammed calling from MBM. I know you're busy running jobs at {company}, so I'll be brief. We help contractors recover missed estimates and co-ordinate booking → dispatch → scheduling in {city}. Do you have 60 seconds?"
        checkout_link = neteller_link(2497.0, f"Contractor Estimate Recovery & Dispatch Workflow - {company}")

        call_script = (
            f"{opening}\n\n"
            f"1. PAIN: Most contractors we work with tell us they lose 2-3 big bids a month because estimating and follow-up are manual, or after-hours calls go to voicemail. Is estimate recovery or dispatch a bottleneck for {company} right now?\n\n"
            f"2. SOLUTION: We implement an estimate recovery + booking / dispatch → scheduling workflow that tracks estimates, co-ordinates tech dispatch and surfaces follow-up — reporting included.\n\n"
            f"3. NEXT STEP: I'd like to show you a 10-minute workflow review customized for your trade in {city}. Are you around tomorrow 10 AM or 2 PM?\n\n"
            f"4. POLITE EXIT: Appreciate your time {first_name}, keep building great work!"
        )

        return {
            "sales_lane": "CONTECH_AI_SOLUTIONS",
            "opening": opening,
            "context_confirmation": f"Confirm operational role at {company}",
            "open_to_selling": "Propose high-ROI AI estimating & dispatch automation.",
            "motivation_discovery": "Discover estimating bottlenecks and missed call rates.",
            "timing_discovery": "Implement within 7 business days.",
            "condition_discovery": "Review current estimating software (Procore/Bluebeam/PlanSwift).",
            "price_expectation": "$2,497/mo retainer with full setup & support.",
            "next_step": "Book 15-minute Zoom workflow diagnostic.",
            "objection_handlers": {
                "TOO_BUSY": "That's exactly why we built this—it saves your estimators 15 hours every week on takeoff calculations.",
                "EXPENSIVE": "Just winning one additional commercial contract pays for the system for an entire year.",
                "HAPPY_WITH_CURRENT": "Great to hear! Many of our clients use us as a 24/7 backup failover so no after-hours job is ever missed.",
            },
            "polite_exit": f"Thanks {first_name}, have a great week on the job site!",
            "offer": {
                "name": "Commercial Contractor AI Takeoff & Dispatch Swarm",
                "tier": "CONTECH_RETAINER",
                "estimated_deal_value_usd": 2497.0,
                "neteller_checkout_link": checkout_link,
            },
            "Call_Script": call_script,
        }

    @classmethod
    def _build_b2b_tech_playbook(
        cls, segment: str, first_name: str, company: str, city: str, lead: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Builds agency and B2B growth automation playbook."""
        services = {
            "AI_CONSULTANCY": ("AI consultancy & enterprise automation workflows", 2997.0),
            "WEBSITE_DESIGN": ("high-converting Next.js / Shopify web design and conversion funnels", 1997.0),
            "MOBILE_APPS": ("cross-platform iOS & Android mobile application engineering", 2497.0),
            "B2B_AGENCY": ("B2B outbound lead-generation and pipeline scaling systems", 1997.0),
        }
        service_name, price = services.get(segment, ("AI agency automation", 1997.0))
        opening = f"Hi {first_name}, this is Mohammed with MBM. I noticed the work {company} is doing in {city}. We partner with growth teams to deploy {service_name} that plug directly into your revenue pipeline. Do you have 45 seconds?"
        checkout_link = neteller_link(price, f"{segment} Monthly Growth Retainer - {company}")

        call_script = (
            f"{opening}\n\n"
            f"1. PROBLEM: Most agency leaders we talk to are dealing with inconsistent deal flow and high fulfillment overhead. We deliver white-label automation systems that scale your delivery without hiring extra staff.\n\n"
            f"2. VALUE: We handle the entire engineering pipeline on a turnkey retainer basis.\n\n"
            f"3. NEXT STEP: Let's do a quick 15-minute technical audit on Zoom to see where automation can unlock your next $25k/mo in revenue. How does Thursday look?\n\n"
            f"4. POLITE EXIT: Thanks for your time {first_name}, all the best with {company}!"
        )

        return {
            "sales_lane": "AI_AND_DIGITAL_SERVICES",
            "opening": opening,
            "context_confirmation": f"Confirm leadership role at {company}",
            "open_to_selling": f"Deploy {service_name} on a risk-reversal model.",
            "motivation_discovery": "Identify agency growth goals and fulfillment bottlenecks.",
            "timing_discovery": "Deploy within 5 business days.",
            "condition_discovery": "Audit current tech stack and client onboarding flow.",
            "price_expectation": f"${price:,.2f}/mo retainer via Neteller.",
            "next_step": "Book 15-minute Executive Discovery Diagnostic.",
            "objection_handlers": {
                "SEND_EMAIL": "Happy to! What's the best email? I'll send our 2-page implementation brief and follow up Friday.",
                "NO_BUDGET": "Our setups pay for themselves on the first closed client through speed-to-lead automation.",
                "IN_HOUSE_TEAM": "We don't replace your team; we arm them with automated infrastructure so they produce 3x the output.",
            },
            "polite_exit": f"Thank you {first_name}, let's stay connected on LinkedIn!",
            "offer": {
                "name": f"{segment.replace('_', ' ').title()} Growth Retainer",
                "tier": "B2B_GROWTH",
                "estimated_deal_value_usd": price,
                "neteller_checkout_link": checkout_link,
            },
            "Call_Script": call_script,
        }

    @classmethod
    def _build_healthcare_playbook(
        cls, segment: str, first_name: str, company: str, city: str, lead: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Builds healthcare clinic operational workflow playbook — recall, rebooking, intake, scheduling, referral."""
        opening = f"Hi {first_name}, this is Mohammed calling. I know you're focused on patient care at {company}, so I'll be very brief. We help practices recover missed recall and rebooking opportunities -- intake -> scheduling -> recall -> follow-up -- so overdue patients get booked without front-desk chasing, in {city}. Do you have 30 seconds?"
        checkout_link = neteller_link(1997.0, f"Clinic Recall & Rebooking Workflow - {company}")

        call_script = (
            f"{opening}\n\n"
            f"1. BOTTLENECK: Most practices have 20-40% of hygiene patients overdue for recall not yet rebooked. Our recall & rebooking workflow surfaces the overdue list and fills the hygiene schedule without manual chasing.\n\n"
            f"2. BENEFIT: Your front-desk staff can focus on in-office patients while recall and intake follow-up run through reporting.\n\n"
            f"3. NEXT STEP: I'd love to show your office manager a 5-minute workflow review of the recall list. Who is the best person to coordinate that with?\n\n"
            f"4. POLITE EXIT: Thank you for your service to the community, have a wonderful day!"
        )

        return {
            "sales_lane": "CLINICAL_RECALL_REBOOKING",
            "opening": opening,
            "context_confirmation": f"Confirm clinic practice at {company} — intake & recall workflow",
            "open_to_selling": "Propose Patient Recall & Rebooking System — intake -> scheduling -> recall -> follow-up with analytics.",
            "motivation_discovery": "Identify overdue recall volume and front-desk follow-up load.",
            "timing_discovery": "Workflow live within 5 business days, reporting weekly.",
            "condition_discovery": "Evaluate PMS/EHR scheduling and recall list handling.",
            "price_expectation": "$1,997/mo retainer with weekly reporting, zero contract lock-in.",
            "next_step": "Coordinate 5-minute workflow review with Office Manager.",
            "objection_handlers": {
                "NOT_INTERESTED": "Understood! Would you like a 1-page recall workflow map for {city} clinics — intake->scheduling->recall — to review?",
                "HIPAA_CONCERN": "All workflows run inside your existing HIPAA-aware PMS/EHR with audit logging and no external patient storage.",
                "ALREADY_HAVE_ANSWERING_SERVICE": "Many practices still work recall manually — we automate the overdue list and rebooking so nothing falls through, with reporting.",
            },
            "polite_exit": f"Thank you {first_name}, have a great day caring for your patients!",
            "offer": {
                "name": "Patient Recall & Rebooking System",
                "tier": "CLINICAL_WORKFLOW",
                "estimated_deal_value_usd": 1997.0,
                "neteller_checkout_link": checkout_link,
            },
            "Call_Script": call_script,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DATASET ENRICHMENT HELPER
# ══════════════════════════════════════════════════════════════════════════════

def enrich_leads_with_playbooks(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriches 100% of leads with their segment, script_id, sales_strategy, and Call_Script."""
    enriched = []
    for lead in leads:
        lead_copy = dict(lead)
        playbook = DialerScriptEngine.generate_playbook(lead_copy)
        
        lead_copy["segment"] = playbook["segment"]
        lead_copy["script_id"] = playbook["script_id"]
        lead_copy["sales_lane"] = playbook.get("sales_lane") or lead_copy.get("sales_lane") or "GENERAL"
        lead_copy["Call_Script"] = playbook["Call_Script"]
        
        # Merge structured sales_strategy
        lead_copy["sales_strategy"] = {
            "script_id": playbook["script_id"],
            "segment": playbook["segment"],
            "opening": playbook["opening"],
            "context_confirmation": playbook["context_confirmation"],
            "open_to_selling": playbook["open_to_selling"],
            "motivation_discovery": playbook["motivation_discovery"],
            "timing_discovery": playbook["timing_discovery"],
            "condition_discovery": playbook.get("condition_discovery", ""),
            "price_expectation": playbook["price_expectation"],
            "next_step": playbook["next_step"],
            "objection_handlers": playbook["objection_handlers"],
            "polite_exit": playbook["polite_exit"],
            "offer": playbook["offer"],
        }
        
        lead_copy["expected_value_usd"] = playbook["offer"]["estimated_deal_value_usd"]
        
        enriched.append(lead_copy)
    return enriched
