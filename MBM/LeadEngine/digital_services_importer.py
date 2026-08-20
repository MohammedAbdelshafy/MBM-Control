#!/usr/bin/env python3
"""
CANONICAL DIGITAL SERVICES IMPORTER
====================================
Imports U.S. digital-services companies (Explorium export) into the MBM Lead
Engine + MBM Dialer as a dedicated DIGITAL_SERVICES sales lane.

Canonical path (single source of truth):
    MBM/Artifacts/DigitalServices/us_digital_service_leads_*.csv  (raw source)
    MBM/LeadEngine/digital_services_importer.py                   (THIS importer)
    MBM/LeadEngine/digital_services_scripts.py                    (sales scripts)
    mbm-dialer/app/public/leads_database.json                     (live dialer DB)

Guarantees:
    1. Zero fabricated contact data — no invented phone/email, ever.
    2. Company-only records stay in DIGITAL_SERVICES marked CONTACT_NEEDED.
    3. Only verified/callable records ever reach the prime-call path.
    4. Idempotent — run twice, zero new duplicates, stable ordering/counts.
    5. Dedupe by normalized domain, stable business identity, and phone.
    6. Never overwrites stronger existing contact/provenance data.
    7. Intent scoring + offer recommendation are deterministic.

Usage:
    python MBM/LeadEngine/digital_services_importer.py --source MBM/Artifacts/DigitalServices/us_digital_service_leads_20260817184607.csv
    python MBM/LeadEngine/digital_services_importer.py --dry-run   # no write
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from MBM.LeadEngine.digital_services_scripts import build_digital_script_pack
from MBM.LeadEngine.digital_services_offers import (
    OFFER_CATALOG,
    CATEGORY_MAINTENANCE,
    recommend_offer,
)

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
SOURCE_DIR = ROOT_DIR / "MBM" / "Artifacts" / "DigitalServices"
REPORT_DIR = ROOT_DIR / "MBM" / "Artifacts" / "DigitalServices"

SALES_LANE = "DIGITAL_SERVICES"
VERTICAL = "Digital Services"

SOURCE_NAME = "Explorium U.S. Digital Services Export"
SOURCE_TYPE = "business_registry"

# Free/placeholder hosting + obvious non-business domains = weakest web presence.
WEAK_DOMAIN_RE = re.compile(
    r"(^|\.)(example\.com|lnk\.bio|work\.gd|github\.io|blogspot\.com|wixsite\.com|"
    r"weebly\.com|wordpress\.com|\.xyz|\.top|\.click|\.online)$",
    re.IGNORECASE,
)

# Legacy site artifacts → replatform intent.
LEGACY_SITE_RE = re.compile(r"(\.html|\.htm|\.asp|\.aspx|/products\.asp|\.cfm)", re.IGNORECASE)

# Digital-native verticals → mobile/app intent.
DIGITAL_NATIVE_NAICS = (
    "custom computer programming",
    "computer systems design",
    "software publishers",
    "telecommunications",
    "data processing",
    "information services",
    "internet",
)

# Commerce verticals → ecommerce intent.
ECOMMERCE_NAICS = (
    "retail trade",
    "merchant wholesalers",
    "electronic shopping",
    "mail-order",
)


def normalize_domain(website: str) -> str:
    """Extract a stable, normalized registrable-ish domain from a website URL."""
    w = (website or "").strip().lower()
    if not w:
        return ""
    if "://" in w:
        w = w.split("://", 1)[1]
    w = w.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    w = w.split("@")[-1]
    if w.startswith("www."):
        w = w[4:]
    return w


def normalize_business_identity(name: str) -> str:
    """Stable identity key for a business name (for dedupe)."""
    n = (name or "").strip().lower()
    n = re.sub(r"\b(inc|llc|l\.l\.c|ltd|corp|corporation|company|co)\b[.,]?", "", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n.strip()


def score_intent(row: Dict[str, str]) -> Dict[str, Any]:
    """Deterministic intent scoring from the raw Explorium row.

    Signals used (only real, observed data — never fabricated):
      - website_design: weak/free/placeholder hosting or bare link-in-bio
      - replatform: legacy site artifacts (.html/.asp) or parked-style domains
      - responsive_web: weak/legacy site that must be rebuilt mobile-first
      - mobile_app: digital-native NAICS / software & telecom verticals
      - ecommerce: retail / merchant-wholesaler NAICS
      - freshness: created_at age (all rows exported same day = full freshness)
      - company_fit: SMB size + revenue band that fits $29-$249 offers
    Returns topic scores 0-100 plus a composite intent_score 0-100.
    """
    website = (row.get("business_website") or "").strip()
    naics = (row.get("business_naics_description") or "").strip().lower()
    employees = (row.get("business_number_of_employees_range") or "").strip()
    revenue = (row.get("business_yearly_revenue_range") or "").strip()
    created = (row.get("created_at") or "").strip()

    domain = normalize_domain(website)

    website_design = 30
    replatform = 20
    responsive = 30
    mobile_app = 20
    ecommerce = 10
    company_fit = 40

    # Weak / free-hosting / link-in-bio domains → strong website-design intent.
    if domain and WEAK_DOMAIN_RE.search(domain):
        website_design = 95
        responsive = 90
        replatform = 70
    elif not domain:
        website_design = 100
        responsive = 95
        replatform = 70
    elif LEGACY_SITE_RE.search(website):
        website_design = 60
        replatform = 85
        responsive = 75
    else:
        website_design = 40
        replatform = 30
        responsive = 45

    # Digital-native verticals → mobile/app intent.
    if any(k in naics for k in DIGITAL_NATIVE_NAICS):
        mobile_app = 85
        website_design = max(website_design, 55)

    # Commerce verticals → ecommerce intent.
    if any(k in naics for k in ECOMMERCE_NAICS):
        ecommerce = 85
        responsive = max(responsive, 70)

    # Company fit: SMB size + revenue band best matches our $29-$249 catalog.
    if employees == "[1-10]" and revenue in ("[0-500K]", "[500K-1M]", "[1M-5M]"):
        company_fit = 90
    elif employees in ("[1-10]", "[11-50]") and revenue in ("[1M-5M]", "[500K-1M]"):
        company_fit = 75
    else:
        company_fit = 55

    # Freshness: all rows share the export timestamp → full freshness score.
    freshness = 90
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created_dt).days
        if age_days <= 1:
            freshness = 100
        elif age_days <= 7:
            freshness = 85
        elif age_days <= 30:
            freshness = 60
        else:
            freshness = 30
    except Exception:
        freshness = 50

    topics = {
        "WEBSITE_DESIGN": round(website_design),
        "REPLATFORM": round(replatform),
        "RESPONSIVE_WEB": round(responsive),
        "MOBILE_APP": round(mobile_app),
        "ECOMMERCE": round(ecommerce),
        "FRESHNESS": round(freshness),
        "COMPANY_FIT": round(company_fit),
    }

    composite = round(
        0.30 * website_design
        + 0.20 * replatform
        + 0.15 * responsive
        + 0.15 * mobile_app
        + 0.10 * ecommerce
        + 0.05 * freshness
        + 0.05 * company_fit
    )
    return {"topics": topics, "intent_score": min(100, max(0, composite))}


def build_digital_lead(row: Dict[str, str], seq: int) -> Dict[str, Any]:
    """Convert one raw Explorium row into a canonical DIGITAL_SERVICES lead."""
    business_id = (row.get("business_id") or "").strip()
    company = (row.get("business_name") or "").strip()
    domain = normalize_domain(row.get("business_website") or "")
    region = (row.get("business_region") or "").strip().title() or "US"
    naics = (row.get("business_naics_description") or "").strip()
    employees = (row.get("business_number_of_employees_range") or "").strip()
    revenue = (row.get("business_yearly_revenue_range") or "").strip()
    created = (row.get("created_at") or "").strip()

    scoring = score_intent(row)
    topics = scoring["topics"]
    intent_score = scoring["intent_score"]

    offer = recommend_offer(topics, intent_score)
    scripts = build_digital_script_pack(company, region, domain, offer)

    lead_id = f"DS-{business_id}" if business_id else f"DS-{seq:03d}"

    return {
        "id": lead_id,
        "vertical": VERTICAL,
        "sales_lane": SALES_LANE,
        "company": company,
        "contact": "",
        "title": "Business Owner",
        "domain": domain,
        "website": (row.get("business_website") or "").strip(),
        "location": region,
        "category": offer["category"],
        "naics": naics,
        "employees_range": employees,
        "revenue_range": revenue,
        "intent_topics": topics,
        "intent_score": intent_score,
        "recommended_offer": offer["name"],
        "offer": {
            "name": offer["name"],
            "sku": offer["sku"],
            "category": offer["category"],
            "setup_price_usd": offer["setup_price"],
            "maintenance_price_usd": offer["maintenance_price"],
            "maintenance_upsell": True,
            "neteller_checkout_link": offer["neteller_link"],
        },
        "setup_price": offer["setup_price"],
        "maintenance_price": offer["maintenance_price"],
        "maintenance_upsell": True,
        "phone": "",
        "phone_verified": False,
        "email": "",
        "verification_status": "CONTACT_NEEDED",
        "callable": False,
        "source": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "source_reference": f"explorium:{business_id}",
        "source_timestamp": created,
        "first_seen_at": (created[:10] if created else datetime.now(timezone.utc).date().isoformat()),
        "new_today": True,
        "priority": 0,
        "notes": "Company-only record. No contact phone/email in source export. Needs approved enrichment before any outreach.",
        "scripts": scripts,
        "next_action": "ENRICH_CONTACT",
        "provenance": {
            "source": SOURCE_NAME,
            "source_reference": f"explorium:{business_id}",
            "source_type": SOURCE_TYPE,
            "observed_at": created,
            "verified_at": "",
            "verification_method": "business_registry",
        },
        "details": {
            "source": SOURCE_NAME,
            "source_dataset": (Path(__file__).name if False else "us_digital_service_leads_20260817184607"),
            "explorium_business_id": business_id,
            "vertical_tag": SALES_LANE,
            "Row": row.get("row_num"),
        },
    }


def load_source(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def load_existing_leads() -> List[Dict[str, Any]]:
    if not DIALER_DB.exists():
        return []
    try:
        data = json.loads(DIALER_DB.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("leads", [])
    except Exception:
        return []


def dedupe_existing(existing: List[Dict[str, Any]], digital_leads: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Merge digital leads into existing DB, deduping by id/domain/identity/phone.

    Existing records are NEVER weakened: if a record already carries a
    phone/email/verified contact it is preserved and the incoming (weaker,
    CONTACT_NEEDED) data does not overwrite it.
    """
    stats = {"duplicates_skipped": 0, "added": 0, "updated": 0, "preserved": 0}

    existing_map: Dict[str, Dict[str, Any]] = {}
    domain_map: Dict[str, str] = {}
    identity_map: Dict[str, str] = {}
    phone_map: Dict[str, str] = {}

    for lead in existing:
        lid = str(lead.get("id") or "")
        existing_map[lid] = lead
        dom = normalize_domain(lead.get("website") or lead.get("domain") or "")
        if dom:
            domain_map.setdefault(dom, lid)
        ident = normalize_business_identity(lead.get("company") or "")
        if ident:
            identity_map.setdefault(ident, lid)
        phone = re.sub(r"\D", "", str(lead.get("phone") or ""))
        if len(phone) >= 10:
            phone_map.setdefault(phone, lid)

    for lead in digital_leads:
        lid = str(lead.get("id") or "")
        dom = normalize_domain(lead.get("website") or lead.get("domain") or "")
        ident = normalize_business_identity(lead.get("company") or "")
        phone = re.sub(r"\D", "", str(lead.get("phone") or ""))

        conflict = (
            (dom and dom in domain_map and domain_map[dom] != lid)
            or (ident and ident in identity_map and identity_map[ident] != lid)
            or (phone and len(phone) >= 10 and phone in phone_map and phone_map[phone] != lid)
        )

        if lid in existing_map:
            existing_map[lid] = merge_lead(existing_map[lid], lead)
            stats["updated"] += 1
            continue

        if conflict:
            stats["duplicates_skipped"] += 1
            continue

        existing_map[lid] = lead
        stats["added"] += 1
        if dom:
            domain_map.setdefault(dom, lid)
        if ident:
            identity_map.setdefault(ident, lid)
        if phone and len(phone) >= 10:
            phone_map.setdefault(phone, lid)

    return list(existing_map.values()), stats


