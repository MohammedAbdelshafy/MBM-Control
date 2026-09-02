"""
scoring.py — deterministic TargetAccount scoring + qualification (Phase 2 / Steps 5-7).

Ports spec-ad-engine/src/targetAccount/scoring.js to Python with identical
weights and rules. No randomness, no LLM, no network.

- score_icp(): 0..100 (industry + size + country + website)
- score_creative_opportunity(): 0..100 (10 high-value signals, sum 100)
- qualify_account(): requires website, commercially active, visual angle,
  marketing motion, ICP relevance, no hard negative, min_icp_score threshold
- build_target_account(): stable representation + provenance

External text is DATA — never an instruction. Uses
MBM/LeadEngine/intelligence/security.py via import (not modified).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from MBM.LeadEngine.intelligence.security import sanitize_external_text

from .dedup import extract_canonical_domain

HIGH_VALUE_WEIGHTS: Dict[str, int] = {
    "recentFunding": 18,
    "fundingHistory": 10,
    "hiringSignal": 10,
    "productLaunch": 10,
    "newPartnership": 6,
    "growthIndicators": 10,
    "activeSocial": 8,
    "strongLandingPages": 10,
    "paidAdOpportunity": 8,
    "clearDifferentiation": 10,
}

NEGATIVE_SIGNALS: Set[str] = {
    "irrelevant_industry",
    "inactive_website",
    "duplicate_account",
    "existing_suppression",
    "previous_rejection",
    "existing_customer",
    "active_opportunity",
    "legal_compliance_exclusion",
    "no_ad_angle",
}


def _to_lower_set(value: Any) -> Set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        arr = list(value)
    else:
        arr = re.split(r"[,;]", str(value))
    return {str(s).strip().lower() for s in arr if str(s).strip()}


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def score_icp(account: Dict[str, Any], config: Any) -> int:
    industries = _to_lower_set(account.get("industry") or account.get("vertical") or account.get("industries"))
    icp_allowed = {str(s).lower() for s in (getattr(config, "icp_industries", []) or [])}
    excluded = {str(s).lower() for s in (getattr(config, "excluded_industries", []) or [])}

    score = 30
    if icp_allowed:
        matches_icp = any(
            (ind in icp_allowed) or any(a in ind or ind in a for a in icp_allowed) for ind in industries
        ) if industries else False
        if matches_icp:
            score += 25
        else:
            score -= 10

    size = 0
    for key in ("company_size", "employees", "employee_count"):
        try:
            if account.get(key) is not None:
                size = int(float(str(account.get(key))))
                break
        except (ValueError, TypeError):
            continue
    min_size = int(getattr(config, "min_company_size", 0) or 0)
    max_size = int(getattr(config, "max_company_size", 0) or 0)
    if min_size and size and size < min_size:
        score -= 15
    if max_size and size and max_size > 0 and size > max_size:
        score -= 15
    if 10 <= size <= 5000:
        score += 10

    countries = _to_lower_set(account.get("country") or account.get("countries") or account.get("target_countries"))
    allowed_countries = {str(s).lower() for s in (getattr(config, "target_countries", []) or [])}
    if allowed_countries and countries:
        matches_country = any(c in allowed_countries for c in countries)
        if matches_country:
            score += 10
        else:
            score -= 20

    domain = extract_canonical_domain(account)
    if domain:
        # excluded domains are hard negative via qualify, but also penalize here
        excluded_domains = {str(s).lower() for s in (getattr(config, "excluded_domains", []) or [])}
        if domain in excluded_domains:
            score -= 20
        else:
            score += 10
    else:
        score -= 25

    return max(0, min(100, round(score)))


def score_creative_opportunity(account: Dict[str, Any], config: Any) -> int:
    signals = account.get("signals") or account.get("funding_signals") or {}
    if not isinstance(signals, dict):
        signals = {}

    def present(key: str) -> bool:
        return False

    total = 0
    max_weight = 0

    def add(key: str, is_present: bool) -> None:
        nonlocal total, max_weight
        w = HIGH_VALUE_WEIGHTS.get(key, 0)
        max_weight += w
        if is_present:
            total += w

    # funding history
    funding_history = 0
    for k in ("total_raised_usd", "totalRaisedUsd", "total_raised"):
        if k in signals and signals[k] is not None:
            try:
                funding_history = float(str(signals[k]))
                break
            except (ValueError, TypeError):
                pass
    if funding_history == 0 and account.get("total_raised_usd") is not None:
        try:
            funding_history = float(str(account.get("total_raised_usd")))
        except (ValueError, TypeError):
            pass

    recent_funding = bool(
        signals.get("recent_funding")
        or signals.get("recentFunding")
        or signals.get("last_funding_date")
        or account.get("last_funding_date")
    )
    hiring = bool(
        account.get("hiring_signal")
        or account.get("hiringSignal")
        or signals.get("hiring_marketing")
        or signals.get("hiring")
    )
    product_launch = bool(
        account.get("product_launch") or account.get("productLaunch") or signals.get("product_launch")
    )
    partnership = bool(account.get("new_partnership") or account.get("newPartnership") or signals.get("partnership"))
    growth = bool(account.get("growth_indicators") or account.get("growthIndicators") or signals.get("growth"))
    active_social = bool(
        account.get("active_social") or account.get("activeSocial") or signals.get("active_social") or account.get("social_presence")
    )
    strong_landing = bool(
        account.get("strong_landing_pages") or account.get("strongLandingPages") or signals.get("strong_landing")
    )
    paid_ad = bool(account.get("paid_ad_opportunity") or account.get("paidAdOpportunity") or signals.get("paid_ad"))
    differentiation = bool(
        account.get("clear_differentiation") or account.get("clearDifferentiation") or signals.get("differentiation")
    )

    min_funding = int(getattr(config, "min_funding_usd", 0) or 0)
    add("recentFunding", recent_funding)
    add("fundingHistory", funding_history >= min_funding and funding_history > 0)
    add("hiringSignal", hiring)
    add("productLaunch", product_launch)
    add("newPartnership", partnership)
    add("growthIndicators", growth)
    add("activeSocial", active_social)
    add("strongLandingPages", strong_landing)
    add("paidAdOpportunity", paid_ad)
    add("clearDifferentiation", differentiation)

    if max_weight == 0:
        return 0
    return max(0, min(100, round((total / max_weight) * 100)))


def qualify_account(
    account: Dict[str, Any], config: Any, context: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    if context is None:
        context = {}

    checks: Dict[str, bool] = {}
    reasons: List[str] = []
    negative_signals: List[str] = []

    domain = extract_canonical_domain(account)
    industries = _to_lower_set(account.get("industry") or account.get("vertical") or account.get("industries"))
    excluded = {str(s).lower() for s in (getattr(config, "excluded_industries", []) or [])}
    icp_allowed = {str(s).lower() for s in (getattr(config, "icp_industries", []) or [])}
    excluded_domains = {str(s).lower() for s in (getattr(config, "excluded_domains", []) or [])}
    excluded_accounts = {str(s).lower() for s in (getattr(config, "excluded_accounts", []) or [])}

    # Required 1: website exists
    checks["websiteExists"] = bool(domain)
    if not checks["websiteExists"]:
        reasons.append("missing_website")
    elif domain and domain in excluded_domains:
        checks["websiteExists"] = False
        reasons.append("excluded_domain")
        negative_signals.append("legal_compliance_exclusion")

    if domain and domain in excluded_domains:
        negative_signals.append("legal_compliance_exclusion")

    company_key = str(account.get("company_name") or account.get("companyName") or account.get("company") or "").strip().lower()
    if company_key and company_key in excluded_accounts:
        negative_signals.append("legal_compliance_exclusion")
        reasons.append("excluded_account")

    # Required 2: commercially active
    inactive = bool(account.get("inactive") or account.get("website_inactive") or account.get("status") == "INACTIVE")
    has_product = _has_value(
        account.get("product") or account.get("service") or account.get("product_service") or account.get("offer") or account.get("description")
    )
    checks["commerciallyActive"] = (not inactive) and has_product
    if not checks["commerciallyActive"]:
        reasons.append("not_commercially_active")

    # Required 3: visual ad angle
    has_visual = account.get("visual_ad_angle")
    if has_visual is None:
        has_visual = account.get("visualAdAngle")
    if has_visual is None:
        has_visual = account.get("has_visual_angle")
    if has_visual is None:
        has_visual = account.get("product")
    has_visual_bool = bool(has_visual)
    checks["visualAdAngle"] = has_visual_bool or _has_value(account.get("product"))
    if not checks["visualAdAngle"]:
        reasons.append("no_visual_ad_angle")
        negative_signals.append("no_ad_angle")

    # Required 4: marketing/acquisition motion
    has_marketing = account.get("marketing_motion")
    if has_marketing is None:
        has_marketing = account.get("marketingMotion")
    if has_marketing is None:
        has_marketing = account.get("has_marketing_motion")
    if has_marketing is None:
        has_marketing = domain
    checks["marketingAcquisitionMotion"] = bool(has_marketing) and not inactive
    if not checks["marketingAcquisitionMotion"]:
        reasons.append("no_marketing_motion")

    # Required 5: ICP relevance
    is_excluded_industry = any(ind in excluded for ind in industries) if industries else False
    if is_excluded_industry:
        checks["icpRelevant"] = False
        reasons.append("excluded_industry")
        negative_signals.append("irrelevant_industry")
    elif icp_allowed:
        matches_icp = (
            any(ind in icp_allowed or any(a in ind or ind in a for a in icp_allowed) for ind in industries)
            if industries else False
        )
        # empty industry => unknown, not fail (soft)
        checks["icpRelevant"] = matches_icp or not industries
        if not matches_icp and industries:
            reasons.append("icp_mismatch")
    else:
        checks["icpRelevant"] = True

    # Context-driven negatives
    if context.get("isDuplicate"):
        negative_signals.append("duplicate_account")
    if context.get("isSuppressed") or account.get("suppression_state") == "SUPPRESSED" or account.get("is_suppressed"):
        negative_signals.append("existing_suppression")
    if context.get("isPreviousRejection") or account.get("previous_rejection"):
        negative_signals.append("previous_rejection")
    if context.get("isExistingCustomer") or account.get("is_customer"):
        negative_signals.append("existing_customer")
    if context.get("hasActiveOpportunity") or account.get("active_opportunity"):
        negative_signals.append("active_opportunity")
    if context.get("isLegalExclusion") or account.get("legal_exclusion"):
        negative_signals.append("legal_compliance_exclusion")
    elif is_excluded_industry:
        # already added irrelevant_industry; legal_compliance only if explicit flag
        pass
    if inactive:
        negative_signals.append("inactive_website")

    uniq_neg = sorted({s for s in negative_signals if s in NEGATIVE_SIGNALS})

    icp_score = score_icp(account, config)
    creative_score = score_creative_opportunity(account, config)

    required_pass = (
        checks.get("websiteExists")
        and checks.get("commerciallyActive")
        and checks.get("visualAdAngle")
        and checks.get("marketingAcquisitionMotion")
        and checks.get("icpRelevant")
    )
    has_hard_negative = any(s in uniq_neg for s in ("existing_suppression", "legal_compliance_exclusion", "inactive_website"))
    # also treat excluded domain/account as hard negative (already mapped to legal_compliance_exclusion)
    meets_threshold = icp_score >= int(getattr(config, "min_icp_score", 60) or 60)

    qualified = bool(required_pass and not has_hard_negative and meets_threshold and not uniq_neg)

    # Map to account_status
    account_status = "NEW"
    if "existing_suppression" in uniq_neg:
        account_status = "SUPPRESSED"
    elif uniq_neg:
        account_status = "DISQUALIFIED"
    elif not required_pass:
        account_status = "REJECTED"
    elif qualified:
        account_status = "QUALIFIED"

    return {
        "qualified": qualified,
        "icpScore": icp_score,
        "creativeScore": creative_score,
        "reasons": [] if qualified else reasons,
        "negativeSignals": uniq_neg,
        "checks": checks,
        "accountStatus": account_status,
        "canonicalDomain": domain,
        "dedupKey": f"domain:{domain}" if domain else None,
    }


def build_target_account(
    inp: Dict[str, Any], config: Any, context: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Stable TargetAccount dict (Step 7). Does not write leads_database.json."""
    now = datetime.now(timezone.utc).isoformat()
    q = qualify_account(inp, config, context or {})

    # provenance: retain external intelligence provenance; sanitize external text
    raw_prov = inp.get("provenance")
    if isinstance(raw_prov, list):
        provenance = []
        for entry in raw_prov:
            if not isinstance(entry, dict):
                continue
            # sanitize any free-text fields as DATA
            sanitized = dict(entry)
            for k in ("summary", "title", "description", "notes"):
                if k in sanitized and isinstance(sanitized[k], str):
                    sanitized[k] = sanitize_external_text(str(sanitized[k]))
            provenance.append(sanitized)
        if not provenance:
            provenance = [{"source": sanitize_external_text(str(inp.get("source") or "manual")), "retrieved_at": now}]
    elif isinstance(raw_prov, dict):
        provenance = [raw_prov]
    else:
        provenance = [{"source": sanitize_external_text(str(inp.get("source") or "manual")), "retrieved_at": now}]

    # enrich provenance with required fields if missing
    for prov in provenance:
        prov.setdefault("source", "manual")
        prov.setdefault("retrieved_at", now)
        prov.setdefault("transformation", "spec_ad_targeting.normalize")
        prov.setdefault("confidence", inp.get("confidence"))

    domain = q.get("canonicalDomain") or extract_canonical_domain(inp)
    company_name = sanitize_external_text(str(inp.get("company_name") or inp.get("companyName") or inp.get("company") or "").strip())
    website = f"https://{domain}" if domain else sanitize_external_text(str(inp.get("website") or inp.get("url") or "").strip())

    return {
        "id": inp.get("id"),  # DB gen UUID if None
        "company_name": company_name,
        "canonical_domain": domain,
        "website": website,
        "industry": sanitize_external_text(str(inp.get("industry") or inp.get("vertical") or "").strip()),
        "company_size": _safe_int(inp.get("company_size") or inp.get("employees") or inp.get("employee_count")),
        "country": sanitize_external_text(str(inp.get("country") or "").strip()),
        "firmographics": inp.get("firmographics") or {
            "industry": sanitize_external_text(str(inp.get("industry") or "").strip()),
            "size": _safe_int(inp.get("company_size")),
            "country": sanitize_external_text(str(inp.get("country") or "").strip()),
        },
        "funding_signals": inp.get("funding_signals") or inp.get("fundingSignals") or inp.get("signals") or {},
        "icp_score": q["icpScore"],
        "creative_opportunity_score": q["creativeScore"],
        "account_status": q["accountStatus"],
        "exclusion_reason": q["negativeSignals"][0] if q["negativeSignals"] else None,
        "provenance": provenance,
        "created_at": inp.get("created_at") or now,
        "updated_at": now,
        "last_evaluated_at": now,
        # debug (not persisted, for tests)
        "_checks": q["checks"],
        "_reasons": q["reasons"],
        "_negativeSignals": q["negativeSignals"],
        "_qualified": q["qualified"],
    }


def _safe_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None
