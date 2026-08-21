#!/usr/bin/env python3
"""
Unit and regression tests for Real-Number Recovery & Bad-Number Purge Engine.
Enforces that the callable dialer NEVER contains unverified, synthetic, bad, or duplicate phones.
"""

import sys
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH
from MBM.LeadEngine.phone_recovery_and_purge_engine import (
    normalize_phone,
    is_synthetic_or_invalid_phone,
    execute_phone_recovery_and_purge,
    SUPPRESSION_FILE,
    QUARANTINE_FILE,
    RECOVERY_AUDIT_JSON,
)

def test_phone_normalization_and_synthetic_detection():
    # Valid phones
    assert normalize_phone("(214) 890-7909") == "+12148907909"
    assert normalize_phone("+12148907909") == "+12148907909"
    assert normalize_phone("2148907909") == "+12148907909"
    assert is_synthetic_or_invalid_phone("+12148907909") is False

    # Synthetic / Invalid phones
    assert is_synthetic_or_invalid_phone("+12005550100") is True
    assert is_synthetic_or_invalid_phone("+15555550199") is True
    assert is_synthetic_or_invalid_phone("+12145550100") is True
    assert is_synthetic_or_invalid_phone("123") is True
    assert is_synthetic_or_invalid_phone("+11111111111") is True


def test_dialer_phone_recovery_audit_invariants():
    metrics = execute_phone_recovery_and_purge()

    assert metrics["UNVERIFIED_NUMBERS_REMAINING"] == 0
    assert metrics["SYNTHETIC_NUMBERS_REMAINING"] == 0
    assert metrics["DUPLICATE_NUMBERS_REMAINING"] == 0
    assert metrics["PREVIOUSLY_BAD_NUMBERS_IN_CALLABLE_QUEUE"] == 0
    assert metrics["CALLABLE_LEADS"] >= 500

    assert SUPPRESSION_FILE.exists()
    assert QUARANTINE_FILE.exists()
    assert RECOVERY_AUDIT_JSON.exists()


def test_every_callable_lead_has_verified_provenance():
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))

    callable_leads = [l for l in leads if l.get("callable") is True]
    assert len(callable_leads) >= 500

    seen_phones = set()
    for lead in callable_leads:
        phone = normalize_phone(lead.get("phone"))
        assert phone, f"Lead {lead.get('id')} missing phone"
        assert not is_synthetic_or_invalid_phone(phone), f"Lead {lead.get('id')} has synthetic phone {phone}"
        assert phone not in seen_phones, f"Duplicate phone {phone} in callable queue"
        seen_phones.add(phone)

        # Verification metadata
        assert lead.get("phone_verified") is True, f"Lead {lead.get('id')} phone not verified"
        assert lead.get("last_verified_at"), f"Lead {lead.get('id')} missing last_verified_at"
        assert lead.get("source"), f"Lead {lead.get('id')} missing source"
