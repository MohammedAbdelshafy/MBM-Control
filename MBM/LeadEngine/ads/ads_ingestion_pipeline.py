"""
MBM LeadEngine — Ad Leads Ingestion & Canonical Bridge
======================================================
Connects Facebook Ads and Google Ads lead retrieval directly into the
authoritative MBM LeadEngine and Dialer pipeline:

Pipeline:
  Ad Lead (Raw Payload)
      ↓
  Normalize & Attribute (Source, Campaign, AdSet, Form, Creative, Niche)
      ↓
  Validate (Phone Sanity, Gate, Suppression Index, DNC, Identity)
      ↓
  Deduplicate (Match Phone/Email/ID vs Existing Leads Database)
      ↓
  Score & Prioritize (Intent, Callability, Motivation, Freshness)
      ↓
  Canonical DB Commit (Single-Writer Gateway Lock)
      ↓
  FRESH_CALL_NOW Partition
      ↓
  Mobile Dialer Ready

Authoritative Invariants:
  - Never bypass the single-writer lock (`dialer_gateway.py`).
  - Never allow duplicate records; update existing while preserving call history.
  - Never allow bad numbers, 555-exchanges, or suppressed phones into callable queue.
  - Stamp full provenance and attribution tags.
  - Enforce freshness ordering (`FRESH_CALL_NOW`, `NEWLY_IMPORTED`).
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.ads.ads_config import (
    log, save_json, LOGS_DIR, neteller_link,
)
from MBM.LeadEngine.dialer_verification_gate import (
    is_valid_phone,
    is_valid_name,
    is_placeholder_identity,
    _extract_phone,
    _extract_name,
)
from MBM.LeadEngine.dialer_queue_engine import (
    _norm_phone,
    get_suppression_index,
    get_callable_state,
    assign_lead_metadata,
    rank_main_queue,
    build_global_queue,
    ordered_db_records,
)
from MBM.LeadEngine.dialer_gateway import (
    commit_dialer_db,
    patch_dialer_db,
    DIALER_DB_PATH,
    SUPPRESSION_FILE,
)

ARTIFACTS_DIR = Path(os.getenv("MBM_ARTIFACTS_ROOT") or str(ROOT_DIR / "MBM" / "Artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
ADS_RECONCILIATION_JSON = ARTIFACTS_DIR / "ads_reconciliation_report.json"
ADS_RECONCILIATION_MD = ARTIFACTS_DIR / "ads_reconciliation_report.md"


# ── Multi-Niche Mapping & Failsafe Router ────────────────────────────────────

CANONICAL_NICHES = {
    "REAL_ESTATE_SELLERS": "Real Estate Sellers",
    "CASH_BUYERS": "Cash Buyers & Flippers",
    "MED_SPAS": "Med Spas & Aesthetics Clinics",
    "CLINICS": "Clinics & Medical Practices",
    "CONTRACTORS_CONTECH": "Commercial Contractors & ConTech",
    "AI_CONSULTANCY": "AI Consultancy & Automation",
    "WEBSITE_CREATION": "Website Design & Development",
    "APP_DEVELOPMENT": "Mobile App Development",
    "B2B_AGENCIES": "Professional Services & B2B Agencies",
}

NICHE_DAILY_TARGETS = {
    "Real Estate Sellers": 100,
    "Cash Buyers & Flippers": 50,
    "Clinics & Medical Practices": 50,
    "Med Spas & Aesthetics Clinics": 25,
    "Commercial Contractors & ConTech": 25,
    "AI Consultancy & Automation": 25,
    "Website Design & Development": 25,
    "Mobile App Development": 25,
    "Professional Services & B2B Agencies": 20,
}


class MultiNicheRouter:
    """Deterministic multi-niche router with strict unknown-niche failsafe."""

    @staticmethod
    def route_niche(raw: Dict[str, Any]) -> Tuple[str, bool, Optional[str]]:
        """
        Maps a lead payload to its canonical niche.
        Returns (canonical_niche, is_confident, rejection_reason).
        
        If ambiguous/unrecognized, returns ("UNCLASSIFIED", False, "UNCLASSIFIED_NICHE")
        to ensure unclassified leads NEVER enter the callable queue.
        """
        # Explicit vertical if already specified and known
        direct_v = raw.get("vertical") or raw.get("category")
        if direct_v in CANONICAL_NICHES.values():
            return direct_v, True, None

        # Build search text from all available attribution fields
        search_blob = " ".join([
            str(raw.get("campaign_name") or raw.get("campaign") or ""),
            str(raw.get("adset_name") or raw.get("ad_set") or raw.get("ad_group") or ""),
            str(raw.get("form_name") or raw.get("form") or ""),
            str(raw.get("keyword") or raw.get("search_query") or ""),
            str(raw.get("creative") or ""),
            str(raw.get("business_type") or raw.get("What type of business do you run?") or ""),
            str(raw.get("interest") or raw.get("ai_interest") or raw.get("What would you like AI to help with?") or ""),
            str(raw.get("trade") or raw.get("treatment_types") or raw.get("property_address") or ""),
            str(raw.get("selling_timeline") or raw.get("capital_ready") or ""),
        ]).lower()

        if not search_blob.strip():
            return "UNCLASSIFIED", False, "UNCLASSIFIED_NICHE_EMPTY_METADATA"

        # 1. Real Estate Sellers
        if any(k in search_blob for k in ("motivated seller", "property address", "as-is", "cash offer", "selling timeline", "distressed seller", "home sale", "house fast")):
            return CANONICAL_NICHES["REAL_ESTATE_SELLERS"], True, None

        # 2. Cash Buyers & Flippers
        if any(k in search_blob for k in ("cash buyer", "buy box", "investor application", "capital ready", "fix & flip", "wholesaler", "off-market deals")):
            return CANONICAL_NICHES["CASH_BUYERS"], True, None

        # 3. Med Spas & Aesthetics
        if any(k in search_blob for k in ("med spa", "medspa", "aesthetics", "injectables", "botox", "body contouring", "cosmetic", "dermatology")):
            return CANONICAL_NICHES["MED_SPAS"], True, None

        # 4. Clinics & Medical Practices
        if any(k in search_blob for k in ("clinic", "dental", "dentistry", "orthodontics", "chiropractic", "optometry", "pediatric", "doctor", "physical therapy", "healthcare")):
            return CANONICAL_NICHES["CLINICS"], True, None

        # 5. Commercial Contractors & ConTech
        if any(k in search_blob for k in ("contractor", "hvac", "mechanical", "electrical", "roofing", "contech", "estimating", "takeoff", "plumbing", "construction")):
            return CANONICAL_NICHES["CONTRACTORS_CONTECH"], True, None

        # 6. Mobile App Development
        if any(k in search_blob for k in ("mobile app", "app development", "ios", "android", "flutter", "react native", "app store", "mvp app")):
            return CANONICAL_NICHES["APP_DEVELOPMENT"], True, None

        # 7. Website Design & Development
        if any(k in search_blob for k in ("website", "web design", "web development", "landing page", "e-commerce", "shopify", "wordpress", "web app")):
            return CANONICAL_NICHES["WEBSITE_CREATION"], True, None

        # 8. AI Consultancy & Automation
        if any(k in search_blob for k in ("ai consultancy", "ai automation", "workflow automation", "ai chatbot", "ai integration", "ai developer", "process automation")):
            return CANONICAL_NICHES["AI_CONSULTANCY"], True, None

        # 9. B2B Professional Services
        if any(k in search_blob for k in ("b2b agency", "consulting agency", "professional services", "staffing agency", "commercial legal")):
            return CANONICAL_NICHES["B2B_AGENCIES"], True, None

        # Failsafe: Unknown / Unclassified
        return "UNCLASSIFIED", False, "UNCLASSIFIED_NICHE_NO_CONFIDENT_MATCH"


class LeadCapacityAnalyzer:
    """Calculates callable inventory, daily targets, and shortfall by niche."""

    @staticmethod
    def analyze_capacity(db_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return full capacity balance sheet across all MBM niches."""
        from collections import Counter
        
        callable_leads = [
            l for l in db_leads 
            if l.get("callable") is True or str(l.get("queue_bucket", "")).startswith("FRESH") or l.get("queue_bucket") == "UNCALLED_VERIFIED"
        ]

        niche_counts = Counter(
            l.get("vertical") or l.get("category") or "UNKNOWN" 
            for l in callable_leads
        )

        balance_sheet = {}
        total_shortfall = 0
        total_callable = len(callable_leads)

        for niche, target in NICHE_DAILY_TARGETS.items():
            # Sum up matching niche variants
            count = sum(cnt for n_key, cnt in niche_counts.items() if niche.lower() in n_key.lower() or n_key.lower() in niche.lower())
            shortfall = max(0, target - count)
            total_shortfall += shortfall
            balance_sheet[niche] = {
                "current_callable": count,
                "daily_target": target,
                "shortfall": shortfall,
                "status": "HEALTHY" if shortfall == 0 else f"SHORTFALL_{shortfall}",
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_callable_inventory": total_callable,
            "total_daily_target": sum(NICHE_DAILY_TARGETS.values()),
            "total_shortfall": total_shortfall,
            "niches": balance_sheet,
        }


