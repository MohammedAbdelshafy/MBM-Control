"""Provider interface: graceful unavailability, failure paths, QA gate."""
from __future__ import annotations

import pytest

from contec.real_estate_media.providers import NullProvider, get_provider
from contec.real_estate_media.providers.base import register
from contec.real_estate_media.sample_store import build_sample_record


class TestProviders:
    def test_null_provider_never_available(self):
        p = NullProvider()
        assert p.available() is False
        r = p.render(prompt="x", images=[], aspects=[])
        assert r["status"] == "SKIPPED_UNAVAILABLE"

    def test_unknown_code_falls_back_to_null(self):
        assert get_provider("does-not-exist").available() is False

    def test_registry_roundtrip(self):
        class FakeOK(NullProvider):
            code = "fakeok"

            def available(self):
                return True

            def render(self, *, prompt, images, aspects, timeout_s=600):
                return {"status": "SUCCEEDED",
                        "outputs": [{"ratio": a["ratio"], "url": f"https://x/{a['ratio']}"}
                                    for a in aspects],
                        "provider": self.code}
        register(FakeOK)
        r = get_provider("FAKEOK").render(prompt="p", images=[],
                                          aspects=[{"ratio": "9:16"}])
        assert r["status"] == "SUCCEEDED"


class FlakyFailProvider(NullProvider):
    code = "flakyfail"

    def available(self):
        return True

    def render(self, **kw):
        return {"status": "FAILED", "outputs": [], "provider": self.code,
                "error": "upstream_500"}


class TestSampleGeneration:
    def test_unconfigured_provider_blocks_honestly(self, good_agent):
        rec = build_sample_record(
            good_agent, {"listing_id": "L1", "address": "12 Main St"},
            [{"bytes": b"a" * 40000, "width": 1280, "height": 720}],
            provider_code="null")
        assert rec["generation_status"] == "SKIPPED_UNAVAILABLE"
        assert rec.get("provider_error") == "provider_not_configured"
        assert rec["delivery_status"] == "NOT_DELIVERED"

    def test_failed_render_recorded_not_simulated(self, good_agent):
        register(FlakyFailProvider)
        rec = build_sample_record(
            good_agent, {"listing_id": "L1", "address": "12 Main St"},
            [{"bytes": b"a" * 40000, "width": 1280, "height": 720}],
            provider_code="flakyfail")
        assert rec["generation_status"] == "FAILED"
        assert rec["provider_error"] == "upstream_500"

    def test_no_valid_assets_blocked_with_reasons(self, good_agent):
        rec = build_sample_record(good_agent, {"listing_id": "L1"},
                                  [{"bytes": b"x", "size": 5}])
        assert rec["generation_status"] == "BLOCKED"
        assert rec["block_reason"] == "no_valid_assets"
