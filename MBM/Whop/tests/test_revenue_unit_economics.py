"""Tests for revenue_unit_economics.py — hermetic; UNKNOWN until REAL evidence."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "revenue_unit_economics.py"
spec = importlib.util.spec_from_file_location("rue", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules.setdefault("rue", mod)
spec.loader.exec_module(mod)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    data = tmp_path / "data"
    logs.mkdir(); data.mkdir()
    monkeypatch.setattr(mod, "EVENTS_FILE", logs / "revenue_events.jsonl")
    monkeypatch.setattr(mod, "LEDGER", data / "unit_economics.jsonl")
    monkeypatch.setattr(mod, "DATA_DIR", data)
    return mod


def _real_purchase(path, event_id="evt_real_1"):
    path.write_text(json.dumps({
        "schema_version": 1, "event_id": event_id, "event_name": "purchase",
        "source": "whop_webhook", "amount_usd": 149,
        "metadata": {"action": "payment.succeeded"}}) + "\n", encoding="utf-8")


def test_blank_is_fully_unknown(env):
    b = mod.blank()
    unknown_keys = ["sale_price", "payment_fee", "AI_cost", "API_cost",
                    "labor_minutes", "labor_cost", "delivery_cost", "refund",
                    "net_revenue", "gross_margin"]
    assert all(b[k] == "UNKNOWN" for k in unknown_keys)
    assert b["provenance"] == "NO_FIRST_DELIVERY_EVIDENCE"


def test_show_before_first_delivery_reports_unknown(env):
    result = mod.show()
    assert result["sale_price"] == "UNKNOWN"
    assert result["net_revenue"] == "UNKNOWN"


def test_record_refuses_unverified_event_id(env):
    with pytest.raises(SystemExit):
        mod.record("evt_never_happened")


def test_record_refuses_smoke_event_id(env):
    _real_purchase(mod.EVENTS_FILE, "smoke_999")
    with pytest.raises(SystemExit):
        mod.record("smoke_999")


def test_record_with_full_actuals_computes_margin(env):
    _real_purchase(mod.EVENTS_FILE)
    rec = mod.record("evt_real_1", payment_fee=5.5, ai_cost=0.4, api_cost=0.0,
                     labor_minutes=90, labor_cost=0.0)
    # 149 - 5.5 - 0.4 - 0 - 0(delivery) - 0(refund) - 0(labor) = 143.10
    assert rec["net_revenue"] == 143.1
    assert rec["classification"] == "REAL"
    assert rec["gross_margin"].endswith("%")


def test_partial_actuals_stay_unknown(env):
    _real_purchase(mod.EVENTS_FILE)
    rec = mod.record("evt_real_1", payment_fee="UNKNOWN")
    assert rec["net_revenue"] == "UNKNOWN"
    assert rec["gross_margin"] == "UNKNOWN"
