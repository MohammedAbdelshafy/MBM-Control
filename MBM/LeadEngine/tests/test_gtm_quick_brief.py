"""Hermetic tests for the GTM Quick Brief Center (daily brief, email center, meeting center)."""

import json
import pytest

import MBM.LeadEngine.gtm_quick_brief as qb_module
from MBM.LeadEngine.gtm_quick_brief import (
    GtmQuickBrief,
    GtmEmailCenter,
    GtmMeetingCenter,
)


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    """Point the quick brief at a hermetic tmp artifacts tree and seed real-state fixtures."""
    a = tmp_path / "Artifacts"
    (a / "GTM" / "daily").mkdir(parents=True)
    (a / "GTM" / "meetings").mkdir(parents=True)
    (a / "GTM" / "email").mkdir(parents=True)

    factory = {
        "date": "2026-08-16",
        "target": 100,
        "verified": 127,
        "callable": 127,
        "new_today": 127,
        "hot": 34,
        "high": 46,
        "warm": 47,
        "shortfall": 0,
        "duplicates_filtered": 60,
        "verification_rate_pct": 28.6,
        "pipeline_value_usd": 329100.0,
    }
    (a / "daily_lead_factory_2026-08-16.json").write_text(json.dumps(factory), encoding="utf-8")

    metrics = {
        "funnel": {
            "contacted": 42, "connected": 19, "qualified": 8,
            "meetings_booked": 3, "proposals_sent": 2, "deals_won": 0,
        },
        "revenue": {
            "pipeline_value_usd": 16000.0, "expected_value_usd": 6400.0,
            "confirmed_realized_usd": 0.0,
        },
        "quality_metrics": {"human_review_required": 1},
    }
    (a / "gtm_production_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    queue = [
        {"rank": 1, "company": "Apex Mechanical", "decision_maker": "Marcus Vance",
         "recommended_channel": "PHONE", "priority": 20.4,
         "contactability": {"phone": "+12148849120"}, "id": "apex"},
        {"rank": 2, "company": "Vanguard Roofing", "decision_maker": "Derek Holloway",
         "recommended_channel": "EMAIL", "priority": 18.1,
         "contactability": {"phone": "+18175591024"}, "id": "vanguard"},
        {"rank": 3, "company": "Premier Smile", "decision_maker": "Dr. Sarah Lin",
         "recommended_channel": "MEETING", "priority": 16.0,
         "contactability": {"phone": "+19726658140"}, "id": "premier"},
    ]
    (a / "GTM_TOP25_EXECUTION_QUEUE.json").write_text(json.dumps(queue), encoding="utf-8")

    monkeypatch.setattr(qb_module, "ARTIFACTS_DIR", a)
    monkeypatch.setattr(qb_module, "GTM_ARTIFACTS_DIR", a / "GTM")
    monkeypatch.setattr(qb_module, "DAILY_DIR", a / "GTM" / "daily")
    monkeypatch.setattr(qb_module, "MEETINGS_DIR", a / "GTM" / "meetings")
    monkeypatch.setattr(qb_module, "EMAIL_DIR", a / "GTM" / "email")
    monkeypatch.setattr(qb_module, "EMAIL_STATE_PATH", a / "GTM" / "email" / "state.json")
    monkeypatch.setattr(qb_module, "MEETING_INDEX_PATH", a / "GTM" / "meetings" / "index.json")
    return a


def make_brief(artifacts):
    qb = GtmQuickBrief()
    qb.email_center = GtmEmailCenter(artifacts / "GTM" / "email" / "state.json")
    qb.meeting_center = GtmMeetingCenter(artifacts / "GTM" / "meetings" / "index.json", artifacts / "GTM" / "meetings")
    return qb


# ---------------------------------------------------------------------------
# Daily brief — numbers come from real fixtures, never invented
# ---------------------------------------------------------------------------

def test_collect_state_uses_real_artifacts(artifacts):
    b = make_brief(artifacts).collect_state()
    leads = b["daily"]["leads"]
    assert leads["verified"] == 127
    assert leads["hot"] == 34
    assert leads["high"] == 46
    assert leads["warm"] == 47
    calling = b["daily"]["calling"]
    assert calling["attempted"] == 42
    assert calling["connected"] == 19
    assert calling["qualified"] == 8
    pipeline = b["daily"]["pipeline"]
    assert pipeline["proposals"] == 2
    assert pipeline["expected_value_usd"] == 6400.0
    assert pipeline["confirmed_revenue_usd"] == 0.0
    assert b["top_actions"][0]["company"] == "Apex Mechanical"


def test_daily_md_format(artifacts):
    md = make_brief(artifacts).render_daily_md()
    assert "🚀 MBM GTM DAILY BRIEF" in md
    assert "127 new verified" in md
    assert "34 HOT" in md and "46 HIGH" in md and "47 WARM" in md
    assert "42 attempted" in md
    assert "19 connected" in md
    assert "3 booked" in md
    assert "2 proposals" in md
    assert "expected value $6,400.00" in md
    assert "1 verification failures" in md


def test_email_format(artifacts):
    email = make_brief(artifacts).render_email_daily()
    assert "# MBM GTM Daily Brief" in email
    assert "127 (34 HOT / 46 HIGH / 47 WARM)" in email
    assert "Top Actions" in email
    assert "Apex Mechanical" in email


def test_generate_daily_writes_artifacts(artifacts):
    b = make_brief(artifacts).generate_daily(notify=False)
    day = b["date"]
    assert (artifacts / "GTM" / "daily" / f"{day}.md").exists()
    assert (artifacts / "GTM" / "daily" / f"{day}.json").exists()
    assert (artifacts / "GTM" / "daily" / "latest.json").exists()
    data = json.loads((artifacts / "GTM" / "daily" / "latest.json").read_text(encoding="utf-8"))
    assert data["daily"]["leads"]["verified"] == 127


