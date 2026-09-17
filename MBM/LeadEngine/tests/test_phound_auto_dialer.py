"""
test_phound_auto_dialer.py - Auto-Dial Execution Suite (Issue #43)
====================================================================
Covers: duplicate-worker protection, cooldown/caps, DNC/closed filtering,
restart recovery (reconcile), DRY_RUN safety, unknown-state safety,
aftercall persistence via lifecycle events, and ANDROID_SIM_ASSISTED
human-gating (#44: never auto-advances).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE.parent.parent))

from MBM.LeadEngine import phound_auto_dialer as ad


def _lead(lid, **kw):
    # NOTE: fixtures must pass the real verification gate: E.164 number with
    # a non-555 exchange, a real two-word name, NPI source + NPI number proof.
    lead = {"id": lid, "contact_name": "Maria Santos", "phone": "+12137773456",
            "source": "NPI", "status": "QUEUED_FOR_AI_AGENT", "vertical": "Clinics",
            "npi_number": "1234567890", "call_count": 0}
    lead.update(kw)
    return lead


def _patch_state(testcase, state_overrides=None):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    state_file = Path(tmp.name) / "state.json"
    attempts_file = Path(tmp.name) / "attempts.jsonl"
    state = ad._default_state()
    if state_overrides:
        state.update(state_overrides)
    state_file.write_text(json.dumps(state), encoding="utf-8")
    p1 = patch.object(ad, "STATE_FILE", state_file)
    p2 = patch.object(ad, "ATTEMPTS_FILE", attempts_file)
    p1.start()
    p2.start()
    testcase.addCleanup(p1.stop)
    testcase.addCleanup(p2.stop)
    return state_file


class TestQueueBuilding(unittest.TestCase):
    def setUp(self):
        _patch_state(self)

    def test_gate_filters_unverified(self):
        queue, qa = ad.build_queue([_lead("A"), {"id": "B", "phone": "555-1234",
                                                 "contact_name": "x"}])
        self.assertEqual([l["id"] for l in queue], ["A"])
        self.assertEqual(qa["gate_rejected"], 1)

    def test_dnc_and_closed_filtered(self):
        leads = [_lead("OK"),
                 _lead("OPT", opted_out=True),
                 _lead("DEAD1", disposition="DEAD"),
                 _lead("DNC1", status="DNC")]
        queue, qa = ad.build_queue(leads)
        self.assertEqual([l["id"] for l in queue], ["OK"])
        self.assertGreaterEqual(qa["optout_closed_inflight_skipped"], 3)

    def test_inflight_excluded(self):
        _patch_state(self)  # fresh tmp pair
        state = ad.load_state()
        state["in_flight"] = {"A": {"request_id": "r1"}}
        ad.save_state(state)
        queue, _ = ad.build_queue([_lead("A"), _lead("B")])
        self.assertEqual([l["id"] for l in queue], ["B"])


class TestExecutionSafety(unittest.TestCase):
    def setUp(self):
        _patch_state(self)
        self.provider = MagicMock()
        self.provider.health.return_value = {"mode": "native_app"}
        self.provider.place_call.return_value = {"status": "dry_run_simulated",
                                                 "provider": "phound"}

    def _dialer(self, **kw):
        args = {"mode": "ASSISTED", "provider": self.provider, "dry_run": True,
                "persona_uid": "P1", "cooldown_seconds": 3600}
        args.update(kw)
        d = ad.AutoDialer(**args)
        d.adapter = MagicMock()
        return d

    def test_duplicate_worker_suppressed(self):
        # Live-mode native fallback keeps the lead in-flight until a
        # lifecycle event completes it; a second worker must be suppressed.
        self.provider.place_call.return_value = {"status": "native_app",
                                                 "provider": "phound"}
        d = self._dialer(dry_run=False)
        state = ad.load_state()
        first = d.execute_one(_lead("D1"), state)
        second = d.execute_one(_lead("D1"), state)
        self.assertEqual(first.get("status"), "native_app")
        self.assertEqual(second["status"], "duplicate_suppressed")
        self.provider.place_call.assert_called_once()  # placed exactly once

    def test_cooldown_skip(self):
        d = self._dialer()
        state = ad.load_state()
        d.execute_one(_lead("C1"), state)
        ad.save_state(state)
        state2 = ad.load_state()
        out = d.execute_one(_lead("C1"), state2)
        self.assertEqual(out["status"], "skipped_cooldown")
        self.provider.place_call.assert_called_once()

    def test_dry_run_never_calls_provider_live(self):
        d = self._dialer()
        state = ad.load_state()
        d.execute_one(_lead("S1"), state)
        _, kwargs = self.provider.place_call.call_args
        self.assertTrue(kwargs.get("dry_run"))

    def test_unknown_state_counts_failed(self):
        self.provider.place_call.return_value = {"status": "unknown_provider_state",
                                                 "provider": "phound",
                                                 "reconciliation_required": True}
        d = self._dialer()
        state = ad.load_state()
        out = d.execute_one(_lead("U1"), state)
        self.assertEqual(out["status"], "unknown_provider_state")
        self.assertEqual(state["session_counts"]["failed"], 1)
        self.assertNotIn("U1", state["in_flight"])

    def test_session_cap_stops(self):
        d = self._dialer(session_cap=1)
        state = ad.load_state()
        out = d.run([_lead("E1"), _lead("E2")])
        statuses = [o.get("status") for o in out["outcomes"]]
        self.assertTrue(any(str(s).startswith("session_stopped") for s in statuses))

    def test_auto_dial_refuses_without_approval(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHOUND_AUTODIAL_APPROVED", None)
            d = ad.AutoDialer(mode="AUTO_DIAL", provider=self.provider,
                              dry_run=True, persona_uid="P1")
            d.adapter = MagicMock()
            cap = d.capability_check()
            self.assertFalse(cap["allowed"])
            out = d.run([_lead("G1")])
            self.assertEqual(out["mode"], "ASSISTED")

    def test_android_mode_never_places_api_call(self):
        d = self._dialer(mode="ANDROID_SIM_ASSISTED")
        state = ad.load_state()
        out = d.execute_one(_lead("AN1"), state)
        self.assertEqual(out["status"], "handoff_presented")
        self.assertTrue(out["handoff"].startswith("tel:"))
        self.provider.place_call.assert_not_called()
        self.assertNotIn("AN1", state["in_flight"])


class TestRecoveryAndEvents(unittest.TestCase):
    def test_reconcile_flags_inflight(self):
        _patch_state(self)
        state = ad.load_state()
        state["in_flight"] = {"Z1": {"request_id": "r1", "started_at": ad.utcnow()}}
        ad.save_state(state)
        out = ad.reconcile()
        self.assertEqual(out["reconciled"], 1)
        self.assertEqual(out["flagged"][0]["status"], "unknown_provider_state")
        self.assertEqual(ad.load_state()["in_flight"], {})

    def test_lifecycle_event_clears_inflight(self):
        _patch_state(self)
        provider = MagicMock()
        provider.ingest_event.return_value = {"status": "event_recorded",
                                              "handed_to_aftercall": True}
        d = ad.AutoDialer(mode="ASSISTED", provider=provider, dry_run=True,
                          persona_uid="P1")
        d.adapter = MagicMock()
        state = ad.load_state()
        state["in_flight"] = {"H1": {"request_id": "r1"}}
        ad.save_state(state)
        d.handle_event({"lead_id": "H1", "lifecycle_status": "completed"})
        self.assertNotIn("H1", ad.load_state()["in_flight"])


if __name__ == "__main__":
    unittest.main()
