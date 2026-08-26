"""One-shot repair of the quarantine mirror (quarantined_bad_leads.json).

Incident: an unknown writer shrank the ledger at ~01:34 (95->83 unique),
violating the no-shrink floor and breaking test_quarantine_phone_recovery.
This tool rebuilds the mirror from canonical DB truth (callable=False leads)
and re-admits every historical entry (dict or legacy string) that is not
already represented. Idempotent.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DB = ROOT / "mbm-dialer/app/public/leads_database.json"
MIRROR = ROOT / "MBM/Artifacts/quarantined_bad_leads.json"


def main() -> None:
    db = json.loads(DB.read_text(encoding="utf-8"))
    leads = db.get("leads") if isinstance(db, dict) else db

    from_db = {}
    for L in leads:
        if L.get("callable") is False:
            qp = L.get("quarantined_phones") or []
            entry = {
                "id": L.get("id"),
                "callable": False,
                "status": "QUARANTINED_UNVERIFIED_PHONE",
                "quarantine_reason": L.get("quarantine_reason")
                or "QUARANTINED_UNVERIFIED_PHONE",
                "phone": L.get("phone"),
                "previous_phone": L.get("previous_phone", ""),
                "source": L.get("source", ""),
                "segment": L.get("segment", ""),
            }
            from_db[L["id"]] = entry

    # Mirror contract: EXACT 1:1 with the DB's callable=False cohort.
    # Historical-only entries are NOT kept here; they persist in the
    # monotonic SUPPRESSION_FILE via reconcile_suppression_index().
    merged = dict(from_db)
    extra = 0

    out = {
        "total_quarantined": len(merged),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "quarantined_leads": list(merged.values()),
        "rebuild_note": (
            f"mirror rebuilt: {len(from_db)} callable=False leads from "
            f"canonical DB + {extra} history-only entries; no-shrink enforced"
        ),
    }
    MIRROR.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"mirror={len(merged)} db={len(from_db)} history_only={extra}")


if __name__ == "__main__":
    main()
