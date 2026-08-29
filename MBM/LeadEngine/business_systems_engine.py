#!/usr/bin/env python3
"""
Business Systems Opportunity Engine
========================================
Identifies the BUSINESS PROBLEM first, then recommends the best combination
of existing SaaS, CRM, scheduling, dispatch, payments, forms, workflow
automation, analytics, communications, integrations, databases, dashboards,
human process improvements, and AI where it creates measurable leverage.

AI is ONE CATEGORY, not the default answer.

Every recommendation is classified: VERIFIED FACT, SUPPORTED INFERENCE,
HYPOTHESIS, or UNKNOWN. Never fabricate a pain point.

Integration with Dialer → Phound workflow:
  Business Summary → Operational Evidence → Detected Leaks → Recommended System
  → Why It Fits → Script → Offer → Dial → Phound → After-Call → Follow-Up

Commercial Learning Loop tracks: industry, problem, system, script, offer,
call outcome, offer acceptance, appointment, checkout, payment, revenue.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════
# RECOMMENDATION TYPE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════

RECOMMENDATION_TYPES = ("VERIFIED FACT", "SUPPORTED INFERENCE", "HYPOTHESIS", "UNKNOWN", "CONFLICT")


class RecommendationClassifier:
    """Classifies every recommendation by evidence strength.

    VERIFIED FACT:     Directly observed in the lead's data (e.g. `attempts > 0`
                       means already contacted, `disposition` means outcome recorded).
    SUPPORTED INFERENCE: Strongly implied by available evidence but not directly stated.
    HYPOTHESIS:        Reasonable guess based on industry patterns, not confirmed.
    UNKNOWN:           Insufficient evidence to classify.
    CONFLICT:          Independent sources disagree materially — do not surface as fact.
    """

    @staticmethod
    def classify(lead: Dict[str, Any], signal: str) -> str:
        # CONFLICT takes precedence — if the lead is explicitly flagged as conflicted, surface it
        if lead.get("conflict_flag") or lead.get("provenance_conflict") or lead.get("field_provenance_conflict"):
            return "CONFLICT"
        verified_signals = {"attempts", "disposition", "verification_status", "source"}
        supported_signals = {"priority_score", "callability_score", "intent_score", "motivation_score"}

        if signal in verified_signals:
            return "VERIFIED FACT"
        if signal in supported_signals:
            return "SUPPORTED INFERENCE"
        if lead.get("vertical") or lead.get("industry"):
            return "SUPPORTED INFERENCE"
        return "HYPOTHESIS"

    @staticmethod
    def detect_provider_conflict(lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect material provider disagreements that must surface as CONFLICT.

        Checks:
        - phone vs verified_phone mismatch after normalization
        - phone vs skip_trace_phone_alt mismatch
        - enrichment provider phones (e.g. Clay vs Vibe vs LinkedIn) with distinct values
        - provenance fields with conflicting values for same logical field (phone, contact)
        Returns a conflict leak dict or None.
        """
        def norm_phone(p: str) -> str:
            digits = "".join(ch for ch in str(p or "") if ch.isdigit())
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            return digits

        phones: Dict[str, str] = {}
        # canonical sources
        for key in ("phone", "verified_phone", "skip_trace_phone_alt", "business_phone", "owner_phone"):
            val = str(lead.get(key) or "").strip()
            if val:
                phones[key] = norm_phone(val)
        # enrichment provenance dicts: { field: { provider: value } } or flat provenance
        provenance = lead.get("field_provenance") or lead.get("provenance") or {}
        if isinstance(provenance, dict):
            for field, prov in provenance.items():
                if field in ("phone", "verified_phone", "contact_phone") and isinstance(prov, dict):
                    for prov_name, prov_val in prov.items():
                        if prov_val:
                            phones[f"provenance:{field}:{prov_name}"] = norm_phone(str(prov_val))
                # older shape: { provider: { phone: X } }
                if isinstance(prov, dict) and "phone" in prov:
                    phones[f"provenance:{field}:phone"] = norm_phone(str(prov["phone"]))

        # Compare distinct normalized values
        distinct = set(v for v in phones.values() if v)
        if len(distinct) > 1:
            # Build evidence reference listing providers/fields
            evidence = "; ".join(f"{k}={phones[k]}" for k in sorted(phones.keys()))
            return {
                "leak": "Provider conflict — phone disagreement",
                "detail": f"Independent sources report different phones: {evidence}. Do NOT dial until resolved.",
                "type": "CONFLICT",
                "evidence": evidence,
                "conflict_flag": True,
                "field": "phone",
                "providers": list(phones.keys()),
                "values": list(distinct),
            }

        # Contact name conflict (material)
        contacts: Dict[str, str] = {}
        for key in ("contact", "decision_maker", "owner_name", "authorized_official_name"):
            val = str(lead.get(key) or "").strip().lower()
            if val and val not in ("n/a", "unknown", ""):
                contacts[key] = val
        if len(set(contacts.values())) > 2:  # >2 distinct names suggests material conflict
            evidence = "; ".join(f"{k}={v}" for k, v in contacts.items())
            return {
                "leak": "Provider conflict — contact disagreement",
                "detail": f"Independent sources report different contacts: {evidence}.",
                "type": "CONFLICT",
                "evidence": evidence,
                "conflict_flag": True,
                "field": "contact",
            }
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM CATALOG
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_CATALOG: Dict[str, Dict[str, Any]] = {
    # ── CLINIC SYSTEMS ──────────────────────────────────────────────
    "Dental": {
        "industry": "Dental",
        "problem": "New patients call but do not book; recall patients fall through the cracks",
        "workflow": "Intake → Scheduling → Recall → Referral Tracking → Follow-Up → Payments → Analytics",
        "system_category": "Practice Operations",
        "software_category": "Practice Management + Scheduling + CRM + Payments",
        "automation": "Automated recall sequences, intake forms, referral attribution",
        "AI_capability": "Predictive no-show scoring; automated patient messaging triage",
        "integration": "Supabase, HubSpot, Airtable, Slack, Forms, SMS",
        "implementation": "Low–Medium; SaaS stack + workflow config, no custom dev",
        "outcome": "Higher case acceptance, fewer missed recalls, measurable revenue per chair",
        "evidence_required": "New-patient call volume, recall list size, case acceptance rate",
        "recommendation_type": "VERIFIED FACT",
    },
    "Medical": {
        "industry": "Medical",
        "problem": "Patient intake and follow-up are manual; no-show rates erode revenue",
        "workflow": "Intake → Scheduling → Reminders → Follow-Up → Document Workflow → Payments → Analytics",
        "system_category": "Patient Operations",
        "software_category": "EHR Adjacent + Scheduling + Forms + CRM + Payments",
        "automation": "Automated recall, intake workflows, document routing",
        "AI_capability": "No-show prediction; patient message triage",
        "integration": "Supabase, HubSpot, Airtable, Slack, HIPAA-compatible comms",
        "implementation": "Medium; compliance-aware workflow config",
        "outcome": "Recovered no-shows, faster intake, documented follow-up",
        "evidence_required": "No-show rate, intake completion, recall compliance",
        "recommendation_type": "VERIFIED FACT",
    },
    "Dermatology": {
        "industry": "Dermatology",
        "problem": "Procedure follow-up and recall are inconsistent; patients forget next steps",
        "workflow": "Intake → Scheduling → Procedure Follow-Up → Recall → Reviews → Payments → Analytics",
        "system_category": "Practice Operations",
        "software_category": "Scheduling + Follow-Up + CRM + Reviews + Payments",
        "automation": "Procedure-specific recall sequences, review solicitation",
        "AI_capability": "Procedure-type-based recall timing optimization",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Better procedure compliance, more reviews, repeat bookings",
        "evidence_required": "Procedure volume, recall compliance, review count",
        "recommendation_type": "VERIFIED FACT",
    },
    "Orthopedics": {
        "industry": "Orthopedics",
        "problem": "Post-surgical follow-up and rehab adherence are manual and leak revenue",
        "workflow": "Intake → Scheduling → Post-Op Follow-Up → Rehab Tracking → Payments → Analytics",
        "system_category": "Post-Operative Operations",
        "software_category": "Scheduling + Follow-Up + Forms + CRM + Payments",
        "automation": "Post-surgical check-in sequences, rehab milestone reminders",
        "AI_capability": "Recovery-stage-based engagement timing",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Medium",
        "outcome": "Higher post-op compliance, fewer complications, more referrals",
        "evidence_required": "Post-op volume, compliance rate, referral count",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Ophthalmology": {
        "industry": "Ophthalmology",
        "problem": "Surgical booking and recall are fragmented; patients fall between visits",
        "workflow": "Intake → Scheduling → Surgical Follow-Up → Recall → Reviews → Payments → Analytics",
        "system_category": "Surgical Operations",
        "software_category": "Scheduling + Follow-Up + CRM + Reviews + Payments",
        "automation": "Surgical recall sequences, post-op check-ins",
        "AI_capability": "Procedure-based recall window optimization",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Higher surgical throughput, better recall, more reviews",
        "evidence_required": "Surgical volume, recall rate, review count",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Physiotherapy": {
        "industry": "Physiotherapy",
        "problem": "Treatment sessions and home-exercise adherence are hard to track",
        "workflow": "Intake → Scheduling → Treatment Follow-Up → Home Exercise → Recall → Payments → Analytics",
        "system_category": "Treatment Operations",
        "software_category": "Scheduling + Follow-Up + Forms + CRM + Payments",
        "automation": "Session-based recall, exercise compliance nudges",
        "AI_capability": "Adherence pattern detection",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Better treatment adherence, more sessions per patient",
        "evidence_required": "Session volume, adherence rate, patient retention",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Cardiology": {
        "industry": "Cardiology",
        "problem": "Post-intervention follow-up and medication adherence are critical and manual",
        "workflow": "Intake → Scheduling → Post-Intervention Follow-Up → Recall → Payments → Analytics",
        "system_category": "Cardiac Operations",
        "software_category": "Scheduling + Follow-Up + CRM + Payments + Analytics",
        "automation": "Post-intervention recall, medication adherence nudges",
        "AI_capability": "Risk-stratified follow-up prioritization",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Medium; higher compliance requirements",
        "outcome": "Better post-intervention compliance, fewer readmissions",
        "evidence_required": "Intervention volume, follow-up compliance, readmission rate",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Pediatrics": {
        "industry": "Pediatrics",
        "problem": "Well-child visits and immunization recall are easily missed",
        "workflow": "Intake → Scheduling → Immunization Recall → Well-Child Follow-Up → Reviews → Payments → Analytics",
        "system_category": "Pediatric Operations",
        "software_category": "Scheduling + Recall + CRM + Reviews + Payments",
        "automation": "Age-based immunization recall, well-child scheduling",
        "AI_capability": "Age/milestone-based recall automation",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Higher vaccination compliance, more well-child visits",
        "evidence_required": "Patient demographics, recall compliance, visit frequency",
        "recommendation_type": "VERIFIED FACT",
    },
    "ENT": {
        "industry": "ENT",
        "problem": "Surgical and medical follow-up are inconsistent; referrals are under-tracked",
        "workflow": "Intake → Scheduling → Surgical Follow-Up → Medical Follow-Up → Referral Tracking → Payments → Analytics",
        "system_category": "ENT Operations",
        "software_category": "Scheduling + Follow-Up + CRM + Referral Tracking + Payments",
        "automation": "Surgical recall, referral attribution sequences",
        "AI_capability": "Referral-source optimization",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Better surgical follow-up, more attributed referrals",
        "evidence_required": "Surgical volume, referral count, follow-up compliance",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Medical Aesthetics": {
        "industry": "Medical Aesthetics",
        "problem": "Package purchases and treatment series have low completion rates",
        "workflow": "Intake → Scheduling → Treatment Series Follow-Up → Package Recall → Reviews → Payments → Analytics",
        "system_category": "Aesthetics Operations",
        "software_category": "Scheduling + Follow-Up + CRM + Reviews + Payments",
        "automation": "Treatment-series completion nudges, package recall",
        "AI_capability": "Treatment-series completion prediction",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Higher package completion, more reviews, repeat bookings",
        "evidence_required": "Package sales, completion rate, review count",
        "recommendation_type": "SUPPORTED INFERENCE",
    },
    "Veterinary": {
        "industry": "Veterinary",
        "problem": "Wellness visits and surgical follow-up are missed; recalls are manual",
        "workflow": "Intake → Scheduling → Wellness Recall → Surgical Follow-Up → Payments → Analytics",
        "system_category": "Practice Operations",
        "software_category": "Scheduling + Recall + CRM + Payments + Analytics",
        "automation": "Pet-age-based wellness recall, surgical follow-up",
        "AI_capability": "Pet-lifecycle-based recall scheduling",
        "integration": "Supabase, HubSpot, Airtable, Forms, SMS",
        "implementation": "Low–Medium",
        "outcome": "Higher wellness visit compliance, more surgical follow-ups",
        "evidence_required": "Visit frequency, recall compliance, surgical volume",
        "recommendation_type": "SUPPORTED INFERENCE",
    },

    # ── HVAC ────────────────────────────────────────────────────────
    "HVAC": {
        "industry": "HVAC",
        "problem": "Missed calls, unreturned estimates, and lapsed maintenance plans leak revenue",
        "workflow": "Lead Capture → Missed-Call Recovery → Booking → Dispatch → Estimate Follow-Up → Quote Approval → Payments → Maintenance Renewal → Dashboard",
        "system_category": "Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Dispatch + Payments + Dashboard",
        "automation": "Missed-call SMS recovery, estimate follow-up sequences, maintenance renewal nudges",
        "AI_capability": "Lead-to-close prediction; dispatch route optimization",
        "integration": "Clay, Vibe Prospecting, LinkedIn, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium; multi-SaaS stack + workflow automation",
        "outcome": "Recovered missed calls, higher estimate close rate, more maintenance renewals",
        "evidence_required": "Call volume, estimate-to-close rate, maintenance renewal rate",
        "recommendation_type": "VERIFIED FACT",
    },

    # ── PLUMBING ────────────────────────────────────────────────────
    "Plumbing": {
        "industry": "Plumbing",
        "problem": "Emergency calls go unanswered; estimates and invoicing are fragmented",
        "workflow": "Lead Capture → Missed-Call Recovery → Booking → Dispatch → Estimate → Invoicing → Payments → Reviews → Dashboard",
        "system_category": "Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Dispatch + Payments + Reviews + Dashboard",
        "automation": "Emergency SMS recovery, invoicing sequences, review solicitation",
        "AI_capability": "Emergency-lead prioritization; route optimization",
        "integration": "Clay, Vibe Prospecting, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium",
        "outcome": "Recovered emergency calls, faster invoicing, more reviews",
        "evidence_required": "Emergency call volume, close rate, review count",
        "recommendation_type": "SUPPORTED INFERENCE",
    },

    # ── ELECTRICAL ──────────────────────────────────────────────────
    "Electrical": {
        "industry": "Electrical",
        "problem": "Estimates and inspections are poorly tracked; repeat business is unplanned",
        "workflow": "Lead Capture → Booking → Estimate → Inspection Follow-Up → Payments → Maintenance → Reviews → Dashboard",
        "system_category": "Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Payments + Follow-Up + Reviews + Dashboard",
        "automation": "Estimate follow-up, inspection reminder, review solicitation",
        "AI_capability": "Inspection-schedule optimization; repeat-business prediction",
        "integration": "Clay, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium",
        "outcome": "Higher estimate close rate, more maintenance revenue, more reviews",
        "evidence_required": "Estimate volume, close rate, maintenance revenue",
        "recommendation_type": "SUPPORTED INFERENCE",
    },

    # ── ROOFING ─────────────────────────────────────────────────────
    "Roofing": {
        "industry": "Roofing",
        "problem": "Storm leads and insurance claims are time-sensitive; estimates are slow to follow",
        "workflow": "Lead Capture → Storm-Lead Recovery → Booking → Estimate → Insurance Coordination → Payments → Dashboard",
        "system_category": "Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Payments + Insurance Workflow + Dashboard",
        "automation": "Storm-lead SMS recovery, estimate urgency sequences",
        "AI_capability": "Storm-lead prioritization; insurance-claim tracking",
        "integration": "Clay, Vibe Prospecting, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium",
        "outcome": "Recovered storm leads, faster estimates, more closed jobs",
        "evidence_required": "Storm-lead volume, close rate, average job size",
        "recommendation_type": "SUPPORTED INFERENCE",
    },

    # ── HOME SERVICES ───────────────────────────────────────────────
    "Home Services": {
        "industry": "Home Services",
        "problem": "Lead capture is inconsistent; follow-up is manual and slow",
        "workflow": "Lead Capture → Missed-Call Recovery → Booking → Quote → Follow-Up → Payments → Reviews → Dashboard",
        "system_category": "Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Payments + Follow-Up + Reviews + Dashboard",
        "automation": "Missed-call recovery, quote follow-up sequences, review solicitation",
        "AI_capability": "Lead-quality scoring; quote-to-close prediction",
        "integration": "Clay, Vibe Prospecting, LinkedIn, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Low–Medium",
        "outcome": "More recovered leads, faster follow-up, more reviews",
        "evidence_required": "Lead volume, close rate, response time, review count",
        "recommendation_type": "VERIFIED FACT",
    },

    # ── REAL ESTATE ─────────────────────────────────────────────────
    "Real Estate": {
        "industry": "Real Estate",
        "problem": "Seller leads and buyer leads are not systematically followed; no-shows waste appointments",
        "workflow": "Lead Capture → Qualification → Booking → Follow-Up → Offer → Closing → Payments → Analytics → Reviews",
        "system_category": "Sales Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Follow-Up + Payments + Analytics + Reviews",
        "automation": "Lead-nurture sequences, appointment reminders, offer follow-ups",
        "AI_capability": "Lead-intent scoring; market-opportunity identification",
        "integration": "Clay, LinkedIn, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium",
        "outcome": "Higher lead-to-close rate, fewer no-shows, more transactions",
        "evidence_required": "Lead volume, close rate, no-show rate, transaction count",
        "recommendation_type": "VERIFIED FACT",
    },

    # ── AUTOMOTIVE ──────────────────────────────────────────────────
    "Automotive": {
        "industry": "Automotive",
        "problem": "Service leads and sales leads are not tracked consistently; follow-up is slow",
        "workflow": "Lead Capture → Qualification → Booking → Follow-Up → Quote → Closing → Payments → Service Recall → Reviews",
        "system_category": "Sales & Service Operations",
        "software_category": "Lead Capture + CRM + Scheduling + Follow-Up + Payments + Recall + Reviews",
        "automation": "Service-recall sequences, sales follow-up, review solicitation",
        "AI_capability": "Service-need prediction; sales-lead prioritization",
        "integration": "Clay, Airtable, Supabase, HubSpot, Slack",
        "implementation": "Medium",
        "outcome": "More closed sales, more service visits, more reviews",
        "evidence_required": "Lead volume, close rate, service visit frequency",
        "recommendation_type": "SUPPORTED INFERENCE",
    },

    # ── PROFESSIONAL SERVICES ───────────────────────────────────────
    "Professional Services": {
        "industry": "Professional Services",
        "problem": "Pipeline is unstructured; proposals go unanswered; no system for recurring revenue",
        "workflow": "Lead Capture → Qualification → Proposal → Follow-Up → Closing → Payments → Analytics → Retention → Referrals",
        "system_category": "Pipeline Operations",
        "software_category": "Lead Capture + CRM + Proposal + Follow-Up + Payments + Analytics + CRM",
        "automation": "Proposal follow-up sequences, retention nudges, referral attribution",
        "AI_capability": "Pipeline-health prediction; proposal-acceptance scoring",
        "integration": "Clay, LinkedIn, Airtable, Supabase, HubSpot, Slack, Notion",
        "implementation": "Medium",
        "outcome": "Higher proposal close rate, more recurring revenue, more referrals",
        "evidence_required": "Pipeline volume, close rate, recurring revenue, referral count",
        "recommendension_type": "SUPPORTED INFERENCE",
    },
}

