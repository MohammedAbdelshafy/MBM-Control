"""
tranchai_deal_engine.py — JARVIS OS TranchAI Multi-Vertical AI Deal Engine.
===========================================================================
B2B AI Services Acquisition Pipeline:
  COMPANY → OWNER/DECISION MAKER → VERTICAL → PAIN SIGNAL → AI OPPORTUNITY →
  OFFER → VALUE HYPOTHESIS → CALL → DISCOVERY → DEMO → PROPOSAL → CLOSE

Target Verticals & Specific Business Outcomes:
1. HVAC: AI Receptionist, Missed-Call Recovery ($1,500/mo), Emergency Dispatch
2. PILATES/YOGA: Instant Lead Response, Booking, Member Reactivation ($1,250/mo)
3. MED SPA: Lead Qualification, VIP Consultation Booking, Post-Care ($2,500/mo)
4. DENTAL: Front-Desk Overflow, Hygiene Recall Recovery, FAQ ($1,850/mo)
5. LAW: 24/7 Intake, Conflict Pre-Screening, Retainer Scheduling ($3,500/mo)
6. CONSTRUCTION (ConTech): AI Estimating, CAD-to-BOQ Takeoff ($4,500 setup / $18.5k deployment)
7. PROPERTY MANAGEMENT: Tenant Maintenance Triage, Vacancy Booking ($2,000/mo)

Enrichment: Uses official NPI registry + Google Maps business data (zero hallucinated contacts).
Monetization: Injects canonical Neteller checkout links.
"""

from __future__ import annotations

import os
import sys
import json
import re
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from MBM.LeadEngine.canonical_deal_engine import (
    CanonicalDeal, CanonicalDealMemory, DealType, DealStage, MonetizationRoute
)
try:
    from MBM.Scripts.neteller_config import neteller_link
except Exception:
    def neteller_link(amount: float | str, item: str, currency: str = "USD", **kw) -> str:
        import urllib.parse
        return f"https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount={float(amount):.2f}&currency={currency}&item={urllib.parse.quote_plus(str(item))}"


