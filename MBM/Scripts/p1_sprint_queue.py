#!/usr/bin/env python3
"""P0->P1 sprint queue: top 10 newest-first VERIFIED callable (non-seller) leads
with their canonical scripts and offer matches. Read-only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from MBM.GLM.single_writer_lock import DialerSingleWriter, DIALER_DB_PATH
from MBM.LeadEngine.dialer_queue_engine import rank_main_queue

MOTIVATED_SELLER_SEGMENTS = {
    "DISTRESSED_SELLER", "ABSENTEE_OWNER", "VACANT_PROPERTY", "HIGH_EQUITY",
    "FREE_AND_CLEAR", "TIRED_LANDLORD", "OUT_OF_STATE_OWNER", "SENIOR_OWNER",
}

def main():
    writer = DialerSingleWriter(db_path=DIALER_DB_PATH)
    leads = writer.read_leads()
    ranked = rank_main_queue(leads)
    q = []
    for l in ranked:
        seg = str(l.get("segment") or "").upper()
        if seg in MOTIVATED_SELLER_SEGMENTS:
            continue
        q.append(l)
        if len(q) >= 10:
            break
    print(f"RANKED_MAIN_QUEUE={len(ranked)} NON_SELLER_TOP10={len(q)}")
    for i, l in enumerate(q, 1):
        ss = l.get("sales_strategy") or {}
        offer = ""
        if isinstance(ss.get("offer"), dict):
            offer = ss["offer"].get("name") or ss["offer"].get("offer_name") or ""
        print("---")
        print(f"#{i} {l.get('id')} | {l.get('company')} | {l.get('contact')}")
        print(f"    phone={l.get('phone')} verified_at={l.get('phone_verified_at') or l.get('verified_at')}")
        print(f"    segment={l.get('segment')} state={l.get('state')} city={l.get('city')}")
        print(f"    script_id={l.get('script_id')} strategy={ss.get('opening','')[:60]!r}")
        print(f"    offer={offer or l.get('recommended_ai_assistant') or 'SEE SCRIPT'}")

if __name__ == "__main__":
    main()
    # EXECUTION NOTE (2026-08-26): The sprint queue is armed and verified.
    # REAL CALLS BLOCKED by telephony provider state (Phound: no endpoint/token;
    # Twilio: TRIAL, live_calls=False). Resume with the exact command:
    #
    #   .venv\Scripts\python.exe MBM/Scripts/p1_sprint_queue.py
    #
    # Once PHOUND_CALL_ENDPOINT + PHOUND_API_TOKEN are set (or Twilio billing
    # is upgraded), fire with:
    #
    #   npm run leads:dial -- --dry-run --limit 10     # verification run
    #   npm run leads:dial:live -- --live --limit 10  # real bridge sprint
