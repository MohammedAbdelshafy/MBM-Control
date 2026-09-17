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
                                        PHOUND_TOKEN="uid123.demo_only_key",
                                        PHOUND_DEFAULT_PERSONA_UID="persona1"))
        self.assertEqual(s["mode"], "api")
        self.assertTrue(s["configured"])
    def test_token_never_echoed(self):
        s = pp.get_provider_status(_env(PHOUND_ENABLED="true",
                                        PHOUND_TOKEN="uid123.demo_only_key",
                                        PHOUND_DEFAULT_PERSONA_UID="persona1"))
        self.assertNotIn("demo_only_key", json.dumps(s))
        self.assertIn("uid1", s["token_preview"])
