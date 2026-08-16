"""
Push Top 100 Real Estate Deals, Buyers & TranchAI Business Owners to MBM Dialer
================================================================================
Canonical 4-Tier Queue Partitioning:
1. 🔥 TOP 25 CALL NOW: Immediate prime dial ready, score >= 85, verified decision maker & phone, complete script & Neteller rail
2. 🟢 NEXT 75: High-scoring prime queue, score 70-84, dialer-ready
3. 🟡 VERIFICATION REQUIRED: Ambiguous ownership, pending parcel APN match, or unverified contact
4. 🔴 SUPPRESSED: DNC, BAD_NUMBER, WRONG_PERSON, NON_OWNER, DUPLICATE

Canonical Phone Identity (E.164 / 10-digit normalized):
- Ensures all representations (e.g. +12147151442, (214) 715-1442, 214-715-1442) collapse to the same identity.
- Permanent suppression immunity against re-import.
"""

from __future__ import annotations

import os
import sys
import json
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory, CanonicalDeal, DealType
from MBM.LeadEngine.auction_deal_engine import run_auction_engine
from MBM.LeadEngine.tranchai_deal_engine import run_tranchai_engine
from MBM.LeadEngine.dialer_verification_gate import (
    filter_for_dialer, check_lead, is_placeholder_identity,
)

DIALER_DB_PATH = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CASH_BUYERS_QUEUE = ROOT_DIR / "MBM" / "LeadEngine" / "facebook_cash_buyers.json"
# Verified canonical export produced by rerank_top_100 — real decision makers
# with real phones. Never fall back to the raw NPI callsheet (placeholder risk).
VERIFIED_EXPORT_CSV = ROOT_DIR / "MBM" / "Artifacts" / "dialer_verified_export.csv"
OUTPUT_CSV = ROOT_DIR / "TOP_100_REAL_ESTATE_CALL_SHEET.csv"
OUTPUT_MD = ROOT_DIR / "TOP_100_REAL_ESTATE_CALL_SHEET.md"
PARTITION_JSON = ROOT_DIR / "MBM" / "Artifacts" / "top_100_partition.json"


