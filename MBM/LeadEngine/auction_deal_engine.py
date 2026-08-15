"""
auction_deal_engine.py — JARVIS OS Auction.com Real Estate Deal Engine.
========================================================================
Responsibilities:
1. Discovery & Freshness: Scrapes/loads Auction.com residential foreclosure/REO listings.
2. Authoritative Verification: Cross-references DCAD / county GIS registries for legal ownership & APN.
3. Financial Underwriting:
   - 70% Rule Maximum Allowable Offer (MAO): (ARV * 0.70) - Estimated_Repairs
   - Starting Bid vs Estimated Debt / Credit Bid
   - Repair Buffer Estimation (10% light cosmetic, 20% moderate, 35% heavy rehab)
   - Wholesale / Assignment Spread Estimation (5%–10% of ARV or minimum $15k spread)
   - Likely Exit Strategy (BUY, MATCH_TO_BUYER, WHOLESALE_ASSIGNMENT, INVESTOR_INTRO)
4. Five Structured Scores:
   - AUCTION DEAL SCORE (0-100)
   - MOTIVATION SCORE (0-100)
   - CONTACTABILITY SCORE (0-100)
   - BUYER FIT SCORE (0-100)
   - ECONOMIC CONFIDENCE (0-100)
5. Four Tiers:
   - 🔥 TOP AUCTION OPPORTUNITIES
   - 🟢 RESEARCH
   - 🟡 NEEDS VERIFICATION
   - 🔴 REJECTED
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
from MBM.LeadEngine.property_intel.ownership_verifier import verify_ownership
from MBM.LeadEngine.property_intel.schema import classify_owner_type, money_to_float
from MBM.LeadEngine.property_intel.scoring import score_callability, score_property


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_money(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", "").replace("$", "")
    if not s or s.lower() == "unknown":
        return 0.0
    mult = 1.0
    if s.lower().endswith("k"):
        mult = 1000.0
        s = s[:-1]
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m.group(0)) * mult
    except ValueError:
        return 0.0


def calculate_repairs(arv: float, distress_level: str = "moderate") -> float:
    """Calculates repair assumptions based on distress severity."""
    if arv <= 0:
        return 0.0
    if distress_level == "light":
        return round(arv * 0.10, 2)
    elif distress_level == "heavy":
        return round(arv * 0.35, 2)
    else:  # moderate default
        return round(arv * 0.20, 2)


def calculate_underwriting(arv: float, starting_bid: float, repair_cost: float) -> Dict[str, Any]:
    """Calculates MAO, assignment spread, and exit route."""
    if arv <= 0:
        return {
            "mao": 0.0,
            "equity_spread": 0.0,
            "potential_fee": 15000.0,
            "exit_strategy": MonetizationRoute.OTHER_VERIFIED_PATH,
            "economic_confidence": 30
        }

    # 70% rule MAO = (ARV * 0.70) - Repairs
    mao = max(0.0, (arv * 0.70) - repair_cost)
    equity_spread = max(0.0, arv - starting_bid - repair_cost) if starting_bid > 0 else (arv - mao)
    
    # 5% to 8% assignment fee projection
    potential_fee = max(10000.0, round(arv * 0.06, 2))

    # Exit strategy evaluation
    if starting_bid > 0 and starting_bid <= mao * 0.85:
        exit_strategy = MonetizationRoute.BUY
        confidence = 90
    elif starting_bid > 0 and starting_bid <= mao:
        exit_strategy = MonetizationRoute.WHOLESALE_ASSIGNMENT
        confidence = 85
    elif starting_bid > 0 and starting_bid < arv * 0.80:
        exit_strategy = MonetizationRoute.MATCH_TO_BUYER
        confidence = 75
    else:
        exit_strategy = MonetizationRoute.INVESTOR_INTRODUCTION
        confidence = 50

    return {
        "mao": round(mao, 2),
        "equity_spread": round(equity_spread, 2),
        "potential_fee": potential_fee,
        "exit_strategy": exit_strategy,
        "economic_confidence": confidence
    }


def evaluate_auction_deal(record: Dict[str, Any], live_verify: bool = False) -> CanonicalDeal:
    """Evaluates an auction record, verifies ownership, scores economics, and returns a CanonicalDeal."""
    addr = record.get("Property_Address") or record.get("address") or ""
    city = record.get("City") or record.get("city") or "Dallas"
    state = record.get("State") or record.get("state") or "TX"
    county = record.get("County") or record.get("county") or "Dallas"
    parcel_id = record.get("parcel_id") or record.get("APN") or ""
    auction_date = record.get("Auction_Date") or record.get("auction_date") or "Upcoming"
    auction_status = record.get("Auction_Status") or record.get("auction_status") or "foreclosure"
    
    arv = parse_money(record.get("Estimated_Value") or record.get("estimated_value") or record.get("Estimated_ARV"))
    starting_bid = parse_money(record.get("Starting_Bid") or record.get("starting_bid") or record.get("opening_bid"))

    # 1. County Ownership Verification
    prop_dict = {
        "address": addr,
        "city": city,
        "state": state,
        "county": county,
        "parcel_id": parcel_id,
        "source": "auction.com",
        "source_url": "https://www.auction.com/residential"
    }
    verification = verify_ownership(prop_dict, live=live_verify)
    owner_name = verification.owner_name or record.get("Owner_Name") or record.get("owner_name") or "Property Owner of Record"
    verified_parcel = verification.parcel_id or parcel_id
    owner_type = verification.owner_type or classify_owner_type(owner_name)
    v_status = verification.verification_status

    # 2. Financial Underwriting & Repairs
    repair_cost = calculate_repairs(arv, "moderate" if "foreclosure" in auction_status.lower() else "light")
    uw = calculate_underwriting(arv, starting_bid, repair_cost)
    mao = uw["mao"]
    potential_fee = uw["potential_fee"]
    exit_strategy = uw["exit_strategy"]
    economic_confidence = uw["economic_confidence"]

    # 3. 5-Dimensional Scoring
    # Motivation Score (Foreclosure / Auction urgency)
    motivation_score = 90 if "foreclosure" in auction_status.lower() else (80 if "tax" in auction_status.lower() else 70)
    
    # Contactability Score
    phone = record.get("Verified_Phone") or record.get("phone") or record.get("phone_number") or ""
    contact_conf = 0.9 if v_status == "VERIFIED" else (0.6 if v_status == "LIKELY" else 0.3)
    call_score_data = score_callability(prop_dict, verification.to_dict() if verification else None, phone=phone)
    contactability_score = call_score_data["total"]

    # Buyer Fit Score (spread vs market liquidity)
    buyer_fit_score = 90 if mao > starting_bid and starting_bid > 0 else (75 if arv > 0 else 40)

    # Auction Deal Score (Combined composite)
    deal_score = int(round(
        0.30 * (85 if mao > starting_bid and starting_bid > 0 else 50) +
        0.25 * motivation_score +
        0.20 * contactability_score +
        0.15 * buyer_fit_score +
        0.10 * economic_confidence
    ))

    # 4. Tier Categorization
    if deal_score >= 75 and (v_status in ("VERIFIED", "LIKELY") or len(phone) >= 10):
        tier = "🔥 TOP AUCTION OPPORTUNITIES"
        stage = DealStage.QUALIFIED
    elif mao > starting_bid and starting_bid > 0:
        tier = "🟢 RESEARCH"
        stage = DealStage.NEW
    elif v_status == "CONFLICT" or not parcel_id:
        tier = "🟡 NEEDS VERIFICATION"
        stage = DealStage.NEW
    else:
        tier = "🔴 REJECTED"
        stage = DealStage.DISQUALIFIED

    # 5. Build Strategic Thesis & Dossier
    why_this_deal = f"Off-market auction asset at {addr} in {city}, {state} with estimated ARV of ${arv:,.2f} and starting bid of ${starting_bid:,.2f}."
    why_now = f"Active auction timeline set for {auction_date} ({auction_status}). Owner facing imminent title transfer."
    economic_thesis = f"Calculated 70% rule MAO is ${mao:,.2f} with ${repair_cost:,.2f} rehab allowance. Estimated assignment spread is ${potential_fee:,.2f}."
    risks = "Verify senior liens, property tax delinquencies, and code compliance before executing full contract assignment."
    unknown_variables = "Internal physical condition, foundation status, and exact junior lien payoff balance."

    # 6. Sales Script for Owner
    first_name = owner_name.split()[0] if owner_name and " " in owner_name else "Property Owner"
    sales_script = (
        f"Hi {first_name}, my name is Omar with MBM Capital. I'm reaching out directly regarding your property on {addr.split(',')[0]}. "
        f"We are local private cash buyers actively purchasing residential properties in {city} this month. "
        f"We purchase 100% as-is, pay all closing costs, and close in as fast as 7 days with zero commissions before the auction date. "
        f"If our cash offer makes sense, would you be open to reviewing a firm written offer today?"
    )

    lead_id = f"AUCTION-{abs(hash(addr + str(parcel_id))):08x}"

    deal = CanonicalDeal(
        id=lead_id,
        deal_type=DealType.PROPERTY,
        lead_id=lead_id,
        source="Auction.com + County GIS",
        source_url=record.get("source_url", "https://www.auction.com/residential"),
        source_date=auction_date,
        owner_name=owner_name,
        company_name=f"Auction Asset @ {addr}",
        contact_phone=phone,
        contact_source=verification.source or "County Tax Assessor & Skip Trace",
        vertical="Distressed Real Estate",
        city=city,
        state=state,
        county=county,
        parcel_id=verified_parcel,
        property_address=addr,
        signals=[auction_status, "70_pct_rule_calculated", f"tier:{tier}"],
        opportunity_score=deal_score,
        callability_score=contactability_score,
        deal_score=deal_score,
        motivation_score=motivation_score,
        buyer_fit_score=buyer_fit_score,
        economic_confidence=economic_confidence,
        estimated_arv=arv if arv > 0 else None,
        starting_bid=starting_bid if starting_bid > 0 else None,
        calculated_mao=mao if mao > 0 else None,
        estimated_repair_cost=repair_cost if repair_cost > 0 else None,
        potential_fee=potential_fee,
        primary_offer=f"As-Is Cash Purchase / Assignment (${mao:,.2f} MAO)",
        monetization_route=exit_strategy,
        tier=tier,
        why_this_deal=why_this_deal,
        why_now=why_now,
        economic_thesis=economic_thesis,
        risks=risks,
        unknown_variables=unknown_variables,
        sales_script=sales_script,
        objection_handling={
            "need_more_time": "We close in 72 hours, which allows us to stop the auction and settle all funds before the bank takes action.",
            "price_too_low": "Our cash offer covers 100% of title, closing fees, and repair liabilities. You pocket clean net cash with zero agent fees."
        },
        stage=stage,
        reason=f"{tier}: MAO ${mao:,.2f} vs Bid ${starting_bid:,.2f}",
        next_action="DIAL_PROSPECT" if contactability_score >= 50 else "SKIP_TRACE_VERIFY",
        next_action_at=_iso_now(),
        evidence_provenance=[e.to_dict() for e in verification.evidence] if verification else [],
        confidence=contact_conf,
        is_prime_callable=contactability_score >= 50 and bool(phone),
        suppression_state="ACTIVE"
    )

    return deal


def run_auction_engine(source_file: Optional[Path] = None, apply: bool = True, live_verify: bool = False) -> List[CanonicalDeal]:
    """Runs the Auction Deal Engine across sample/live feeds and stores into Deal Memory."""
    print("=" * 70)
    print("  🏠 JARVIS OS — AUCTION.COM & DISTRESSED REAL ESTATE DEAL ENGINE")
    print("=" * 70)

    raw_records = []
    if source_file and source_file.exists():
        if source_file.suffix.lower() == ".csv":
            with open(source_file, "r", encoding="utf-8") as f:
                raw_records = list(csv.DictReader(f))
        else:
            data = json.loads(source_file.read_text(encoding="utf-8"))
            raw_records = data if isinstance(data, list) else data.get("listings", data.get("rows", data.get("leads", [])))
    else:
        # Check for pre-existing real estate artifacts or default sample fixture
        sample_path = ROOT_DIR / "MBM" / "LeadEngine" / "property_intel" / "samples" / "sample_auction_records.json"
        if sample_path.exists():
            data = json.loads(sample_path.read_text(encoding="utf-8"))
            raw_records = data if isinstance(data, list) else data.get("listings", data.get("rows", data.get("leads", [])))

        # Also load real estate calling queue if available to enrich real verified leads
        re_queue = ROOT_DIR / "MBM" / "LeadEngine" / "real_estate_calling_queue.json"
        if re_queue.exists():
            try:
                data_re = json.loads(re_queue.read_text(encoding="utf-8"))
                if isinstance(data_re, list):
                    raw_records.extend(data_re[:30])
            except Exception:
                pass

    print(f"  [+] Ingested {len(raw_records)} raw auction records.")

    memory = CanonicalDealMemory()
    processed_deals = []

    for rec in raw_records:
        deal = evaluate_auction_deal(rec, live_verify=live_verify)
        if apply:
            memory.register_deal(deal)
        processed_deals.append(deal)
        print(f"  [{deal.tier[:15]}] {deal.property_address[:28]:<28} | ARV: ${deal.estimated_arv or 0:,.0f} | MAO: ${deal.calculated_mao or 0:,.0f} | Score: {deal.deal_score}/100")

    if apply:
        memory.save()
        print(f"\n  ✓ Synchronized {len(processed_deals)} deals into Canonical Deal Memory: {memory.storage_path}")

    return processed_deals


if __name__ == "__main__":
    run_auction_engine(apply=True)
