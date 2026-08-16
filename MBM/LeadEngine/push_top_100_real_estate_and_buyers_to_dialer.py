"""
Push Top 100 Real Estate Deals, Buyers & TranchAI Business Owners to MBM Dialer
================================================================================
Canonical 6-State Queue Partitioning & Seller-First Re-Ranking:
1. 🔥 CALL_NOW (Top 25): Immediate prime dial ready, high-equity DCAD real estate sellers
2. 🟢 NEXT (Next 75): High-scoring real estate sellers and verified opportunities
3. 🔵 VERIFIED_ACTIVE: Remaining 662 verified dial-ready leads (Clinics, ConTech, Cash Buyers)
   -> Total Dial-Ready Leads: 762
4. 🟡 VERIFICATION_REQUIRED: Ambiguous ownership, pending parcel APN match, or unverified contact (135)
5. 🔴 SUPPRESSED: DNC, BAD_NUMBER, WRONG_PERSON, NON_OWNER, DUPLICATE (373)
6. 🟣 QUARANTINED: Corrupt, unverified, or placeholder identities (217)

Canonical Phone Identity (E.164 / 10-digit normalized):
- Ensures all representations collapse to the same identity.
- Permanent suppression immunity against re-import.
- Preserves historical sales state (dispositions, notes, attempts).
- 100% preservation of all 78 recovered leads.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
LEADENGINE_DIR = ROOT_DIR / "MBM" / "LeadEngine"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(LEADENGINE_DIR))

from reconcile_dialer_partitions import run_reconciliation, normalize_dialer_phone, format_e164


def main():
    run_reconciliation()


if __name__ == "__main__":
    main()
