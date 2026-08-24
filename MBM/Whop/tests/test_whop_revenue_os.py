"""Hermetic tests for the Whop Revenue OS core (no network, no live API).

Run:  python -m pytest MBM/Whop/tests -q
"""

import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

ros = importlib.import_module("whop_revenue_os")
wexp = importlib.import_module("whop_experiments")
gov = importlib.import_module("whop_governor")


# ── event store ─────────────────────────────────────────────────────────────

def _evt(name="purchase", eid=None, amount=100.0, session=None, **kw):
    return ros.make_event(name, source="test", event_id=eid, amount_usd=amount,
                          session_id=session, **kw)


def test_append_event_is_idempotent(tmp_path):
    f = tmp_path / "events.jsonl"
    e = _evt(eid="evt_fixed_1")
    assert ros.append_event(e, f) is True
    assert ros.append_event(e, f) is False          # duplicate blocked
    assert len(ros.load_events(f)) == 1


def test_event_schema_fields_present():
    e = _evt()
    for field in ("event_id", "event_name", "timestamp", "source",
                  "customer_ref", "amount_usd", "attribution", "metadata"):
        assert field in e


def test_make_event_deterministic_id_for_same_inputs():
    ts = "2026-08-24T00:00:00+00:00"
    a = ros.make_event("purchase", "webhook", timestamp=ts)
    b = ros.make_event("purchase", "webhook", timestamp=ts)
    assert a["event_id"] == b["event_id"]


# ── webhook normalization ───────────────────────────────────────────────────

def test_normalize_payment_succeeded():
    payload = {"id": "wh_1", "action": "payment.succeeded",
               "data": {"payment": {"amount": 29700}, "member": {"user_id": "usr_1"}}}
    evt = ros.normalize_whop_webhook(payload, received_at="2026-08-24T00:00:00+00:00")
    assert evt["event_name"] == "purchase"
    assert evt["amount_usd"] == pytest.approx(297.0)   # cents -> dollars
    assert evt["customer_ref"]["user_id"] == "usr_1"


def test_normalize_unknown_action_kept_not_invented():
    evt = ros.normalize_whop_webhook({"id": "wh_2", "action": "something.unusual"})
    assert evt["event_name"] == "webhook_received"
    assert evt["metadata"]["action"] == "something.unusual"


def test_normalize_missing_amount_stays_none():
    payload = {"id": "wh_3", "action": "payment.succeeded", "data": {}}
    evt = ros.normalize_whop_webhook(payload)
    assert evt["event_name"] == "purchase"
    assert evt["amount_usd"] is None


def test_normalize_churn_and_renewal_actions():
    assert ros.normalize_whop_webhook({"action": "membership.went_invalid"})["event_name"] == "churn"
    assert ros.normalize_whop_webhook({"action": "membership.renewed"})["event_name"] == "subscription_renewed"


# ── client analytics normalization ──────────────────────────────────────────

def test_client_event_allowlist_blocks_unknown():
    assert ros.normalize_client_event({"event": "<script>alert(1)</script>"}) is None
    assert ros.normalize_client_event({"event": "totally_made_up"}) is None


def test_client_event_attribution_and_session_captured():
    body = {"event": "landing_view", "session_id": "s123",
            "utm_source": "reddit", "utm_campaign": "launch",
            "props": {"landing_variant": "B"}}
    evt = ros.normalize_client_event(body, received_at="2026-08-24T01:00:00Z")
    assert evt["attribution"]["utm_source"] == "reddit"
    assert evt["session_id"] == "s123"
    assert evt["attribution"]["landing_variant"] == "B"


def test_client_event_truncates_long_values():
    body = {"event": "signup", "session_id": "x" * 500,
            "props": {"big": "y" * 999}}
    evt = ros.normalize_client_event(body)
    assert len(evt["session_id"]) <= 64
    assert all(len(str(v)) <= 200 for v in evt["metadata"].values())


def test_legacy_analytics_ingestion_idempotent(tmp_path):
    legacy = tmp_path / "analytics_log.json"
    legacy.write_text(json.dumps([
        {"event": "cta_click", "received_at": "2026-08-23T21:42:28Z"},
        {"event": "bogus_event_name", "received_at": "2026-08-23T21:42:29Z"},
        "not-a-dict",
    ]), encoding="utf-8")
    store = tmp_path / "events.jsonl"
    rows1 = _ingest_with_paths(legacy, store)
    rows2 = _ingest_with_paths(legacy, store)
    assert rows1["appended"] >= 2           # cta_click + custom.bogus_event_name
    assert rows1["invalid"] == 1            # non-dict row counted, not crash
    assert rows2["appended"] == 0           # second pass fully deduplicated


def _ingest_with_paths(analytics_file, store_file):
    saved_a, saved_e = ros.ANALYTICS_LOG, ros.EVENTS_FILE
    ros.ANALYTICS_LOG, ros.EVENTS_FILE = analytics_file, store_file
    try:
        return ros.ingest_legacy_analytics()
    finally:
        ros.ANALYTICS_LOG, ros.EVENTS_FILE = saved_a, saved_e


