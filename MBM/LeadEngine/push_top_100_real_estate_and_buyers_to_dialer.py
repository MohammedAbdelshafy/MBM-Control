"""
Push Top 100 Real Estate Deals, Buyers & TranchAI Business Owners to MBM Dialer
================================================================================
Canonical 6-State Queue Partitioning & Seller-First Re-Ranking, followed by
freshness promotion inside every dialer category.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
LEADENGINE_DIR = ROOT_DIR / "MBM" / "LeadEngine"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(LEADENGINE_DIR))

from reconcile_dialer_partitions import run_reconciliation
from promote_new_verified_leads_to_top import main as promote_new_verified_leads


def main():
    result = run_reconciliation()
    promote_new_verified_leads()
    return result


if __name__ == "__main__":
    main()
