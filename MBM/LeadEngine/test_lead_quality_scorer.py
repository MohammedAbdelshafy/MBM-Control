import sys, json
sys.path.insert(0, "MBM/LeadEngine")
from lead_quality_scorer import score_lead

rich = {
    "contact_name": "John Smith",
    "verified_phone": "+12145551234",
    "phone_number": "+12145551234",
    "est_arv": "350000",
    "asking_price": "250000",
    "target_cash_offer": "210000",
    "property_address": "12124 Schroeder Rd",
    "city": "Dallas",
    "state": "TX",
    "skip_trace_status": "VERIFIED",
    "verified_source": "DCAD",
    "motivation_score": 77,
    "motivation_tier": "VERY_HIGH",
    "motivation_signals": ["absentee", "out_of_state"],
    "details": {"Motivated_At": "2026-08-01T00:00:00+00:00"},
}
r = score_lead(rich)
print(json.dumps(r, indent=2))
assert r["outreach_eligible"] is True, "rich lead should be eligible"
assert r["quality_score"] > 55, f"rich lead should score >55, got {r['quality_score']}"
print("ASSERT: rich lead eligible + high score PASS")

poor = {
    "contact_name": "",
    "phone_number": "",
    "skip_trace_status": "UNVERIFIED",
    "details": {},
}
r2 = score_lead(poor)
print(json.dumps(r2, indent=2))
assert r2["outreach_eligible"] is False, "poor lead must not be eligible"
assert r2["quality_score"] < 55, "poor lead must score low"
print("ASSERT: poor lead ineligible + low score PASS")