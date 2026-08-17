"""Fast purge of generic placeholder names + compact JSON save."""
import json, sys

DB = r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json"

with open(DB, "r", encoding="utf-8") as f:
    leads = json.load(f)

GENERIC = [
    "the practice administrator", "practice administrator",
    "physical therapist", "behavior analyst", "office manager",
    "front desk", "receptionist", "billing department",
    "medical director", "clinical director",
]

total = len(leads)
kept = [l for l in leads if not any(g in (l.get("contact","") or "").strip().lower() for g in GENERIC)]

v = sum(1 for l in kept if l.get("skip_trace_status") == "VERIFIED")
e = sum(1 for l in kept if l.get("skip_trace_status") == "ENRICHED")
u = sum(1 for l in kept if l.get("skip_trace_status") == "UNVERIFIED")
p = sum(1 for l in kept if not l.get("skip_trace_status"))

print(f"Before: {total}")
print(f"Removed generic: {total - len(kept)}")
print(f"Kept: {len(kept)}")
print(f"  VERIFIED: {v}")
print(f"  ENRICHED: {e}")
print(f"  UNVERIFIED: {u}")
print(f"  PENDING: {p}")

# Compact JSON (no indent) for speed
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from MBM.LeadEngine.dialer_gateway import commit_dialer_db
commit_dialer_db(kept, reason="fast_purge", allow_shrink=True, author="FAST_PURGE")
print("DONE")
