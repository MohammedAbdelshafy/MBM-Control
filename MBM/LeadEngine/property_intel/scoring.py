"""scoring -- issue #23 property opportunity score + callability score.

Opportunity weights (baseline, sum 100, configurable):
  distress 25, equity 20, vacancy 15, ownership_profile 10, property_fit 10,
  recency 8, contact_confidence 7, market_liquidity 5.

Callability weights (separate, sum 100, configurable):
  contact_source 30, phone_quality 20, owner_match 20, recency 15,
  prior_success 10, negative_dispositions 5.

Every score exposes component values + a reason trace explaining WHY a lead
ranked where it did. Negative dispositions (BAD_NUMBER, WRONG_PERSON,
NON_OWNER) suppress callability so garbage is not recycled into the prime queue.
"""
from __future__ import annotations

import json
from typing import Any, Optional

PROPERTY_WEIGHTS: dict[str, int] = {
    "distress": 25,
    "equity": 20,
    "vacancy": 15,
    "ownership_profile": 10,
    "property_fit": 10,
    "recency": 8,
    "contact_confidence": 7,
    "market_liquidity": 5,
}

CALLABILITY_WEIGHTS: dict[str, int] = {
    "contact_source": 30,
    "phone_quality": 20,
    "owner_match": 20,
    "recency": 15,
    "prior_success": 10,
    "negative_dispositions": 5,
}

NEGATIVE_DISPOSITIONS = ("BAD_NUMBER", "WRONG_PERSON", "NON_OWNER", "DNC")


def _weight(weights: dict, key: str) -> float:
    return float(weights.get(key, 0))


def resolve_weights(overrides: Optional[dict] = None) -> dict:
    """Merge user overrides into defaults. Accepts dict or path to JSON file."""
    out = dict(PROPERTY_WEIGHTS)
    if isinstance(overrides, str):
        overrides = json.loads(open(overrides, encoding="utf-8").read())
    for k, v in (overrides or {}).items():
        if k in out:
            out[k] = int(v)
    return out


def _normalize_value(x: Any) -> float:
    """Parse a dollar value field (number, '$50k', '225000') to float or None."""
    if x is None:
        return 0.0
    s = str(x).strip().replace(",", "").lower()
    if not s:
        return 0.0
    mult = 1.0
    if s.endswith("k"):
        mult, s = 1000.0, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def score_property(rec: dict, ownership: Optional[dict] = None, weights: Optional[dict] = None) -> dict:
    """Property opportunity score 0-100 + component breakdown + reason trace.

    `rec` is a normalized property dict (auction_freshness output or pipeline).
    `ownership` is an OwnershipVerification dict when available.
    """
    w = weights or PROPERTY_WEIGHTS
    signals = rec.get("distress_signals") or []
    status = str(rec.get("auction_status") or "").lower()
    vacancy = str(rec.get("occupancy_signal") or "").lower()
    fresh = rec.get("freshness_components") or {}

    reasons: list[str] = []
    comps: dict[str, int] = {}

    # Distress (25).
    score = 0
    if status in ("foreclosure", "pre-foreclosure", "tax_deed"):
        score += 60
        reasons.append(f"distress:{status}")
    if "foreclosure" in signals:
        score += 20
        reasons.append("distress:foreclosure_signal")
    if "tax_delinquent" in signals:
        score += 10
        reasons.append("distress:tax_delinquent")
    if "bankruptcy" in signals or status == "bankruptcy":
        score += 25
        reasons.append("distress:bankruptcy")
    if score > 100:
        score = 100
    comps["distress"] = score

    # Equity / value opportunity (20).
    bid = _normalize_value(rec.get("opening_bid"))
    value = _normalize_value(rec.get("estimated_value"))
    if bid and value:
        ratio = bid / value
        equity = max(0, int((1.0 - ratio) * 100))
        comps["equity"] = equity
        reasons.append(f"equity:bid/value={ratio:.0%}")
    elif value:
        comps["equity"] = 40
        reasons.append("equity:value known, no opening bid")
    else:
        comps["equity"] = 20
        reasons.append("equity:no value data")

    # Vacancy / occupancy (15).
    if vacancy == "vacant":
        comps["vacancy"] = 100
        reasons.append("vacancy:vacant")
    elif vacancy:
        comps["vacancy"] = 60
        reasons.append(f"vacancy:{vacancy}")
    else:
        comps["vacancy"] = 30
        reasons.append("vacancy:unknown")

    # Ownership profile / portfolio relevance (10).
    if ownership:
        status_o = str(ownership.get("verification_status") or "").upper()
        otype = str(ownership.get("owner_type") or "unknown")
        if status_o == "VERIFIED":
            comps["ownership_profile"] = 70 + (15 if otype == "entity" else 0)
            reasons.append(f"ownership:verified/{otype}")
        elif status_o == "LIKELY":
            comps["ownership_profile"] = 40
            reasons.append("ownership:likely")
        else:
            comps["ownership_profile"] = 10
            reasons.append(f"ownership:{status_o.lower()}")
    else:
        comps["ownership_profile"] = 10
        reasons.append("ownership:unverified")

    # Property fit (10).
    comps["property_fit"] = 70 if status else 40
    reasons.append("fit:residential-auction" if status else "fit:no-auction-status")

    # Recency (8).
    days = fresh.get("recency")
    if days is not None:
        comps["recency"] = days
        reasons.append(f"recency:{days}")
    else:
        comps["recency"] = 40
        reasons.append("recency:unknown")

    # Contact confidence (7) -- hinges on ownership evidence.
    if ownership:
        conf = float(ownership.get("confidence") or 0.0)
        comps["contact_confidence"] = int(conf * 100)
        reasons.append(f"contact_conf:{conf:.0%}")
    else:
        comps["contact_confidence"] = 0
        reasons.append("contact_conf:none")

    # Market liquidity / buyer fit (5).
    if rec.get("county"):
        comps["market_liquidity"] = 80
        reasons.append(f"liquidity:county={rec['county']}")
    else:
        comps["market_liquidity"] = 30
        reasons.append("liquidity:county unknown")

    total = int(round(sum(_weight(w, k) * comps[k] for k in comps) / 100.0))
    trace = [
        {
            "component": k,
            "score": comps[k],
            "weight": _weight(w, k),
            "reason": reasons[i] if i < len(reasons) else "",
        }
        for i, k in enumerate(comps)
    ]
    return {"total": total, "component_scores": comps, "reasons": reasons, "trace": trace}


