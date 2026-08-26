"""Duplicate-sample prevention, limits, fulfillment, upsell, automation."""
from __future__ import annotations

from datetime import datetime, timezone

from contec.real_estate_media.automation import WorkQueue, qualify_and_route
from contec.real_estate_media.fulfillment import (
    create_fulfillment_job, upsell_opportunities,
)
from contec.real_estate_media.sample_store import (
    generation_limit_reached, is_duplicate_sample,
)


class TestSampleGuards:
    def test_duplicate_prevented(self):
        existing = [{"agent_id": "AG-1", "listing_id": "L1",
                     "generation_status": "SUCCEEDED"}]
        assert is_duplicate_sample(existing, "L1", "AG-1")

    def test_failed_sample_allows_retry(self):
        existing = [{"agent_id": "AG-1", "listing_id": "L1",
                     "generation_status": "FAILED"}]
        assert not is_duplicate_sample(existing, "L1", "AG-1")

    def test_generation_limit(self):
        assert generation_limit_reached(1, {"max_auto_samples_per_agent": 1})
        assert not generation_limit_reached(0, {"max_auto_samples_per_agent": 1})


class TestFulfillment:
    def test_won_creates_job_with_provenance(self, good_agent):
        job = create_fulfillment_job(
            customer=good_agent,
            listing={"listing_id": "L9", "address": "9 Oak Ln"},
            package={"code": "SINGLE_PROPERTY", "price": 300})
        assert job["assigned_workflow"] == "REAL_ESTATE_PROPERTY_VIDEO_FACTORY"
        assert job["status"] == "QUEUED" and job["due_at"] > job["created_at"]
        assert job["quoted_price"] == 300

    def test_custom_quote_never_invents_price(self, good_agent):
        job = create_fulfillment_job(customer=good_agent,
                                     listing={"listing_id": "L9"},
                                     package={"code": "CUSTOM_QUOTE", "price": None})
        assert job["quoted_price"] is None

    def test_batch_jobs(self, good_agent):
        jobs = [create_fulfillment_job(customer=good_agent,
                                       listing={"listing_id": f"L{i}"},
                                       package={"code": "MULTI_PROPERTY"}) for i in range(3)]
        assert len(jobs) == 3


class TestUpsell:
    def test_no_history_no_upsell(self):
        assert upsell_opportunities({}) == []

    def test_delivery_triggers_additional_videos(self):
        ops = upsell_opportunities({"delivered_count": 1})
        assert any(o["offer"] == "additional_property_videos" for o in ops)

    def test_volume_triggers_subscription(self):
        ops = upsell_opportunities({"deliveries_30d": 3})
        assert any(o["offer"] == "monthly_content_subscription" for o in ops)

    def test_brokerage_trigger(self):
        ops = upsell_opportunities({"brokerage_package_customer": True})
        assert any(o["offer"] == "listing_reels_bundle" for o in ops)


class TestAutomationLoop:
    def test_duplicate_routed_to_reject_reason(self, good_agent):
        res = qualify_and_route(good_agent, settings={},
                                existing_agents=[good_agent],
                                enqueue_dialer=lambda p: None)
        assert res["routed"] is False and res["reason"].startswith("duplicate_of")

    def test_low_score_nurture_only(self):
        res = qualify_and_route({"agent_name": "x"}, settings={},
                                existing_agents=[], enqueue_dialer=lambda p: None)
        assert res["routed"] is False and res["reason"].startswith("below_threshold")

    def test_qualified_enters_dialer_queue(self, good_agent):
        seen = []
        res = qualify_and_route(good_agent, settings={}, existing_agents=[],
                                enqueue_dialer=seen.append)
        assert res["routed"] is True and seen[0]["qualification_score"] >= 45


class TestWorkQueue:
    def test_failures_land_in_retry_then_dead(self):
        q = WorkQueue(max_attempts=2)
        q.push({"id": 1})
        calls = {"n": 0}

        def always_fails(item):
            calls["n"] += 1
            raise RuntimeError("boom")

        s1 = q.process(always_fails)
        assert s1["retry"] == 1
        q.requeue_retries()
        q.process(always_fails)
        assert len(q.dead) == 1 and q.dead[0]["last_error"] == "boom"

    def test_success_path(self):
        q = WorkQueue()
        q.push({"id": 2})
        stats = q.process(lambda item: item.update(ok=True))
        assert stats["done"] == 1 and not q.pending
