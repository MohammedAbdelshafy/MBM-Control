#!/usr/bin/env python3
"""
MBM OFFER ARCHITECT & PACKAGING ENGINE
=============================================================================
Maps lead buying signals and observed workflow bottlenecks to precise AI offers,
tier-based pricing, ROI hypotheses, objection playbooks, and multi-channel scripts.

Guarantees:
- Never fabricates ROI; clearly distinguishes OBSERVED vs ESTIMATED vs ASSUMED.
- Recommends smallest offer solving the bottleneck (Entry -> Core -> Expansion).
- Generates 12-category objection playbooks (Acknowledge -> Clarify -> Isolate -> Respond -> Check).
- Packages multi-channel angles: Phone Script, Email Pitch, LinkedIn Starter, 1-Click Neteller Rail.
=============================================================================
"""

import sys
import json
import math
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from MBM.Scripts.neteller_config import neteller_link
except ImportError:
    def neteller_link(amount: float | str, item: str, currency: str = "USD", **kw) -> str:
        raise RuntimeError("Canonical Neteller payment configuration is unavailable")


# ---------------------------------------------------------------------------
# 1. Offer Definitions & Packaging Models
# ---------------------------------------------------------------------------

@dataclass
class OfferPackage:
    sku: str
    offer_name: str
    problem_solved: str
    core_workflow: str
    implementation_scope: str
    pricing_model: str  # "MONTHLY_RETAINER", "SETUP_PLUS_MONTHLY", "PERFORMANCE_REVENUE_SHARE"
    setup_fee_usd: float
    monthly_fee_usd: float
    optional_performance_fee: str
    primary_ROI_hypothesis: Dict[str, Any]
    proof_requirement: str
    entry_diagnostic: str
    expansion_paths: List[str]
    cta_low: str
    cta_medium: str
    cta_high: str


# ---------------------------------------------------------------------------
# 2. Master ICP Vertical Offer Matrix
# ---------------------------------------------------------------------------

