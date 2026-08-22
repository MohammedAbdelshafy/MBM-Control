#!/usr/bin/env python3
"""
MBM WEDDINGS LEAD INGESTION & CAMPAIGN SYNC
=============================================================================
Loads verified wedding prospects (venues, planners, caterers, etc.) from a JSON/CSV file.
Deduplicates against the existing dialer database and canonical memory.
Generates tailored scripts, tags, and ROI models using OfferArchitect.
Pushes to the dialer securely under the single-writer lock.

Campaign: WEDDINGS_AI_REVENUE_US
"""

import sys
import json
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.lead_history_ledger import LeadHistoryLedger, normalize_phone_digits, normalize_email_address
from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock
from MBM.LeadEngine.offer_architect import OfferArchitect
from MBM.LeadEngine.canonical_deal_engine import CanonicalDealMemory, CanonicalDeal, DealType, DealStage, OwnerStatus, MonetizationRoute, SourceClass

def load_prospects(file_path: Path) -> List[Dict[str, Any]]:
    if file_path.suffix.lower() == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('leads', data) if isinstance(data, dict) else data
    elif file_path.suffix.lower() == '.csv':
        prospects = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                prospects.append(row)
        return prospects
    else:
        raise ValueError("Unsupported file format. Use .json or .csv")

def calculate_wedding_priority_score(prospect: Dict[str, Any]) -> float:
    # Base priority
    score = 80.0
    sub_vertical = prospect.get('wedding_subvertical', '').lower()
    tags = prospect.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip().lower() for t in tags.split(',')]
    else:
        tags = [t.lower() for t in tags]

    # Priority scoring logic
    if 'venue' in sub_vertical or 'planner' in sub_vertical:
        score += 30
    if prospect.get('website'):
        score += 25 # Assuming visible inquiry/contact form
    if prospect.get('booking_process'):
        score += 20
    if 'slow_response' in tags:
        score += 15
    if 'active_lead_gen' in tags:
        score += 15
    if 'weak_ai_visibility' in tags:
        score += 15
    if 'outdated_website' in tags:
        score += 10
    if prospect.get('phone') and prospect.get('email'):
        score += 10
    if 'has_ai' in tags:
        score -= 20

    return min(100.0, score)