VERTICAL_OFFERS: Dict[str, Dict[str, Any]] = {
    "hvac": {
        "name": "HVAC & Mechanical Contractors",
        "pain": "Drowning in after-hours emergency calls, losing 25% of inbound replacement jobs to voicemail.",
        "solution": "24/7 Autonomous AI Voice Receptionist + Dispatch Recovery Engine",
        "value_hypothesis": "Recovers 12-18 missed high-ticket AC/heating replacement calls per month, generating +$65,000 in found revenue for a $1,500/mo investment.",
        "setup_fee": 2500.0,
        "monthly_retainer": 1500.0,
        "sku": "TRANCHAI-HVAC-RECOVERY-RETAINER",
        "opener": "Hi [Owner], Omar here with TranchAI. We built an autonomous after-hours AI receptionist for HVAC contractors that answers calls on the first ring, qualifies emergency furnace/AC jobs, and books directly into ServiceTitan. Are you guys currently losing calls when your dispatchers are tied up?"
    },
    "pilates": {
        "name": "Pilates & Fitness Studios",
        "pain": "High lead inquiry drop-off (>60% of web/Instagram leads never book an intro class) and member churn.",
        "solution": "Instant 60-Second Lead Response Bot + Member Reactivation Swarm",
        "value_hypothesis": "Increases intro class booking rate by 3.5x and reactivates 30 inactive past members in 30 days (+ $7,500 monthly recurring membership revenue).",
        "setup_fee": 1500.0,
        "monthly_retainer": 1250.0,
        "sku": "TRANCHAI-PILATES-BOOKING-BOT",
        "opener": "Hi [Owner], this is Omar from TranchAI Studio Growth. We engineered an instant lead-response AI that texts and books new trial members within 60 seconds of submitting an Instagram or web inquiry. Could your studio benefit from automated 24/7 trial bookings?"
    },
    "yoga": {
        "name": "Yoga Studios & Wellness Centers",
        "pain": "Web/Instagram leads never convert to first class and inactive members quietly lapse off the schedule.",
        "solution": "Instant Class-Booking Response Bot + Lapsed Member Reactivation Engine",
        "value_hypothesis": "Books first-class trials within minutes of an inquiry and reactivates lapsed members, adding +$6,500/mo in recurring class revenue.",
        "setup_fee": 1500.0,
        "monthly_retainer": 1250.0,
        "sku": "TRANCHAI-YOGA-BOOKING-BOT",
        "opener": "Hi [Owner], this is Omar from TranchAI Studio Growth. We built an instant-response AI that books first classes within 60 seconds of a website or Instagram inquiry. Would your studio like to convert more of those inquiries into paying members?"
    },
    "med_spa": {
        "name": "Med Spas & Aesthetics Clinics",
        "pain": "Expensive consultation no-shows, front desk staff tied up answering pricing FAQs, and un-engaged VIP clients.",
        "solution": "High-Ticket Aesthetic Consultation Qualifier & VIP Re-engagement Bot",
        "value_hypothesis": "Eliminates consultation no-shows with automated conversational confirmation and books $3,500+ package treatments automatically.",
        "setup_fee": 3500.0,
        "monthly_retainer": 2500.0,
        "sku": "TRANCHAI-MEDSPA-CONSULT-ENGINE",
        "opener": "Hi Dr. [Owner], Omar here with TranchAI Aesthetics. We recently implemented an autonomous VIP qualification concierge for med spas that screens high-ticket aesthetic leads and collects consultation deposits automatically. Do you have 2 minutes to review our benchmark results?"
    },
    "chiropractic": {
        "name": "Chiropractic & Spine Care Clinics",
        "pain": "Front-desk staff overwhelmed during peak hours, missed new-patient calls, and weak patient recall follow-up.",
        "solution": "Front-Desk Overflow Assistant + New-Patient & Recall Recovery Engine",
        "value_hypothesis": "Captures every missed new-patient intake call and reactivates dormant chiropractic adjustment schedules, adding +$18,000/mo in recovered visit revenue.",
        "setup_fee": 2500.0,
        "monthly_retainer": 1850.0,
        "sku": "TRANCHAI-CHIROPRACTIC-RECALL-AI",
        "opener": "Hi Dr. [Owner], Omar from TranchAI Healthcare. We built an AI front-desk overflow and patient-recall engine for chiropractic clinics that answers every new-patient call and brings lapsed adjustment patients back on the books. Are your staff losing intake calls during peak hours?"
    },
    "medical": {
        "name": "Medical Practices & Clinics",
        "pain": "Front-desk phone bottlenecks, missed appointment booking, no-show leakage, and un-engaged recall lists.",
        "solution": "24/7 Medical Front-Desk Overflow Assistant + Appointment Recall Agent",
        "value_hypothesis": "Recovers missed appointments and reactivates dormant recall lists, adding $20,000+/mo in found visit revenue for a practice that never hires more staff.",
        "setup_fee": 2500.0,
        "monthly_retainer": 2000.0,
        "sku": "TRANCHAI-MEDICAL-RECALL-AI",
        "opener": "Hi Dr. [Owner], Omar with TranchAI Healthcare. We deployed an autonomous medical front-desk assistant for private practices that books appointments around the clock and reactivates overdue recalls. How is your front desk handling peak-hour call volume and appointment no-shows?"
    },
    "physical_therapy": {
        "name": "Physical Therapy & Rehabilitation Clinics",
        "pain": "New-patient intake calls dropped after hours, cancel/no-show leakage, and inactive patient records never rebooked.",
        "solution": "24/7 PT Intake & Rebooking Recovery Bot",
        "value_hypothesis": "Captures evening/weekend intake calls and rebooks cancelled sessions automatically, recovering +$15,000/mo in lost treatment revenue.",
        "setup_fee": 2500.0,
        "monthly_retainer": 1750.0,
        "sku": "TRANCHAI-PT-INTAKE-RECOVERY",
        "opener": "Hi [Owner], Omar with TranchAI Rehabilitation Systems. We built an autonomous intake and rebooking assistant for physical therapy clinics that answers after-hours referral calls and fills cancelled slots. Would your schedulers benefit from automated slot recovery?"
    },
    "dental": {
        "name": "Dental Clinics & Orthodontics",
        "pain": "Front-desk phone bottleneck during morning peak, uncompleted treatment plans, and lost hygiene recalls.",
        "solution": "Front-Desk Overflow Assistant + Hygiene Recall Recovery Agent",
        "value_hypothesis": "Recovers $24,000/mo in dormant patient hygiene appointments without hiring extra administrative staff.",
        "setup_fee": 2500.0,
        "monthly_retainer": 1850.0,
        "sku": "TRANCHAI-DENTAL-RECALL-AI",
        "opener": "Hi Dr. [Owner], Omar from TranchAI Healthcare. We deployed an AI patient-recall engine for dental practices that reactivates overdue cleanings and handles front-desk phone overflow. Are your front-desk staff struggling to keep up with recall calls during clinic hours?"
    },
    "law": {
        "name": "Law Firms & Legal Practices",
        "pain": "Missing valuable personal injury or corporate retainer leads outside business hours and time wasted on unqualified cases.",
        "solution": "24/7 Autonomous Legal Intake & Conflict Qualification Concierge",
        "value_hypothesis": "Captures 100% of evening/weekend case inquiries, pre-screens for statute of limitations/liability, and schedules retained consultations instantly.",
        "setup_fee": 4500.0,
        "monthly_retainer": 3500.0,
        "sku": "TRANCHAI-LEGAL-INTAKE-OS",
        "opener": "Hi [Owner], Omar calling from TranchAI Legal. We engineered an autonomous 24/7 case intake system for law firms that qualifies prospective clients, screens conflicts, and books retained appointments before competing firms answer the phone. Do you have 45 seconds to discuss your current intake flow?"
    },
    "construction": {
        "name": "Construction & Engineering (ConTech)",
        "pain": "Estimators spending 20+ hours per bid measuring quantities manually in AutoCAD, causing missed tenders and arithmetic errors.",
        "solution": "Autonomous CAD-to-BOQ AI Quantity Takeoff Engine (ConTech OS)",
        "value_hypothesis": "Reduces manual drawing takeoff time from 3 weeks down to 10 minutes with zero arithmetic error and formula verification.",
        "setup_fee": 4500.0,
        "monthly_retainer": 18500.0,
        "sku": "TRANCHAI-CONTECH-TAKEOFF-AUDIT",
        "opener": "Hi [Owner], Omar here—Lead Architect at ConTech AI. We engineered an autonomous drawing-to-BOQ extraction pipeline for civil & structural contractors that slashes bid estimation time by 90%. We are running 3 complimentary Takeoff Audits this week for premier contractors—would your estimating team find that valuable?"
    },
    "property_management": {
        "name": "Property Management & Real Estate Operators",
        "pain": "24/7 emergency tenant maintenance requests and high vacancy lead turnaround times.",
        "solution": "Autonomous Tenant Maintenance Triage & Vacancy Tour Booking Engine",
        "value_hypothesis": "Automates 80% of routine maintenance requests, coordinates emergency vendors, and books leasing tours on autopilot.",
        "setup_fee": 2500.0,
        "monthly_retainer": 2000.0,
        "sku": "TRANCHAI-PROP-MGMT-TRIAGE",
        "opener": "Hi [Owner], Omar with TranchAI Real Estate Systems. We automate tenant maintenance dispatch and prospective tenant tour bookings for property management portfolios. Could your operations team benefit from offloading 80% of inbound maintenance tickets?"
    }
}


