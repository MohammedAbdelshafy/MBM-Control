#!/usr/bin/env python3
"""
Deep-dive reconciliation analysis script.
Audits all records across:
- leads_database.json
- canonical_deals_memory.json
- top_100_partition.json
- real_estate_calling_queue.json
- cold_calling_queue.json
- logs/recovery/recovered_candidates.json
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "MBM" / "LeadEngine"))

from MBM.LeadEngine.canonical_schema import load_canonical_memory, assert_canonical_list
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
PARTITION_FILE = ROOT / "MBM" / "Artifacts" / "top_100_partition.json"
CANONICAL_MEMORY = ROOT / "MBM" / "Artifacts" / "canonical_deals_memory.json"
RE_QUEUE = ROOT / "MBM" / "LeadEngine" / "real_estate_calling_queue.json"
COLD_QUEUE = ROOT / "MBM" / "LeadEngine" / "cold_calling_queue.json"
RECOVERY_FILE = ROOT / "logs" / "recovery" / "recovered_candidates.json"

def norm_phone(p):
    digits = re.sub(r"\D", "", str(p or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits

def main():
    with open(DIALER_DB, "r", encoding="utf-8") as f:
        db_leads = json.load(f)

    with open(PARTITION_FILE, "r", encoding="utf-8") as f:
        partition_data = json.load(f)

    with open(CANONICAL_MEMORY, "r", encoding="utf-8") as f:
        canonical_deals = load_canonical_memory(CANONICAL_MEMORY)
    assert_canonical_list(canonical_deals)

    with open(RE_QUEUE, "r", encoding="utf-8") as f:
        re_leads = json.load(f)

    with open(COLD_QUEUE, "r", encoding="utf-8") as f:
        cold_leads = json.load(f)

    with open(RECOVERY_FILE, "r", encoding="utf-8") as f:
        rec_leads = json.load(f)

    print("=" * 70)
    print("1. INVENTORY SUMMARY ACROSS ALL STORES")
    print("=" * 70)
    print(f"leads_database.json:            {len(db_leads)}")
    print(f"canonical_deals_memory.json:    {len(canonical_deals)}")
    print(f"real_estate_calling_queue.json: {len(re_leads)}")
    print(f"cold_calling_queue.json:        {len(cold_leads)}")
    print(f"recovered_candidates.json:      {len(rec_leads)}")

    print("\n" + "=" * 70)
    print("2. REAL ESTATE CALLING QUEUE AUDIT (170 LEADS)")
    print("=" * 70)
    for i, r in enumerate(re_leads[:15]):
        rid = r.get("id")
        prop = r.get("property_address") or r.get("company")
        owner = r.get("owner_name") or r.get("contact")
        phone = r.get("phone")
        score = r.get("deal_score") or r.get("motivation_score")
        tier = r.get("motivation_tier") or r.get("tier")
        source = r.get("source") or r.get("details", {}).get("source")
        print(f"  #{i+1:02d} [{rid}] {prop} | {owner} | {phone} | Score: {score} | Tier: {tier} | Src: {source}")

    # Check seller vs buyer in re_leads
    re_buyers = [r for r in re_leads if "buyer" in str(r.get("vertical", "")).lower() or "buyer" in str(r.get("role_type", "")).lower()]
    re_sellers = [r for r in re_leads if r not in re_buyers]
    print(f"\n  RE Sellers: {len(re_sellers)} | RE Buyers: {len(re_buyers)}")

    print("\n" + "=" * 70)
    print("3. CANONICAL DEALS MEMORY BREAKDOWN")
    print("=" * 70)
    canon_types = Counter(d.get("deal_type") for d in canonical_deals)
    canon_verts = Counter(d.get("vertical") for d in canonical_deals)
    canon_supp = Counter(d.get("suppression_state") for d in canonical_deals)
    canon_prime = Counter(d.get("is_prime_callable") for d in canonical_deals)
    print(f"  Deal Types: {dict(canon_types)}")
    print(f"  Verticals: {dict(canon_verts)}")
    print(f"  Suppression: {dict(canon_supp)}")
    print(f"  Prime Callable: {dict(canon_prime)}")

    print("\n" + "=" * 70)
    print("4. MAPPING OF ALL 762 LEADS IN LIVE DIALER DB")
    print("=" * 70)
    db_verts = Counter(l.get("vertical") for l in db_leads)
    print(f"  Verticals in dialer DB (total {len(db_leads)}):")
    for v, c in db_verts.most_common():
        print(f"    - {v}: {c}")

if __name__ == "__main__":
    main()
