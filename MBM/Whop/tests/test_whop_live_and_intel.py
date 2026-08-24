"""Hermetic tests for whop_live (API truth + snapshot protection) and
whop_product_intel (inventory, CTAs, cross-sell). No network access.

Run: python -m pytest MBM/Whop/tests -q
"""

import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

wl = importlib.import_module("whop_live")
wpi = importlib.import_module("whop_product_intel")

NOW = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)

FIVE_PRODUCTS = {
    "data": [
        {"id": "prod_R5uDTAhXCKAcf", "title": "DFY AI Employee Suite",
         "visibility": "visible", "member_count": 0},
        {"id": "prod_hseWnnhfVigJo", "title": "Property Intelligence API",
         "visibility": "visible", "member_count": 0},
        {"id": "prod_L2MmMKYlE9LAv", "title": "Revenue Audit Engine",
         "visibility": "visible", "member_count": 0},
        {"id": "prod_Y8rcA2dgkbxyZ", "title": "AI Voice Agent Factory",
         "visibility": "visible", "member_count": 0},
        {"id": "prod_MaHYZkh3AfEEf", "title": "AI Video Clipping Engine",
         "visibility": "visible", "member_count": 0},
    ]
}
SIX_PLANS = {
    "data": [
        {"id": "plan_nqybZK0ZpJS3J", "product": "prod_R5uDTAhXCKAcf",
         "plan_type": "renewal", "initial_price": "1997.0", "renewal_price": "1997.0",
         "base_currency": "usd", "billing_period": 30,
         "direct_link": "https://whop.com/checkout/plan_nqybZK0ZpJS3J"},
        {"id": "plan_T6t6iMlvJvE9e", "product": "prod_hseWnnhfVigJo",
         "plan_type": "renewal", "initial_price": "97.0", "renewal_price": "97.0",
         "base_currency": "usd", "billing_period": 30,
         "direct_link": "https://whop.com/checkout/plan_T6t6iMlvJvE9e"},
        {"id": "plan_Sg0oIq3Tf4rlQ", "product": "prod_L2MmMKYlE9LAv",
         "plan_type": "one_time", "initial_price": "149.0", "renewal_price": "0.0",
         "base_currency": "usd", "billing_period": None,
         "direct_link": "https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ"},
        {"id": "plan_ZtH6wc9mYpl3j", "product": "prod_Y8rcA2dgkbxyZ",
         "plan_type": "renewal", "initial_price": "297.0", "renewal_price": "297.0",
         "base_currency": "usd", "billing_period": 30,
         "direct_link": "https://whop.com/checkout/plan_ZtH6wc9mYpl3j"},
        {"id": "plan_KkeWhWGi53doc", "product": "prod_MaHYZkh3AfEEf",
         "plan_type": "renewal", "initial_price": "497.0", "renewal_price": "497.0",
         "base_currency": "usd", "billing_period": 30,
         "direct_link": "https://whop.com/checkout/plan_KkeWhWGi53doc"},
        {"id": "plan_HzmxF6LtJcoEG", "product": "prod_MaHYZkh3AfEEf",
         "plan_type": "renewal", "initial_price": "997.0", "renewal_price": "997.0",
         "base_currency": "usd", "billing_period": 30,
         "direct_link": "https://whop.com/checkout/plan_HzmxF6LtJcoEG"},
    ]
}

UNAUTHORIZED_400 = (False, 400, None,
                    '{"error":{"type":"bad_request","message":"You are not '
                    'authorized - ensure that you have access to this resource"}}', 42)
SSL_ERROR = (False, 0, None, "SSLError: certificate verify failed", 13)


def _ok(payload):
    return (True, 200, payload, "", 55)