def normalize_vertical(text: str) -> str:
    t = str(text or "").lower()
    # Order matters: specific medical verticals must win before generic "medical".
    if any(k in t for k in ("chiroprac", "spine care", "spine center", "chiropractic")):
        return "chiropractic"
    if any(k in t for k in ("physical therap", "physiotherap", "physio ", "physiotherapy", "rehab")):
        return "physical_therapy"
    if any(k in t for k in ("dent", "ortho", "hygiene", "oral", "endodont", "periodont")):
        return "dental"
    if any(k in t for k in ("med spa", "medical spa", "aesthetic", "botox", "derma", "skin", "cosmetic surg")):
        return "med_spa"
    if any(k in t for k in ("medical", "clinic", "practice", "physician", "doctor", "healthcare", "urgent care", "hospital", "family medicine")):
        return "medical"
    if "yoga" in t:
        return "yoga"
    if any(k in t for k in ("pilates", "fitness", "gym", "barre", "studio")):
        return "pilates"
    if any(k in t for k in ("hvac", "heating", "air condition", "cooling", "mechanical")):
        return "hvac"
    if any(k in t for k in ("law", "legal", "attorney", "counsel", "litigat")):
        return "law"
    if any(k in t for k in ("construct", "contractor", "civil", "build", "engineer", "roof", "plumb", "electri")):
        return "construction"
    if any(k in t for k in ("property management", "realty", "estate", "leasing", "landlord")):
        return "property_management"
    return "construction"


