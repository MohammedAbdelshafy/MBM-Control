"""Tests for whop_first_revenue_campaign.py — hermetic (tmp dirs, no network)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "whop_first_revenue_campaign.py"
spec = importlib.util.spec_from_file_location("wfr_campaign", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules.setdefault("wfr_campaign", mod)
spec.loader.exec_module(mod)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    queue = tmp_path / "queue.json"
    rows = [
        {"rank": 1, "id": "c1", "company": "Clinic One", "decision_maker": "JANE DOE",
         "role": "owner", "pain": "Front desk overload.", "why_now": "hiring",
         "recommended_channel": "PHONE", "phone": "+1 (214) 555-0100"},
        {"rank": 2, "id": "c2", "company": "Clinic Two", "decision_maker": "BOB ROE",
         "role": "president", "pain": "Slow follow up.", "why_now": "growth",
         "recommended_channel": "PHONE", "phone": ""},
    ]
    queue.write_text(json.dumps(rows), encoding="utf-8")
    cdir = tmp_path / "campaign"
    monkeypatch.setattr(mod, "QUEUE_JSON", queue)
    monkeypatch.setattr(mod, "CAMPAIGN_DIR", cdir)
    monkeypatch.setattr(mod, "EVENTS_LOG", tmp_path / "events.jsonl")  # NEVER touch real logs
    return mod


def test_build_creates_artifacts_with_mission_schema(env):
    env.build(base_url="https://x.test", limit=None)
    d = env.CAMPAIGN_DIR
    assert (d / "campaign.json").exists()
    assert (d / "prospects.csv").exists()
    assert (d / "DAY1_PLAYBOOK.md").exists()
    assert (d / "state.json").exists()
    assert (d / "contact_log.jsonl").exists()

    import csv
    with open(d / "prospects.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    required = {"prospect_id", "business", "source", "channel", "message_key",
                "timestamp", "status", "response", "cta", "checkout_started", "purchase"}
    assert required.issubset(rows[0].keys())
    assert all(r["source"] == "CMS_NPI_REGISTRY" for r in rows)
    assert all(r["status"] == "pending" for r in rows)
    assert "utm_campaign=whop_audit_day1" in rows[0]["tracked_landing_url"]
    assert "AUDIT-01" in (d / "DAY1_PLAYBOOK.md").read_text(encoding="utf-8")


def test_build_is_idempotent(env):
    env.build(limit=2)
    s1 = json.loads((env.CAMPAIGN_DIR / "state.json").read_text(encoding="utf-8"))
    env.build(limit=2)
    s2 = json.loads((env.CAMPAIGN_DIR / "state.json").read_text(encoding="utf-8"))
    assert set(s1["prospects"]) == set(s2["prospects"])
    assert s2["prospects"]["AUDIT-01"]["created_at"] == s1["prospects"]["AUDIT-01"]["created_at"]


def test_mark_transitions_and_duplicate_guard(env):
    env.build(limit=2)
    env.mark("AUDIT-01", "contacted", note="called")
    env.mark("AUDIT-01", "replied")
    env.mark("AUDIT-01", "checkout_started")
    env.mark("AUDIT-01", "purchased")
    state = json.loads((env.CAMPAIGN_DIR / "state.json").read_text(encoding="utf-8"))
    p = state["prospects"]["AUDIT-01"]
    assert p["status"] == "purchased"
    assert p["contacted_at"] and p["responded_at"] and p["checkout_started_at"] and p["purchased_at"]

    log = (env.CAMPAIGN_DIR / "contact_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1, "contact_log must record exactly one contacted event (duplicate guard)"

    with pytest.raises(SystemExit):
        env.mark("AUDIT-01", "bogus")


def test_funnel_diagnoses_each_leak_stage(env, monkeypatch, tmp_path):
    evlog = tmp_path / "events.jsonl"
    env.build(limit=2)
    out = env.funnel()["outputs"]
    assert any("NO_TRAFFIC" in p for p in out["diagnosis"])

    env.mark("AUDIT-01", "contacted")
    out = env.funnel()["outputs"]
    assert any("NO_REPLY" in p for p in out["diagnosis"])

    env.mark("AUDIT-01", "replied")
    out = env.funnel()["outputs"]
    assert any("REPLY_NO_CHECKOUT" in p for p in out["diagnosis"])

    env.mark("AUDIT-01", "checkout_started")
    out = env.funnel()["outputs"]
    assert any("CHECKOUT_NO_PURCHASE" in p for p in out["diagnosis"])

    env.mark("AUDIT-01", "purchased")
    out = env.funnel()["outputs"]
    assert any("PURCHASE_NO_WEBHOOK" in p for p in out["diagnosis"])

    evlog.write_text(json.dumps({
        "event_id": "real_1", "event_name": "purchase",
        "source": "whop_webhook", "amount_usd": 149}) + "\n", encoding="utf-8")
    out = env.funnel()["outputs"]
    assert any("FUNNEL_HEALTHY" in p for p in out["diagnosis"])
    assert not evlog.exists() or evlog.read_text(encoding="utf-8") != ""


def test_smoke_events_never_count_as_revenue(env, tmp_path):
    evlog = tmp_path / "events.jsonl"
    evlog.parent.mkdir(parents=True, exist_ok=True)
    evlog.write_text(json.dumps({
        "event_id": "smoke_123", "event_name": "purchase",
        "source": "whop_webhook"}) + "\n", encoding="utf-8")
    out = env.funnel()["outputs"]
    assert out["webhook_real_purchases"] == 0


def test_landing_url_carries_prospect_level_attribution(env):
    u = env.landing_url("https://x.test/", "AUDIT-07")
    assert u.startswith("https://x.test/productized-service/ai-consultancy-sprint/landing.html#engines?")
    assert "utm_content=AUDIT-07" in u
