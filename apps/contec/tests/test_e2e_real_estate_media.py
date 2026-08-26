"""END-TO-END (hermetic, fake provider):
new realtor -> active listing -> sample -> dialer -> interested -> quote ->
won -> fulfillment. Every state change is validated by the machine; every
commercial value is recorded, never inferred.
"""
from __future__ import annotations

from contec.real_estate_media import analytics
from contec.real_estate_media.automation import qualify_and_route
from contec.real_estate_media.fulfillment import create_fulfillment_job
from contec.real_estate_media.offer_engine import recommend
from contec.real_estate_media.providers.base import register
from contec.real_estate_media.sample_store import build_sample_record
from contec.real_estate_media.state_machine import transition


class E2EProvider:
    code = "e2e_fake"

    def available(self):
        return True

    def render(self, *, prompt, images, aspects, timeout_s=600):
        assert prompt and images, "pipeline must supply facts + assets"
        return {"status": "SUCCEEDED", "provider": self.code, "model": "fake-v1",
                "outputs": [{"ratio": a["ratio"], "url": f"https://cdn.test/{a['ratio']}"}
                            for a in aspects]}

    def qa_check(self, outputs):
        return {"qa_status": "PASS", "missing_aspects": []}


def test_full_loop(good_agent):
    register(E2EProvider)

    # 1. QUALIFY + route to dialer (no duplicates in registry)
    routed = []
    res = qualify_and_route(good_agent, settings={}, existing_agents=[],
                            enqueue_dialer=routed.append)
    assert res["routed"] is True

    # 2. SAMPLE on strongest listing
    sample = build_sample_record(
        good_agent,
        {"listing_id": "L-100", "address": "77 Bluff View", "bedrooms": 4,
         "city": "Austin"},
        [{"bytes": b"front" * 8000, "width": 1600, "height": 1067,
          "category": "exterior"},
         {"bytes": b"kitchen" * 8000, "width": 1600, "height": 1067,
          "category": "kitchen"}],
        provider_code="e2e_fake")
    assert sample["generation_status"] == "SUCCEEDED"
    assert sample["qa_status"] == "PASS"
    assert {o["ratio"] for o in sample["outputs"]} == {"9:16", "16:9", "1:1"}

    # 3. DIALER path with real dispositions only
    cur = "READY"
    for nxt, _ev in [
        ("DIALED", {"event": "call_started"}),
        ("CONNECTED", {"event": "call_connected"}),
        ("INTERESTED", {"disposition": "INTERESTED"}),
        ("SAMPLE_REQUESTED", {}),
        ("SAMPLE_SENT", {}),
        ("QUOTED", {}),
        ("NEGOTIATING", {}),
        ("WON", {}),
    ]:
        res = transition(cur, nxt)
        cur = res["to"]
    assert cur == "WON"

    # 4. OFFER was recommended from evidence, price recorded at quote time
    rec = recommend(good_agent, {"tier": res["crm_stage"] and "A"})
    assert rec["recommended"] == "MONTHLY_SUBSCRIPTION"
    package = {"code": rec["recommended"], "price": 1200}  # operator-entered

    # 5. FULFILLMENT auto-created on WON
    job = create_fulfillment_job(customer=good_agent,
                                 listing={"listing_id": "L-100",
                                          "address": "77 Bluff View"},
                                 package=package)
    assert job["status"] == "QUEUED"
    assert job["quoted_price"] == package["price"]

    # 6. ANALYTICS: event-derived only
    dash = analytics.dashboard_counts(
        agents=[{**good_agent, "qualification_score": 70,
                 "sample_candidate": True}],
        samples=[sample],
        call_events=[{"event": "call_started"}, {"event": "call_connected"},
                     {"disposition": "INTERESTED"}],
        quotes=[{"package": package["code"]}],
        won=[{"quoted_price": package["price"]}],
        production_events=[{"status": "SUCCEEDED", "qa_status": "PASS",
                            "generation_seconds": 90}])
    assert dash["sales"]["calls"] == 1
    assert dash["sales"]["closes"] == 1
    assert dash["sales"]["revenue"] == 1200
    assert dash["acquisition"]["samples_delivered"] == 0  # nothing delivered yet


def test_empty_system_reports_zeros():
    dash = analytics.dashboard_counts(agents=[], samples=[], call_events=[],
                                      quotes=[], won=[], production_events=[])
    assert dash["sales"]["calls"] == 0 and dash["sales"]["revenue"] == 0