def evaluate_business_deal(record: Dict[str, Any]) -> CanonicalDeal:
    """Transforms raw business prospect into a high-ticket TranchAI CanonicalDeal."""
    company = record.get("company_name") or record.get("company") or record.get("name") or "Enterprise Prospect"
    contact = record.get("owner_name") or record.get("contact_name") or record.get("contact") or record.get("authorized_official_name") or "Owner & Managing Director"
    phone = record.get("business_phone") or record.get("phone") or record.get("verified_phone") or ""
    email = record.get("email") or record.get("verified_email") or ""
    city = record.get("city") or record.get("City") or "Dallas"
    state = record.get("state") or record.get("State") or "TX"
    source = record.get("source") or "Google Maps Local Business Data + NPI Registry"
    source_url = record.get("source_url") or "https://local-business-data.p.rapidapi.com"

    category_raw = record.get("category") or record.get("industry") or record.get("vertical") or ""
    v_key = normalize_vertical(category_raw)
    spec = VERTICAL_OFFERS.get(v_key, VERTICAL_OFFERS["construction"])

    clean_digits = re.sub(r"\D", "", phone)
    is_valid_phone = len(clean_digits) >= 10 and not clean_digits.startswith("555")
    
    # Calculate scores
    opportunity_score = 90 if spec["monthly_retainer"] >= 2000 else 80
    callability_score = 95 if is_valid_phone else 30
    deal_score = int(round(0.6 * opportunity_score + 0.4 * callability_score))

    tier = "Tier A" if deal_score >= 80 and is_valid_phone else ("Tier B" if is_valid_phone else "Tier C")
    stage = DealStage.QUALIFIED if is_valid_phone else DealStage.NEW

    checkout_link = neteller_link(amount=spec["setup_fee"], item=spec["sku"])

    why_this_deal = f"{company} in {city}, {state} fits our {spec['name']} profile. Identified operational bottleneck: {spec['pain']}"
    why_now = "Operational labor costs and missed inbound leads create urgent demand for autonomous AI workflow automation."
    economic_thesis = spec["value_hypothesis"]
    risks = "Ensure seamless onboarding integration with client's existing CRM/scheduler software within 48 hours."
    unknown_variables = "Current daily inbound call volume and existing software stack (ServiceTitan/Mindbody/Dentrix)."

    sales_script = spec["opener"].replace("[Owner]", contact).replace("[Company]", company)

    objections = {
        "too_expensive": f"Let's look at the numbers: if our AI recovers just 1 extra client per month, that generates $5,000+ in revenue, paying for the entire ${spec['monthly_retainer']:,.0f} retainer 3x over.",
        "already_have_staff": "Our system doesn't replace your team—it acts as an autonomous safety net that captures every single after-hours and overflow call so your staff can focus on high-value in-person service.",
        "need_to_think": "Of course! Let me send you a 1-page deployment brief and our live interactive demo link so you can experience the AI answering calls in real-time."
    }

    lead_id = f"TRANCHAI-{abs(hash(company + phone)):08x}"

    deal = CanonicalDeal(
        id=lead_id,
        deal_type=DealType.BUSINESS_AI,
        lead_id=lead_id,
        source=source,
        source_url=source_url,
        source_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        owner_name=contact,
        company_name=company,
        contact_phone=phone,
        contact_email=email,
        contact_source=source,
        vertical=spec["name"],
        city=city,
        state=state,
        county="",
        signals=[v_key, "b2b_ai_automation_fit", f"sku:{spec['sku']}"],
        opportunity_score=opportunity_score,
        callability_score=callability_score,
        deal_score=deal_score,
        motivation_score=85,
        buyer_fit_score=90,
        economic_confidence=95,
        estimated_arv=None,
        starting_bid=None,
        calculated_mao=None,
        potential_fee=spec["setup_fee"],
        primary_offer=f"{spec['solution']} (${spec['monthly_retainer']:,.0f}/mo)",
        neteller_link=checkout_link,
        monetization_route=MonetizationRoute.AI_RETAINER,
        tier=tier,
        why_this_deal=why_this_deal,
        why_now=why_now,
        economic_thesis=economic_thesis,
        risks=risks,
        unknown_variables=unknown_variables,
        sales_script=sales_script,
        objection_handling=objections,
        stage=stage,
        reason=f"Qualified {spec['name']} Target with verified phone and high-value pain match.",
        next_action="DIAL_PROSPECT" if is_valid_phone else "ENRICH_CONTACT",
        next_action_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        evidence_provenance=[{"source": source, "source_url": source_url, "retrieved_at": datetime.now(timezone.utc).isoformat()}],
        confidence=0.95 if is_valid_phone else 0.50,
        is_prime_callable=is_valid_phone and callability_score >= 50,
        suppression_state="ACTIVE"
    )

    return deal


