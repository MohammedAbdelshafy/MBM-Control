"""
Zero-Simulation Law enforcement tests (OX ALPHA vNEXT §1, §2, §12, §14).
=========================================================================
Guards:
  - no_simulated_outcomes: production code paths cannot fabricate
    MEETING_BOOKED / CONNECTED / QUALIFIED / PROPOSAL_SENT / PAYMENT.
  - real_disposition_required: canonical model rejects synthetic dispositions.
  - revenue_event_required: payments/revenue exist only with event evidence.
  - dialer_outcome: telephony layer never returns a fake connected status.
"""

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

LE = Path(__file__).resolve().parent.parent          # MBM/LeadEngine
ROOT = LE.parent.parent
sys.path.insert(0, str(LE))

outreach_event = importlib.import_module("outreach_event")


@pytest.fixture()
def tmp_store(tmp_path):
    return {
        "store": tmp_path / "outreach_events.jsonl",
        "review": tmp_path / "review.jsonl",
    }


# ---------------------------------------------------------------- model ----

def test_real_disposition_required_rejects_synthetic(tmp_store):
    for bad in ("MEETING_BOOKED", "INTEREST_CONFIRMED", "CONNECTED", "SIMULATED_WIN", ""):
        ev = outreach_event.OutreachEvent(
            event_id="evt_x", lead_id="L1", channel="phone",
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor="tester", disposition=bad,
        )
        with pytest.raises(outreach_event.DispositionError):
            ev.validate()


def test_canonical_event_roundtrip_and_idempotency(tmp_store):
    ev = outreach_event.OutreachEvent(
        event_id="evt_ok1", lead_id="DENTAL-GOLD-001-FAME", channel="phone",
        timestamp=datetime.now(timezone.utc).isoformat(), actor="human_operator",
        disposition="CONNECTED_DECISION_MAKER", provider="twilio_bridge",
        evidence={"call_sid": "CA123"}, source="test", campaign_id="S1", notes="real call",
    )
    outreach_event.record_event(ev, store=tmp_store["store"])
    outreach_event.record_event(ev, store=tmp_store["store"])  # idempotent
    lines = [json.loads(l) for l in tmp_store["store"].read_text(encoding="utf-8").splitlines() if l]
    assert len(lines) == 1
    assert lines[0]["disposition"] == "CONNECTED_DECISION_MAKER"


def test_funnel_counts_only_count_allowed_dispositions():
    events = [
        {"disposition": "NO_ANSWER"},
        {"disposition": "VOICEMAIL"},
        {"disposition": "WRONG_NUMBER"},
        {"disposition": "WRONG_PARTY"},
        {"disposition": "CONNECTED_OWNER"},
        {"disposition": "QUALIFIED"},
        {"disposition": "APPOINTMENT_BOOKED"},
        {"disposition": "OFFER_SENT"},
        {"disposition": "PAYMENT_RECEIVED"},   # commercial: not a call attempt
    ]
    c = outreach_event.funnel_counts(events)
    assert c["calls_attempted"] == 7
    assert c["conversations"] == 3
    assert c["wrong_numbers"] == 1 and c["wrong_parties"] == 1
    assert c["qualified"] == 1 and c["appointments"] == 1  # each counts as conversation AND stage
    assert c["offers_sent"] == 1


# ------------------------------------------------- gtm_production_runner ---

def test_no_simulated_outcomes_in_production_runner():
    src = (LE / "gtm_production_runner.py").read_text(encoding="utf-8")
    assert "simulated_outcome" not in src, "simulated_outcome path must not exist"
    assert 'or "INTEREST_CONFIRMED"' not in src


def test_no_fabricated_outcomes_in_voice_agent_dispatch():
    """Phase 12 (2026-08-26): the voice dispatcher once generated random
    appointment_booked / sentiment / 'strong interest' summaries on calls
    that were never placed. It must stay fail-closed: QUEUED + no outcomes
    until a real provider webhook delivers evidence."""
    import re as _re
    src = (LE / "voice_agent_dispatch.py").read_text(encoding="utf-8")
    assert "simulated_outcome" not in src
    assert not _re.search(r"random\.(choice|randint|uniform)\([^\n]*appointment", src)
    assert "strong interest in" not in src
    assert '"outcome": None' in src


def test_batch_run_yields_zero_commercial_outcomes_without_events(tmp_path, monkeypatch):
    """A fresh environment with no events must produce zero meetings/proposals."""
    import gtm_production_runner as gpr

    monkeypatch.setattr(outreach_event, "load_events", lambda *a, **k: [])
    runner = object.__new__(gpr.GtmProductionRunner)  # skip heavy init
    queue = [{"id": f"L{i}", "intent_tier": "HOT"} for i in range(10)]
    metrics = gpr.GtmProductionRunner.generate_production_report(runner, queue, [])

    f = metrics["funnel"]
    assert f["contacted"] == 0 and f["connected"] == 0
    assert f["meetings_booked"] == 0 and f["proposals_sent"] == 0 and f["deals_won"] == 0
    assert metrics["revenue"]["pipeline_value_usd"] == 0.0


def test_apply_disposition_validates_via_canonical_model(tmp_path, monkeypatch):
    """apply_disposition must refuse non-canonical outcomes."""
    import gtm_production_runner as gpr
    monkeypatch.setattr("MBM.LeadEngine.gtm_production_runner._revenue_events", lambda: [])
    runner = object.__new__(gpr.GtmProductionRunner)
    opp = {"id": "X1", "company": "C", "recommended_channel": "PHONE"}
    with pytest.raises(Exception):
        gpr.GtmProductionRunner.apply_disposition(runner, opp, "MEETING_BOOKED")


