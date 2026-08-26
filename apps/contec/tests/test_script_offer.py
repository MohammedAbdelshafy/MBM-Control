"""Script engine honesty + offer engine recommendation/override."""
from __future__ import annotations

import pytest

from contec.real_estate_media.offer_engine import recommend
from contec.real_estate_media.script_engine import (
    objection_branch, render_primary, validate_no_fabrication,
)


class TestScriptEngine:
    def _listing(self):
        return {"address": "1204 Willow Creek Dr", "sample_url": None}

    def test_renders_with_real_tokens(self, good_agent):
        text = render_primary(good_agent, self._listing())
        assert "Dana Whitfield" in text and "1204 Willow Creek Dr" in text
        assert validate_no_fabrication(text)

    def test_missing_address_refuses_to_render(self, good_agent):
        with pytest.raises(ValueError, match="NEEDS_REVIEW"):
            render_primary(good_agent, {"address": None})

    def test_sample_clause_switches_on_presence(self, good_agent):
        with_s = render_primary(good_agent, {**self._listing(), "sample_url": "https://x/v.mp4"})
        assert "already had a sample cut" in with_s

    def test_all_ten_objection_branches_exist_and_clean(self):
        keys = ["how_much", "have_videographer", "dont_need_video", "send_it",
                "how_it_works", "is_it_ai", "multiple_listings", "too_expensive",
                "call_me_later", "not_interested"]
        assert len(keys) == 10
        for k in keys:
            assert validate_no_fabrication(objection_branch(k))

    def test_unknown_objection_flagged_not_invented(self):
        assert "NEEDS_REVIEW" in objection_branch("martian_discount")


class TestOfferEngine:
    def test_single_listing_pilot(self):
        r = recommend({"active_listings": 1}, {"tier": "C"})
        assert r["recommended"] == "SINGLE_PROPERTY"

    def test_high_volume_subscription(self, good_agent):
        r = recommend(good_agent, {"tier": "A"})
        assert r["recommended"] == "MONTHLY_SUBSCRIPTION"

    def test_brokerage_scale_requires_brokerage_contact(self):
        r = recommend({"active_listings": 2, "brokerage_agent_count": 50,
                       "is_brokerage_decision_maker": True},
                      {"tier": "B"})
        assert r["recommended"] == "BROKERAGE_PACKAGE"
        # same numbers WITHOUT brokerage contact flag -> agent-level offer
        r2 = recommend({"active_listings": 2, "brokerage_agent_count": 50},
                       {"tier": "B"})
        assert r2["recommended"] != "BROKERAGE_PACKAGE"

    def test_no_inventory_no_quote(self):
        r = recommend({"active_listings": 0}, {"tier": "D"})
        assert r["recommended"] is None and "nurture" in r["why"]

    def test_catalog_has_no_hardcoded_prices(self):
        r = recommend({"active_listings": 1}, {"tier": "C"})
        for pkg in r["catalog"]:
            assert pkg.get("price") is None  # config-only pricing (owner countersign)