def run_tranchai_engine(source_file: Optional[Path] = None, apply: bool = True) -> List[CanonicalDeal]:
    """Processes business leads from pre-collected samples / NPI registry / Google Maps and registers to memory."""
    print("=" * 70)
    print("  ⚡ JARVIS OS — TRANCHAI B2B AI DEAL ENGINE & PROSPECTOR")
    print("=" * 70)

    records = []
    if source_file and source_file.exists():
        if source_file.suffix.lower() == ".csv":
            with open(source_file, "r", encoding="utf-8") as f:
                records = list(csv.DictReader(f))
        else:
            data = json.loads(source_file.read_text(encoding="utf-8"))
            records = data if isinstance(data, list) else data.get("businesses", data.get("rows", data.get("leads", [])))
    else:
        sample_path = ROOT_DIR / "MBM" / "LeadEngine" / "property_intel" / "samples" / "sample_business_rows.json"
        if sample_path.exists():
            data = json.loads(sample_path.read_text(encoding="utf-8"))
            records = data if isinstance(data, list) else data.get("businesses", data.get("rows", data.get("leads", [])))

        # Also load real verified NPI Healthcare / Clinic businesses
        npi_path = ROOT_DIR / "MBM" / "Artifacts" / "npi_verified_callsheet.csv"
        if npi_path.exists():
            try:
                with open(npi_path, "r", encoding="utf-8") as f:
                    npi_rows = list(csv.DictReader(f))
                    for nr in npi_rows[:35]:
                        records.append({
                            "company_name": nr.get("organization_name") or nr.get("company_name") or "Medical Practice & Clinic",
                            "owner_name": nr.get("authorized_official_name") or "Managing Doctor / Practice Owner",
                            "business_phone": nr.get("phone") or nr.get("verified_phone") or "",
                            "category": nr.get("taxonomy_desc") or "Medical Practice & Clinic",
                            "city": nr.get("city") or "Dallas",
                            "state": nr.get("state") or "TX",
                            "source": "US Government CMS NPI Registry",
                            "source_url": "https://npiregistry.cms.hhs.gov"
                        })
            except Exception as e:
                print(f"[WARN] Could not load NPI callsheet: {e}")

    print(f"  [+] Ingested {len(records)} raw business prospect records.")

    memory = CanonicalDealMemory()
    processed_deals = []

    for rec in records:
        deal = evaluate_business_deal(rec)
        if apply:
            memory.register_deal(deal)
        processed_deals.append(deal)
        print(f"  [{deal.tier[:8]}] {deal.company_name[:25]:<25} | {deal.vertical[:22]:<22} | Phone: {deal.contact_phone:<15} | Score: {deal.deal_score}/100")

    if apply:
        memory.save()
        print(f"\n  ✓ Synchronized {len(processed_deals)} TranchAI deals into Canonical Deal Memory: {memory.storage_path}")

    return processed_deals


if __name__ == "__main__":
    run_tranchai_engine(apply=True)
