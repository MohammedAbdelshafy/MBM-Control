"""Asset pipeline: validation, sequencing, facts-only prompt, stage walk."""
from __future__ import annotations

import pytest

from contec.real_estate_media import asset_pipeline as ap


def _img(i, w=1920, h=1080, cat="interior", size=100_000):
    return {"bytes": f"img-{i}".encode() * (size // 5), "width": w, "height": h,
            "category": cat, "source_url": f"https://cdn.example/{i}.jpg"}


class TestValidation:
    def test_accepts_good_assets(self):
        ok, rej = ap.validate_assets([_img(1), _img(2)])
        assert len(ok) == 2 and rej == []

    def test_rejects_low_resolution(self):
        ok, rej = ap.validate_assets([_img(1, w=300, h=200)])
        assert not ok and rej[0]["reason"] == "low_resolution"

    def test_rejects_corrupt_tiny(self):
        ok, rej = ap.validate_assets([{"bytes": b"x", "size": 10,
                                       "width": 800, "height": 600}])
        assert not ok and rej[0]["reason"] == "corrupt_or_tiny_payload"

    def test_rejects_duplicates(self):
        same = _img(1)
        ok, rej = ap.validate_assets([same, dict(same)])
        assert len(ok) == 1 and rej[0]["reason"] == "duplicate_asset"


class TestSequencingAndPrompt:
    def test_exterior_first_order(self):
        ok, _ = ap.validate_assets([_img(1, cat="kitchen"), _img(2, cat="exterior"),
                                    _img(3, cat="bedroom")])
        seq = ap.sequence_assets(ok)
        assert [a["category"] for a in seq][0] == "exterior"

    def test_prompt_contains_only_supplied_facts(self):
        prompt = ap.build_prompt({"bedrooms": 3, "bathrooms": 2, "city": "Austin"},
                                 [{"category": "exterior"}])
        assert "3 bedroom" in prompt["prompt"] and "Austin" in prompt["prompt"]
        assert "pool" not in prompt["prompt"].lower()

    def test_no_facts_still_honest(self):
        prompt = ap.build_prompt({}, [])
        assert "residential home" in prompt["prompt"]


def test_stage_walk():
    cur = "LISTING_DISCOVERED"
    seen = [cur]
    while (nxt := ap.next_stage(cur)):
        seen.append(nxt)
        cur = nxt
    assert seen == ap.PIPELINE_STAGES
    with pytest.raises(ValueError):
        ap.next_stage("NOT_A_STAGE")
