#!/usr/bin/env python3
"""
Diagnostic & Reconciliation Audit Script
Traces all records in leads_database.json, top_100_partition.json, canonical_deals_memory.json,
and logs/recovery/recovered_candidates.json.
"""

import json
import re
from pathlib import Path

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
    print("1. INVENTORY COUNTS")
    print("=" * 60)
    print(f"leads_database.json total: {len(db_leads)}")
    top_25 = partition_data.get("top_25_call_now", [])
    next_75 = partition_data.get("next_75", [])
    verif = partition_data.get("verification_leads", [])
    supp = partition_data.get("suppressed_leads", [])
    print(f"top_100_partition.json:")
    print(f"  - top_25_call_now:        {len(top_25)}")
    print(f"  - next_75:                {len(next_75)}")
    print(f"  - verification_leads:     {len(verif)}")
    print(f"  - suppressed_leads:       {len(supp)}")
    sum_part = len(top_25) + len(next_75) + len(verif) + len(supp)
    print(f"  - sum of 4 partition lists: {sum_part}")
    print(f"  - discrepancy (762 vs {sum_part}): {len(db_leads) - sum_part}")

    # Trace IDs / Phones across partitions and db_leads
    db_by_id = {l.get("id"): l for l in db_leads}
    db_by_phone = {norm_phone(l.get("phone")): l for l in db_leads}

    top_25_ids = {l.get("id") for l in top_25}
    next_75_ids = {l.get("id") for l in next_75}
    verif_ids = {l.get("id") for l in verif}
    supp_ids = {l.get("id") for l in supp}

    top_25_phones = {norm_phone(l.get("phone")) for l in top_25}
    next_75_phones = {norm_phone(l.get("phone")) for l in next_75}
    verif_phones = {norm_phone(l.get("phone")) for l in verif}
    supp_phones = {norm_phone(l.get("phone")) for l in supp}

    all_part_ids = top_25_ids | next_75_ids | verif_ids | supp_ids
    all_part_phones = top_25_phones | next_75_phones | verif_phones | supp_phones

    in_db_not_in_part = [l for l in db_leads if l.get("id") not in all_part_ids and norm_phone(l.get("phone")) not in all_part_phones]
    in_part_not_in_db = [pid for pid in all_part_ids if pid not in db_by_id]

    print(f"\nLeads in leads_database.json NOT in any partition list: {len(in_db_not_in_part)}")
    for l in in_db_not_in_part[:10]:
        print(f"  - {l.get('id')} | {l.get('company')} | {l.get('phone')} | {l.get('vertical')}")

    # Also check overlap between db_leads and partitions
    in_db_in_top25 = [l for l in db_leads if l.get("id") in top_25_ids or norm_phone(l.get("phone")) in top_25_phones]
    in_db_in_next75 = [l for l in db_leads if l.get("id") in next_75_ids or norm_phone(l.get("phone")) in next_75_phones]
    in_db_in_verif = [l for l in db_leads if l.get("id") in verif_ids or norm_phone(l.get("phone")) in verif_phones]
    in_db_in_supp = [l for l in db_leads if l.get("id") in supp_ids or norm_phone(l.get("phone")) in supp_phones]

    print(f"\nBreakdown of what is actually INSIDE leads_database.json (total {len(db_leads)}):")
    print(f"  - in top_25:      {len(in_db_in_top25)}")
    print(f"  - in next_75:     {len(in_db_in_next75)}")
    print(f"  - in verif:       {len(in_db_in_verif)}")
    print(f"  - in supp:        {len(in_db_in_supp)}")
    print(f"  - in none:        {len(in_db_not_in_part)}")

    print("\n" + "=" * 60)
    print("2. TOP 100 COMPOSITION AUDIT")
    print("=" * 60)
    top_100 = db_leads[:100]
    print(f"Top 100 in leads_database.json:")
    verticals = {}
    roles = {}
    sources = {}
    is_buyer = 0
    is_seller = 0
    owner_verified = 0
    callable_cnt = 0
    high_intent = 0
    fresh_cnt = 0

    for i, l in enumerate(top_100):
        v = l.get("vertical", "Unknown")
        verticals[v] = verticals.get(v, 0) + 1
        r = l.get("role_type", "Unknown")
        roles[r] = roles.get(r, 0) + 1
        s = l.get("details", {}).get("source", l.get("source", "Unknown"))
        sources[s] = sources.get(s, 0) + 1

        phone = norm_phone(l.get("phone"))
        if len(phone) == 10:
            callable_cnt += 1

        # Check if buyer vs seller
        v_lower = str(v).lower()
        r_lower = str(r).lower()
        if "buyer" in v_lower or "flipper" in v_lower or "buyer" in r_lower:
            is_buyer += 1
        else:
            is_seller += 1

        if l.get("owner_status") == "VERIFIED_OWNER" or "owner" in r_lower or l.get("details", {}).get("Owner_Name"):
            owner_verified += 1

        if l.get("motivation_score", 0) >= 80 or l.get("deal_score", 0) >= 80:
            high_intent += 1

        if l.get("freshness") or l.get("details", {}).get("freshness") or l.get("created_at") or l.get("timestamp"):
            fresh_cnt += 1

    print(f"  Top 100 Total:         {len(top_100)}")
    print(f"  Seller Leads:          {is_seller}")
    print(f"  Buyer Leads:           {is_buyer}")
    print(f"  Owner Verified:        {owner_verified}")
    print(f"  Callable (10-digit):   {callable_cnt}")
    print(f"  High Intent (Score>=80): {high_intent}")
    print(f"  Fresh:                 {fresh_cnt}")
    print(f"\n  Vertical distribution in Top 100:")
    for v, c in sorted(verticals.items(), key=lambda x: -x[1]):
        print(f"    - {v}: {c}")

    print("\n" + "=" * 60)
    print("3. RECOVERY LEADS AUDIT (78 LEADS)")
    print("=" * 60)
    print(f"Recovered candidates file count: {len(recovery_leads)}")
    rec_phones = {norm_phone(r.get("phone")): r for r in recovery_leads}
    print(f"Unique recovery phones: {len(rec_phones)}")

    # Check presence in canonical memory
    canon_deals = canonical_data.get("deals", {})
    canon_phones = {norm_phone(d.get("phone")): d for d in canon_deals.values()}

    rec_in_canon = [p for p in rec_phones if p in canon_phones]
    rec_in_db = [p for p in rec_phones if p in db_by_phone]
    rec_callable = [r for r in recovery_leads if len(norm_phone(r.get("phone"))) == 10]
    rec_verified = [r for r in recovery_leads if r.get("skip_trace_status") == "VERIFIED" or r.get("verified")]

    print(f"  78_expected:   78 (actual in file: {len(recovery_leads)})")
    print(f"  78_present in canonical memory: {len(rec_in_canon)}")
    print(f"  78_present in leads_database.json: {len(rec_in_db)}")
    print(f"  78_callable:   {len(rec_callable)}")
    print(f"  78_verified:   {len(rec_verified)}")

if __name__ == "__main__":
    run_audit()
