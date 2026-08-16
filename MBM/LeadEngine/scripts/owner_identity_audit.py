#!/usr/bin/env python3
"""
Owner Identity Audit — TOP 100
==============================
Separates DATABASE ownership verification from LIVE caller identity
confirmation across the current seller-first Top 100 in the live dialer DB.

    DATABASE OWNERSHIP VERIFICATION   — records (DCAD/county/parcel) say owner
    LIVE CALLER IDENTITY CONFIRMATION — the person answering the phone was
                                        actually confirmed as the owner/ADM

Nothing is ever counted OWNER_CONFIRMED without call-level evidence.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "MBM" / "LeadEngine"))

from MBM.LeadEngine.owner_identity import audit_identity

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"


def main():
    if not DIALER_DB.exists():
        print(f"ERROR: {DIALER_DB} missing")
        sys.exit(1)
    data = json.loads(DIALER_DB.read_text(encoding="utf-8"))
    arr = data if isinstance(data, list) else data.get("leads", [])
    top100 = arr[:100]
    report = audit_identity(top100)

    print("=" * 50)
    print("  OWNER IDENTITY AUDIT")
    print("=" * 50)
    print("  TOP 100:")
    for key in ("owner_confirmed", "owner_likely", "authorized_decision_maker",
                "identity_unconfirmed", "wrong_person", "wrong_number", "tenant"):
        print(f"    {key}: {report[key]}")
    print(f"    quarantined: {report['quarantined']}")
    print("  DATABASE:")
    print(f"    ownership_verified: {report['database_ownership_verified']}")
    print(f"    caller_identity_verified: {report['caller_identity_verified']}")
    print(f"    identity_unknown: {report['identity_unknown']}")
    print("=" * 50)

    # Highlight the DB-vs-phone distinction explicitly.
    print("\n  Note: database_ownership_verified counts records a public record")
    print("  says are owned by the contact. caller_identity_verified counts only")
    print("  owners/decision-makers CONFIRMED on a live call. They are different.")
    return report


if __name__ == "__main__":
    main()