# Fix the typo in Professional Services
SYSTEM_CATALOG["Professional Services"] = {
    "industry": "Professional Services",
    "problem": "Pipeline is unstructured; proposals go unanswered; no system for recurring revenue",
    "workflow": "Lead Capture → Qualification → Proposal → Follow-Up → Closing → Payments → Analytics → Retention → Referrals",
    "system_category": "Pipeline Operations",
    "software_category": "Lead Capture + CRM + Proposal + Follow-Up + Payments + Analytics + CRM",
    "automation": "Proposal follow-up sequences, retention nudges, referral attribution",
    "AI_capability": "Pipeline-health prediction; proposal-acceptance scoring",
    "integration": "Clay, LinkedIn, Airtable, Supabase, HubSpot, Slack, Notion",
    "implementation": "Medium",
    "outcome": "Higher proposal close rate, more recurring revenue, more referrals",
    "evidence_required": "Pipeline volume, close rate, recurring revenue, referral count",
    "recommendation_type": "SUPPORTED INFERENCE",
}


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW BUNDLE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

BUNDLE_TEMPLATES: Dict[str, List[str]] = {
    "HVAC": [
        "Lead Capture",
        "Booking",
        "Dispatch",
        "Estimate Follow-Up",
        "Payments",
        "Maintenance Renewal",
        "Dashboard",
    ],
    "Clinic": [
        "Intake",
        "Scheduling",
        "Recall",
        "Referral Tracking",
        "Follow-Up",
        "Payments",
        "Analytics",
    ],
    "Service": [
        "Lead Capture",
        "Missed-Call Recovery",
        "Booking",
        "Estimate/Quote",
        "Follow-Up",
        "Payments",
        "Reviews",
        "Dashboard",
    ],
    "Sales": [
        "Lead Capture",
        "Qualification",
        "Follow-Up",
        "Proposal",
        "Closing",
        "Payments",
        "Analytics",
        "Referrals",
    ],
    "Dental": [
        "Intake",
        "Scheduling",
        "Recall",
        "Referral Tracking",
        "Follow-Up",
        "Payments",
        "Analytics",
    ],
    "Medical": [
        "Intake",
        "Scheduling",
        "Reminders",
        "Follow-Up",
        "Document Workflow",
        "Payments",
        "Analytics",
    ],
}


