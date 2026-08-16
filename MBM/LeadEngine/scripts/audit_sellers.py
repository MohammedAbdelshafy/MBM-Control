#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "MBM" / "LeadEngine"))

from MBM.LeadEngine.canonical_schema import load_canonical_memory, assert_canonical_list
CANON_PATH = ROOT / "MBM" / "Artifacts" / "canonical_deals_memory.json"
RE_QUEUE = ROOT / "MBM" / "LeadEngine" / "real_estate_calling_queue.json"
RECOVERY_PATH = ROOT / "logs" / "recovery" / "recovered_candidates.json"

def main():
    with open(CANON_PATH, "r", encoding="utf-8") as f:
        canon = load_canonical_memory(CANON_PATH)
    assert_canonical_list(canon)

    prop_deals = [d for d in canon if d.get("deal_type") == "property" or "real estate" in str(d.get("vertical", "")).lower()]
    print(f"Total property/RE deals in canonical memory: {len(prop_deals)}")

    prime_props = [d for d in prop_deals if d.get("is_prime_callable")]
    unprime_props = [d for d in prop_deals if not d.get("is_prime_callable")]
    print(f"  Prime callable: {len(prime_props)}")
    print(f"  Unprime / Need verification: {len(unprime_props)}")

    print("\nSample Prime Property Deals:")
    for i, d in enumerate(prime_props[:15]):
        pid = d.get("id")
        addr = d.get("property_address") or d.get("company_name")
        owner = d.get("owner_name")
        phone = d.get("contact_phone")
        arv = d.get("estimated_arv") or 0
        mao = d.get("calculated_mao") or 0
        ds = d.get("deal_score") or 0
        ms = d.get("motivation_score") or 0
        signals = d.get("signals", [])
        print(f"  #{i+1:02d} [{pid}] {addr} | Owner: {owner} | Phone: {phone} | ARV: ${int(arv):,} | MAO: ${int(mao):,} | Scores: (D:{ds}, M:{ms}) | Signals: {signals}")

if __name__ == "__main__":
    main()