# ── funnel + economics ──────────────────────────────────────────────────────

def test_funnel_math_with_aliases():
    events = [
        _evt("landing_view", session="s1"),
        _evt("cta_click", session="s1"),
        _evt("checkout_started", session="s1"),
        _evt("checkout_completed", amount=497.0, session="s1"),  # alias -> purchase
    ]
    fun = ros.compute_funnel(events)
    assert fun["counts"]["purchase"] == 1
    assert fun["overall_view_to_purchase"] == 1.0
    assert fun["step_rates"]["landing_view->cta_click"] == 1.0


def test_empty_funnel_no_division_errors():
    fun = ros.compute_funnel([])
    assert fun["counts"]["purchase"] == 0
    assert fun["overall_view_to_purchase"] is None


def test_revenue_summary_refunds_subtracted():
    events = [_evt(amount=497.0), _evt("refund", amount=97.0)]
    rev = ros.revenue_summary(events)
    assert rev["gross_revenue_usd"] == 400.0
    assert rev["aov_usd"] == 497.0


def test_unit_economics_unavailable_without_orders():
    eco = ros.unit_economics([])
    assert eco["ltv_usd"] == "UNAVAILABLE"
    assert eco["cac_usd"] == "UNAVAILABLE"
    assert eco["net_revenue_usd"] is None


def test_unit_economics_applies_configured_rates(monkeypatch):
    monkeypatch.setenv("WHOP_FEE_PCT", "3")
    monkeypatch.setenv("WHOP_AFFILIATE_PCT", "20")
    eco = ros.unit_economics([_evt(amount=100.0)])
    assert eco["net_revenue_usd"] == pytest.approx(77.0)


# ── catalog + offer matching ────────────────────────────────────────────────

def test_catalog_loads_real_spec():
    cat = ros.load_catalog()
    if not (BASE_DIR / "ai-consultancy-agency" / "whop_product_spec.json").exists():
        assert cat["provenance"] == "UNAVAILABLE"
        return
    assert cat["provenance"] == "REAL"
    sprint = next(p for p in cat["products"] if p.get("name") == "AI Consultancy Sprint")
    urls = [pl["checkout_url"] for pl in sprint["plans"]]
    assert all(u and u.startswith("https://whop.com/checkout/") for u in urls)


def test_match_offer_ranks_by_stage_and_never_invents_products():
    offers = ros.match_offer({"lifecycle_state": "UPSELL_READY"})
    assert offers and offers[0]["score"] >= offers[-1]["score"]
    assert all(o["plan_id"] or o["product_key"] for o in offers)


def test_match_offer_entry_stage_prefers_one_time():
    top = ros.match_offer({"lifecycle_state": "LEAD"})[0]
    assert top["plan_type"] == "one_time" or "audit" in top["title"].lower()


# ── NBA engine + anti-fatigue guardrails ────────────────────────────────────

def test_nba_cancelled_respects_attempt_ceiling(monkeypatch):
    monkeypatch.setattr(ros, "_engage_state", lambda: {"last_emailed": {}, "processed_ids": []})
    d = ros.get_next_best_action({"lifecycle_state": "CANCELLED", "outreach_attempts": 3})
    assert d["action"] == "DO_NOT_CONTACT"
    d2 = ros.get_next_best_action({"lifecycle_state": "CANCELLED", "outreach_attempts": 1})
    assert d2["action"] == "WINBACK"
    assert d2["max_attempts"] == ros.MAX_OUTREACH_ATTEMPTS


def test_nba_cooldown_detected_from_engage_log(monkeypatch):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    fake = {"last_emailed": {"vip@example.com": recent}, "processed_ids": []}

    class FakeEngage:
        def __getitem__(self, k):
            return fake[k]
        get = dict.get

    monkeypatch.setattr(ros, "_engage_state", lambda: fake)
    d = ros.get_next_best_action({"lifecycle_state": "UPSELL_READY",
                                  "email": "vip@example.com"}, now=now)
    assert d["in_cooldown"] is True
    assert d["cooldown_days"] == ros.OUTREACH_COOLDOWN_DAYS


def test_nba_decision_contract_complete(monkeypatch):
    monkeypatch.setattr(ros, "_engage_state", lambda: {"last_emailed": {}, "processed_ids": []})
    d = ros.get_next_best_action({"lifecycle_state": "AT_RISK"})
    for field in ("action", "reason", "evidence", "timing", "channel",
                  "offer" if False else "confidence", "governor_level"):
        assert field in d


# ── customer 360 ────────────────────────────────────────────────────────────

def test_customer360_builds_from_events(monkeypatch):
    monkeypatch.setattr(ros, "_memberships_latest", lambda: [])
    buyer = ros.make_event("purchase", source="whop_webhook",
                           customer_ref={"user_id": "usr_9"}, amount_usd=1497.0)
    churn = ros.make_event("churn", source="whop_webhook",
                           customer_ref={"user_id": "usr_9"})
    monkeypatch.setattr(ros, "load_events", lambda: [buyer, churn])
    customers = {c["identity"]["customer_id"]: c for c in ros.build_customer_360()}
    c = customers["usr_9"]
    assert c["revenue_usd"] == 1497.0
    assert c["lifecycle_state"] == "CANCELLED"
    assert c["churn_risk"] == 0.9
    assert "next_best_action" in c