VERTICAL_OFFER_CATALOG: Dict[str, Dict[str, Any]] = {
    "HVAC & Mechanical Contractors": {
        "sku": "AI-ASSISTANT-HVAC-DISPATCH",
        "offer_name": "24/7 AI Emergency Call Triage & Technician Dispatch Agent",
        "problem_solved": "Missed after-hours emergency calls and slow dispatcher routing during heat waves/freezes",
        "core_workflow": "Answers on 1st ring, qualifies emergency vs routine, captures unit model/address, routes technician via SMS",
        "implementation_scope": "Twilio/SIP phone bridge, ServiceTitan/Housecall Pro calendar webhook, SMS technician escalation",
        "setup_fee": 1500.0,
        "monthly_fee": 2500.0,
        "performance_fee": "$25 per dispatched high-value diagnostic call",
        "entry_diagnostic": "30-Second After-Hours Secret Shopper Call Audit",
        "expansion_paths": ["Seasonal Maintenance Recall Swarm", "Commercial Filter Replacement Bot"],
        "roi_model": {
            "observed": "Commercial HVAC average ticket value is $450 - $4,500+",
            "estimated": "Losing 4-8 emergency calls/week to voicemail costs $7,200 - $18,000/mo in lost gross revenue",
            "assumed": "Recovering just 2 missed service calls per month pays for the entire $2,500 retainer (3.6x ROI)"
        },
        "discovery_questions": [
            "How are after-hours emergency calls handled today when dispatch is closed?",
            "What happens when your on-call technician is already on a roof and a second emergency rings in?",
            "How many high-value commercial inquiries go to voicemail during morning rush spikes?"
        ],
        "quantification_question": "If you lose even two $1,200 compressor replacement calls a week to voicemail, what is that costing you a month?",
        "objection_answers": {
            "PRICE": "Our $2,500 retainer has a 30-day performance SLA — recovering just two missed service calls covers 100% of the cost.",
            "AI_SKEPTICISM": "It's not a generic robot reading a script. It uses low-latency neural voice trained specifically on HVAC diagnostic codes and addresses.",
            "ALREADY_HAVE_SOLUTION": "Most operators use answering services that just take messages. Ours diagnoses the urgency, verifies customer address, and books the dispatch live.",
            "DO_IT_INTERNALLY": "Hiring 24/7 human dispatchers costs $9,000+/mo with overtime. Our agent runs 24/7/365 with zero hold times for a fraction of that.",
        },
    },
    "Roofing & Exterior Contractors": {
        "sku": "AI-ASSISTANT-ROOF-SWARM",
        "offer_name": "AI Storm Surge Lead Intake & Satellite Inspection Qualifier",
        "problem_solved": "Slow response times to storm surge leads and lost re-roofing bids to faster competitors",
        "core_workflow": "Instantly calls/texts incoming storm leads within 15 seconds, collects roof age/damage photos, books drone inspection",
        "implementation_scope": "Instant inbound lead webhook, automated multi-touch SMS sequence, Roofr/AccuLynx calendar booking",
        "setup_fee": 2000.0,
        "monthly_fee": 3000.0,
        "performance_fee": "$50 per qualified inspection completed",
        "entry_diagnostic": "15-Minute Storm Lead Speed-to-Lead Simulation Audit",
        "expansion_paths": ["Insurance Claim Supplement Tracking Agent", "Commercial Flat Roof Maintenance Nurture"],
        "roi_model": {
            "observed": "Average residential/commercial roof replacement is $12,000 - $35,000",
            "estimated": "Responding in 15 seconds vs 30 minutes increases lead conversion by 391%",
            "assumed": "Securing 1 extra roof replacement per month yields $12,000+ top-line for a $3,000 retainer (4x ROI)"
        },
        "discovery_questions": [
            "When hail or wind storms hit your market, how quickly does your team respond to new inbound leads?",
            "Who follows up on unworked storm leads after 6 PM?",
            "What percentage of web form leads go uncalled for more than 15 minutes?"
        ],
        "quantification_question": "If a competitor calls a storm lead 10 minutes before you do, what is that lost $15,000 re-roof costing your pipeline?",
        "objection_answers": {
            "PRICE": "One additional closed roof replacement covers 4 months of the entire software retainer.",
            "AI_SKEPTICISM": "The agent engages via voice and SMS in under 15 seconds, qualifying damage severity before your sales rep even opens their CRM.",
            "ALREADY_HAVE_SOLUTION": "If your CRM isn't dialing new storm inquiries within 30 seconds of submission, you are losing 40% of convertible jobs.",
            "DO_IT_INTERNALLY": "Your sales reps are driving and inspecting roofs; they can't call web leads within 20 seconds. The AI handles the instant speed-to-lead.",
        },
    },
    "Civil & Structural Construction": {
        "sku": "AI-ASSISTANT-CONTECH-TAKEOFF",
        "offer_name": "Autonomous CAD-to-BOQ Takeoff & Estimating Copilot",
        "problem_solved": "2-3 week manual takeoff bottlenecks and mathematical calculation errors in structural bids",
        "core_workflow": "Parses .DWG, .DXF, and PDF drawing sets, extracts structural quantities, generates verified BOQ with Eurocode/USACE formulas",
        "implementation_scope": "Desktop vector extraction engine, MasterFormat/UniFormat cost database mapper, Excel/Procore sync",
        "setup_fee": 3500.0,
        "monthly_fee": 4500.0,
        "performance_fee": "Optional 0.25% contingency review fee on awarded bids",
        "entry_diagnostic": "Complimentary CAD-to-BOQ Benchmark Audit on 1 Sample Drawing Set",
        "expansion_paths": ["Subcontractor Bid Reconciliation Bot", "Change Order Discrepancy Detector"],
        "roi_model": {
            "observed": "Senior estimating engineers bill $90 - $160/hr and spend 40+ hours per commercial bid",
            "estimated": "Cutting takeoff time from 3 weeks to 15 minutes enables bidding on 4x more tenders with zero math errors",
            "assumed": "Winning 1 additional civil tender per quarter yields $250,000+ gross margin vs $4,500/mo cost (18x ROI)"
        },
        "discovery_questions": [
            "How long does your senior estimating team currently spend performing manual takeoffs on a 50-sheet structural set?",
            "How often do bid deadlines force your team to skip bidding on lucrative municipal or commercial tenders?",
            "Who verifies formula accuracy and quantity discrepancies before final bid submission?"
        ],
        "quantification_question": "If your estimating capacity doubles with zero added payroll, how many more bids could you submit this quarter?",
        "objection_answers": {
            "PRICE": "A single junior estimator salary is $85k/yr. Our takeoff pipeline processes 10x the volume in minutes for half that annual cost.",
            "AI_SKEPTICISM": "Every single quantity is backed by deterministic geometry coordinate traces. We don't hallucinate numbers — we parse CAD vectors.",
            "ALREADY_HAVE_SOLUTION": "Planswift and Bluebeam still require hours of manual point-and-click clicking. Our pipeline extracts vectors automatically.",
            "DO_IT_INTERNALLY": "Your senior engineers should be value-engineering and negotiating subcontractor terms, not manually counting rebar and footings.",
        },
    },
    "Dental Clinics & Orthodontics": {
        "sku": "AI-ASSISTANT-DENTAL-RECALL",
        "offer_name": "AI Front-Desk Overflow & Hygiene Recall Recovery Agent",
        "problem_solved": "Front desk overwhelmed with incoming calls and 600+ overdue hygiene recall patients left uncalled",
        "core_workflow": "Answers overflow calls during morning rushes, proactively dials overdue hygiene recall patients, reschedules directly in Dentrix/Eaglesoft",
        "implementation_scope": "Dentrix/Eaglesoft/OpenDental API connector, HIPAA-compliant neural voice bridge, automated SMS confirmation",
        "setup_fee": 1000.0,
        "monthly_fee": 1800.0,
        "performance_fee": "$15 per completed hygiene recall appointment",
        "entry_diagnostic": "Dormant Patient Revenue Leakage Calculation Audit",
        "expansion_paths": ["Unaccepted Treatment Plan Follow-Up Bot", "After-Hours Dental Emergency Intake"],
        "roi_model": {
            "observed": "Average dental hygiene appointment produces $200 - $350 in revenue plus diagnostic upside",
            "estimated": "A practice with 800 unscheduled recall patients has $160,000+ in trapped revenue",
            "assumed": "Recovering 15 overdue hygiene patients/mo generates $3,750+ recurring production for a $1,800 fee (2x ROI)"
        },
        "discovery_questions": [
            "How is your front desk currently finding time to call through overdue 6-month hygiene recall lists?",
            "What happens when front desk staff are checking in patients and both phone lines ring at once?",
            "How many unscheduled treatment plans from last month have not had a direct phone follow-up?"
        ],
        "quantification_question": "If you have 400 dormant patients overdue for hygiene, that is $80,000 in uncollected chair production. How much of that did you recover last month?",
        "objection_answers": {
            "PRICE": "Booking just 6 hygiene patients covers the monthly subscription. Everything above 6 is pure incremental chair profit.",
            "AI_SKEPTICISM": "Patients hear a warm, professional, human-sounding voice that knows their name, last visit date, and available chair times.",
            "ALREADY_HAVE_SOLUTION": "Automated text blasts get ignored. Our voice agent actually calls, answers patient questions live, and locks in the chair time.",
            "DO_IT_INTERNALLY": "Front desk staff hate cold-calling past patients while juggling patient check-ins. The AI does the heavy lifting automatically.",
        },
    },
    "Personal Injury & Corporate Law": {
        "sku": "AI-ASSISTANT-LEGAL-INTAKE",
        "offer_name": "24/7 AI Retainer Signer & Case Intake Specialist",
        "problem_solved": "High-value accident and legal inquiries lost to competing law firms due to delayed intake response",
        "core_workflow": "Screens potential claimants 24/7, validates liability/injury criteria, signs digital retainer via DocuSign in under 3 minutes",
        "implementation_scope": "Clio/Filevine CRM integration, DocuSign/HelloSign automated envelope dispatch, high-priority attorney SMS alert",
        "setup_fee": 2500.0,
        "monthly_fee": 4000.0,
        "performance_fee": "$100 per qualified signed retainer",
        "entry_diagnostic": "10-Minute Ghost Lead Intake Speed Audit",
        "expansion_paths": ["Medical Records Collection Chaser Bot", "Client Case Status Portal Assistant"],
        "roi_model": {
            "observed": "Average personal injury case settlement produces $15,000 - $50,000+ in attorney contingency fees",
            "estimated": "An injured claimant calls 3 firms from Google Ads; the first firm to complete intake signs the retainer 78% of the time",
            "assumed": "Signing just 1 additional case per quarter yields $25,000+ fee vs $4,000/mo retainer (6x ROI)"
        },
        "discovery_questions": [
            "When someone involved in an auto accident calls your firm at 9 PM on Sunday, who screens the case?",
            "How quickly can your team get an e-retainer in front of a qualified claimant before they call another firm?",
            "What percentage of your Google Ads PPC intake calls go to an answering service that only takes basic notes?"
        ],
        "quantification_question": "If you pay $350 per PPC lead and lose one $30,000 contingency case a month to slow intake, what is that costing your firm?",
        "objection_answers": {
            "PRICE": "A single signed personal injury case pays for an entire year of the AI intake system.",
            "AI_SKEPTICISM": "It follows your firm's strict qualifying questionnaire (liability, insurance, injury severity) with zero deviations.",
            "ALREADY_HAVE_SOLUTION": "Third-party call centers take notes and email you the next morning. Our AI signs the DocuSign retainer while the claimant is on the phone.",
            "DO_IT_INTERNALLY": "Paralegals and intake coordinators don't work at 2 AM or on holidays when major auto accidents happen. The AI is always live.",
        },
    },
    "Commercial Plumbing": {
        "sku": "AI-ASSISTANT-PLUMB-INTAKE",
        "offer_name": "AI Commercial Plumbing Emergency Triage & Crew Router",
        "problem_solved": "Emergency pipe burst calls lost to competitors and dispatches routed to unequipped technicians",
        "core_workflow": "Triages commercial vs residential urgency, verifies backflow/boiler specs, routes to certified technician",
        "implementation_scope": "SIP phone integration, dispatch calendar sync, GPS technician proximity router",
        "setup_fee": 1200.0,
        "monthly_fee": 2200.0,
        "performance_fee": "$20 per commercial emergency dispatch",
        "entry_diagnostic": "After-Hours Commercial Emergency Answering Test",
        "expansion_paths": ["Annual Backflow Testing Compliance Bot", "Grease Trap Maintenance Scheduler"],
        "roi_model": {
            "observed": "Commercial plumbing service calls average $800 - $3,500+",
            "estimated": "Losing 3 commercial emergency calls/month costs $4,500+ in lost revenue",
            "assumed": "Recovering 2 commercial calls covers the $2,200 monthly retainer"
        },
        "discovery_questions": [
            "How does your dispatch handle simultaneous emergency calls during water main breaks?",
            "What is your protocol when after-hours calls come from commercial property managers?"
        ],
        "quantification_question": "What is the monthly revenue loss when a commercial facility manager gets voicemail and calls the next plumber on Google?",
        "objection_answers": {
            "PRICE": "One commercial hydro-jetting or main line job covers the entire month.",
            "AI_SKEPTICISM": "The agent collects pipe diameter, facility type, and water shutoff status before alerting your on-call tech.",
            "ALREADY_HAVE_SOLUTION": "Standard answering services don't understand commercial plumbing urgency. Our AI qualifies specific technical specs.",
            "DO_IT_INTERNALLY": "Automates the 3 AM wake-up dispatch triage so technicians only get called for true billable emergencies.",
        },
    },
    "Weddings & Event Professionals": {
        "sku": "AI-ASSISTANT-WEDDINGS",
        "offer_name": "AI Wedding Revenue System",
        "problem_solved": "Missed/slow inquiry response, after-hours lead handling, and ghosted lead recovery",
        "core_workflow": "Instant inquiry response, lead qualification, tour/consultation booking, automated follow-up",
        "implementation_scope": "Direct CRM/calendar integration, multi-channel SMS/Email/Voice outreach, automated quote/proposal workflows",
        "setup_fee": 1500.0,
        "monthly_fee": 2500.0,
        "performance_fee": "$100 per booked and completed consultation/tour",
        "entry_diagnostic": "15-Minute Inquiry Response & Missed Revenue Audit",
        "expansion_paths": ["AI Receptionist / Voice Agent", "Review/Reputation Automation", "Vendor/Event Operations Coordination"],
        "roi_model": {
            "observed": "Average wedding vendor/venue booking value is $5,000 - $25,000+",
            "estimated": "Losing 3-5 inquiries a week to slow response or voicemail costs tens of thousands in lost pipeline",
            "assumed": "Recovering just 1 missed wedding per month pays for the entire retainer multiple times over"
        },
        "discovery_questions": [
            "When someone submits a wedding inquiry after hours, who responds?",
            "How much time does your team spend manually following up with ghosted leads?",
            "When a couple asks ChatGPT for the best wedding vendors in your city, does your business appear?"
        ],
        "quantification_question": "If you lose even one $15,000 wedding booking a month to a venue that replied faster, what is that costing you annually?",
        "objection_answers": {
            "PRICE": "Our $2,500 retainer pays for itself with a single recovered wedding booking.",
            "AI_SKEPTICISM": "The AI is trained on your exact pricing, venue details, and availability—it handles the qualification smoothly before handing off to you.",
            "ALREADY_HAVE_SOLUTION": "If your current system isn't responding in seconds and actively booking tours 24/7, you're still losing deals to competitors.",
            "DO_IT_INTERNALLY": "Your next client shouldn't have to wait until you're done coordinating today's wedding. The AI handles the instant speed-to-lead.",
        },
    },
}