def merge_lead(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge incoming digital lead into an existing row, preserving stronger data.

    Rule: never overwrite a stronger existing value with a weaker/null incoming
    value. Existing phone/email/verified contact always wins. Incoming fills
    gaps (scripts, offers, intent scoring, provenance).
    """
    merged = {**existing}

    # Preserve existing contact + verification if present (never weaken).
    if not merged.get("phone") and incoming.get("phone"):
        merged["phone"] = incoming["phone"]
    if not merged.get("email") and incoming.get("email"):
        merged["email"] = incoming["email"]
    if not merged.get("contact") and incoming.get("contact"):
        merged["contact"] = incoming["contact"]

    for k in ("domain", "website", "location", "naics", "employees_range",
              "revenue_range", "intent_topics", "intent_score",
              "recommended_offer", "offer", "setup_price", "maintenance_price",
              "maintenance_upsell", "scripts", "category", "next_action",
              "provenance", "source_timestamp", "first_seen_at"):
        if not merged.get(k) and incoming.get(k):
            merged[k] = incoming[k]

    # Intent/offer are deterministic — always refresh to current canonical state.
    merged["intent_topics"] = incoming.get("intent_topics", merged.get("intent_topics"))
    merged["intent_score"] = incoming.get("intent_score", merged.get("intent_score"))
    merged["recommended_offer"] = incoming.get("recommended_offer", merged.get("recommended_offer"))
    merged["offer"] = incoming.get("offer", merged.get("offer"))

    # Digital lane metadata always refreshed.
    merged["sales_lane"] = SALES_LANE
    merged["vertical"] = VERTICAL

    # Do not downgrade verification: existing verified/callable stays.
    if merged.get("verification_status") == "CONTACT_NEEDED" and incoming.get("verification_status"):
        merged["verification_status"] = incoming["verification_status"]

    return merged


def rank_digital_leads(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank digital leads: verified/callable > intent > offer fit > freshness > fit."""
    def sort_key(lead: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
        callable_rank = 1 if (lead.get("callable") or lead.get("phone_verified")) else 0
        intent = int(lead.get("intent_score") or 0)
        offer_rank = {
            "$249 Business App": 5,
            "$149 Mini App": 4,
            "$99 Pro Website": 3,
            "$49 Business Website": 2,
            "$29 Quick Website": 1,
        }.get(lead.get("recommended_offer") or "", 0)
        freshness = 1 if lead.get("new_today") else 0
        fit = int((lead.get("intent_topics") or {}).get("COMPANY_FIT", 0))
        return (callable_rank, intent, offer_rank, freshness, fit)

    return sorted(leads, key=sort_key, reverse=True)


def write_report(imported: List[Dict[str, Any]], stats: Dict[str, int],
                 source_path: Path, dry_run: bool) -> Dict[str, Any]:
    """Write the import report + manifest into MBM/Artifacts/DigitalServices."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    website = [l for l in imported if l["offer"]["category"] == "WEBSITE"]
    app = [l for l in imported if l["offer"]["category"] == "APP"]
    maintenance = [l for l in imported if l.get("maintenance_upsell")]
    contact_needed = [l for l in imported if l.get("verification_status") == "CONTACT_NEEDED"]
    callable = [l for l in imported if l.get("callable") or l.get("phone_verified")]

    report = {
        "status": "success",
        "dry_run": dry_run,
        "source": str(source_path),
        "source_rows": len(imported) if not dry_run else 0,
        "imported": len(imported),
        "duplicates_skipped": stats.get("duplicates_skipped", 0),
        "added": stats.get("added", 0),
        "updated": stats.get("updated", 0),
        "preserved": stats.get("preserved", 0),
        "contact_needed": len(contact_needed),
        "verified_callable": len(callable),
        "website_leads": len(website),
        "app_leads": len(app),
        "maintenance_upsell": len(maintenance),
        "by_offer": {name: sum(1 for l in imported if l["recommended_offer"] == name)
                     for name in OFFER_CATALOG},
        "top_10": [{"id": l["id"], "company": l["company"], "intent_score": l["intent_score"],
                    "offer": l["recommended_offer"]} for l in imported[:10]],
        "owner": "system",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "next_action": "ENRICH_CONTACT_FOR_MISSING_PHONES" if contact_needed else "NONE",
    }

    report_path = REPORT_DIR / f"digital_services_import_report_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    latest = REPORT_DIR / "digital_services_latest.json"
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Canonical Digital Services Importer")
    ap.add_argument("--source", type=str, default="",
                    help="Path to the Explorium export CSV (default: latest in source dir)")
    ap.add_argument("--dry-run", action="store_true", help="Score + rank only; no DB write")
    args = ap.parse_args()

    source_path = Path(args.source) if args.source else None
    if source_path is None or not source_path.exists():
        candidates = sorted(SOURCE_DIR.glob("us_digital_service_leads_*.csv"), reverse=True)
        if not candidates:
            print("[ERROR] No source CSV found. Pass --source.")
            return 1
        source_path = candidates[0]

    rows = load_source(source_path)
    if not rows:
        print("[ERROR] Source CSV is empty.")
        return 1

    print(f"[IMPORT] Source: {source_path.name} | rows={len(rows)}")

    digital_leads = [build_digital_lead(r, i + 1) for i, r in enumerate(rows)]
    digital_leads = rank_digital_leads(digital_leads)

    existing = load_existing_leads() if not args.dry_run else []
    if args.dry_run:
        print(f"[IMPORT] DRY-RUN: would import {len(digital_leads)} leads (no DB write)")
    else:
        merged, stats = dedupe_existing(existing, digital_leads)
        print(f"[IMPORT] merged={stats['added']} added, {stats['updated']} updated, "
              f"{stats['duplicates_skipped']} dupes skipped, {len(merged)} total DB rows")

        # Stamp canonical queue metadata so every row is eligible/marked exactly
        # once (single source of truth: dialer_queue_engine).
        from MBM.LeadEngine.dialer_queue_engine import assign_lead_metadata, get_callable_state
        for lead in merged:
            state = get_callable_state(lead)
            lead["_callable_state"] = state
            assign_lead_metadata(lead, state)
            lead.pop("_callable_state", None)

        from MBM.LeadEngine.dialer_gateway import commit_dialer_db
        result = commit_dialer_db(
            merged,
            reason="digital_services_importer",
            allow_shrink=False,
            author="DIGITAL_SERVICES_IMPORTER",
        )
        print(f"[IMPORT] commit ok={result.get('ok')} final={result.get('final_count')} "
              f"rejected_synthetic={result.get('rejected_synthetic')}")

        digital = [l for l in merged if l.get("sales_lane") == SALES_LANE]
        report = write_report(digital, stats, source_path, dry_run=False)
        print(f"[IMPORT] report -> {REPORT_DIR / 'digital_services_latest.json'}")
        print(f"[IMPORT] DIGITAL_SERVICES total={len(digital)} "
              f"website={sum(1 for l in digital if l['offer']['category']=='WEBSITE')} "
              f"app={sum(1 for l in digital if l['offer']['category']=='APP')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())