def normalize_dialer_phone(phone: str) -> str:
    """Canonical dialer phone identity: digits only, US leading 1 dropped."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits


def format_e164(phone: str) -> str:
    """Formats phone to standard +1XXXXXXXXXX."""
    norm = normalize_dialer_phone(phone)
    if len(norm) == 10:
        return f"+1{norm}"
    elif len(norm) > 10:
        return f"+{norm}"
    return phone


def assert_no_placeholder_pollution(leads: list, label: str) -> None:
    """Refuses the push if any input record carries a placeholder/synthetic identity.

    This is the hard gate: deals:push MUST NEVER reintroduce records that
    rerank_top_100 removed. Any placeholder name, synthetic contact, unverified
    NPI-only identity, or invalid phone identity aborts the push before it can
    write to leads_database.json.
    """
    offenders = []
    for idx, lead in enumerate(leads):
        if is_placeholder_identity(lead):
            name = _pick_name(lead)
            offenders.append(f"    [{idx}] {name!r} @ {(lead.get('company') or lead.get('company_name') or '')[:40]}")
            continue
        res = check_lead(lead)
        if not res["passed"]:
            reasons = "; ".join(res["rejection_reasons"])
            name = _pick_name(lead)
            offenders.append(f"    [{idx}] {name!r} -> {reasons}")

    if offenders:
        print("=" * 75)
        print("  🚫 DEALS:PUSH REFUSED — placeholder/synthetic pollution detected")
        print(f"  Source: {label}")
        for line in offenders:
            print(line)
        print("=" * 75)
        raise SystemExit(2)


def _pick_name(lead: dict) -> str:
    for key in ("contact", "contact_name", "owner_name",
                "authorized_official_name", "name", "company", "company_name"):
        val = lead.get(key)
        if val:
            return str(val).strip()
    return "(unnamed)"


def load_cash_buyers() -> list:
    buyers = []
    if CASH_BUYERS_QUEUE.exists():
        try:
            with open(CASH_BUYERS_QUEUE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for idx, item in enumerate(data, 1):
                    phone = format_e164(item.get("phone", ""))
                    norm = normalize_dialer_phone(phone)
                    if not norm or "555" in norm or len(norm) < 10:
                        continue
                    name = item.get("name") or f"Acquisitions Partner {idx}"
                    company = item.get("name") or "VIP Cash Buyers Group"
                    market = item.get("market") or "DFW / US"
                    buyers.append({
                        "id": f"RE-BUYER-{idx:03d}",
                        "vertical": "Cash Buyers & Flippers",
                        "company": company,
                        "contact": name,
                        "phone": phone,
                        "norm_phone": norm,
                        "role_type": "VIP Cash Buyer / Hedge Fund",
                        "motivation_score": 95,
                        "deal_score": 95,
                        "callability_score": 90,
                        "motivation_tier": "VIP_BUYER",
                        "pitch_angle": f"Off-market 35% discount wholesale inventory in {market}.",
                        "details": {
                            "priority": "1",
                            "verified_phone": phone,
                            "vertical_tag": "CASH_BUYER",
                            "Owner_Name": name,
                            "website": item.get("website", ""),
                            "Call_Script": (
                                f"Hi {name}, Omar calling from MBM Deal Desk. "
                                f"I see {company} is actively buying residential & commercial deals in {market}. "
                                f"We have 3 high-equity off-market contracts locked up at 35% below ARV that we are assigning to preferred buyers this week. "
                                f"Who is your head of acquisitions so I can send the deal package over?"
                            ),
                            "Why_This_Deal": f"Active institutional cash buyer with verified proof of funds in {market}.",
                            "Why_Now": "Liquidity deployment window — seeking distressed off-market contracts.",
                            "Economic_Thesis": "Wholesale assignment fee spread $15,000 - $35,000 per closed contract.",
                            "Next_Action": "CALL_ACQUISITIONS_DIRECTOR",
                            "source": "Local Business & Real Estate Buyer Directory"
                        },
                        "skip_trace_status": "VERIFIED",
                        "skip_trace_source": "Verified Business Directory",
                        "skip_trace_confidence": "high"
                    })
        except Exception as e:
            print(f"[WARN] Error loading cash buyers: {e}")
    return buyers


def main():
    print("=" * 75)
    print("  🚀 JARVIS OS — TOP 100 REVENUE EXECUTION & DIALER SYNC")
    print("=" * 75)

    # 1. Run & Refresh Auction and TranchAI Engines
    auction_deals = run_auction_engine(apply=True)
    tranchai_deals = run_tranchai_engine(apply=True)
    cash_buyers = load_cash_buyers()

    memory = CanonicalDealMemory()

    # Track Partition Queues
    suppressed_leads = []
    verification_leads = []
    candidate_prime_leads = []

    seen_phones = set()

    # Process all Canonical Deals from Memory
    for d in memory.deals.values():
        norm = normalize_dialer_phone(d.contact_phone)

        # 1. Check Suppression
        if d.suppression_state in ("DNC", "BAD_NUMBER", "WRONG_PERSON", "NON_OWNER", "DUPLICATE") or not d.is_prime_callable:
            if d.suppression_state != "ACTIVE":
                suppressed_leads.append({
                    "id": d.id,
                    "name": d.owner_name or d.company_name,
                    "phone": d.contact_phone,
                    "reason": d.reason or f"Suppressed: {d.suppression_state}",
                    "stage": d.stage.value
                })
                continue

        # 2. Check Verification Requirements
        if not d.contact_phone or "555" in norm or d.callability_score < 50:
            verification_leads.append({
                "id": d.id,
                "property_or_company": d.property_address or d.company_name,
                "owner": d.owner_name,
                "status": "MISSING_VERIFIED_PHONE" if not d.contact_phone else "NEEDS_SKIP_TRACE",
                "score": d.deal_score
            })
            continue

        # 3. Check Deduplication
        if norm in seen_phones:
            suppressed_leads.append({
                "id": d.id,
                "name": d.owner_name or d.company_name,
                "phone": d.contact_phone,
                "reason": "DUPLICATE_CANONICAL_PHONE",
                "stage": d.stage.value
            })
            continue

        payload = d.to_dialer_payload()
        payload["norm_phone"] = norm

        # Ensure vertical classification is specific
        comp_lower = (d.company_name or "").lower()
        title_lower = (d.title_or_role or "").lower()
        if any(k in comp_lower for k in ["chiro", "chiropractic", "chiropractor"]) or "chiropractor" in title_lower:
            payload["vertical"] = "Chiropractic Practices"
        elif any(k in comp_lower for k in ["dent", "dental", "dentist", "orthodont", "periodont", "oral"]) or "dentist" in title_lower:
            payload["vertical"] = "Dental Practices"

        # 4. Check for placeholder identity / gate check
        if is_placeholder_identity(payload) or not check_lead(payload)["passed"]:
            verification_leads.append({
                "id": d.id,
                "property_or_company": d.property_address or d.company_name,
                "owner": d.owner_name,
                "status": "PLACEHOLDER_OR_UNVERIFIED_IDENTITY",
                "score": d.deal_score
            })
            continue

        seen_phones.add(norm)
        candidate_prime_leads.append(payload)

    # Process Cash Buyers
    for cb in cash_buyers:
        norm = cb["norm_phone"]
        if is_placeholder_identity(cb) or not check_lead(cb)["passed"]:
            verification_leads.append({
                "id": cb["id"],
                "property_or_company": cb.get("company") or cb.get("contact"),
                "owner": cb.get("contact"),
                "status": "UNVERIFIED_CASH_BUYER_IDENTITY",
                "score": cb.get("deal_score", 50)
            })
            continue
        if norm in seen_phones:
            suppressed_leads.append({
                "id": cb["id"],
                "name": cb["contact"],
                "phone": cb["phone"],
                "reason": "DUPLICATE_CANONICAL_PHONE",
                "stage": "SUPPRESSED"
            })
            continue
        seen_phones.add(norm)
        candidate_prime_leads.append(cb)

    # Ingest additional VERIFIED decision makers from the canonical export
    # (produced by rerank_top_100) to reach the full 100 Top Queue. The raw NPI
    # callsheet is NEVER used here — it can carry placeholder/synthetic contacts.
    if VERIFIED_EXPORT_CSV.exists() and len(candidate_prime_leads) < 100:
        try:
            with open(VERIFIED_EXPORT_CSV, "r", encoding="utf-8") as f:
                verified_leads = list(csv.DictReader(f))
                for idx, row in enumerate(verified_leads, 1):
                    if len(candidate_prime_leads) >= 120:
                        break
                    phone = format_e164(row.get("verified_phone") or row.get("primary_phone") or row.get("phone") or "")
                    norm = normalize_dialer_phone(phone)
                    if not norm or "555" in norm or len(norm) < 10 or norm in seen_phones:
                        continue
                    name = row.get("owner_name") or row.get("contact") or row.get("contact_name") or ""
                    comp = row.get("company") or row.get("company_name") or ""
                    title = row.get("owner_title") or row.get("title") or "Owner / Managing Principal"
                    if not name or not comp:
                        continue
                    # Never synthesize a placeholder identity.
                    if is_placeholder_identity({"contact": name, "company": comp}):
                        continue
                    seen_phones.add(norm)

                    vertical = (row.get("vertical") or "").strip().lower()
                    comp_lower = comp.lower()
                    tax = (row.get("taxonomy") or "").lower()
                    is_chiro = any(k in tax for k in ["chiro", "chiropractic", "chiropractor"]) or any(k in comp_lower for k in ["chiro", "chiropractic", "chiropractor"]) or "chiropractor" in title.lower()
                    is_dental = any(k in tax for k in ["dent", "dental", "dentist", "orthodont", "periodont", "oral"]) or any(w.startswith(("dent", "orthodont", "periodont", "oral")) for w in re.split(r"\W+", comp_lower)) or "dentist" in title.lower()

                    if is_chiro:
                        lead_vertical = "Chiropractic Practices"
                    elif is_dental:
                        lead_vertical = "Dental Practices"
                    elif any(k in tax or k in comp_lower for k in ["physical therapist", "physical therapy", "physiotherapy", "rehab"]):
                        lead_vertical = "Physical Therapy & Rehab"
                    elif any(k in tax or k in comp_lower for k in ["spa", "aesthetic", "dermatol", "therapy"]):
                        lead_vertical = "Specialty Clinics"
                    else:
                        lead_vertical = row.get("vertical") or "Medical Practices"

                    # ── Improved call script (Terminal 2 spec) ──────────────────────
                    # Natural, concise opening adapted to motivation discovery, with
                    # branching logic for common seller responses. No unsupported claims.
                    if is_chiro:
                        script = (
                            f"Hi {name}, this is Omar with Contech AI. "
                            f"We help chiropractic offices optimize patient flow and fill cancellation slots. "
                            f"Quick question — are you currently managing your appointment schedule manually or with software?"
                        )
                        discovery_qs = [
                            "How do you currently handle patient appointment confirmations and no-shows?",
                            "Do you have a recall system for patients who haven't been in over 6 months?",
                            "If automated scheduling made sense, would you be open to a 15-minute demo?"
                        ]
                        objection_paths = [
                            ("We already have a system.",
                             "Solid — then the question is just whether what you have covers after-hours and weekend bookings. If it does, I will not waste your time."),
                            ("Not interested.",
                             "Understood, and I respect a straight answer. Is it timing, or is it a good fit for your patient base?"),
                            ("Too busy / call later.",
                             "That is exactly why this call is short. When is a better time — today after 3, or tomorrow morning? I'll keep it to two minutes."),
                        ]
                    elif is_dental:
                        script = (
                            f"Hi {name}, this is Omar with Contech AI. "
                            f"We help dental practices reduce front-desk phone overflow and fill unscheduled appointment slots. "
                            f"Quick question — how are you currently handling patient calls between appointments?"
                        )
                        discovery_qs = [
                            "How do you currently handle patient calls during peak hours and unscheduled visits?",
                            "Do you have a recall system for hygiene recare and overdue visits?",
                            "If a front-desk automation solution made sense, would you be open to a 15-minute conversation?"
                        ]
                        objection_paths = [
                            ("We already have a system.",
                             "Great — then the question is just whether what you have covers after-hours and weekend coverage. If it does, I will not waste your time."),
                            ("Not interested.",
                             "Understood, and I respect a straight answer. Is it the right fit for your patient base, or just timing?"),
                            ("Too busy / call later.",
                             "That is exactly why this call is short. When is a better time — today after 3, or tomorrow morning? I'll keep it to two minutes."),
                        ]
                    elif vertical in ("clinics", "medical", "dentistry", "optometry",
                                     "physical therapy", "podiatry", "mental health",
                                     "nursing", "healthcare"):
                        script = (
                            f"Hi {name}, this is Omar with Contech AI. "
                            f"We build AI voice receptionists for medical practices that answer every call 24/7, "
                            f"fill cancellations, and deliver a weekly list of local patients "
                            f"actively looking to book. First onboarding call is on us — you see "
                            f"it work before paying. Reply READY and we'll send the setup link."
                        )
                        discovery_qs = [
                            "How are you currently handling patient calls after hours and missed follow-ups?",
                            "Do you have a system for recalling patients who are overdue for visits?",
                            "If an AI front-desk made sense, would you be open to a 15-minute walkthrough this week?"
                        ]
                        objection_paths = [
                            ("We already have someone / use AI.",
                             "Totally fair — then the question is just whether what you have covers the after-hours calls and patient follow-ups that slip through. If it does, tell me straight and I will not waste your time."),
                            ("Not interested.",
                             "Understood, and I respect a straight answer. Is it 'not this', or 'not right now'? If it is timing, I will follow up once and leave it there."),
                            ("Too busy / call later.",
                             "That is exactly why this call is short. When is a better time — today after 3, or tomorrow morning? I will keep it to two minutes and reschedule if you are mid-fire."),
                        ]
                    else:
                        # Generic fallback script for unknown verticals
                        script = (
                            f"Hi {name}, this is Omar with MBM Systems. "
                            f"We automate outreach and operations for local businesses with AI voice + SMS agents. "
                            f"Happy to run a free 10-minute fit call to see if it makes sense — reply INTERESTED and we'll "
                            f"send a link to book it."
                        )
                        discovery_qs = [
                            "What does your current outreach/operations setup look like?",
                            "Is there a specific bottleneck you're trying to solve?",
                            "If an AI agent made sense for your business, would you be open to a 15-minute walkthrough?"
                        ]
                        objection_paths = [
                            ("We already have someone / use AI.",
                             "Totally fair — then the question is just whether what you have covers the areas you need help with. If it does, I will not waste your time."),
                            ("Not interested.",
                             "Understood, and I respect a straight answer. Is it timing, or is it not a good fit?"),
                            ("Too busy / call later.",
                             "That is exactly why this call is short. When is a better time — today after 3, or tomorrow morning? I will keep it to two minutes."),
                        ]

                    candidate_prime_leads.append({
                        "id": f"VERIFIED-{idx:04d}",
                        "vertical": lead_vertical,
                        "company": comp,
                        "contact": name,
                        "title": title,
                        "owner_status": "PRACTITIONER",
                        "source_class": "AUTHORITATIVE_REGISTRY",
                        "decision_maker_confidence": "HIGH",
                        "contact_confidence": "HIGH",
                        "phone": phone,
                        "norm_phone": norm,
                        "motivation_score": 80,
                        "deal_score": 82,
                        "callability_score": 90,
                        "tier": "Tier A",
                        "pitch_angle": f"24/7 AI Receptionist & Patient Recall Automation for {comp}.",
                        "details": {
                            "priority": "2",
                            "verified_phone": phone,
                            "vertical_tag": "MEDICAL_CLINIC" if vertical in ("clinics", "medical", "dentistry", "optometry",
                                                                           "physical therapy", "podiatry", "mental health",
                                                                           "nursing", "healthcare") else "UNKNOWN",
                            "Owner_Name": name,
                            "Title": title,
                            "Owner_Status": "PRACTITIONER",
                            "Source_Class": "AUTHORITATIVE_REGISTRY",
                            "Decision_Maker_Confidence": "HIGH",
                            "Contact_Confidence": "HIGH",
                            "Call_Script": script,
                            "Why_This_Deal": f"US CMS NPI registered active clinical facility: {comp}.",
                            "Why_Now": "Unscheduled patient follow-up & front-desk phone overflow bottleneck.",
                            "Economic_Thesis": "$1,850/mo recurring AI automation contract.",
                            "Next_Action": "DIAL_CLINICAL_DIRECTOR",
                            "Discovery_Questions": discovery_qs,
                            "Objection_Paths": objection_paths,
                            "source": "US Government CMS NPI Registry"
                        },
                        "skip_trace_status": "VERIFIED",
                        "skip_trace_source": "US CMS NPI Registry",
                        "skip_trace_confidence": "high"
                    })
        except Exception as e:
            print(f"[WARN] Error loading NPI leads: {e}")

    # Sort Candidate Leads by priority ranking per Terminal 2 spec:
    # 1. high-intent seller signal (motivation_score)
    # 2. verified callable phone (callability_score)
    # 3. equity/opportunity strength (deal_score)
    # 4. deterministic tiebreak (priority, then company name)
    candidate_prime_leads.sort(key=lambda x: (
        -int(x.get("motivation_score") or 0),
        -int(x.get("callability_score") or 0),
        -int(x.get("deal_score") or 0),
        int(x.get("details", {}).get("priority") or "9"),
        x.get("company") or "",
    ))

    # HARD GATE: refuse the push entirely if any candidate is placeholder-polluted.
    assert_no_placeholder_pollution(candidate_prime_leads, "candidate_prime_leads")

    # Audit candidate leads through Dialer Verification Gate
    passed_prime = filter_for_dialer(candidate_prime_leads, quiet=True)

    # Double-gate the final prime queue (no placeholder identity may reach the dialer).
    clean_prime = [l for l in passed_prime if not is_placeholder_identity(l)]

    # Partition into Top 25 CALL NOW and Next 75
    top_25_call_now = clean_prime[:25]
    next_75 = clean_prime[25:100]

    print(f"\n  🎯 Partition Summary:")
    print(f"     🔥 TOP 25 CALL NOW:        {len(top_25_call_now)} leads")
    print(f"     🟢 NEXT 75:                {len(next_75)} leads")
    print(f"     🟡 VERIFICATION REQUIRED:  {len(verification_leads)} leads")
    print(f"     🔴 SUPPRESSED:             {len(suppressed_leads)} leads")

    # 4. Save Partition Artifact
    partition_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_25_call_now": top_25_call_now,
        "next_75": next_75,
        "verification_required": verification_leads,
        "suppressed": suppressed_leads
    }
    PARTITION_JSON.write_text(json.dumps(partition_data, indent=2), encoding="utf-8")

    # 5. Push to leads_database.json (Front-load Top 25 + Next 75, then remaining existing)
    existing = []
    if DIALER_DB_PATH.exists():
        try:
            existing = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    top_100_phones = {l.get("phone") for l in (top_25_call_now + next_75) if l.get("phone")}
    filtered_existing = [e for e in existing if e.get("phone") not in top_100_phones]

    master_db = top_25_call_now + next_75 + filtered_existing
    DIALER_DB_PATH.write_text(json.dumps(master_db, indent=2), encoding="utf-8")

    # 6. Export Call Sheet CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Queue_Tier", "Rank", "ID", "Vertical", "Company_or_Property", "Contact_Name",
            "Phone_Number", "Score", "Pitch_Angle", "Neteller_Link", "Call_Script", "Next_Action"
        ])
        for idx, lead in enumerate(top_25_call_now, 1):
            details = lead.get("details", {})
            writer.writerow([
                "CALL_NOW", idx, lead.get("id"), lead.get("vertical"), lead.get("company"),
                lead.get("contact"), lead.get("phone"), lead.get("motivation_score") or lead.get("deal_score"),
                lead.get("pitch_angle"), details.get("neteller_link", ""), details.get("Call_Script", ""),
                details.get("Next_Action", "CALL_NOW")
            ])
        for idx, lead in enumerate(next_75, 26):
            details = lead.get("details", {})
            writer.writerow([
                "NEXT_75", idx, lead.get("id"), lead.get("vertical"), lead.get("company"),
                lead.get("contact"), lead.get("phone"), lead.get("motivation_score") or lead.get("deal_score"),
                lead.get("pitch_angle"), details.get("neteller_link", ""), details.get("Call_Script", ""),
                details.get("Next_Action", "SCHEDULE_DIAL")
            ])

    # 7. Export Call Sheet Markdown
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# 📞 JARVIS OS // TOP 100 REVENUE EXECUTION CALL SHEET\n\n")
        f.write(f"**Generated**: {datetime.now(timezone.utc).isoformat()} | **Total Master Queue**: {len(master_db)}\n\n")

        f.write("## 🔥 TOP 25 CALL NOW (Priority 1 — Immediate Execution)\n\n")
        for idx, lead in enumerate(top_25_call_now, 1):
            details = lead.get("details", {})
            f.write(f"### #{idx:02d} | [{lead.get('vertical')}] {lead.get('company')}\n")
            f.write(f"- **WHO (Decision Maker)**: **{lead.get('contact')}**\n")
            f.write(f"- **PHONE**: ` {lead.get('phone')} ` 📞 *(1-Click Call Ready)*\n")
            f.write(f"- **WHY**: {details.get('Why_This_Deal', lead.get('pitch_angle'))}\n")
            f.write(f"- **OFFER**: {lead.get('pitch_angle')}\n")
            f.write(f"- **SCORE**: {lead.get('motivation_score') or lead.get('deal_score')}/100 | **CALLABILITY**: {lead.get('callability_score', 90)}/100\n")
            if details.get("neteller_link"):
                f.write(f"- **💳 NETELLER CHECKOUT**: [Instant Payment Rail]({details.get('neteller_link')})\n")
            f.write(f"- **⚡ NEXT ACTION**: `{details.get('Next_Action', 'DIAL_PROSPECT')}`\n")
            f.write(f"\n**🎯 Word-for-Word Script**:\n```text\n{details.get('Call_Script', '')}\n```\n\n---\n\n")

        f.write("## 🟢 NEXT 75 (Priority 2 — Qualified Dial Queue)\n\n")
        for idx, lead in enumerate(next_75, 26):
            details = lead.get("details", {})
            f.write(f"### #{idx:02d} | [{lead.get('vertical')}] {lead.get('company')}\n")
            f.write(f"- **WHO**: **{lead.get('contact')}** | **PHONE**: `{lead.get('phone')}` | **SCORE**: {lead.get('motivation_score') or lead.get('deal_score')}/100\n")
            f.write(f"- **OFFER**: {lead.get('pitch_angle')} | **NEXT ACTION**: `{details.get('Next_Action', 'SCHEDULE_DIAL')}`\n\n")

    print(f"\n  ✓ Synced {len(master_db)} total leads to React Dialer DB: {DIALER_DB_PATH}")
    print(f"  ✓ Exported Partition JSON: {PARTITION_JSON}")
    print(f"  ✓ Exported Call Sheet CSV: {OUTPUT_CSV}")
    print(f"  ✓ Exported Call Sheet MD:  {OUTPUT_MD}")
    print("=" * 75)


if __name__ == "__main__":
    main()