def _transport_for(products=_ok(FIVE_PRODUCTS), plans=_ok(SIX_PLANS),
                   memberships=None):
    """Build a fake transport keyed by endpoint path."""
    def transport(url, headers, params, timeout):
        if url.endswith("/products"):
            return products(url) if callable(products) else products
        if url.endswith("/plans"):
            return plans(url) if callable(plans) else plans
        if url.endswith("/memberships"):
            if memberships is None:
                return _ok({"data": [], "total_count": 0})
            return memberships(url) if callable(memberships) else memberships
        raise AssertionError(f"unexpected endpoint {url}")
    return transport


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Redirect snapshot + sync-health storage into a temp dir."""
    monkeypatch.setattr(wl, "SNAPSHOT_FILE", tmp_path / "whop_revenue.json")
    monkeypatch.setattr(wl, "SYNC_HEALTH_LOG", tmp_path / "sync_health.jsonl")
    monkeypatch.setenv("WHOP_ACCOUNT_ID", "biz_UxlhGUdO9TpGb0")
    return tmp_path


# ── Phase 17 matrix ──────────────────────────────────────────────────────────

def test_successful_sync_all_endpoints(isolated):
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    assert snap["snapshot_status"] == wl.LIVE_VALID
    assert snap["memberships_active"] == 0
    assert snap["memberships_data_status"] == "VERIFIED"
    assert len(snap["products"]) == 5
    assert len(snap["plans"]) == 6
    assert snap["last_successful_sync"] is not None


def test_authorization_failure_on_memberships_keeps_products_unverified_members(isolated):
    snap = wl.build_snapshot(
        "biz_UxlhGUdO9TpGb0",
        transport=_transport_for(memberships=UNAUTHORIZED_400), now=NOW)
    assert snap["snapshot_status"] == wl.LIVE_PARTIAL
    rep = wl.members_report(snap)
    assert rep["value"] == "UNVERIFIED"
    assert "MEMBERSHIPS_ENDPOINT" in rep["reason"]
    # A failed call must NOT fabricate a member count.
    assert snap["members"] != 0 or snap["members_status"] != "VERIFIED"


def test_ssl_failure_never_destroys_prior_good_snapshot(isolated):
    # Step 1: a good live snapshot exists.
    good = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    wl.persist_snapshot(good, isolated / "whop_revenue.json")
    # Step 2: every endpoint dies with an SSL error.
    bad = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                            transport=_transport_for(products=SSL_ERROR,
                                                     plans=SSL_ERROR,
                                                     memberships=SSL_ERROR),
                            now=NOW + timedelta(hours=1))
    wl.persist_snapshot(bad, isolated / "whop_revenue.json")
    # Step 3: the previously-verified catalog survived untouched.
    assert len(bad["products"]) == 5
    assert {p["id"] for p in bad["products"]} == {p["id"] for p in FIVE_PRODUCTS["data"]}
    assert "products" in bad["_carry_forward_applied"]
    assert bad["memberships_reason"]
    stored = json.loads((isolated / "whop_revenue.json").read_text(encoding="utf-8"))
    assert len(stored["products"]) == 5


def test_empty_response_is_valid_zero_not_failure(isolated):
    empty = _transport_for(
        products=_ok({"data": []}),
        plans=_ok({"data": []}),
        memberships=_ok({"data": [], "total_count": 0}))
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0", transport=empty, now=NOW)
    assert snap["snapshot_status"] == wl.LIVE_VALID
    assert snap["products"] == []
    assert snap["memberships_active"] == 0          # genuinely zero -> VERIFIED
    assert snap["memberships_data_status"] == "VERIFIED"


def test_partial_response_products_ok_plans_fail(isolated):
    snap = wl.build_snapshot(
        "biz_UxlhGUdO9TpGb0",
        transport=_transport_for(plans=SSL_ERROR), now=NOW)
    assert snap["snapshot_status"] == wl.LIVE_PARTIAL
    assert len(snap["products"]) == 5
    assert any("/plans" in e for e in snap["errors"])


def test_stale_snapshot_classification(isolated):
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    wl.persist_snapshot(snap, isolated / "whop_revenue.json")
    fresh = wl.classify_staleness(snap, now=NOW + timedelta(hours=2))
    stale = wl.classify_staleness(snap, now=NOW + timedelta(hours=48))
    assert fresh == wl.LIVE_VALID
    assert stale == wl.STALE_VALID
    assert wl.classify_staleness({}) == wl.UNAVAILABLE


def test_recovery_after_failure_overwrites_cleanly(isolated):
    good = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    wl.persist_snapshot(good, isolated / "whop_revenue.json")
    broken = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                               transport=_transport_for(products=SSL_ERROR,
                                                        plans=SSL_ERROR,
                                                        memberships=SSL_ERROR),
                               now=NOW + timedelta(minutes=30))
    wl.persist_snapshot(broken, isolated / "whop_revenue.json")
    recovered = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                                  transport=_transport_for(),
                                  now=NOW + timedelta(hours=1))
    assert recovered["snapshot_status"] == wl.LIVE_VALID
    assert recovered["_carry_forward_applied"] == []
    assert recovered["memberships_data_status"] == "VERIFIED"
    assert recovered["last_successful_sync"] > good["last_successful_sync"]


def test_null_revenue_stays_unavailable(isolated):
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    rep = wl.revenue_report(snap)
    assert rep == {"value": "UNAVAILABLE", "status": "UNAVAILABLE",
                   "reason": "NO_REVENUE_EVIDENCE"}
    assert snap["net_revenue_7d"] is None


def test_membership_unavailable_semantics(isolated):
    rep = wl.members_report({})
    assert rep["value"] == "UNVERIFIED"
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(memberships=UNAUTHORIZED_400),
                             now=NOW)
    rep2 = wl.members_report(snap)
    assert rep2["value"] == "UNVERIFIED"
    assert rep2["status"] in ("UNVERIFIED", "STALE")


def test_product_discovery_from_live_payload(isolated):
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(), now=NOW)
    titles = {p["title"] for p in snap["products"]}
    assert titles == {"DFY AI Employee Suite", "Property Intelligence API",
                      "Revenue Audit Engine", "AI Voice Agent Factory",
                      "AI Video Clipping Engine"}
    clipping = next(p for p in snap["products"]
                    if p["id"] == "prod_MaHYZkh3AfEEf")
    assert len(clipping.get("plans") or []) == 2     # both tiers attached
    prices = sorted(pl["initial_price_usd"] for pl in clipping["plans"])
    assert prices == [497.0, 997.0]


def test_sync_health_states(isolated):
    wl.sync_live("biz_UxlhGUdO9TpGb0", transport=_transport_for(), now=NOW)
    health = wl.compute_sync_health(now=NOW + timedelta(minutes=5))
    assert health["health"] == wl.HEALTHY
    wl._log_call("biz_UxlhGUdO9TpGb0", "/memberships", False, 401, 10, 0, "unauthorized")
    health2 = wl.compute_sync_health(now=NOW + timedelta(minutes=6))
    assert health2["health"] == wl.DEGRADED


def test_sync_log_never_contains_secrets(isolated, monkeypatch):
    monkeypatch.setattr(wl, "get_api_key", lambda: "apik_SUPER_SECRET")
    snap = wl.build_snapshot("biz_UxlhGUdO9TpGb0",
                             transport=_transport_for(memberships=UNAUTHORIZED_400),
                             now=NOW)
    log_text = (isolated / "sync_health.jsonl").read_text(encoding="utf-8")
    assert "apik_SUPER_SECRET" not in log_text
    stored = (isolated / "whop_revenue.json").exists()


# ── Product intelligence / CTA / cross-sell ─────────────────────────────────

def test_intel_prices_match_live_inventory():
    assert wpi.LIVE_INVENTORY["Revenue Audit Engine"]["plans"][0]["initial_price_usd"] == 149.0
    assert wpi.LIVE_INVENTORY["DFY AI Employee Suite"]["plans"][0]["initial_price_usd"] == 1997.0
    ids = {row["product_id"] for row in wpi.PRODUCT_INTEL}
    assert ids == set(wpi.PRODUCT_IDS)
    for row in wpi.PRODUCT_INTEL:
        assert row["price_source"].startswith("REAL"), row["product"]


def test_cross_sell_never_recommends_owned():
    recs = wpi.recommend_next_product(None, ["Revenue Audit Engine"])
    assert all(r["product"] != "Revenue Audit Engine" for r in recs)
    top = recs[0]
    assert top["product"] == "AI Voice Agent Factory"
    assert 0 <= top["confidence"] <= 1 and top["reason"]
    by_id = wpi.recommend_next_product(None, ["prod_hseWnnhfVigJo"])
    assert all(r["product"] != "Property Intelligence API" for r in by_id)
    assert any(r["product"] == "AI Voice Agent Factory" for r in by_id)


def test_cross_sell_cold_start_offers_entry_doors_only():
    recs = wpi.recommend_next_product(None, [])
    names = {r["product"] for r in recs}
    assert "DFY AI Employee Suite" not in names      # never push flagship cold
    assert names <= {"Revenue Audit Engine", "Property Intelligence API"}


def test_cta_audit_maps_all_five_live_products():
    rows = wpi.build_cta_map()
    audit = wpi.audit_ctas(rows)
    assert audit["dead"] == 0
    assert audit["live_products_without_cta"] == []
    assert audit["untracked_checkouts"] == 0
    checkout_rows = [r for r in rows
                     if r["status"].startswith("OK_CHECKOUT") and r["product_id"]]
    covered = {r["product_id"] for r in checkout_rows}
    assert covered == set(wpi.PRODUCT_IDS)
    for r in checkout_rows:
        assert "checkout_started" in r["tracking_event"]
        assert r["url"].startswith("https://whop.com/checkout/")


def test_cta_audit_flags_dead_buttons(tmp_path, monkeypatch):
    page = tmp_path / "landing.html"
    page.write_text(
        '<a class="track-cta" href="">DEAD</a>'
        '<a class="track-cta" href="https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ">AUDIT</a>',
        encoding="utf-8")
    rows = wpi.build_cta_map(pages=[page])
    assert any(r["status"] == "DEAD" for r in rows)
    audit = wpi.audit_ctas(rows)
    assert audit["status"] in ("FAIL", "PARTIAL")


def test_first_revenue_objective_complete_and_honest():
    obj = wpi.FIRST_REVENUE_OBJECTIVE
    for field in ("product", "target_audience", "offer", "price_usd",
                  "CTA", "landing_path", "success_event"):
        assert field in obj and obj[field], field
    assert obj["expected_revenue"].startswith("NOT_PROJECTED")


def test_opportunity_queue_shape():
    objectives = [o["objective"] for o in wpi.OPPORTUNITY_QUEUE]
    assert objectives == ["FIRST_PURCHASE", "FIRST_REPEAT_PURCHASE",
                          "FIRST_SUBSCRIPTION", "FIRST_REFERRAL",
                          "FIRST_B2B_CUSTOMER"]
    for o in wpi.OPPORTUNITY_QUEUE:
        for field in ("required_infrastructure", "current_status",
                      "blocker", "next_action"):
            assert o[field]


def test_funnel_by_product_groups_events():
    events = [
        {"event_name": "cta_click", "metadata": {"product_id": "prod_L2MmMKYlE9LAv"}},
        {"event_name": "checkout_started", "metadata": {"product_id": "prod_L2MmMKYlE9LAv"}},
        {"event_name": "checkout_completed", "metadata": {"product_id": "prod_L2MmMKYlE9LAv"}},
        {"event_name": "landing_view", "metadata": {}},
    ]
    grouped = wpi.funnel_by_product(events)
    audit = grouped["prod_L2MmMKYlE9LAv"]
    assert audit["checkout_started"] == 1
    assert audit["purchase"] == 1                    # alias handled
    assert grouped["unattributed"]["landing_view"] == 1