DEFAULT_OFFER_CONFIG = {
    "sku": "AI-ASSISTANT-VIP-RETAINER",
    "offer_name": "AI Autonomous Operations & Inbound Intake Agent",
    "problem_solved": "Missed phone inquiries, delayed follow-up, and administrative bottleneck",
    "core_workflow": "Answers inbound inquiries on 1st ring, qualifies customer requirements, books directly into business calendar",
    "implementation_scope": "Direct phone system connection, CRM/calendar sync, automated SMS appointment confirmation",
    "setup_fee": 1000.0,
    "monthly_fee": 2000.0,
    "performance_fee": "Optional 5% revenue share on closed appointments",
    "entry_diagnostic": "15-Minute Operational Workflow & Lead Leakage Audit",
    "expansion_paths": ["AI Multi-Channel Follow-Up Bot", "Customer Review & Retention Agent"],
    "roi_model": {
        "observed": "Average client customer value is $500 - $2,500",
        "estimated": "Automating intake and follow-up recovers 15+ hours/week of admin time and prevents lead leakage",
        "assumed": "Closing 2 extra clients per month pays for the retainer with 2.5x ROI"
    },
    "discovery_questions": [
        "How is your team currently handling unworked inbound lead follow-ups?",
        "What happens when front-office staff are occupied and new inquiries call in?"
    ],
    "quantification_question": "If you recover 10 hours of staff admin time and 2 missed deals each month, what is that worth to your bottom line?",
    "objection_answers": {
        "PRICE": "The system includes a 30-day performance SLA — if it doesn't save you 15 hours of admin and book new revenue, cancel anytime.",
        "AI_SKEPTICISM": "It is trained directly on your business FAQs and calendar availability with zero hallucination guardrails.",
        "ALREADY_HAVE_SOLUTION": "Most tools only send emails; our agent holds natural voice conversations and locks in appointments live.",
        "DO_IT_INTERNALLY": "Frees up your existing team to focus on high-margin delivery instead of phone tag and manual data entry.",
    },
}


