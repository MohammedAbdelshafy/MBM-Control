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
    fit_score: int = 50
    evidence: list[str] = field(default_factory=list)
    recommended_pitch: str = ""
    recommended_CTA: str = ""


_PITCH_CTA = {
    "AI_RECEPTIONIST_APPOINTMENT_RECOVERY": (
        "Your next missed call becomes a booked appointment instead.",
        "Call our demo line and try to stump it"),
    "AI_MISSED_CALL_RECOVERY": (
        "Every missed call gets a second chance in under a minute.",
        "Send last week's call log - we show what was lost"),
    "AI_ESTIMATING_QUOTING_DOCUMENT_PROCESSING": (
        "Draft estimates in hours; approvals stay yours.",
        "Pick 3 past projects for a blind comparison"),
    "AI_LEAD_QUALIFICATION_ENGINE": (
        "Work only the leads that deserve a callback.",
        "Send 20 recent leads - scored+reasoned in 48h"),
    "AI_INTAKE_QUALIFICATION": (
        "Structured intake that protects billable hours.",
        "We map your intake in one 30-minute call"),
    "AI_CUSTOMER_SUPPORT": (
        "Instant answers for the 80%, humans for the 20%.",
        "Share your top support questions"),
}


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
                rec = OfferRecommendation(
                    rule["primary"], rule["secondary"], rule["entry"],
                    list(rule["upsell"]), rule["why"],
                    fit_score=_fit_score(p, rule),
                    evidence=[f"industry={industry}",
                              *[f"pain_signal={s}" for s in p.pain_signals],
                              f"documents_heavy={p.documents_heavy}",
                              f"uses_crm={p.uses_crm}"],
                )
                pitch, cta = _PITCH_CTA.get(rule["primary"], ("", ""))
                rec.recommended_pitch = pitch
                rec.recommended_CTA = cta
                return rec
        except Exception:
            continue
    rec = OfferRecommendation(DEFAULT_RULE["primary"], DEFAULT_RULE["secondary"],
                              DEFAULT_RULE["entry"], list(DEFAULT_RULE["upsell"]),
                              DEFAULT_RULE["why"], fit_score=45,
                              evidence=[f"industry={industry or 'unknown'} -> default entry path"])
    rec.recommended_pitch, rec.recommended_CTA = _PITCH_CTA[DEFAULT_RULE["primary"]]
    return rec


def _fit_score(p: ProspectProfile, rule: dict) -> int:
    """Deterministic 0-100 fit. Base 55; +8 per reinforcing signal, capped."""
    score = 55
    if p.pain_signals:
        score += min(24, 8 * len(p.pain_signals))
    if p.industry in ("dental", "medspa", "construction", "real_estate", "law"):
        score += 9
    if rule is not _RULES[-1]:
        score += 6
    return max(0, min(100, score))