def test_missing_factory_reports_zeros(tmp_path, monkeypatch):
    a = tmp_path / "Artifacts"
    (a / "GTM" / "daily").mkdir(parents=True)
    monkeypatch.setattr(qb_module, "ARTIFACTS_DIR", a)
    monkeypatch.setattr(qb_module, "GTM_ARTIFACTS_DIR", a / "GTM")
    monkeypatch.setattr(qb_module, "DAILY_DIR", a / "GTM" / "daily")
    qb = GtmQuickBrief()
    qb.email_center = GtmEmailCenter(a / "GTM" / "email" / "state.json")
    qb.meeting_center = GtmMeetingCenter(a / "GTM" / "meetings" / "index.json", a / "GTM" / "meetings")
    b = qb.collect_state()
    # No artifacts -> honest zeros, no invented metrics.
    assert b["daily"]["leads"]["verified"] == 0
    assert b["daily"]["calling"]["attempted"] == 0
    assert b["daily"]["pipeline"]["confirmed_revenue_usd"] == 0.0
    assert b["top_actions"] == []


# ---------------------------------------------------------------------------
# Daily target contract
# ---------------------------------------------------------------------------

def test_daily_target_reached(artifacts):
    result = make_brief(artifacts).evaluate_daily_target()
    assert result["event"] == "DAILY_TARGET_REACHED"
    assert result["actual"] == 127
    assert result["target"] == 100
    assert result["reached"] is True


def test_daily_target_missed(artifacts):
    factory = {"date": "2026-08-16", "target": 150, "verified": 80, "shortfall": 70,
               "verification_rate_pct": 20.0}
    (artifacts / "daily_lead_factory_2026-08-16.json").write_text(json.dumps(factory), encoding="utf-8")
    result = make_brief(artifacts).evaluate_daily_target()
    assert result["event"] == "DAILY_TARGET_MISSED"
    assert result["shortfall"] == 70
    assert result["reached"] is False
    assert "GEOGRAPHIC_REGIONS" in result["best_next_search_expansion"]


# ---------------------------------------------------------------------------
# Email Center — idempotent counters
# ---------------------------------------------------------------------------

def test_email_center_idempotent(tmp_path):
    ec = GtmEmailCenter(tmp_path / "email_state.json")
    ec.record_event("sent", message_id="m1", company="A")
    ec.record_event("replied", message_id="m1", company="A")
    ec.record_event("positive", message_id="m1", company="A")
    # Re-running the same event is a no-op.
    ec.record_event("positive", message_id="m1", company="A")
    c = ec.counters()
    assert c["sent"] == 1
    assert c["replied"] == 1
    assert c["positive"] == 1
    assert c["bounce"] == 0


def test_email_center_counts_types(tmp_path):
    ec = GtmEmailCenter(tmp_path / "email_state.json")
    ec.record_event("prepared", message_id="p1")
    ec.record_event("approved", message_id="p1")
    ec.record_event("sent", message_id="p1")
    ec.record_event("bounce", message_id="p1")
    ec.record_event("opt_out", message_id="p1")
    ec.record_event("followup_due", message_id="p1")
    c = ec.summary()
    assert c["prepared"] == 1
    assert c["approved"] == 1
    assert c["sent"] == 1
    assert c["bounce"] == 1
    assert c["opt_out"] == 1
    assert c["followup_due"] == 1


# ---------------------------------------------------------------------------
# Meeting Center
# ---------------------------------------------------------------------------

def test_meeting_center_writes_md_and_json(tmp_path):
    mc = GtmMeetingCenter(tmp_path / "index.json", tmp_path)
    mc.upsert({
        "company": "Premier Smile Partners",
        "buyer": "Dr. Sarah Lin",
        "role": "Practice Owner",
        "date": "2026-08-17",
        "time": "10:30 AM",
        "pain": "Overdue recall hygiene patients",
        "ai_fit": "AI Recall / Front Desk Assistant",
        "ROI_hypothesis": "Recovers $12k/mo recall revenue",
    })
    assert (tmp_path / "meeting_premier_smile_partners.json").exists()
    assert (tmp_path / "meeting_premier_smile_partners.md").exists()
    md = (tmp_path / "meeting_premier_smile_partners.md").read_text(encoding="utf-8")
    assert "Premier Smile Partners" in md
    assert "2026-08-17 10:30 AM" in md
    assert mc.briefs_ready() == 0  # explicit upsert does not imply a source brief


def test_meeting_center_sync_imports_briefs(tmp_path):
    mc = GtmMeetingCenter(tmp_path / "index.json", tmp_path)
    (tmp_path / "meeting_brief_apex_mechanical.md").write_text(
        "# Executive Discovery & Meeting Brief: Apex Mechanical\n\n"
        "**Meeting With:** Marcus Vance (Founder)  \n"
        "**Observed Problem:** After-hours calls missed  \n"
        "**Why Now:** Hiring weekend dispatcher  \n"
        "**Assistant Package:** 24/7 AI Emergency Call Answering & Dispatch\n",
        encoding="utf-8",
    )
    added = mc.sync_from_artifacts(briefs_dir=tmp_path, prod_report_path=tmp_path / "missing_report.md")
    assert added == 1
    meetings = mc.meetings()
    assert meetings[0]["company"] == "Apex Mechanical"
    assert meetings[0]["buyer"] == "Marcus Vance"
    assert meetings[0]["brief_ready"] is True
    assert mc.briefs_ready() == 1