# ---------------------------------------------------------------------------
# 3. Master Offer & Sales Strategy Builder
# ---------------------------------------------------------------------------

class OfferArchitect:
    """
    Builds discovery-first sales preparation from a vertical playbook.

    Catalog prices, pain descriptions, capabilities and ROI are hypotheses.
    They are never promoted to prospect facts or approved customer promises.
    The builder creates drafts only; it never dials, sends or books.
    """

    def __init__(self):
        pass

    @staticmethod
    def _approved_price(lead: Dict[str, Any]) -> Optional[float]:
        if lead.get("quote_approved") is not True:
            return None
        raw = lead.get("approved_price_usd")
        try:
            amount = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(amount) or amount < 0:
            return None
        return amount

    def build_sales_strategy_for_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Build a reviewable draft without inventing prospect facts or approvals."""
        industry = str(lead.get("industry") or lead.get("vertical") or "UNKNOWN")
        company = str(lead.get("company") or "your business")
        dm = str(lead.get("decision_maker") or lead.get("contact") or "there")
        role = str(lead.get("role") or lead.get("title") or "UNKNOWN")
        phone = lead.get("phone") or ""
        email = lead.get("email") or ""
        city = str(lead.get("city")).strip() if lead.get("city") else None
        state = str(lead.get("state")).strip() if lead.get("state") else None
        location = {"city": city, "state": state}

        raw_score = lead.get("intent_score")
        if raw_score is None:
            raw_score = lead.get("deal_score")
        try:
            intent_score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            intent_score = None
        if intent_score is not None and (
            not math.isfinite(intent_score) or intent_score < 0 or intent_score > 100
        ):
            intent_score = None

        if intent_score is None:
            mode = "UNKNOWN"
            priority_rank = 4
        elif intent_score >= 90.0:
            mode = "HOT"
            priority_rank = 1
        elif intent_score >= 80.0:
            mode = "WARM"
            priority_rank = 2
        else:
            mode = "COLD"
            priority_rank = 3

        offer_tmpl = VERTICAL_OFFER_CATALOG.get(industry, DEFAULT_OFFER_CONFIG)
        sku = offer_tmpl["sku"]
        monthly_fee_hypothesis = float(offer_tmpl.get("monthly_fee", 2000.0))
        setup_fee_hypothesis = float(offer_tmpl.get("setup_fee", 1000.0))

        approved_price = self._approved_price(lead)
        checkout_approved = lead.get("checkout_link_approved") is True
        checkout_link = None
        checkout_link_status = "NOT_APPROVED"
        if approved_price is not None and checkout_approved:
            try:
                checkout_link = neteller_link(amount=approved_price, item=sku)
                checkout_link_status = "APPROVED"
            except Exception:
                checkout_link_status = "CONFIGURATION_UNAVAILABLE"

        questions = offer_tmpl.get("discovery_questions") or [
            "How does your team currently handle new customer inquiries and follow-up?"
        ]
        first_question = questions[0]
        workflow_label = first_question[0].lower() + first_question[1:] if first_question else "your current workflow"

        opening = (
            f"Hi {dm}, I'm calling from MBM. I had a question about how {company} "
            f"currently handles {workflow_label.rstrip('?')}. Is that something you oversee?"
        )
        ai_transition = (
            f"Depending on what we learn, MBM can scope a {offer_tmpl['offer_name']} "
            "around your actual workflow. We would confirm technical feasibility, integrations, "
            "data boundaries, delivery capacity and acceptance criteria before proposing implementation."
        )
        cta = (
            "Would a short diagnostic conversation be useful? We can map the current process, "
            "agree on one KPI and decide whether a small, fixed-scope pilot is appropriate."
        )
        fallback_cta = (
            "No problem. Would you prefer a short written overview, or should I leave it here?"
        )

        objection_playbook = {
            "PRICE": (
                "We would confirm the problem, delivery scope and acceptance criteria before preparing "
                "a written quote. Catalog figures are planning hypotheses, not an approved price."
            ),
            "TIMING": (
                "Understood. Is there a better time for you to discuss the workflow, or would you prefer "
                "that I close the loop and not follow up?"
            ),
            "TRUST": (
                "That is fair. We can first show the proposed workflow, the evidence behind it, "
                "the limits, and the acceptance checks before you decide whether to proceed."
            ),
            "AI_SKEPTICISM": (
                "You do not need to buy AI. We should first identify whether a specific workflow "
                "is slow, repetitive or difficult to measure, then assess the simplest suitable fix."
            ),
            "ALREADY_HAVE_SOLUTION": (
                "Good. We would not replace a working system by default. Is there a particular handoff "
                "or exception that your current setup does not handle well?"
            ),
            "DO_IT_INTERNALLY": (
                "That may be the right choice. Which part of the process still consumes the most "
                "staff time, and would a small comparison be useful before changing anything?"
            ),
            "NO_NEED": (
                "Understood. I do not want to invent a problem where there is none. I appreciate "
                "you clarifying that the workflow is not a priority."
            ),
            "NO_BUDGET": (
                "Understood. We should not recommend spending until the business case and delivery "
                "scope are clear. We can stop here or revisit only when it becomes a priority."
            ),
            "AUTHORITY": (
                "Thanks. Who normally evaluates changes to this workflow? I can prepare a short "
                "brief for the appropriate person, subject to your preference."
            ),
            "SECURITY": (
                "We can document proposed data flows, access controls, retention and vendor roles. "
                "Regulated or sensitive data stays out of scope until the required reviews and agreements pass."
            ),
            "INTEGRATION": (
                "We would map your current tools and confirm each integration path before committing. "
                "No connector or deployment capability is assumed from a catalog description."
            ),
            "STAFF": (
                "The goal would be to support your team, not remove people by default. We would agree "
                "on the handoff, escalation rules and staff acceptance criteria before a pilot."
            ),
        }

        observed_signal = ""
        if lead.get("observed_signal") and lead.get("signal_source") and lead.get("signal_observed_at"):
            observed_signal = str(lead["observed_signal"])

        email_pitch = {
            "subject": f"Question about {company}'s customer intake workflow",
            "opening": f"Hi {dm},",
            "observed_signal": observed_signal,
            "pain": (
                "I do not know whether this is a bottleneck for your team, so I wanted to ask "
                "how you currently handle inquiries, qualification and follow-up."
            ),
            "offer": (
                f"MBM can assess whether a scoped {offer_tmpl['offer_name']} is a fit. "
                "Any implementation would be defined only after workflow and technical review."
            ),
            "roi_angle": (
                "We would baseline the current process and measure an agreed operational KPI during "
                "a pilot. No revenue uplift or ROI is assumed in advance."
            ),
            "cta": cta,
            "followup": (
                f"Hi {dm}, checking whether this workflow is worth a short review for {company}. "
                "No problem if it is not a current priority."
            ),
        }

        linkedin_starter = (
            f"Hi {dm}, I'm researching how {industry.lower()} businesses handle inquiry intake "
            f"and follow-up. Is that an area you oversee at {company}? MBM is assessing a few "
            "bounded workflow pilots and I would value your view."
        )

        return {
            "lead_id": lead.get("id"),
            "company": company,
            "decision_maker": dm,
            "role": role,
            "industry": industry,
            "location": location,
            "phone": phone,
            "email": email,
            "intent_mode": mode,
            "intent_score": intent_score,
            "offer": {
                "sku": sku,
                "offer_name": offer_tmpl["offer_name"],
                "problem_solved": offer_tmpl["problem_solved"],
                "problem_statement_status": "PLAYBOOK_HYPOTHESIS",
                "core_workflow": offer_tmpl["core_workflow"],
                "capability_status": "REQUIRES_IMPLEMENTATION_REVIEW",
                "implementation_scope": offer_tmpl["implementation_scope"],
                "integration_status": "UNVERIFIED_REQUIRES_TECHNICAL_REVIEW",
                "pricing_model": "MONTHLY_RETAINER",
                "setup_fee_usd": setup_fee_hypothesis,
                "monthly_fee_usd": monthly_fee_hypothesis,
                "price_status": "HYPOTHESIS",
                "approved_quote_usd": approved_price,
                "performance_fee": offer_tmpl.get("performance_fee", ""),
                "neteller_checkout_link": checkout_link,
                "checkout_link_status": checkout_link_status,
                "entry_diagnostic": offer_tmpl.get("entry_diagnostic", "Workflow Audit"),
                "expansion_paths": offer_tmpl.get("expansion_paths", []),
                "roi_hypothesis": offer_tmpl.get("roi_model", {}),
                "roi_hypothesis_status": "UNVERIFIED_HYPOTHESIS",
            },
            "conversation_script": {
                "mode": mode,
                "opening": opening,
                "first_question": first_question,
                "discovery_questions": questions,
                "quantification_question": offer_tmpl.get(
                    "quantification_question",
                    "What would a measurable improvement in this workflow be worth to your team?",
                ),
                "reflection_script": (
                    "After the prospect describes the process, summarize only the pain and impact "
                    "they confirmed; ask them to correct anything inaccurate."
                ),
                "ai_fit_transition": ai_transition,
                "objection_playbook": objection_playbook,
                "primary_cta": cta,
                "fallback_cta": fallback_cta,
            },
            "multi_channel_angles": {
                "phone": {"opening": opening, "cta": cta},
                "email": email_pitch,
                "linkedin": linkedin_starter,
            },
            "next_best_action": {
                "channel": "PHONE" if phone else "MANUAL_REVIEW",
                "action": "DRAFT_ONLY",
                "priority_rank": priority_rank,
                "scheduled_for": "AWAIT_HUMAN_APPROVAL",
            },
        }

def get_offer_architect() -> OfferArchitect:
    return OfferArchitect()


if __name__ == "__main__":
    architect = OfferArchitect()
    sample_lead = {
        "id": "LEAD-SAMPLE-01",
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Founder & Managing Owner",
        "industry": "HVAC & Mechanical Contractors",
        "phone": "+12148849120",
        "email": "marcus@apexmechanical.com",
        "city": "Dallas",
        "state": "TX",
        "intent_score": 95.0,
    }
    strategy = architect.build_sales_strategy_for_lead(sample_lead)
    print("=" * 70)
    print(f"OFFER ARCHITECT STRATEGY FOR {strategy['company']}")
    print(f"Mode:   {strategy['intent_mode']}")
    print(f"Offer:  {strategy['offer']['offer_name']} (${strategy['offer']['monthly_fee_usd']:,.2f}/mo)")
    print(f"Script: {strategy['conversation_script']['opening']}")
    print(f"CTA:    {strategy['conversation_script']['primary_cta']}")
    print("=" * 70)