# ------------------------------------------------------ cycle_3 A/B test --

def test_cycle_3_ab_reports_not_measured_without_real_data(monkeypatch):
    sys.path.insert(0, str(LE))
    import cycle_3_winner_expansion as c3

    monkeypatch.setattr(
        outreach_event, "import_legacy_dispositions", lambda *a, **k: {"imported": 0, "review": 0}
    )
    monkeypatch.setattr(outreach_event, "load_events", lambda *a, **k: [])
    inst = object.__new__(c3.Cycle3WinnerExpansion)
    result = c3.Cycle3WinnerExpansion._run_ab_experiment(inst, cohort=[{"id": f"E{i}"} for i in range(50)])
    assert result["control"]["calls"] == 0 and result["control"]["connections"] == 0
    assert result["test"]["demos"] == 0
    assert "NOT_MEASURED" in result["statistical_lift"]["scientific_conclusion"]
    assert "+20.3%" not in json.dumps(result)


def test_cycle_3_source_has_no_index_outcomes():
    src = (LE / "cycle_3_winner_expansion.py").read_text(encoding="utf-8")
    assert "lead_idx in (" not in src, "index-based outcome assignment must be gone"
    assert "78.6% vs 58.3%" not in src


# ------------------------------------------------------------ free dialer -

def test_dialer_never_returns_fake_connected(monkeypatch):
    sys.path.insert(0, str(LE))
    free_dialer = importlib.reload(importlib.import_module("free_us_phone_dialer"))

    monkeypatch.setattr(free_dialer, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(free_dialer, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(free_dialer, "TWILIO_PHONE_NUMBER", "")

    res = free_dialer.place_outbound_call("+12145550123")
    assert res["status"] == "TELEPHONY_BLOCKED"
    assert res["call_placed"] is False

    status = free_dialer.telephony_status()
    assert status["status"] == "TELEPHONY_BLOCKED"
    src = (LE / "free_us_phone_dialer.py").read_text(encoding="utf-8")
    assert "connected_webrtc" not in src
    assert "minutes_used" not in src and "free_calling_minutes_remaining" not in src


# --------------------------------------------- server fake endpoints gone -

def test_server_has_no_fake_webrtc_place_call():
    src = (ROOT / "server" / "index.js").read_text(encoding="utf-8")
    assert "'connected_webrtc'" not in src.replace('"connected_webrtc"', "'connected_webrtc'") or "status: 'connected_webrtc'" not in src
    assert "free_trial_credit_usd" not in src
    assert "free_calling_minutes_remaining" not in src


# ------------------------------------------------------- revenue gating ---

def test_revenue_event_required_for_payments(tmp_path):
    """Scoreboard counts payments ONLY from revenue event rows."""
    import revenue_scoreboard as rs

    empty_rev = tmp_path / "revenue_events.jsonl"
    monkey_target = rs.REVENUE_EVENTS
    try:
        rs.REVENUE_EVENTS = empty_rev
        board = rs.build("2099-01-01")
        assert board["payments"] == 0 and board["revenue"] == 0.0
        assert board["calls_attempted"] == 0
    finally:
        rs.REVENUE_EVENTS = monkey_target


def test_scoreboard_ignores_zero_amount_payment_rows(tmp_path):
    import revenue_scoreboard as rs
    rev = tmp_path / "rev.jsonl"
    day = "2099-01-01"
    rows = [
        {"event_id": "e1", "event_name": "purchase", "amount_usd": 149.0,
         "timestamp": f"{day}T10:00:00Z"},
        {"event_id": "e2", "event_name": "purchase", "amount_usd": None,
         "timestamp": f"{day}T11:00:00Z"},   # zero/unknown amount: not money yet
        {"event_id": "e3", "event_name": "purchase", "amount_usd": 97.0,
         "timestamp": "2098-01-01T00:00:00Z"},  # different day
    ]
    rev.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    orig = rs.REVENUE_EVENTS
    try:
        rs.REVENUE_EVENTS = rev
        board = rs.build(day)
        assert board["payments"] == 1 and board["revenue"] == 149.0
    finally:
        rs.REVENUE_EVENTS = orig


# ---------------------------------------------------- brief fixture ban ---

def test_quick_brief_biggest_win_has_no_fixture_fallbacks():
    from gtm_quick_brief import GtmQuickBrief  # noqa: F401  (import proves it loads)
    src = (LE / "gtm_quick_brief.py").read_text(encoding="utf-8")
    assert "Apex Mechanical" not in src.split("_build_preview")[0] or "_determine_biggest_win" in src
    win_src = src[src.index("_determine_biggest_win"):src.index("def _determine_next_moves")]
    assert "Apex" not in win_src
    assert ", 4000.0" not in win_src
    assert 'return ""' in win_src


def test_legacy_answered_import_never_becomes_connected(tmp_store):
    close_log = tmp_store["store"].parent / "close.json"
    rows = [{
        "timestamp": "2026-08-20T10:00:00+00:00", "phone": "+12145550100",
        "company": "TEST CO", "outcome": "answered", "detail": "manual",
    }]
    close_log.write_text(json.dumps(rows), encoding="utf-8")
    stats = outreach_event.import_legacy_dispositions(
        store=tmp_store["store"], review_path=tmp_store["review"],
        close_log=close_log, call_log=tmp_store["store"].parent / "nope.json",
    )
    assert stats["imported"] == 0 and stats["review"] == 1
    events = outreach_event.load_events(store=tmp_store["store"])
    assert all(e["disposition"] not in outreach_event.CONVERSATION_DISPOSITIONS for e in events)
