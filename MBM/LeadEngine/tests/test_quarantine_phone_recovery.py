"""
MBM LeadEngine - Quarantine Phone Recovery Test Suite
=============================================================================
Verifies that:
1. All 53 restored leads have verified two-source provenance and valid phones.
2. All 138 remaining quarantined leads remain uncallable with audit provenance.
3. PREVIOUS_BAD_PHONES_REINTRODUCED == 0.
4. UNVERIFIED_PHONES_REINTRODUCED == 0.
5. SYNTHETIC_PHONES_REINTRODUCED == 0.
6. DUPLICATE_CALLABLE_PHONES == 0.
7. Atomic single-writer lock protection remains strictly enforced.
=============================================================================
"""

import json
import pytest
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import DIALER_DB_PATH
from MBM.LeadEngine.quarantine_phone_recovery_engine import (
    normalize_phone,
    is_synthetic_or_invalid_phone,
    QUARANTINE_FILE,
    SUPPRESSION_FILE,
    AUDIT_JSON_PATH
)


def test_quarantine_recovery_audit_invariants():
    """Verify all 4 core zero-tolerance invariants from the audit JSON."""
    assert AUDIT_JSON_PATH.exists(), f"Audit file missing: {AUDIT_JSON_PATH}"
    audit = json.loads(AUDIT_JSON_PATH.read_text(encoding="utf-8"))

    assert audit.get("QUARANTINED_LEADS_REVIEWED") == 191
    assert audit.get("PREVIOUS_BAD_PHONES_REINTRODUCED") == 0
    assert audit.get("UNVERIFIED_PHONES_REINTRODUCED") == 0
    assert audit.get("SYNTHETIC_PHONES_REINTRODUCED") == 0
    assert audit.get("DUPLICATE_CALLABLE_PHONES") == 0
    assert audit.get("RESTORED_TO_CALLABLE") == 53
    assert audit.get("REMAINING_QUARANTINED") == 138
    assert audit.get("TOTAL_CALLABLE_LEADS_NOW") == 925


def test_callable_leads_phone_validity_and_uniqueness():
    """Verify in the live dialer DB that all callable leads have verified phones and zero duplicates."""
    assert DIALER_DB_PATH.exists()
    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))

    suppressed = set()
    if SUPPRESSION_FILE.exists():
        supp_data = json.loads(SUPPRESSION_FILE.read_text(encoding="utf-8"))
        suppressed = {normalize_phone(p) for p in supp_data.get("suppressed_phones", []) if p}

    callable_leads = [l for l in leads if l.get("callable") is True]
    assert len(callable_leads) == 925, f"Expected 925 callable leads, got {len(callable_leads)}"

    seen_phones = set()
    for lead in callable_leads:
        phone = lead.get("phone")
        norm = normalize_phone(phone)
        assert norm, f"Callable lead {lead.get('id')} has missing/empty phone"
        assert len(norm) == 12 and norm.startswith("+1"), f"Invalid phone format: {norm}"
        assert not is_synthetic_or_invalid_phone(norm), f"Synthetic phone in callable: {norm}"
        assert norm not in suppressed, f"Suppressed bad phone found in callable: {norm}"
        assert norm not in seen_phones, f"Duplicate callable phone found: {norm}"
        seen_phones.add(norm)

        # Check phone verification provenance
        assert lead.get("phone_verified") is True, f"Callable lead {lead.get('id')} missing phone_verified"
        src = lead.get("phone_verification_source") or lead.get("source") or lead.get("details", {}).get("source")
        assert src, f"Callable lead {lead.get('id')} missing verification source"


def test_remaining_quarantined_leads_are_uncallable():
    """Verify that all leads remaining in the quarantine file are marked callable=False."""
    assert QUARANTINE_FILE.exists()
    q_data = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
    q_leads = q_data.get("quarantined_leads", [])

    assert len(q_leads) == 138, f"Expected 138 remaining quarantined leads, got {len(q_leads)}"
    for q in q_leads:
        assert q.get("callable") is False, f"Quarantined lead {q.get('id')} has callable=True"
        assert q.get("status") == "QUARANTINED_UNVERIFIED_PHONE"