class AdLeadNormalizer:
    """Normalizes disparate Facebook and Google Ad form payloads into Canonical DB schema."""

    @staticmethod
    def normalize_facebook_lead(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Facebook Lead Ad submission."""
        now_ts = datetime.now(timezone.utc).isoformat()
        lead_id = raw.get("id") or raw.get("leadgen_id") or f"AD-FB-{uuid.uuid4().hex[:8].upper()}"
        
        name = raw.get("full_name") or raw.get("name") or raw.get("contact_name") or ""
        email = raw.get("email") or raw.get("business_email") or ""
        phone = raw.get("phone_number") or raw.get("phone") or ""
        company = raw.get("company_name") or raw.get("company") or "Direct Business Prospect"
        business_type = raw.get("business_type") or raw.get("What type of business do you run?") or "General Commercial"
        interest = raw.get("ai_interest") or raw.get("What would you like AI to help with?") or "Workflow Automation & Lead Gen"
        
        # Attribution fields
        campaign = raw.get("campaign_name") or raw.get("campaign") or "Facebook Lead Ads Campaign"
        ad_set = raw.get("adset_name") or raw.get("ad_set") or "Target Audience"
        ad = raw.get("ad_name") or raw.get("ad") or "Inbound Creative"
        form = raw.get("form_name") or raw.get("form") or "Default Instant Form"
        creative = raw.get("creative") or "AI Automation Inbound"
        source_id = str(raw.get("id") or raw.get("leadgen_id") or lead_id)
        lead_timestamp = raw.get("created_time") or raw.get("submitted_at") or now_ts
        
        # Determine niche via MultiNicheRouter
        vertical, is_confident, niche_reason = MultiNicheRouter.route_niche(raw)

        lead_record = {
            "id": lead_id,
            "company": company,
            "contact": name,
            "phone": phone,
            "email": email,
            "source": "FACEBOOK_ADS",
            "source_class": "PAID_AD_INBOUND",
            "source_type": "paid_ad_inbound",
            "source_reference": f"https://facebook.com/ads/leadgen/{source_id}",
            "source_id": source_id,
            "verification_method": "paid_ad_inbound",
            "observed_at": lead_timestamp,
            "vertical": vertical,
            "category": vertical,
            "tier": "Tier A",
            "stage": "FRESH_INBOUND",
            "intent_score": 95,
            "motivation_score": 95,
            "deal_score": 95,
            "callability_score": 100 if is_confident else 0,
            "verified": is_confident,
            "phone_verified": is_confident,
            "new_today": is_confident,
            "imported_at": now_ts,
            "first_seen_at": lead_timestamp,
            "created_at": lead_timestamp,
            "verified_at": now_ts if is_confident else None,
            "discovered_at": lead_timestamp,
            "niche_routing_confident": is_confident,
            "niche_routing_reason": niche_reason,
            "attribution": {
                "source": "FACEBOOK_ADS",
                "campaign": campaign,
                "ad_set": ad_set,
                "ad": ad,
                "form": form,
                "creative": creative,
                "source_id": source_id,
                "lead_timestamp": lead_timestamp,
            },
            "details": {
                "verified_phone": phone,
                "Owner_Name": name,
                "email": email,
                "company_name": company,
                "business_type": business_type,
                "interest": interest,
                "source": "FACEBOOK_ADS",
                "campaign": campaign,
                "ad_set": ad_set,
                "ad": ad,
                "form": form,
                "neteller_link": neteller_link(500, f"Consulting_{name.replace(' ', '_')}"),
                "Call_Script": (
                    f"Hi {name.split()[0] if name else 'there'}, this is Omar from Base44 Systems. "
                    f"I saw you just submitted an inquiry regarding {interest} for {company}. "
                    f"We specialize in rapid deployments for {vertical}. "
                    f"Do you have 3 minutes to review your requirements?"
                ),
            },
            "ingestion_timestamp": now_ts,
        }

        if not is_confident:
            lead_record["verification_status"] = "REVIEW_REQUIRED"
            lead_record["callable"] = False
            lead_record["queue_bucket"] = "VERIFICATION_REQUIRED"
            lead_record["blocked_reason"] = niche_reason

        return lead_record

    @staticmethod
    def normalize_google_lead(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Google Ads Lead Form submission."""
        now_ts = datetime.now(timezone.utc).isoformat()
        lead_id = raw.get("id") or raw.get("google_lead_id") or f"AD-GOOG-{uuid.uuid4().hex[:8].upper()}"
        
        name = raw.get("full_name") or raw.get("name") or raw.get("contact_name") or ""
        email = raw.get("email") or raw.get("user_email") or ""
        phone = raw.get("phone_number") or raw.get("phone") or ""
        company = raw.get("company_name") or raw.get("company") or "Search Inbound Client"
        
        # Attribution fields
        campaign = raw.get("campaign") or raw.get("campaign_name") or "Google Search Lead Campaign"
        ad_group = raw.get("ad_group") or raw.get("ad_group_name") or "High Intent Keywords"
        keyword = raw.get("keyword") or raw.get("search_query") or "business services inquiry"
        form = raw.get("form") or raw.get("asset") or "Google Lead Form Extension"
        source_id = str(raw.get("google_lead_id") or raw.get("id") or lead_id)
        lead_timestamp = raw.get("submitted_at") or now_ts
        
        # Determine niche via MultiNicheRouter
        vertical, is_confident, niche_reason = MultiNicheRouter.route_niche(raw)

        lead_record = {
            "id": lead_id,
            "company": company,
            "contact": name,
            "phone": phone,
            "email": email,
            "source": "GOOGLE_ADS",
            "source_class": "PAID_AD_INBOUND",
            "source_type": "paid_ad_inbound",
            "source_reference": f"https://ads.google.com/leadforms/{source_id}",
            "source_id": source_id,
            "verification_method": "paid_ad_inbound",
            "observed_at": lead_timestamp,
            "vertical": vertical,
            "category": vertical,
            "tier": "Tier A",
            "stage": "FRESH_INBOUND",
            "intent_score": 98,  # Search intent is exceptionally high
            "motivation_score": 95,
            "deal_score": 95,
            "callability_score": 100 if is_confident else 0,
            "verified": is_confident,
            "phone_verified": is_confident,
            "new_today": is_confident,
            "imported_at": now_ts,
            "first_seen_at": lead_timestamp,
            "created_at": lead_timestamp,
            "verified_at": now_ts if is_confident else None,
            "discovered_at": lead_timestamp,
            "niche_routing_confident": is_confident,
            "niche_routing_reason": niche_reason,
            "attribution": {
                "source": "GOOGLE_ADS",
                "campaign": campaign,
                "ad_group": ad_group,
                "keyword": keyword,
                "form": form,
                "source_id": source_id,
                "lead_timestamp": lead_timestamp,
            },
            "details": {
                "verified_phone": phone,
                "Owner_Name": name,
                "email": email,
                "company_name": company,
                "keyword": keyword,
                "source": "GOOGLE_ADS",
                "campaign": campaign,
                "form": form,
                "neteller_link": neteller_link(500, f"Audit_{name.replace(' ', '_')}"),
                "Call_Script": (
                    f"Hi {name.split()[0] if name else 'there'}, this is Omar from Base44 Engineering. "
                    f"You requested information on our {vertical} solutions. "
                    f"We specialize in accelerated delivery and high-ROI implementations. "
                    f"Have you already defined your project timeline?"
                ),
            },
            "ingestion_timestamp": now_ts,
        }

        if not is_confident:
            lead_record["verification_status"] = "REVIEW_REQUIRED"
            lead_record["callable"] = False
            lead_record["queue_bucket"] = "VERIFICATION_REQUIRED"
            lead_record["blocked_reason"] = niche_reason

        return lead_record


class AdLeadIngestionPipeline:
    """Ingests, validates, deduplicates, and commits Ad Leads into the Canonical Dialer DB."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DIALER_DB_PATH

    def load_existing_db(self) -> List[Dict[str, Any]]:
        """Load current live dialer records."""
        if not self.db_path.exists():
            return []
        try:
            data = json.loads(self.db_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else data.get("leads", [])
        except Exception as e:
            log.error(f"Failed to load dialer DB from {self.db_path}: {e}")
            return []

    def validate_ad_lead(self, lead: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate an ad lead through strict gates:
          1. Phone validity & format (E.164, non-555, non-placeholder)
          2. Suppression index check (suppressed_bad_phones.json)
          3. DNC check
          4. Name sanity
        """
        phone = _extract_phone(lead)
        name = _extract_name(lead)

        # 1. DNC / Bad state in details or text
        disp = str(lead.get("disposition") or (lead.get("details") or {}).get("disposition") or "").upper()
        if "DNC" in disp or "BAD_NUMBER" in disp or "DO_NOT_CALL" in disp:
            return False, f"SUPPRESSED_DISPOSITION:{disp}"

        # 2. Phone check
        phone_ok, phone_reason = is_valid_phone(phone)
        if not phone_ok:
            return False, f"INVALID_PHONE:{phone_reason}"

        # 3. Suppression Index Check
        norm_p = _norm_phone(phone)
        suppressed_set = get_suppression_index()
        if norm_p and norm_p in suppressed_set:
            return False, "SUPPRESSED_PHONE_INDEX"

        # 4. Name sanity
        name_ok, name_reason = is_valid_name(name)
        if not name_ok:
            return False, f"INVALID_NAME:{name_reason}"

        # 5. Placeholder identity
        if is_placeholder_identity(lead):
            return False, "PLACEHOLDER_IDENTITY"

        # 6. Source-to-niche failsafe
        if not lead.get("niche_routing_confident", True) or lead.get("vertical") == "UNCLASSIFIED":
            return False, f"UNCLASSIFIED_NICHE:{lead.get('niche_routing_reason', 'unknown_niche')}"

        return True, "VALID"

    def deduplicate_and_merge(
        self,
        new_leads: List[Dict[str, Any]],
        existing_leads: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        """
        Matches incoming ad leads against existing DB by phone, email, or lead_id.
        If lead exists: merges/updates attribution & latest notes, preserves call history.
        If lead is new: adds as new canonical lead.
        
        Returns (merged_all_leads, newly_added_leads, updated_duplicates_count).
        """
        existing_by_phone: Dict[str, Dict[str, Any]] = {}
        existing_by_email: Dict[str, Dict[str, Any]] = {}
        existing_by_id: Dict[str, Dict[str, Any]] = {}

        for lead in existing_leads:
            p = _norm_phone(_extract_phone(lead))
            if p:
                existing_by_phone[p] = lead
            em = str(lead.get("email") or (lead.get("details") or {}).get("email") or "").strip().lower()
            if em:
                existing_by_email[em] = lead
            lid = str(lead.get("id") or "")
            if lid:
                existing_by_id[lid] = lead

        duplicate_count = 0
        new_added = []
        all_leads = list(existing_leads)

        for new_lead in new_leads:
            p = _norm_phone(_extract_phone(new_lead))
            em = str(new_lead.get("email") or "").strip().lower()
            lid = str(new_lead.get("id") or "")

            target_lead = None
            if p and p in existing_by_phone:
                target_lead = existing_by_phone[p]
            elif em and em in existing_by_email:
                target_lead = existing_by_email[em]
            elif lid and lid in existing_by_id:
                target_lead = existing_by_id[lid]

            if target_lead:
                # Update existing lead without destroying call history
                duplicate_count += 1
                target_lead["last_ad_touch"] = new_lead.get("ingestion_timestamp")
                target_lead["updated_at"] = new_lead.get("ingestion_timestamp")
                target_lead["latest_attribution"] = new_lead.get("attribution")
                
                # Merge details
                if "details" not in target_lead:
                    target_lead["details"] = {}
                for k, v in new_lead.get("details", {}).items():
                    if k not in target_lead["details"] or not target_lead["details"][k]:
                        target_lead["details"][k] = v
                log.info(f"Deduplicated and updated existing lead {target_lead.get('id')} with new Ad data")
            else:
                all_leads.append(new_lead)
                new_added.append(new_lead)
                if p:
                    existing_by_phone[p] = new_lead
                if em:
                    existing_by_email[em] = new_lead
                if lid:
                    existing_by_id[lid] = new_lead

        return all_leads, new_added, duplicate_count

    def ingest_batch(
        self,
        raw_leads: List[Dict[str, Any]],
        platform: str = "facebook",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a batch of raw leads from Facebook or Google.
        Enforces validation, deduplication, latency tracking, and canonical gateway commit.
        """
        start_time = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Normalize
        normalized_leads = []
        for raw in raw_leads:
            if platform.lower() == "facebook" or raw.get("source") == "FACEBOOK_ADS":
                norm = AdLeadNormalizer.normalize_facebook_lead(raw)
            else:
                norm = AdLeadNormalizer.normalize_google_lead(raw)
            normalized_leads.append(norm)

        # 2. Validate
        validated_leads = []
        rejected_leads = []
        for lead in normalized_leads:
            val_ok, reason = self.validate_ad_lead(lead)
            lead["validated_timestamp"] = datetime.now(timezone.utc).isoformat()
            if val_ok:
                lead["_gate_passed"] = True
                lead["_gate_source"] = "PAID_AD_VERIFIED"
                validated_leads.append(lead)
            else:
                lead["callable"] = False
                lead["verification_status"] = "REJECTED"
                lead["blocked_reason"] = reason
                lead["queue_bucket"] = "SUPPRESSED" if "SUPPRESS" in reason or "DNC" in reason else "VERIFICATION_REQUIRED"
                rejected_leads.append((lead, reason))

        # 3. Deduplicate
        existing = self.load_existing_db()
        merged_pool, newly_added, dupes_count = self.deduplicate_and_merge(validated_leads, existing)

        # 4. Rank & assign queue metadata
        for l in merged_pool:
            state = get_callable_state(l)
            assign_lead_metadata(l, state)

        # Build globally partitioned buckets
        buckets = build_global_queue(merged_pool, call_now_size=25, next_size=75)
        final_ordered = ordered_db_records(buckets)

        end_time = time.time()
        latency_sec = round(end_time - start_time, 4)

        # Stamp latency on new leads
        for l in newly_added:
            l["dialer_timestamp"] = datetime.now(timezone.utc).isoformat()
            l["latency_seconds"] = latency_sec

        commit_result = {}
        if not dry_run:
            # Commit through single writer gateway
            commit_result = commit_dialer_db(
                final_ordered,
                reason=f"ad_leads_ingestion_{platform}",
                allow_shrink=False,
                db_path=self.db_path,
            )
            log.info(f"Committed {len(final_ordered)} total leads into dialer DB via gateway")

        # 5. Compile summary
        top_now_ad_leads = [
            l for l in buckets.get("FRESH_CALL_NOW", [])
            if l.get("source") in ("FACEBOOK_ADS", "GOOGLE_ADS")
        ]

        summary = {
            "timestamp": now_iso,
            "platform": platform.upper(),
            "dry_run": dry_run,
            "raw_count": len(raw_leads),
            "validated_count": len(validated_leads),
            "rejected_count": len(rejected_leads),
            "duplicates_updated": dupes_count,
            "newly_added_callable": len(newly_added),
            "total_db_records": len(final_ordered),
            "fresh_call_now_count": len(buckets.get("FRESH_CALL_NOW", [])),
            "ad_leads_in_call_now": len(top_now_ad_leads),
            "latency_seconds": latency_sec,
            "commit_result": commit_result,
            "rejections": [{"id": r[0].get("id"), "reason": r[1]} for r in rejected_leads],
            "capacity": LeadCapacityAnalyzer.analyze_capacity(final_ordered),
        }

        # Update reconciliation logs
        self.record_reconciliation(summary, final_ordered)
        return summary

    def record_reconciliation(self, summary: Dict[str, Any], all_records: Optional[List[Dict[str, Any]]] = None) -> None:
        """Update daily ad lead reconciliation ledger and generate reports."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        reconciliation_data = {}
        if ADS_RECONCILIATION_JSON.exists():
            try:
                reconciliation_data = json.loads(ADS_RECONCILIATION_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass

        platform = summary["platform"].lower()
        if today not in reconciliation_data:
            reconciliation_data[today] = {
                "date": today,
                "facebook": {"received": 0, "validated": 0, "rejected": 0, "duplicates": 0, "callable": 0, "dialer_delivered": 0},
                "google": {"received": 0, "validated": 0, "rejected": 0, "duplicates": 0, "callable": 0, "dialer_delivered": 0},
                "total_pushed_to_dialer": 0,
                "niche_shortfall": {},
            }

        plat_stats = reconciliation_data[today].get(platform, {
            "received": 0, "validated": 0, "rejected": 0, "duplicates": 0, "callable": 0, "dialer_delivered": 0
        })
        plat_stats["received"] += summary["raw_count"]
        plat_stats["validated"] += summary["validated_count"]
        plat_stats["rejected"] += summary["rejected_count"]
        plat_stats["duplicates"] += summary["duplicates_updated"]
        plat_stats["callable"] += summary["newly_added_callable"]
        plat_stats["dialer_delivered"] += summary["ad_leads_in_call_now"]
        reconciliation_data[today][platform] = plat_stats
        reconciliation_data[today]["total_pushed_to_dialer"] = (
            reconciliation_data[today]["facebook"]["dialer_delivered"] +
            reconciliation_data[today]["google"]["dialer_delivered"]
        )

        # Capacity analysis
        if all_records:
            cap = LeadCapacityAnalyzer.analyze_capacity(all_records)
            reconciliation_data[today]["capacity_balance_sheet"] = cap
            reconciliation_data[today]["niche_shortfall"] = {
                n: d["shortfall"] for n, d in cap["niches"].items()
            }

        save_json(ADS_RECONCILIATION_JSON, reconciliation_data)

        # Generate markdown report with Capacity Balance Sheet
        cap_section = ""
        if "capacity_balance_sheet" in reconciliation_data[today]:
            cap = reconciliation_data[today]["capacity_balance_sheet"]
            rows = []
            for n, d in cap["niches"].items():
                rows.append(f"| {n} | {d['current_callable']} | {d['daily_target']} | {d['shortfall']} | {d['status']} |")
            cap_rows_md = "\n".join(rows)
            cap_section = f"""
## Niche Capacity & Lead Shortfall Analysis

| Niche | Current Callable | Daily Target | Shortfall | Status |
|---|---|---|---|---|
{cap_rows_md}

**Total Callable Inventory:** {cap['total_callable_inventory']} | **Total Daily Target:** {cap['total_daily_target']} | **Total Shortfall:** {cap['total_shortfall']}
"""

        md_content = f"""# Daily Ad Lead Reconciliation Report
**Date:** {today}
**Last Run:** {summary['timestamp']}

## Platform Performance

| Metric | Facebook Ads | Google Ads | Total |
|---|---|---|---|
| **Raw Leads Received** | {reconciliation_data[today]['facebook']['received']} | {reconciliation_data[today]['google']['received']} | {reconciliation_data[today]['facebook']['received'] + reconciliation_data[today]['google']['received']} |
| **Passed Validation** | {reconciliation_data[today]['facebook']['validated']} | {reconciliation_data[today]['google']['validated']} | {reconciliation_data[today]['facebook']['validated'] + reconciliation_data[today]['google']['validated']} |
| **Rejected (Bad Phone / DNC / Unknown)** | {reconciliation_data[today]['facebook']['rejected']} | {reconciliation_data[today]['google']['rejected']} | {reconciliation_data[today]['facebook']['rejected'] + reconciliation_data[today]['google']['rejected']} |
| **Duplicates Merged** | {reconciliation_data[today]['facebook']['duplicates']} | {reconciliation_data[today]['google']['duplicates']} | {reconciliation_data[today]['facebook']['duplicates'] + reconciliation_data[today]['google']['duplicates']} |
| **New Callable Added** | {reconciliation_data[today]['facebook']['callable']} | {reconciliation_data[today]['google']['callable']} | {reconciliation_data[today]['facebook']['callable'] + reconciliation_data[today]['google']['callable']} |
| **Delivered to FRESH_CALL_NOW** | {reconciliation_data[today]['facebook']['dialer_delivered']} | {reconciliation_data[today]['google']['dialer_delivered']} | {reconciliation_data[today]['total_pushed_to_dialer']} |
{cap_section}
## Attribution & Pipeline Status
- **Source Tracking:** ACTIVE (Full attribution tagged on every record)
- **Multi-Niche Routing:** ACTIVE (Failsafe prevents unclassified ingestion)
- **Single-Writer Lock:** ENFORCED (`dialer_gateway.py`)
- **Freshness Bucket:** `FRESH_CALL_NOW` (Stage: `NEWLY_IMPORTED`)
"""
        ADS_RECONCILIATION_MD.write_text(md_content, encoding="utf-8")


def reconcile_ad_leads() -> Dict[str, Any]:
    """Return the latest reconciliation metrics."""
    if ADS_RECONCILIATION_JSON.exists():
        try:
            return json.loads(ADS_RECONCILIATION_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}
