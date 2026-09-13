"""
test_phound_provider.py - Phound SDK Bridge Suite (Issue #42)
===============================================================
Covers: DRY_RUN never places calls/SMS, idempotency (duplicate-worker
protection), native-app fallback, unknown-provider-state safety,
transient-only retry classification, aftercall persistence wiring,
and no-secret leakage into records/logs.
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

from MBM.LeadEngine import phound_provider as pp


def _env(**kw):
    e = {"PHOUND_ENABLED": "false", "PHOUND_TOKEN": "",
         "PHOUND_PERSONAS": "", "PHOUND_DEFAULT_PERSONA_UID": ""}
    e.update(kw)
    return e


class TestNormalizeE164(unittest.TestCase):
    def test_valid_us(self):
        self.assertEqual(pp.normalize_e164("(212) 555-1234"), "+12125551234")

    def test_valid_e164_passthrough(self):
        self.assertEqual(pp.normalize_e164("+12125551234"), "+12125551234")

    def test_blank_raises(self):
        with self.assertRaises(ValueError):
            pp.normalize_e164("")

    def test_too_short_raises(self):
        with self.assertRaises(ValueError):
            pp.normalize_e164("123")


class TestProviderStatus(unittest.TestCase):
    def test_disabled_is_native_app(self):
        s = pp.get_provider_status(_env())
        self.assertEqual(s["mode"], "native_app")
        self.assertFalse(s["configured"])

    def test_enabled_without_token_is_not_configured(self):
        s = pp.get_provider_status(_env(PHOUND_ENABLED="true"))
        self.assertEqual(s["mode"], "native_app")
        self.assertIn("PHOUND_TOKEN", s["error"])

    def test_enabled_with_token_and_persona_is_api(self):
        s = pp.get_provider_status(_env(PHOUND_ENABLED="true",
                                        PHOUND_TOKEN="uid123.apikey456",
                                        PHOUND_DEFAULT_PERSONA_UID="persona1"))
        self.assertEqual(s["mode"], "api")
        self.assertTrue(s["configured"])

    def test_token_never_echoed(self):
        s = pp.get_provider_status(_env(PHOUND_ENABLED="true",
                                        PHOUND_TOKEN="uid123.apikey456",
                                        PHOUND_DEFAULT_PERSONA_UID="persona1"))
        self.assertNotIn("apikey456", json.dumps(s))
        self.assertIn("uid1", s["token_preview"])


class TestDryRunSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_records = patch.object(pp, "CALL_RECORDS",
                                          Path(self.tmp.name) / "calls.jsonl")
        self.patch_records.start()
        self.addCleanup(self.patch_records.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_dry_run_call_places_nothing(self):
        p = pp.PhoundProvider(_env())
        with patch.object(pp.PhoundProvider, "_sdk") as sdk:
            out = p.place_call(lead_id="L1", phone="+12125551234",
                               persona_uid="P1", dry_run=True)
            sdk.assert_not_called()
        self.assertEqual(out["status"], "dry_run_simulated")

    def test_dry_run_sms_sends_nothing(self):
        p = pp.PhoundProvider(_env())
        with patch.object(pp.PhoundProvider, "_sdk") as sdk:
            out = p.send_sms(lead_id="L1", phone="+12125551234",
                             persona_uid="P1", text="hello", dry_run=True)
            sdk.assert_not_called()
        self.assertEqual(out["status"], "dry_run_simulated")

    def test_duplicate_request_suppressed(self):
        p = pp.PhoundProvider(_env())
        first = p.place_call(lead_id="L9", phone="+12125551234", persona_uid="P1",
                             request_id="req_dup", dry_run=True)
        second = p.place_call(lead_id="L9", phone="+12125551234", persona_uid="P1",
                              request_id="req_dup", dry_run=True)
        self.assertEqual(second["status"], "duplicate_suppressed")
        self.assertEqual(second["record"]["request_id"], "req_dup")

    def test_native_fallback_without_config(self):
        p = pp.PhoundProvider(_env())  # disabled, no token
        out = p.place_call(lead_id="L2", phone="+12125551234",
                           persona_uid="P1", dry_run=False)
        self.assertEqual(out["status"], "native_app")
        self.assertIn("handoff", out)

    def test_unknown_state_on_unexpected_error(self):
        p = pp.PhoundProvider(_env(PHOUND_ENABLED="true",
                                   PHOUND_TOKEN="uid1.key12345",
                                   PHOUND_DEFAULT_PERSONA_UID="P1"))
        with patch.object(pp.PhoundProvider, "_sdk",
                           side_effect=RuntimeError("mystery provider boom")):
            out = p.place_call(lead_id="L3", phone="+12125551234",
                               persona_uid="P1", dry_run=False)
        self.assertEqual(out["status"], "unknown_provider_state")
        self.assertTrue(out["reconciliation_required"])

    def test_transient_error_classified_retryable(self):
        p = pp.PhoundProvider(_env(PHOUND_ENABLED="true",
                                   PHOUND_TOKEN="uid1.key12345",
                                   PHOUND_DEFAULT_PERSONA_UID="P1"))
        with patch.object(pp.PhoundProvider, "_sdk",
                           side_effect=RuntimeError("connection timed out")):
            out = p.place_call(lead_id="L4", phone="+12125551234",
                               persona_uid="P1", dry_run=False)
        self.assertEqual(out["status"], "error_transient_no_call_placed")
        self.assertTrue(pp.retry_allowed(out["record"]))
        self.assertFalse(pp.retry_allowed({"lifecycle_status": "unknown_provider_state"}))

    def test_no_token_in_records(self):
        p = pp.PhoundProvider(_env(PHOUND_ENABLED="true",
                                   PHOUND_TOKEN="uid1.supersecretkey",
                                   PHOUND_DEFAULT_PERSONA_UID="P1"))
        p.place_call(lead_id="L5", phone="+12125551234", persona_uid="P1",
                     dry_run=True)
        raw = (Path(self.tmp.name) / "calls.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("supersecretkey", raw)


class TestEventIngestion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_records = patch.object(pp, "CALL_RECORDS",
                                          Path(self.tmp.name) / "calls.jsonl")
        self.patch_records.start()
        self.addCleanup(self.patch_records.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_non_completed_event_not_handed_to_aftercall(self):
        p = pp.PhoundProvider(_env())
        out = p.ingest_event({"lead_id": "LX", "lifecycle_status": "ringing"})
        self.assertEqual(out["status"], "event_recorded")
        self.assertFalse(out["handed_to_aftercall"])

    def test_completed_event_hands_to_aftercall(self):
        p = pp.PhoundProvider(_env())
        fake_adapter = MagicMock()
        fake_adapter.record_aftercall.return_value = {"ok": True}
        with patch("MBM.LeadEngine.ad_dialer_adapter.DialerAdapter",
                   return_value=fake_adapter):
            out = p.ingest_event({"lead_id": "L7", "lifecycle_status": "completed",
                                  "provider_call_id": "pc_1", "transcript": "hi",
                                  "disposition": "CONNECTED"})
        self.assertTrue(out["handed_to_aftercall"])
        fake_adapter.record_aftercall.assert_called_once()
        _, kwargs = fake_adapter.record_aftercall.call_args
        self.assertEqual(kwargs.get("lead_id"), "L7")


if __name__ == "__main__":
    unittest.main()