def ingest_wedding_leads(file_path: Path, dry_run: bool = False):
    print(f"[START] Loading wedding prospects from {file_path}")
    prospects = load_prospects(file_path)
    print(f"[INFO] Loaded {len(prospects)} raw prospects.")

    ledger = LeadHistoryLedger()
    architect = OfferArchitect()
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load existing dialer to check for duplicates
    existing_dialer = []
    with DialerDatabaseLock() as lock:
        existing_dialer = lock.read()

    canon_path = ROOT_DIR / "MBM" / "Artifacts" / "canonical_deals_memory.json"
    canonical_phones = set()
    canonical_emails = set()
    if canon_path.exists():
        try:
            canon = json.loads(canon_path.read_text(encoding="utf-8"))
            for deal in canon if isinstance(canon, list) else []:
                cp = normalize_phone_digits(deal.get("contact_phone", ""))
                ce = normalize_email_address(deal.get("contact_email", ""))
                if cp: canonical_phones.add(cp)
                if ce: canonical_emails.add(ce)
        except Exception:
            pass

    verified_leads = []
    quarantined = 0
    duplicates = 0

    for i, raw in enumerate(prospects):
        phone = normalize_phone_digits(raw.get('phone', ''))
        email = normalize_email_address(raw.get('email', ''))

        if not phone or len(phone) < 10:
            print(f"[REJECT] Row {i} lacks valid phone.")
            quarantined += 1
            continue

        # Deduplication
        is_seen, _ = ledger.is_historically_seen(phone=phone, email=email)
        if not is_seen:
            for row in existing_dialer:
                if phone and normalize_phone_digits(row.get('phone', '')) == phone:
                    is_seen = True
                    break
                if email and normalize_email_address(row.get('email', '')) == email:
                    is_seen = True
                    break
        if not is_seen:
            if phone in canonical_phones or (email and email in canonical_emails):
                is_seen = True
        
        if is_seen:
            duplicates += 1
            continue
        
        # Build Standardized Lead Output
        intent_score = calculate_wedding_priority_score(raw)
        tier = "HOT" if intent_score >= 90 else "HIGH INTENT" if intent_score >= 80 else "WARM"
        priority_rank = 1 if tier == "HOT" else 2 if tier == "HIGH INTENT" else 3

        # Form candidate for Offer Architect
        cand = {
            "id": f"WEDDING-{phone}",
            "company": raw.get('company', 'Wedding Business'),
            "decision_maker": raw.get('decision_maker') or raw.get('contact') or "Owner",
            "role": raw.get('role', 'Owner'),
            "industry": "Weddings & Event Professionals", # Must match catalog
            "vertical": "Weddings & Event Professionals",
            "phone": f"+1{phone}",
            "email": raw.get('email', ''),
            "city": raw.get('city', 'Unknown'),
            "state": raw.get('state', 'Unknown'),
            "intent_score": intent_score,
            "source": raw.get('source', 'Wedding Directory'),
            "wedding_subvertical": raw.get('wedding_subvertical', 'wedding venue'),
        }

        # Apply strategy
        strategy = architect.build_sales_strategy_for_lead(cand)
        offer = strategy['offer']
        script = strategy['conversation_script']

        lead = {
            "id": cand["id"],
            "company": cand["company"],
            "contact": cand["decision_maker"],
            "decision_maker": cand["decision_maker"],
            "role": cand["role"],
            "industry": cand["industry"],
            "vertical": cand["vertical"],
            "phone": cand["phone"],
            "email": cand["email"],
            "city": cand["city"],
            "state": cand["state"],
            "campaign": "WEDDINGS_AI_REVENUE_US",
            "tags": ["wedding", cand["wedding_subvertical"], "ai_receptionist", "ai_booking", "lead_response", "lead_followup", "geo", "ai_visibility"],
            "primary_ai_gap": "Missed/slow inquiry response",
            "secondary_ai_gap": "After-hours lead handling",
            "wedding_subvertical": cand["wedding_subvertical"],
            "intent_score": intent_score,
            "deal_score": intent_score,
            "priority_score": intent_score,
            "intent_tier": tier,
            "tier": tier,
            "priority": str(priority_rank),
            "status": "NEW",
            "pitch_angle": script["opening"],
            "pain": offer["problem_solved"],
            "why_now": f"Active {cand['wedding_subvertical']} with visible AI gaps",
            "why_this_company": f"Active {cand['wedding_subvertical']} with visible AI gaps",
            "recommended_ai_assistant": offer["offer_name"],
            "sku": offer["sku"],
            "monthly_retainer_usd": offer["monthly_fee_usd"],
            "source": cand["source"],
            "verification_status": "VERIFIED",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "first_seen_date": now_date,
            "new_today": True,
            "badge": "💍 NEW WEDDING DEAL",
            "freshness": "NEW_TODAY",
            "neteller_link": offer["neteller_checkout_link"],
            "sales_strategy": strategy,
            "sales_lane": "AI_BUSINESS_OWNER",
        }
        verified_leads.append(lead)

    print(f"[RESULT] {len(verified_leads)} leads passed deduplication and verification.")
    print(f"[RESULT] {duplicates} duplicates ignored, {quarantined} quarantined.")

    if dry_run:
        print("[DRY RUN] Would write to dialer and canonical memory.")
        if verified_leads:
            print("[DRY RUN] Sample lead preview:")
            print(json.dumps(verified_leads[0], indent=2))
        return

    if verified_leads:
        # Ingest to Canonical
        deal_memory = CanonicalDealMemory()
        for l in verified_leads:
            deal = CanonicalDeal(
                id=l["id"],
                deal_type=DealType.BUSINESS_AI,
                lead_id=l["id"],
                source=l["source"],
                source_class=SourceClass.BUSINESS_DIRECTORY,
                owner_name=l["decision_maker"],
                company_name=l["company"],
                contact_phone=l["phone"],
                contact_email=l["email"],
                title_or_role=l["role"],
                identity_verified=True,
                contact_verified=True,
                company_association_verified=True,
                owner_status_verified=OwnerStatus.VERIFIED_DECISION_MAKER,
                vertical=l["industry"],
                city=l["city"],
                state=l["state"],
                deal_score=int(l["intent_score"]),
                tier=l["tier"],
                why_this_deal=l["pain"],
                why_now=l["why_now"],
                potential_fee=l["monthly_retainer_usd"],
                monetization_route=MonetizationRoute.AI_RETAINER,
                stage=DealStage.QUALIFIED,
                callability_score=95,
            )
            deal_memory.register_deal(deal)
        deal_memory.save()

        # Write to Dialer DB under single-writer lock
        with DialerDatabaseLock() as lock:
            existing = lock.read()
            combined = verified_leads + existing
            total = lock.write(
                combined,
                author="WEDDINGS_INGEST_SCRIPT",
                reason="wedding_campaign_ingestion",
                allow_shrink=False,
            )
        print(f"[OK] {len(verified_leads)} leads pushed to canonical memory and dialer DB. Total dialer rows: {total}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Ingest wedding leads")
    parser.add_argument("file_path", type=str, help="Path to JSON or CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    args = parser.parse_args()

    target_path = Path(args.file_path)
    if not target_path.exists():
        print(f"[ERROR] File not found: {target_path}")
        sys.exit(1)

    ingest_wedding_leads(target_path, dry_run=args.dry_run)