def test_health_score_bounded_and_reasoned():
    s, reasons = ros.health_score({"stage": "churned", "status": "expired"})
    assert 0 <= s <= 100 and reasons
    s2, _ = ros.health_score({"stage": "stable", "status": "active"})
    assert s2 > s


# ── opportunities ───────────────────────────────────────────────────────────

def test_opportunity_abandoned_checkout_has_evidence_and_caps(monkeypatch):
    starts = [_evt("checkout_started", session=f"s{i}") for i in range(3)]
    monkeypatch.setattr(ros, "load_events", lambda: starts)
    ops = ros.identify_revenue_opportunities()
    op = next(o for o in ops if o["type"] == "abandoned_checkout_recovery")
    assert op["count"] == 3
    assert str(ros.EVENTS_FILE) in op["evidence"]
    assert op["estimated_value"] == "UNAVAILABLE"   # no basket value captured


def test_opportunity_funnel_top_leak_when_zero_checkouts(monkeypatch):
    views = [_evt("landing_view") for _ in range(25)]
    monkeypatch.setattr(ros, "load_events", lambda: views)
    monkeypatch.setattr(ros, "build_customer_360", lambda: [])
    ops = ros.identify_revenue_opportunities()
    assert any(o["type"] == "funnel_top_leak_no_checkouts" for o in ops)


# ── experiments ─────────────────────────────────────────────────────────────

@pytest.fixture()
def exp_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(wexp, "REGISTRY_FILE", tmp_path / "experiments.json")
    monkeypatch.setattr(wexp, "EVENTS_FILE", tmp_path / "missing.jsonl")
    return wexp


def test_experiment_assignment_is_sticky(exp_registry):
    wexp.create_experiment("t1", "hypothesis", "A", ["B"])
    v1 = wexp.assign_variant("t1", "unit-x")
    v2 = wexp.assign_variant("t1", "unit-x")
    assert v1 == v2 and v1 in ("A", "B")


def test_experiment_verdict_inconclusive_on_small_sample(exp_registry):
    wexp.create_experiment("t2", "hypothesis", "A", ["B"], min_sample=100, min_days=7)
    res = wexp.analyze_experiment("t2", events=[], now=datetime.now(timezone.utc))
    assert res["verdict"] == "INCONCLUSIVE"
    assert res["why"]


def test_experiment_leader_requires_full_gates(exp_registry):
    wexp.create_experiment("t3", "hypothesis", "A", ["B"], min_sample=2, min_days=0)
    started = datetime.now(timezone.utc) - timedelta(days=10)

    reg = json.loads(wexp.REGISTRY_FILE.read_text())
    reg["experiments"]["t3"]["start"] = started.isoformat()
    wexp.REGISTRY_FILE.write_text(json.dumps(reg))

    events = []
    for i in range(5):
        events.append(ros.make_event("landing_view", source="landing",
                                     attribution={"landing_variant": "A"}))
        events.append(ros.make_event("cta_click", source="landing",
                                     attribution={"landing_variant": "A"}))
        events.append(ros.make_event("landing_view", source="landing",
                                     attribution={"landing_variant": "B"}))
    res = wexp.analyze_experiment("t3", events=events, now=datetime.now(timezone.utc))
    assert res["verdict"].startswith("LEADER=")
    assert res["verdict"] == "LEADER=A"      # A converts at 100%, B at 0%


# ── governor ────────────────────────────────────────────────────────────────

def test_sensitive_kinds_floored_at_l3_or_higher(tmp_path, monkeypatch):
    monkeypatch.setattr(gov, "QUEUE_FILE", tmp_path / "queue.jsonl")
    for kind in gov.SENSITIVE_FLOOR:
        entry = gov.propose(kind, {"x": 1}, requested_level=0)
        assert entry["level"] >= gov.SENSITIVE_FLOOR[kind]
        assert entry["status"] != "executed"


def test_execution_requires_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(gov, "QUEUE_FILE", tmp_path / "queue.jsonl")
    entry = gov.propose("mass_campaign", {"audience": "all_members"})
    assert gov.is_execution_approved(entry["action_id"]) is False
    gov.override(entry["action_id"], "approve", actor="omar", reason="ok for launch")
    assert gov.is_execution_approved(entry["action_id"]) is True
    gov.override(entry["action_id"], "pause", actor="omar", reason="hold")
    assert gov.is_execution_approved(entry["action_id"]) is False


def test_override_records_actor_timestamp_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(gov, "QUEUE_FILE", tmp_path / "queue.jsonl")
    entry = gov.propose("price_change", {"plan": "managed_growth", "to": 597})
    rec = gov.override(entry["action_id"], "reject", actor="qa_bot",
                       reason="margin check failed")
    assert rec["actor"] == "qa_bot" and rec["reason"] and rec["timestamp"]
