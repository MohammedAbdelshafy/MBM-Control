"""Dedup, qualification, listing-selection tests."""
from __future__ import annotations

from contec.real_estate_media.lead_dedup import dedup_key, find_duplicate
from contec.real_estate_media.scoring import real_estate_media_score


class TestLeadDeduplication:
    def test_same_email_is_duplicate(self, good_agent):
        other = {**good_agent, "agent_name": "Dana Whitfield-Smith"}
        assert find_duplicate(other, [good_agent]) is good_agent

    def test_phone_normalization_matches(self, good_agent):
        other = {**good_agent, "email": "", "phone": "512-555-0142"}
        assert find_duplicate(other, [{**good_agent, "email": ""}]) is not None

    def test_moved_brokerage_same_person(self, good_agent):
        mover = {**good_agent, "brokerage": "New Co Realty", "active_listings": 2}
        assert find_duplicate(mover, [good_agent]) is good_agent

    def test_different_people_not_duplicate(self, good_agent):
        stranger = {**good_agent, "agent_name": "John Park",
                    "email": "john@otherco.com", "phone": "+1 214 555 9999",
                    "website": "otherco.com"}
        assert find_duplicate(stranger, [good_agent]) is None

    def test_no_contact_info_never_collides(self):
        a = {"agent_name": "Chris Doe"}
        b = {"agent_name": "Chris Doe", "brokerage": "X"}
        assert dedup_key(a) == ("", "")
        assert find_duplicate(a, [b]) is None

    def test_free_mail_domains_not_treated_as_company_identity(self):
        p, s = dedup_key({"email": "dana@gmail.com", "website": "summitrealty.com"})
        assert not p.startswith("email:dana@gmail.com@")
        assert "summitrealty.com" in s


class TestQualification:
    def test_score_traceable_and_tiered(self, good_agent):
        r = real_estate_media_score(good_agent)
        assert r["score"] >= 45 and r["tier"] in ("A", "B")
        assert r["evidence"] and all("points" in e for e in r["evidence"])

    def test_empty_agent_scores_zero_with_unknowns(self):
        r = real_estate_media_score({})
        assert r["score"] == 0 and r["tier"] == "D"
        assert len(r["unknown_factors"]) >= 5

    def test_max_cap(self, good_agent):
        r = real_estate_media_score({**good_agent,
                                     "market_median_price": 2_000_000})
        assert r["score"] <= r["max"]
