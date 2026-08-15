"""scoring tests — opportunity + callability with reason traces + suppression."""
from property_intel.scoring import (
    CALLABILITY_WEIGHTS,
    PROPERTY_WEIGHTS,
    apply_negative_outcomes,
    resolve_weights,
    score_callability,
    score_property,
)

VERIFIED_OWNER = {
    "verification_status": "VERIFIED",
    "confidence": 0.95,
    "owner_type": "entity",
    "source": "Dallas Central Appraisal District (DCAD)",
}


def _rec(**kw):
    base = {
        "address": "12124 Schroeder Rd",
        "state": "TX",
        "county": "Dallas",
        "auction_status": "foreclosure",
        "occupancy_signal": "vacant",
        "opening_bid": 225000,
        "estimated_value": 450000,
        "freshness_components": {"recency": 90},
    }
    base.update(kw)
    return base


def test_weights_sum_100():
    assert sum(PROPERTY_WEIGHTS.values()) == 100
    assert sum(CALLABILITY_WEIGHTS.values()) == 100


def test_resolve_weights_override():
    w = resolve_weights({"distress": 40})
    assert w["distress"] == 40
    assert w["equity"] == 20  # untouched default
    assert sum(w.values()) != 100  # user takes responsibility


def test_score_property_total_in_range_and_has_trace():
    s = score_property(_rec(), ownership=VERIFIED_OWNER)
    assert 0 <= s["total"] <= 100
    assert s["component_scores"]["distress"] >= 60
    assert any(r.startswith("equity:bid/value") for r in s["reasons"])
    assert len(s["trace"]) == len(s["component_scores"])
    assert all("component" in t and "score" in t for t in s["trace"])


def test_score_property_unverified_owner_lower_confidence():
    low = score_property(_rec(), ownership={"verification_status": "NOT_FOUND", "confidence": 0.0, "owner_type": "unknown"})
    high = score_property(_rec(), ownership=VERIFIED_OWNER)
    assert low["component_scores"]["ownership_profile"] < high["component_scores"]["ownership_profile"]
    assert low["component_scores"]["contact_confidence"] < high["component_scores"]["contact_confidence"]


def test_score_callability_cap_without_contact():
    s = score_callability(_rec(), ownership={"verification_status": "NOT_FOUND", "confidence": 0.0}, phone="")
    assert s["total"] <= 39  # hard cap: no phone, no verified owner
    assert any("cap" in r for r in s["reasons"])


def test_score_callability_high_with_verified_owner_and_phone():
    s = score_callability(_rec(), ownership=VERIFIED_OWNER, phone="+1 555-010-0001")
    assert s["total"] > 50
    assert s["component_scores"]["contact_source"] == 90
    assert s["component_scores"]["phone_quality"] == 80


def test_score_callability_negative_disposition_suppresses():
    history = [{"disposition": "BAD_NUMBER"}, {"disposition": "NON_OWNER"}]
    s = score_callability(_rec(), ownership=VERIFIED_OWNER, phone="+1 555-010-0001", history=history)
    assert s["component_scores"]["negative_dispositions"] == 0
    assert s["total"] < 60
    assert any("negative:NON_OWNER" in r for r in s["reasons"])


def test_score_callability_prior_success_boosts():
    history = [{"disposition": "INTERESTED"}]
    s = score_callability(_rec(), ownership=VERIFIED_OWNER, phone="+1 555-010-0001", history=history)
    assert s["component_scores"]["prior_success"] == 90


def test_apply_negative_outcomes_attaches_history():
    history = [{"disposition": "INTERESTED"}, {"disposition": "DNC"}]
    out = apply_negative_outcomes({}, history)
    assert [h["disposition"] for h in out["negative_dispositions"]] == ["DNC"]