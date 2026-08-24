"""offer_recommendation_engine -- deterministic PRIMARY/SECONDARY/ENTRY/UPSELL
selection for the AI Consultancy catalog (MBM/Offers/ai_consultancy).

Pure rules over a prospect profile. No ML, no randomness: same input always
yields the same recommendation so outreach stays consistent and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProspectProfile:
    industry: str = ""                 # e.g. dental, hvac, real_estate, construction, law
    company_size: str = "smb"          # micro | smb | mid | enterprise
    services: list[str] = field(default_factory=list)
    pain_signals: list[str] = field(default_factory=list)   # e.g. missed_calls, slow_quotes
    lead_source: str = ""              # inbound | outbound | referral
    has_call_volume: bool = True
    uses_crm: bool = False
    documents_heavy: bool = False      # invoices/BOQ/contracts workload
    ecommerce: bool = False


@dataclass
class OfferRecommendation:
    primary_offer: str
    secondary_offer: str
    entry_offer: str
    upsell_path: list[str]
    rationale: str


_RULES: list[dict] = [
    {
        "match": lambda p: p.industry in ("dental", "medspa", "dermatology", "optometry",
                                          "chiropractic", "physical_therapy", "veterinary"),
        "primary": "AI_RECEPTIONIST_APPOINTMENT_RECOVERY",
        "secondary": "AI_MISSED_CALL_RECOVERY",
        "entry": "AI_MISSED_CALL_RECOVERY",
        "upsell": ["AI_LEAD_QUALIFICATION_ENGINE", "AI_CRM_AUTOMATION", "AI_PATIENT_FOLLOW_UP"],
        "why": "clinic phone-first intake; appointments are the revenue unit",
    },
    {
        "match": lambda p: p.industry in ("construction", "contractor", "roofing", "hvac",
                                          "plumbing", "electrical") or p.documents_heavy,
        "primary": "AI_ESTIMATING_QUOTING_DOCUMENT_PROCESSING",
        "secondary": "AI_DOCUMENT_PROCESSING",
        "entry": "AI_DOCUMENT_PROCESSING",
        "upsell": ["SUPPLIER_PRICE_INTELLIGENCE", "AI_OPERATIONS_COPILOT"],
        "why": "estimate/document bottleneck is the paid-hours sink; human approval retained",
    },
    {
        "match": lambda p: p.industry in ("real_estate", "wholesale", "property_management",
                                          "insurance"),
        "primary": "AI_LEAD_QUALIFICATION_ENGINE",
        "secondary": "AI_SALES_FOLLOW_UP_ENGINE",
        "entry": "AI_SALES_FOLLOW_UP_ENGINE",
        "upsell": ["AI_CRM_AUTOMATION", "AI_VOICE_SALES_AGENT"],
        "why": "lead decay between inquiry and follow-up is the dominant leak",
    },
    {
        "match": lambda p: p.ecommerce or p.industry in ("ecommerce", "retail"),
        "primary": "AI_CUSTOMER_SUPPORT",
        "secondary": "AI_CRM_AUTOMATION",
        "entry": "AI_CUSTOMER_SUPPORT_FAQ",
        "upsell": ["AI_OPERATIONS_COPILOT"],
        "why": "ticket volume scales with orders; FAQ deflection is measurable fast",
    },
    {
        "match": lambda p: p.industry in ("law", "accounting", "agency",
                                          "professional_services"),
        "primary": "AI_INTAKE_QUALIFICATION",
        "secondary": "AI_DOCUMENT_PROCESSING",
        "entry": "AI_MISSED_CALL_RECOVERY",
        "upsell": ["AI_CLIENT_FOLLOW_UP_ENGINE", "AI_OPERATIONS_COPILOT"],
        "why": "billable-time protection via structured intake and doc handling",
    },
]

DEFAULT_RULE = {
    "primary": "AI_MISSED_CALL_RECOVERY",
    "secondary": "AI_LEAD_QUALIFICATION_ENGINE",
    "entry": "AI_MISSED_CALL_RECOVERY",
    "upsell": ["AI_RECEPTIONIST", "AI_CRM_AUTOMATION"],
    "why": "universal entry point with fastest measurable baseline (missed-call log)",
}


def recommend(prospect: ProspectProfile) -> OfferRecommendation:
    industry = (prospect.industry or "").lower().strip()
    p = ProspectProfile(
        industry=industry, company_size=prospect.company_size,
        services=[s.lower() for s in prospect.services],
        pain_signals=[s.lower() for s in prospect.pain_signals],
        lead_source=prospect.lead_source, has_call_volume=prospect.has_call_volume,
        uses_crm=prospect.uses_crm, documents_heavy=prospect.documents_heavy,
        ecommerce=prospect.ecommerce,
    )
    for rule in _RULES:
        try:
            if rule["match"](p):
                return OfferRecommendation(rule["primary"], rule["secondary"], rule["entry"],
                                           list(rule["upsell"]), rule["why"])
        except Exception:
            continue
    return OfferRecommendation(DEFAULT_RULE["primary"], DEFAULT_RULE["secondary"],
                               DEFAULT_RULE["entry"], list(DEFAULT_RULE["upsell"]),
                               DEFAULT_RULE["why"])