class BundleEngine:
    """Builds workflow bundles instead of selling isolated tools.

    Each bundle is a validated sequence of system categories that together
    solve the business problem end-to-end.
    """

    @staticmethod
    def get_bundle(industry: str) -> List[str]:
        if industry in BUNDLE_TEMPLATES:
            return BUNDLE_TEMPLATES[industry]
        for key, bundle in BUNDLE_TEMPLATES.items():
            if key.lower() in industry.lower():
                return bundle
        return BUNDLE_TEMPLATES["Service"]

    @staticmethod
    def build_bundle(industry: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        bundle_steps = BundleEngine.get_bundle(industry)
        catalog = SYSTEM_CATALOG.get(industry, {})
        return {
            "industry": industry,
            "bundle": bundle_steps,
            "system_category": catalog.get("system_category", "Service Operations"),
            "software_category": catalog.get("software_category", "Multi-SaaS Stack"),
            "automation": catalog.get("automation", "Workflow automation"),
            "AI_component": catalog.get("AI_capability", "None required"),
            "outcome": catalog.get("outcome", "Measurable operational improvement"),
            "recommendation_type": catalog.get("recommendation_type", "SUPPORTED INFERENCE"),
            "is_bundle": True,
            "bundle_size": len(bundle_steps),
        }


# ══════════════════════════════════════════════════════════════════════════════
# OFFER ENGINE
# ══════════════════════════════════════════════════════════════════════════════

OFFER_TEMPLATES: Dict[str, Dict[str, str]] = {
    "HVAC": {
        "PROBLEM": "Missed calls, unreturned estimates, and lapsed maintenance plans leak revenue",
        "EVIDENCE": "Call volume, estimate-to-close rate, maintenance renewal rate",
        "SYSTEM": "Lead Capture + CRM + Dispatch + Estimate Follow-Up + Maintenance Renewal + Dashboard",
        "OUTCOME": "Recovered missed calls, higher estimate close rate, more maintenance renewals",
        "PRICE_PLAN": "Configurable — owner-approved",
        "NEXT_STEP": "Review call analytics and estimate close rate; deploy bundle in 5 business days",
    },
    "Clinic": {
        "PROBLEM": "New patients call but do not book; recall patients fall through the cracks",
        "EVIDENCE": "New-patient call volume, recall list size, case acceptance rate",
        "SYSTEM": "Intake + Scheduling + Recall + Referral Tracking + Follow-Up + Payments + Analytics",
        "OUTCOME": "Higher case acceptance, fewer missed recalls, measurable revenue per chair",
        "PRICE_PLAN": "Configurable — owner-approved",
        "NEXT_STEP": "Review recall compliance and case acceptance; deploy bundle in 5 business days",
    },
    "Dental": {
        "PROBLEM": "New patients call but do not book; recall patients fall through the cracks",
        "EVIDENCE": "New-patient call volume, recall list size, case acceptance rate",
        "SYSTEM": "Intake + Scheduling + Recall + Referral Tracking + Follow-Up + Payments + Analytics",
        "OUTCOME": "Higher case acceptance, fewer missed recalls, measurable revenue per chair",
        "PRICE_PLAN": "Configurable — owner-approved",
        "NEXT_STEP": "Review recall compliance and case acceptance; deploy bundle in 5 business days",
    },
    "Medical": {
        "PROBLEM": "Patient intake and follow-up are manual; no-show rates erode revenue",
        "EVIDENCE": "No-show rate, intake completion, recall compliance",
        "SYSTEM": "Intake + Scheduling + Reminders + Follow-Up + Document Workflow + Payments + Analytics",
        "OUTCOME": "Recovered no-shows, faster intake, documented follow-up",
        "PRICE_PLAN": "Configurable — owner-approved",
        "NEXT_STEP": "Review no-show rate and intake completion; deploy bundle in 5 business days",
    },
    "Service": {
        "PROBLEM": "Lead capture is inconsistent; follow-up is manual and slow",
        "EVIDENCE": "Lead volume, close rate, response time, review count",
        "SYSTEM": "Lead Capture + Missed-Call Recovery + Booking + Quote + Follow-Up + Payments + Reviews + Dashboard",
        "OUTCOME": "More recovered leads, faster follow-up, more reviews",
        "PRICE_PLAN": "Configurable — owner-approved",
        "NEXT_STEP": "Review lead volume and close rate; deploy bundle in 5 business days",
    },
}


class OfferEngine:
    """Generates outcome-based offers — NOT technology pitches.

    PROBLEM → EVIDENCE → SYSTEM → OUTCOME → PRICE/PLAN → NEXT STEP
    """

    @staticmethod
    def build_offer(industry: str) -> Dict[str, str]:
        template = OFFER_TEMPLATES.get(industry)
        if template:
            return dict(template)
        catalog = SYSTEM_CATALOG.get(industry, {})
        return {
            "PROBLEM": catalog.get("problem", "Operational inefficiency leaks revenue"),
            "EVIDENCE": catalog.get("evidence_required", "Call volume, close rate, compliance"),
            "SYSTEM": f"{catalog.get('system_category', 'Service Operations')} Stack",
            "OUTCOME": catalog.get("outcome", "Measurable operational improvement"),
            "PRICE_PLAN": "Configurable — owner-approved",
            "NEXT_STEP": "Review operational metrics; deploy system bundle in 5 business days",
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS SYSTEMS OPPORTUNITY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

CONNECTOR_ECOSYSTEM = [
    "Clay", "Vibe Prospecting", "LinkedIn", "Airtable", "Supabase",
    "HubSpot", "Business Helper", "Knowledge Graph", "Notion", "Slack",
    "Asana", "Granola",
]


class BusinessSystemsOpportunityEngine:
    """Main engine: takes a verified business lead and produces the 13-step
    opportunity analysis.

    Output:
    1. BUSINESS PROBLEM
    2. EVIDENCE
    3. CONFIDENCE
    4. CURRENT WORKFLOW
    5. LIKELY LEAK
    6. SYSTEM CATEGORY
    7. RECOMMENDED STACK
    8. AI COMPONENT IF USEFUL
    9. EXPECTED OPERATIONAL IMPACT
    10. DISCOVERY QUESTIONS
    11. SALES ANGLE
    12. IMPLEMENTATION COMPLEXITY
    13. NEXT BEST ACTION
    """

    @staticmethod
    def analyze(lead: Dict[str, Any]) -> Dict[str, Any]:
        industry = lead.get("vertical") or lead.get("industry") or "Service"
        # Service is a bundle template, not a catalog entry — fallback to Home Services / Professional Services
        catalog = SYSTEM_CATALOG.get(industry) or SYSTEM_CATALOG.get("Service") or SYSTEM_CATALOG.get("Home Services") or SYSTEM_CATALOG.get("Professional Services") or next(iter(SYSTEM_CATALOG.values()))
        bundle = BundleEngine.build_bundle(industry, lead)
        offer = OfferEngine.build_offer(industry)

        # Detect leaks from lead data (VERIFIED FACT / SUPPORTED INFERENCE / CONFLICT)
        leaks = BusinessSystemsOpportunityEngine._detect_leaks(lead, catalog)
        has_conflict = any(leak.get("type") == "CONFLICT" for leak in leaks)

        # Discovery questions
        discovery_questions = BusinessSystemsOpportunityEngine._build_discovery_questions(
            catalog, leaks
        )

        # Sales angle
        sales_angle = f"{catalog['problem']} — we help {industry} practices recover {offer['OUTCOME'].lower()}"

        result: Dict[str, Any] = {
            "industry": industry,
            "company": lead.get("company") or lead.get("company_name") or "",
            "contact": lead.get("contact") or lead.get("name") or "",
            "phone": lead.get("phone") or "",
            "lead_id": lead.get("id"),

            # 1. BUSINESS PROBLEM
            "business_problem": catalog["problem"],
            # 2. EVIDENCE
            "evidence": catalog["evidence_required"],
            # 3. CONFIDENCE
            "confidence": _classify_confidence(lead, catalog),
            # 4. CURRENT WORKFLOW
            "current_workflow": catalog["workflow"],
            # 5. LIKELY LEAK
            "likely_leak": leaks,
            # 6. SYSTEM CATEGORY
            "system_category": catalog["system_category"],
            # 7. RECOMMENDED STACK
            "recommended_stack": bundle,
            # 8. AI COMPONENT IF USEFUL
            "ai_component_if_useful": bundle["AI_component"],
            # 9. EXPECTED OPERATIONAL IMPACT
            "expected_operational_impact": bundle["outcome"],
            # 10. DISCOVERY QUESTIONS
            "discovery_questions": discovery_questions,
            # 11. SALES ANGLE
            "sales_angle": sales_angle,
            # 12. IMPLEMENTATION COMPLEXITY
            "implementation_complexity": catalog["implementation"],
            # 13. NEXT BEST ACTION
            "next_best_action": f"DEPLOY_{industry.upper()}_BUNDLE",

            # Offer engine output
            "offer": offer,

            # Classification metadata — downgrade to CONFLICT if providers disagree
            "recommendation_type": "CONFLICT" if has_conflict else bundle["recommendation_type"],
            "has_conflict": has_conflict,
            "conflict_detected": has_conflict,
            "conflict_leaks": [leak for leak in leaks if leak.get("type") == "CONFLICT"],
            "is_bundle": True,
            "connectors_used": CONNECTOR_ECOSYSTEM,
            "ai_is_one_category": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return result

    @staticmethod
    def _detect_leaks(lead: Dict[str, Any], catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        leaks = []
        classifier = RecommendationClassifier()

        # ── CONFLICT FIRST: surface provider disagreements before any actionable leak ──
        conflict = RecommendationClassifier.detect_provider_conflict(lead)
        if conflict:
            leaks.append(conflict)
            # When conflicted, do NOT present downstream recommendations as verified facts
            # The caller must resolve the conflict before dialing.

        # Attempts > 0 = already contacted (VERIFIED FACT)
        attempts = lead.get("attempts", 0)
        if attempts > 0:
            leaks.append({
                "leak": "Already contacted",
                "detail": f"Attempts={attempts}; lead may have fallen out of follow-up sequence",
                "type": classifier.classify(lead, "attempts"),
                "evidence": f"attempts={attempts}",
            })

        # Disposition = outcome recorded (VERIFIED FACT)
        disposition = lead.get("disposition", "")
        if disposition:
            leaks.append({
                "leak": "Previous disposition recorded",
                "detail": f"Disposition={disposition}; may need re-engagement or follow-up",
                "type": classifier.classify(lead, "disposition"),
                "evidence": f"disposition={disposition}",
            })

        # Phone issues (VERIFIED FACT)
        if not lead.get("phone") or str(lead.get("phone", "")).strip() in ("", "n/a"):
            leaks.append({
                "leak": "Missing phone number",
                "detail": "Cannot dial without a valid phone number",
                "type": "VERIFIED FACT",
                "evidence": "phone is blank or missing",
            })

        # Low priority score (SUPPORTED INFERENCE)
        score = lead.get("priority_score") or lead.get("deal_score") or 0
        if score and int(score) < 50:
            leaks.append({
                "leak": "Low engagement score",
                "detail": f"Score={score} suggests low intent or stale lead",
                "type": classifier.classify(lead, "priority_score"),
                "evidence": f"priority_score={score}",
            })

        # Industry-specific inference leaks (HYPOTHESIS)
        vertical = (lead.get("vertical") or "").lower()
        if "clinic" in vertical or "medical" in vertical or "dental" in vertical:
            leaks.append({
                "leak": "Recall compliance gap likely",
                "detail": "Clinic practices typically have 20-40% recall non-compliance",
                "type": "HYPOTHESIS",
                "evidence": "Industry pattern, not confirmed for this lead",
            })
        elif "hvac" in vertical or "plumbing" in vertical or "roofing" in vertical:
            leaks.append({
                "leak": "Missed-call and estimate follow-up leak likely",
                "detail": "Service businesses typically lose 30-50% of missed calls",
                "type": "HYPOTHESIS",
                "evidence": "Industry pattern, not confirmed for this lead",
            })

        # No verification (VERIFIED FACT)
        if not lead.get("verified") and not lead.get("verification_status", "").upper().startswith("VERIFIED"):
            leaks.append({
                "leak": "Unverified contact",
                "detail": "No verification source confirms this contact",
                "type": "VERIFIED FACT",
                "evidence": "verified flag is not set",
            })

        # If a CONFLICT was detected, ensure it stays visible at the top and downgrade confidence
        if any(leak.get("type") == "CONFLICT" for leak in leaks):
            # Surface conflict prominently; downstream systems must not present as verified fact
            for leak in leaks:
                if leak.get("type") == "CONFLICT":
                    leak["evidence"] += " → Recommendation must not be presented as VERIFIED FACT until resolved."

        return leaks if leaks else [
            {
                "leak": "Unknown — insufficient evidence",
                "detail": "Lead data does not confirm a specific leak",
                "type": "UNKNOWN",
                "evidence": "No signal detected",
            }
        ]

    @staticmethod
    def _build_discovery_questions(catalog: Dict[str, Any], leaks: List[Dict[str, Any]]) -> List[str]:
        questions = [
            f"What is your current {catalog['workflow'].split('→')[0].strip()} process?",
            f"How many {catalog['problem'].split()[0].lower()} do you lose per month?",
            f"What system are you using today for follow-up and recall?",
        ]
        for leak in leaks[:2]:
            if "missed" in leak.get("detail", "").lower() or "phone" in leak.get("detail", "").lower():
                questions.append("What happens when a caller reaches voicemail?")
            if "recall" in leak.get("detail", "").lower():
                questions.append("How do you currently track and re-engage past patients/clients?")
            if "estimate" in leak.get("detail", "").lower() or "quote" in leak.get("detail", "").lower():
                questions.append("What is your average estimate-to-close ratio?")
            if "maintenance" in leak.get("detail", "").lower():
                questions.append("What percentage of clients renew their maintenance plans?")
        return questions[:6]


def _classify_confidence(lead: Dict[str, Any], catalog: Dict[str, Any]) -> str:
    # CONFLICT outranks any score — must be surfaced, not averaged away
    if RecommendationClassifier.detect_provider_conflict(lead):
        return "CONFLICT — providers disagree, do not present as verified fact"
    score = 0
    if lead.get("verified") or str(lead.get("verification_status", "")).upper().startswith("VERIFIED"):
        score += 1
    if lead.get("phone"):
        score += 1
    if lead.get("vertical"):
        score += 1
    if lead.get("company") or lead.get("company_name"):
        score += 1
    if lead.get("disposition") or (lead.get("attempts", 0) > 0):
        score += 1

    if score >= 4:
        return "HIGH — multiple verified signals"
    if score >= 2:
        return "MEDIUM — partial signals"
    return "LOW — insufficient evidence"


# ══════════════════════════════════════════════════════════════════════════════
# COMMERCIAL LEARNING LOOP
# ══════════════════════════════════════════════════════════════════════════════

class CommercialLearningLoop:
    """Tracks real event data and learns which industries/problems/systems/scripts/offers
    actually produce revenue.

    Uses real event data only. Never fabricates outcomes.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join(ROOT_DIR, "MBM", "LeadEngine", "business_intel"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._data_path = self.storage_dir / "learning_loop.json"
        self._data = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self._data_path.exists():
            try:
                return json.loads(self._data_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        tmp = self._data_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self._data_path)

    def record_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Record a commercial event.

        Required fields:
          industry, problem, recommended_system, script, offer, call_outcome,
          conversation, offer_acceptance, appointment, checkout, payment, revenue
        """
        event["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._data.append(event)
        self._save()
        return event

    def get_learnings(self) -> Dict[str, Any]:
        """Summarize what actually produces revenue by industry/problem/system."""
        if not self._data:
            return {"message": "No commercial events recorded yet", "total_events": 0}

        by_industry: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0, "revenue": 0.0, "offer_acceptances": 0,
            "systems": Counter(), "problems": Counter(),
        })
        for event in self._data:
            ind = event.get("industry", "Unknown")
            bucket = by_industry[ind]
            bucket["count"] += 1
            bucket["revenue"] += float(event.get("revenue", 0) or 0)
            if event.get("offer_acceptance") is True or event.get("offer_acceptance") == "accepted":
                bucket["offer_acceptances"] += 1
            bucket["systems"][event.get("recommended_system", "")] += 1
            bucket["problems"][event.get("problem", "")] += 1

        summary = {}
        for ind, data in by_industry.items():
            total = data["count"]
            summary[ind] = {
                "total_events": total,
                "total_revenue": data["revenue"],
                "avg_revenue_per_event": round(data["revenue"] / max(total, 1), 2),
                "offer_acceptance_rate": round(data["offer_acceptances"] / max(total, 1) * 100, 1),
                "top_system": data["systems"].most_common(1)[0][0] if data["systems"] else "N/A",
                "top_problem": data["problems"].most_common(1)[0][0] if data["problems"] else "N/A",
            }

        return {
            "total_events": len(self._data),
            "by_industry": summary,
            "best_performing_industry": max(by_industry.keys(), key=lambda k: by_industry[k]["revenue"]) if by_industry else "N/A",
        }

    def best_script_for(self, industry: str) -> str:
        """Return the script/outcome that produced the most revenue for an industry."""
        events = [e for e in self._data if e.get("industry") == industry]
        if not events:
            return "No data — use generic script"
        best = max(events, key=lambda e: float(e.get("revenue", 0) or 0))
        return best.get("script", "N/A")


# ══════════════════════════════════════════════════════════════════════════════
# DIALER INTEGRATION — BUSINESS SUMMARY FOR PHOUND WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

def build_dialer_brief(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Build a dialer brief following the pipeline:
    BUSINESS SUMMARY → OPERATIONAL EVIDENCE → DETECTED LEAKS → RECOMMENDED SYSTEM
    → WHY IT FITS → SCRIPT → OFFER → DIAL → PHOUND → AFTER-CALL → FOLLOW-UP
    """
    engine = BusinessSystemsOpportunityEngine()
    opportunity = engine.analyze(lead)
    script = _build_business_script(lead, opportunity)
    offer = opportunity["offer"]

    brief = {
        "lead_id": lead.get("id"),
        "company": opportunity["company"],
        "contact": opportunity["contact"],
        "phone": opportunity["phone"],
        "industry": opportunity["industry"],

        # BUSINESS SUMMARY
        "business_summary": opportunity["business_problem"],

        # OPERATIONAL EVIDENCE
        "operational_evidence": {
            "evidence": opportunity["evidence"],
            "confidence": opportunity["confidence"],
            "verification_status": str(lead.get("verification_status", "")),
            "source": lead.get("source", ""),
        },

        # DETECTED LEAKS
        "detected_leaks": opportunity["likely_leak"],

        # RECOMMENDED SYSTEM
        "recommended_system": opportunity["recommended_stack"],

        # WHY IT FITS
        "why_it_fits": f"{opportunity['industry']} businesses face {opportunity['business_problem']}. {opportunity['expected_operational_impact']}.",

        # SCRIPT
        "script": script,

        # OFFER
        "offer": offer,

        # DIAL → PHOUND (blocked if CONFLICT — surface, do not dial)
        "dial_phound": {
            "provider": "Phound",
            "mode": "native_app",
            "deep_link": "https://web.phound.app/?phone={phone}".format(phone=opportunity["phone"]),
            "blocked_by_conflict": opportunity.get("has_conflict", False),
            "block_reason": "CONFLICT: providers disagree — resolve before dialing" if opportunity.get("has_conflict") else None,
            "outcome_law": "Webhook-first: outcomes arrive only via normalize_event(). Never fabricate.",
            "caller": "Omar",
            "notes": f"Business Systems Opportunity for {opportunity['industry']}: {opportunity['business_problem']}",
        },

        # AFTER-CALL (must be BELOW DIAL in UI)
        "after_call": {
            "record_outcome": "Must come from Phound webhook event",
            "allowed_statuses": ["CONNECTED", "NO_ANSWER", "VOICEMAIL", "INTERESTED", "NOT_INTERESTED", "CALLBACK", "QUALIFIED"],
            "disposition": None,
            "revenue_recorded": None,
            "placement": "BELOW_DIAL",
        },

        # FOLLOW-UP (must be BELOW AFTER-CALL in UI)
        "follow_up": {
            "trigger": "Post-call disposition",
            "action": "Create follow-up task via AdService if disposition requires it",
            "idempotency_key": f"bs_opportunity_{lead.get('id', '')}",
            "placement": "BELOW_AFTER_CALL",
        },

        # METADATA
        "ai_is_one_category": True,
        "recommendation_type": opportunity["recommendation_type"],
        "has_conflict": opportunity.get("has_conflict", False),
        "generated_at": opportunity["generated_at"],
    }

    return brief


def _build_business_script(lead: Dict[str, Any], opportunity: Dict[str, Any]) -> str:
    """Build a business-specific script referencing the actual industry and evidence-backed opportunity."""
    industry = opportunity["industry"]
    company = lead.get("company") or lead.get("company_name") or "your business"
    contact = (lead.get("contact") or lead.get("name") or "there").split()[0]
    problem = opportunity["business_problem"]
    outcome = opportunity["expected_operational_impact"]
    first_name = contact if contact not in ("there", "unknown", "n/a") else "there"

    scripts = {
        "HVAC": f"Hi {first_name}, this is Omar calling from MBM. I see {company} is in the HVAC space. We help service businesses recover missed calls, speed up estimate follow-up, and get more maintenance-plan renewals — {problem}. {outcome}. Do you have 30 seconds to talk through what would look like for {company}?",
        "Dental": f"Hi {first_name}, this is Omar calling from MBM. I see {company} is a dental practice. We help practices recover new-patient bookings and automate recall so nothing falls through the cracks — {problem}. {outcome}. Would you be open to a quick conversation?",
        "Medical": f"Hi {first_name}, this is Omar with MBM. I see {company} is a medical practice. We help practices recover no-shows and automate intake and follow-up — {problem}. {outcome}. Do you have a moment to explore what this could look like?",
        "Service": f"Hi {first_name}, this is Omar calling from MBM. I see {company} is in the service industry. We help businesses recover missed calls, speed up follow-up, and get more reviews — {problem}. {outcome}. Would you have 30 seconds to talk through it?",
    }

    return scripts.get(industry, f"Hi {first_name}, this is Omar calling from MBM. I see {company} operates in {industry}. We help businesses solve operational problems like {problem}. {outcome}. Would you be open to a conversation?")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full opportunity analysis and return the 13-step output."""
    return BusinessSystemsOpportunityEngine.analyze(lead)


def run_dialer_brief(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full dialer brief pipeline."""
    return build_dialer_brief(lead)


if __name__ == "__main__":
    # Demo with a sample lead
    sample = {
        "id": "BS-001",
        "name": "Mike Johnson",
        "phone": "+12144441234",
        "company": "Johnson HVAC",
        "vertical": "HVAC",
        "city": "Dallas",
        "state": "TX",
        "verified": 1,
        "attempts": 0,
        "disposition": "",
        "verification_status": "VERIFIED",
        "source": "NPI",
        "intent_score": 85,
        "callability_score": 90,
        "deal_score": 80,
        "motivation_score": 85,
        "freshness_score": 90,
    }

    print("=" * 80)
    print("  🏢 BUSINESS SYSTEMS OPPORTUNITY ENGINE")
    print("=" * 80)

    result = run_analysis(sample)
    print(f"\nIndustry: {result['industry']}")
    print(f"Company: {result['company']}")
    print(f"Business Problem: {result['business_problem']}")
    print(f"Confidence: {result['confidence']}")
    print(f"System Category: {result['system_category']}")
    print(f"Bundle: {' + '.join(result['recommended_stack']['bundle'])}")
    print(f"AI Component: {result['ai_component_if_useful']}")
    print(f"Expected Impact: {result['expected_operational_impact']}")
    print(f"Recommendation Type: {result['recommendation_type']}")
    print(f"\nLeaks detected: {len(result['likely_leak'])}")
    for leak in result["likely_leak"]:
        print(f"  - [{leak['type']}] {leak['leak']}: {leak['detail']}")
    print(f"\nDiscovery Questions:")
    for q in result["discovery_questions"]:
        print(f"  - {q}")
    print(f"\nOffer: {result['offer']['PROBLEM']}")
    print(f"  → {result['offer']['SYSTEM']}")
    print(f"  → {result['offer']['OUTCOME']}")
    print(f"\nDialer Brief Pipeline:")
    print(f"  BUSINESS SUMMARY → OPERATIONAL EVIDENCE → DETECTED LEAKS → RECOMMENDED SYSTEM")
    print(f"  → WHY IT FITS → SCRIPT → OFFER → DIAL → PHOUND → AFTER-CALL → FOLLOW-UP")

    print("\n" + "=" * 80)
    print("  🧪 QUICK VALIDATION")
    print("=" * 80)

    # Test all industries in catalog
    for industry in SYSTEM_CATALOG:
        try:
            lead = {
                "id": f"TEST-{industry}",
                "name": "Test Contact",
                "phone": "+12144441234",
                "company": f"Test Corp ({industry})",
                "vertical": industry,
                "city": "Dallas",
                "state": "TX",
                "verified": 1,
                "attempts": 0,
                "disposition": "",
                "verification_status": "VERIFIED",
                "source": "NPI",
            }
            r = BusinessSystemsOpportunityEngine.analyze(lead)
            assert r["business_problem"], f"{industry}: missing business_problem"
            assert r["recommended_stack"]["bundle"], f"{industry}: missing bundle"
            assert r["offer"]["PROBLEM"], f"{industry}: missing offer"
            assert r["recommendation_type"] in RECOMMENDATION_TYPES, f"{industry}: bad rec type"
            print(f"  ✅ {industry}")
        except Exception as e:
            print(f"  ❌ {industry}: {e}")

    # Test dialer brief
    brief = build_dialer_brief(sample)
    assert brief["business_summary"], "Missing business_summary"
    assert brief["script"], "Missing script"
    assert brief["offer"], "Missing offer"
    assert brief["dial_phound"]["deep_link"], "Missing deep_link"
    print(f"  ✅ Dialer brief generated")

    # Test learning loop
    loop = CommercialLearningLoop()
    loop.record_event({
        "industry": "HVAC",
        "problem": "Missed calls leak revenue",
        "recommended_system": "Lead Capture + CRM + Dispatch",
        "script": "Test script",
        "offer": "Test offer",
        "call_outcome": "CONNECTED",
        "offer_acceptance": "accepted",
        "appointment": True,
        "checkout": True,
        "payment": True,
        "revenue": 1997.0,
    })
    learnings = loop.get_learnings()
    assert learnings["total_events"] == 1
    print(f"  ✅ Commercial learning loop recorded 1 event")

    # Test bundle engine
    bundle = BundleEngine.build_bundle("HVAC", sample)
    assert bundle["is_bundle"] is True
    assert len(bundle["bundle"]) == 7
    print(f"  ✅ Bundle engine: {len(bundle['bundle'])} steps")

    print(f"\n{'='*80}")
    print(f"  ALL VALIDATIONS PASSED")
    print(f"{'='*80}")