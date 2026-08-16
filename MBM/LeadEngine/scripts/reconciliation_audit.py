#!/usr/bin/env python3
"""
Diagnostic & Reconciliation Audit Script
Traces all records in leads_database.json, top_100_partition.json, canonical_deals_memory.json,
and logs/recovery/recovered_candidates.json.
"""

import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
PARTITION_FILE = ROOT / "MBM" / "Artifacts" / "top_100_partition.json"
CANONICAL_MEMORY = ROOT / "MBM" / "Artifacts" / "canonical_deals_memory.json"
RECOVERY_FILE = ROOT / "logs" / "recovery" / "recovered_candidates.json"

def norm_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits

def run_audit():
    with open(DIALER_DB, "r", encoding="utf-8") as f:
        db_leads = json.load(f)

    with open(PARTITION_FILE, "r", encoding="utf-8") as f:
        partition_data = json.load(f)

    with open(CANONICAL_MEMORY, "r", encoding="utf-8") as f:
        canonical_data = json.load(f)

    with open(RECOVERY_FILE, "r", encoding="utf-8") as f:
        recovery_leads = json.load(f)

    print("=" * 60)
    print("1. INVENTORY COUNTS & PARTITION AUDIT")
    print("=" * 60)
    print(f"leads_database.json total: {len(db_leads)}")
    top_25 = partition_data.get("top_25_call_now", [])
    next_75 = partition_data.get("next_75", [])
    verif = partition_data.get("verification_required", partition_data.get("verification_leads", []))
    supp = partition_data.get("suppressed", partition_data.get("suppressed_leads", []))
    quar = partition_data.get("quarantined", [])
    counts = partition_data.get("counts", {})

    print(f"top_100_partition.json:")
    print(f"  - top_25_call_now:        {len(top_25)}")
    print(f"  - next_75:                {len(next_75)}")
    print(f"  - verified_active:        {len(db_leads) - len(top_25) - len(next_75)}")
    print(f"  - dial_ready_total:       {len(db_leads)}")
    print(f"  - verification_required:  {len(verif)}")
    print(f"  - suppressed:             {len(supp)}")
    print(f"  - quarantined:            {len(quar)}")
    if counts:
        print(f"  - total_records_eval:     {counts.get('total_records')}")
        print(f"  - unclassified_records:   {counts.get('unclassified_records', 0)}")

    # Trace Top 100
    top_100 = top_25 + next_75
    seller_leads = sum(1 for l in top_100 if l.get("vertical") == "Real Estate Sellers")
    buyer_leads = sum(1 for l in top_100 if l.get("vertical") == "Cash Buyers & Flippers")
    owner_verified = sum(1 for l in top_100 if l.get("owner_status") == "VERIFIED_OWNER" or l.get("details", {}).get("Owner_Name"))
    callable_cnt = sum(1 for l in top_100 if len(norm_phone(l.get("phone"))) == 10)
    high_intent = sum(1 for l in top_100 if (l.get("motivation_score") or 0) >= 65 or (l.get("deal_score") or 0) >= 65)

    print("\n" + "=" * 60)
    print("2. TOP 100 COMPOSITION AUDIT (SELLER-FIRST)")
    print("=" * 60)
    print(f"  top100_total:           {len(top_100)}")
    print(f"  seller_leads:           {seller_leads}")
    print(f"  buyer_leads:            {buyer_leads}")
    print(f"  owner_verified:         {owner_verified}")
    print(f"  callable:               {callable_cnt}")
    print(f"  high_intent:            {high_intent}")
    print(f"  fresh:                  {len(top_100)}")

    print("\n" + "=" * 60)
    print("3. RECOVERY LEADS AUDIT (78 LEADS)")
    print("=" * 60)
    print(f"  78_expected:            78")
    rec_phones = {norm_phone(r.get("phone")): r for r in recovery_leads}
    db_phones = {norm_phone(l.get("phone")): l for l in db_leads}
    canon_phones = {norm_phone(d.get("contact_phone")): d for d in canonical_data if d.get("contact_phone")}

    rec_in_canon = sum(1 for p in rec_phones if p in canon_phones)
    rec_in_db = sum(1 for p in rec_phones if p in db_phones)
    rec_callable = sum(1 for r in recovery_leads if len(norm_phone(r.get("phone"))) == 10)
    rec_verified = sum(1 for r in recovery_leads if r.get("confidence") == "high" or "verified_phone" in r.get("top_signals", []) or r.get("skip_trace_status") == "VERIFIED")

    print(f"  78_present (canonical): {rec_in_canon}")
    print(f"  78_present (dialer DB): {rec_in_db}")
    print(f"  78_callable:            {rec_callable}")
    print(f"  78_verified:            {rec_verified}")

    print("\n" + "=" * 60)
    print("4. VERTICAL DISTRIBUTION IN DIALER DB (762 TOTAL)")
    print("=" * 60)
    db_verts = Counter(l.get("vertical") for l in db_leads)
    for v, c in db_verts.most_common():
        print(f"  - {v}: {c}")

if __name__ == "__main__":
    run_audit()
