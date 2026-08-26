"""seller_benchmark_cohort - stratified 100-seller benchmark cohort (P0 P2).

Ground-truth law: statuses are assigned ONLY from recorded evidence.
- KNOWN_BAD  : phone has a quarantine event or adverse call outcome
               (BAD_NUMBER / WRONG_NUMBER / DISCONNECTED / WRONG_PARTY).
- KNOWN_GOOD : owner<->phone identity evidence exists AND no adverse events.
               (Expected count today: 0 - honest.)
- UNKNOWN    : no ground truth either way. Never guessed.

Stratification axes: source, geography (city/zip), lead age bucket, value tier,
current phone confidence. Cohort is written as an immutable artifact with the
seed used so runs are reproducible.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ADVERSE_FEEDBACK = {"BAD_NUMBER", "WRONG_NUMBER", "DISCONNECTED", "WRONG_PARTY"}
COHORT_SIZE = 100


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_sellers(db_path: str | Path) -> list[dict]:
    data = json.loads(Path(db_path).read_text(encoding="utf-8"))
    leads = data.get("leads") if isinstance(data, dict) else data
    return [x for x in leads if x.get("segment") == "DISTRESSED_SELLER"]


def evaluation_status(lead: dict) -> tuple[str, str]:
    """Return (status, reason). Evidence-based only."""
    details = lead.get("details") or {}
    for ev in lead.get("quarantined_phones") or []:
        if ev.get("phone") == lead.get("phone") or ev.get("status") in (
                "BAD", "DISCONNECTED", "WRONG_PARTY", "OWNER_MISMATCH"):
            return "KNOWN_BAD", f"quarantine:{ev.get('status')}"
    for fb in details.get("call_feedback") or []:
        if fb.get("outcome") in ADVERSE_FEEDBACK:
            return "KNOWN_BAD", f"feedback:{fb.get('outcome')}"
    evidence = details.get("owner_phone_evidence")
    if evidence in ("TITLED_OWNER_DIRECT", "AUTHORIZED_REPRESENTATIVE",
                    "MULTI_SOURCE_IDENTITY_AGREEMENT"):
        return "KNOWN_GOOD", f"identity_evidence:{evidence}"
    return "UNKNOWN", "no_ground_truth"


def _geo_bucket(lead: dict) -> str:
    addr = (lead.get("address") or "")
    city = (lead.get("city") or details_city(lead) or "").strip()
    return city or (addr.split(",")[-1].strip()[:20] if "," in addr else "unknown")


def details_city(lead: dict) -> str:
    return (lead.get("details") or {}).get("city") or ""


def _age_bucket(lead: dict) -> str:
    ts = lead.get("added_at") or ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "unknown_age"
    days = (datetime.now(timezone.utc) - dt).days
    if days <= 7:
        return "0-7d"
    if days <= 30:
        return "8-30d"
    if days <= 90:
        return "31-90d"
    return "90d+"


def _value_tier(lead: dict) -> str:
    score = lead.get("lead_score") or (lead.get("details") or {}).get("lead_score") or 0
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0
    return "high_value" if score >= 70 else "normal"


def build_cohort(sellers: list[dict], size: int = COHORT_SIZE,
                 seed: int = 42) -> dict:
    rng = random.Random(seed)
    by_status: dict[str, list[dict]] = {"KNOWN_BAD": [], "KNOWN_GOOD": [], "UNKNOWN": []}
    for s in sellers:
        status, reason = evaluation_status(s)
        by_status[status].append(s)

    cohort: list[dict] = []
    # Keep every known-outcome record first (they are scarce and precious).
    for status in ("KNOWN_BAD", "KNOWN_GOOD"):
        for s in by_status[status]:
            cohort.append(_row(s, status))
    fill = max(0, size - len(cohort))
    unknown_pool = sorted(by_status["UNKNOWN"], key=lambda x: x.get("id", ""))
    rng.shuffle(unknown_pool)
    cohort.extend(_row(s, "UNKNOWN") for s in unknown_pool[:fill])

    strat = Counter(
        (_row_source(c), c["geo"], c["age_bucket"], c["value_tier"]) for c in cohort)
    return {
        "cohort_id": "SELLER-BENCH-001",
        "created_at": _iso_now(),
        "seed": seed,
        "size": len(cohort),
        "population": len(sellers),
        "status_counts": {k: len(v) for k, v in by_status.items()},
        "stratification": {f"{s}|{g}|{a}|{v}": n for (s, g, a, v), n
                           in sorted(strat.items())},
        "records": cohort,
    }


def _row_source(row: dict) -> str:
    src = row.get("source", "?")
    return "DCAD" if "DCAD" in src else ("PHASE1" if "Phase" in src else src)


def _row(lead: dict, status: str) -> dict:
    status_reason_map = dict([evaluation_status(lead)])
    return {
        "lead_id": lead.get("id"),
        "source": _row_source(lead),
        "geo": _geo_bucket(lead),
        "age_bucket": _age_bucket(lead),
        "value_tier": _value_tier(lead),
        "phone_confidence": lead.get("phone_confidence", "n/a"),
        "evaluation_status": status,
        "status_reason": status_reason_map.get(status, ""),
    }


def run(db_path: str | Path, out_path: str | Path) -> dict:
    cohort = build_cohort(load_sellers(db_path))
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cohort, indent=2), encoding="utf-8")
    print(f"cohort={cohort['cohort_id']} size={cohort['size']} "
          f"statuses={cohort['status_counts']} -> {p}")
    return cohort


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="mbm-dialer/app/public/leads_database.json")
    ap.add_argument("--out",
                    default="MBM/Artifacts/GTM/seller_benchmark/cohort_SELLER-BENCH-001.json")
    args = ap.parse_args()
    run(args.db, args.out)