def score_callability(rec: dict, ownership: Optional[dict] = None, history: Optional[list] = None,
                      weights: Optional[dict] = None, phone: str = "") -> dict:
    """Callability score 0-100 (separate from opportunity).

    Negative dispositions in `history` are applied as penalties so recycled
    garbage (bad numbers, wrong persons, non-owners) is suppressed.
    """
    w = weights or CALLABILITY_WEIGHTS
    history = history or []
    reasons: list[str] = []
    comps: dict[str, int] = {}

    # Contact source (30).
    if ownership and str(ownership.get("verification_status") or "").upper() == "VERIFIED":
        comps["contact_source"] = 90
        reasons.append(f"contact_source:{ownership.get('source')}")
    elif ownership and str(ownership.get("verification_status") or "").upper() == "LIKELY":
        comps["contact_source"] = 55
        reasons.append("contact_source:likely")
    else:
        comps["contact_source"] = 0
        reasons.append("contact_source:none")

    # Phone quality (20).
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 10:
        comps["phone_quality"] = 80
        reasons.append("phone:valid")
    elif phone:
        comps["phone_quality"] = 30
        reasons.append("phone:short")
    else:
        comps["phone_quality"] = 0
        reasons.append("phone:none")

    # Owner/entity match confidence (20).
    if ownership:
        comps["owner_match"] = int(float(ownership.get("confidence") or 0.0) * 100)
        reasons.append(f"owner_match:{comps['owner_match']}%")
    else:
        comps["owner_match"] = 0
        reasons.append("owner_match:none")

    # Recency (15).
    days = (rec.get("freshness_components") or {}).get("recency")
    if days is not None:
        comps["recency"] = days
        reasons.append(f"recency:{days}")
    else:
        comps["recency"] = 40
        reasons.append("recency:unknown")

    # Prior successful contact (10).
    successes = [h for h in history if str(h.get("disposition") or "").upper() in
                 ("INTERESTED", "CALLBACK", "SOLD")]
    if successes:
        comps["prior_success"] = 90
        reasons.append("prior_success:yes")
    else:
        comps["prior_success"] = 30
        reasons.append("prior_success:none")

    # Negative disposition penalties (5).
    negatives = [h for h in history if str(h.get("disposition") or "").upper() in NEGATIVE_DISPOSITIONS]
    if negatives:
        comps["negative_dispositions"] = 0
        reasons.append(f"negative:{negatives[-1].get('disposition')}")
    else:
        comps["negative_dispositions"] = 100
        reasons.append("negative:none")

    total = int(round(sum(_weight(w, k) * comps[k] for k in comps) / 100.0))
    # Hard caps: no contact at all, or a recorded negative outcome, can never
    # rank into the prime queue (garbage is not recycled).
    if comps["phone_quality"] == 0 or comps["contact_source"] == 0:
        total = min(total, 39)
        reasons.append("cap:not-callable-no-contact")
    if comps["negative_dispositions"] == 0:
        total = min(total, 39)
        reasons.append("cap:negative-disposition")
    trace = [
        {"component": k, "score": comps[k], "weight": _weight(w, k),
         "reason": next(r for r in reasons if r.startswith(k.replace("_", ":")) or k in r or r.endswith(k))
                   if any(k.replace("_", ":") in r or k in r for r in reasons) else ""}
        for k in comps
    ]
    return {"total": total, "component_scores": comps, "reasons": reasons, "trace": trace}


def apply_negative_outcomes(rec: dict, history: Optional[list]) -> dict:
    """Attach the most recent negative disposition to a record (suppression)."""
    out = dict(rec)
    out["negative_dispositions"] = [
        h for h in (history or []) if str(h.get("disposition") or "").upper() in NEGATIVE_DISPOSITIONS
    ]
    return out