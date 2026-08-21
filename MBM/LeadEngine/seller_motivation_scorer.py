#!/usr/bin/env python3
"""
MBM Seller Motivation Scorer — Multi-Signal Distress & Motivation Scoring
=========================================================================
Annotates the Real Estate Seller leads in mbm-dialer/leads_database.json with a
0-100 motivation score and tier using only data ALREADY verified in the row:

Signals used (weighted, additive on a 40 base):
  * Distress signal type      — Code Concern / Rental Registration / Vacation
  * Absentee owner            — DCAD mailing address != site city/state
  * Out-of-state owner        — mailing state differs from property state
  * Entity (investor) owner   — LLC/Trust/company-held property
  * Owner-occupied            — mails to the property itself (deducts)
  * Signal recency            — fresher 311/registration signal scores higher

Output on each lead (top-level + nested in details):
  motivation_score    : int 0-100
  motivation_tier     : VERY_HIGH | HIGH | MEDIUM | LOW
  motivation_signals  : list of signal names that fired
  pitch_angle         : suggested opening angle per dominant signal

Nothing is written until --apply (backup goes to logs/db_backups/). Scores are
also propagated to the RE dialer queues (real_estate_calling_queue.json by
deal_id, us_re_dialer_queue.json by parcel_id) so dialers can rank by tier.

  python seller_motivation_scorer.py                      # dry-run
  python seller_motivation_scorer.py --apply              # write DB + queues
  python seller_motivation_scorer.py --apply --limit 20
"""

import io
import json
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path

sysout = io.TextIOWrapper
import sys
sys.stdout = sysout(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = sysout(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
RE_QUEUE = BASE / "real_estate_calling_queue.json"
US_RE_QUEUE = BASE / "us_re_dialer_queue.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REPORT = LOGS / "seller_motivation_report.json"

BASE_SCORE = 25

ENTITY_MARKERS = (
    "LLC", "LLP", "LP ", "L.P.", "INC", "CORP", "TRUST", "GROUP",
    "PROPERTIES", "PROPERTY", "INVESTMENTS", "REALTY", "HOLDINGS",
    "LTD", "COMPANY", "PARTNERSHIP", "ESTATE",
)

# Canonical single-writer gateway for the live dialer DB (never raw-write it).
sys.path.insert(0, str(ROOT))
from MBM.LeadEngine.dialer_gateway import commit_dialer_db  # noqa: E402

SIGNAL_WEIGHTS = {
    "code_concern": 10,
    "rental_registration": 18,
    "vacation_rental": 15,
    "foreclosure": 30,
    "tax_delinquent": 25,
    "probate": 20,
    "vacant": 15,
}

TIER_BANDS = [
    (75, "VERY_HIGH"),
    (60, "HIGH"),
    (45, "MEDIUM"),
    (0, "LOW"),
]

PITCH_ANGLES = {
    "absentee": (
        "You're a busy investor/landlord based elsewhere — we buy as-is, "
        "close remotely, and pay your asking price in cash with no repairs."
    ),
    "out_of_state": (
        "Since you're out of state we can handle everything remotely — "
        "walk away with a clean cash sale and no property-management hassle."
    ),
    "rental": (
        "Rental management headaches solved — we'll take the property off "
        "your hands as-is for a cash offer and handle the tenants."
    ),
    "code_concern": (
        "The city has an open case on this property — we can close fast "
        "with cash before it escalates into fines or further liens."
    ),
    "entity": (
        "As an entity owner you may be consolidating assets — we buy "
        "distressed/held properties outright for cash in one closing."
    ),
    "owner_occupied": (
        "We're local cash buyers looking for a few more properties this "
        "month — would you consider a cash offer on this one?"
    ),
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[SELLER MOTIVATION] {ts} - {msg}"
    print(line)
    try:
        with open(LOGS / "seller_motivation.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def normalize_addr(addr):
    return re_sub_addr(str(addr or "").upper())


def re_sub_addr(s):
    import re
    s = re.sub(r"[,\s]+", " ", s).strip()
    s = re.sub(r"\b(?:DALLAS|TX|TEXAS|US)\b.*$", "", s).strip()
    s = re.sub(r"\s+\d{5}(?:-\d{4})?\s*$", "", s).strip()
    return s


def detect_signal(d):
    sig = (d.get("Distress_Signal") or d.get("Signal_Type") or "").lower()
    if "code concern" in sig:
        return "code_concern"
    if "rental needs registration" in sig or "rental registration" in sig:
        return "rental_registration"
    if "vacation" in sig or "short term" in sig:
        return "vacation_rental"
    if "foreclosure" in sig:
        return "foreclosure"
    if "tax" in sig:
        return "tax_delinquent"
    if "probate" in sig:
        return "probate"
    if "vacant" in sig:
        return "vacant"
    return None


def is_entity_owner(lead, d):
    name = " ".join([
        str(lead.get("company") or ""),
        str(lead.get("contact") or ""),
        str(d.get("Owner_Name") or ""),
    ]).upper()
    return any(m in name for m in ENTITY_MARKERS)


def signal_recency_points(d):
    sdate = d.get("Signal_Date") or d.get("Verified_Date") or ""
    if not sdate:
        return 0
    try:
        parsed = datetime.fromisoformat(str(sdate).replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days
    except Exception:
        return 0
    if days <= 30:
        return 8
    if days <= 90:
        return 4
    if days <= 365:
        return 2
    return 0


def score_lead(lead):
    d = lead.get("details") or {}
    signals = []
    score = BASE_SCORE
    pitch = ""

    sig = detect_signal(d)
    if sig:
        score += SIGNAL_WEIGHTS.get(sig, 0)
        signals.append(sig)

    site_city = (d.get("City") or "").strip().upper()
    site_state = (d.get("State") or "").strip().upper()
    mail_city = (d.get("Owner_Mail_City") or "").strip().upper()
    mail_state = (d.get("Owner_Mail_State") or "").strip().upper()
    site_addr = normalize_addr(d.get("Site_Address") or lead_address(lead))
    mail_addr = normalize_addr(d.get("Owner_Mail_Address") or "")

    out_of_state = bool(mail_state) and site_state and mail_state != site_state
    absentee = (
        (mail_state and site_state and mail_state != site_state)
        or (mail_addr and site_addr and mail_addr != site_addr)
    )
    owner_occupied = bool(mail_addr) and site_addr and mail_addr == site_addr

    if absentee:
        score += 20
        signals.append("absentee")
    if out_of_state:
        score += 10
        signals.append("out_of_state")
    if owner_occupied:
        score -= 15
        signals.append("owner_occupied")

    if is_entity_owner(lead, d):
        score += 8
        signals.append("entity")

    recency = signal_recency_points(d)
    if recency:
        score += recency

    score = max(0, min(100, int(score)))

    if "absentee" in signals:
        pitch = PITCH_ANGLES["absentee"]
    elif "out_of_state" in signals:
        pitch = PITCH_ANGLES["out_of_state"]
    elif "rental_registration" in signals or "vacation_rental" in signals:
        pitch = PITCH_ANGLES["rental"]
    elif "code_concern" in signals:
        pitch = PITCH_ANGLES["code_concern"]
    elif "entity" in signals:
        pitch = PITCH_ANGLES["entity"]
    else:
        pitch = PITCH_ANGLES["owner_occupied"]

    tier = next(t for bound, t in TIER_BANDS if score >= bound)

    return {
        "motivation_score": score,
        "motivation_tier": tier,
        "motivation_signals": signals,
        "pitch_angle": pitch,
    }


def lead_address(lead):
    d = lead.get("details") or {}
    return d.get("Property_Address") or d.get("Address") or d.get("address") or ""


def load_json(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("queue", data.get("leads", data.get("data", [])))


def save_json(path, data, backup=False):
    if backup and path.exists():
        bak_dir = LOGS / "db_backups"
        bak_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, bak_dir / f"{path.stem}.{stamp}.bak.json")
    if path == DIALER_DB:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from MBM.LeadEngine.dialer_gateway import commit_dialer_db
        rows = data if isinstance(data, list) else data.get("leads", [])
        commit_dialer_db(rows, reason="seller_motivation_scorer", author="SELLER_MOTIVATION_SCORER")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


TIER_RANK = {"VERY_HIGH": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def sort_rank(row):
    return (
        TIER_RANK.get(str(row.get("motivation_tier") or "").upper(), 9),
        -(int(row.get("motivation_score") or 0)),
        str(row.get("contact_name") or row.get("contact") or ""),
    )


def main():
    ap = argparse.ArgumentParser(description="Seller Motivation Scorer")
    ap.add_argument("--apply", action="store_true", help="write results (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="max leads to score")
    ap.add_argument("--vertical", type=str, default="Real Estate Sellers,Master Catch-All",
                    help="comma-separated verticals")
    ap.add_argument("--sync-queues", action="store_true",
                    help="also propagate scores to RE dialer queues")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.vertical.split(",") if v.strip()]

    db = load_json(DIALER_DB)
    if not db:
        log(f"ERROR: {DIALER_DB} missing or empty — cannot run.")
        return
    log(f"Loaded {len(db)} leads from {DIALER_DB.name}")

    targets = [l for l in db if (l.get("vertical") or l.get("type") or "") in verticals]
    log(f"Targeting {len(targets)} seller leads in {', '.join(verticals)}")

    if args.limit:
        targets = targets[: args.limit]

    stats = {}
    for i, lead in enumerate(targets, 1):
        res = score_lead(lead)
        lead["motivation_score"] = res["motivation_score"]
        lead["motivation_tier"] = res["motivation_tier"]
        lead["motivation_signals"] = res["motivation_signals"]
        lead["pitch_angle"] = res["pitch_angle"]
        d = lead.setdefault("details", {})
        d["Motivation_Score"] = res["motivation_score"]
        d["Motivation_Tier"] = res["motivation_tier"]
        d["Motivation_Signals"] = res["motivation_signals"]
        d["Pitch_Angle"] = res["pitch_angle"]
        d["Motivated_At"] = datetime.now(timezone.utc).isoformat()
        lead["details"] = d
        stats[res["motivation_tier"]] = stats.get(res["motivation_tier"], 0) + 1
        log(f"[{i}/{len(targets)}] {lead.get('id')} -> "
            f"{res['motivation_score']} ({res['motivation_tier']}) "
            f"{','.join(res['motivation_signals']) or '-'}")

    if args.apply:
        # Route the live dialer DB through the canonical single-writer gateway
        # (atomic + locked + audited). save_json() is only used for the
        # non-authoritative RE dialer queues below.
        commit_dialer_db(
            db, reason="seller_motivation_scorer", author="SELLER_MOTIVATION_SCORER",
            allow_shrink=False,
        )
        log(f"Updated {len(db)} leads in {DIALER_DB.name} via canonical gateway")

        if args.sync_queues:
            db_by_id = {l.get("id"): l for l in db}
            db_by_parcel = {}
            for l in db:
                pid = (l.get("details") or {}).get("DCAD_Parcel_ID") or l.get("parcel_id")
                if pid:
                    db_by_parcel[pid] = l

            re_queue = load_json(RE_QUEUE)
            re_updated = 0
            for row in re_queue:
                src = db_by_id.get(row.get("deal_id"))
                if src:
                    row["motivation_score"] = src.get("motivation_score")
                    row["motivation_tier"] = src.get("motivation_tier")
                    row["motivation_signals"] = src.get("motivation_signals")
                    row["pitch_angle"] = src.get("pitch_angle")
                    re_updated += 1
            re_queue.sort(key=sort_rank)
            save_json(RE_QUEUE, re_queue, backup=True)
            log(f"Synced motivation scores to {RE_QUEUE.name} ({re_updated} rows, tier-sorted)")

            us_re_queue = load_json(US_RE_QUEUE)
            us_updated = 0
            for row in us_re_queue:
                src = db_by_parcel.get(row.get("parcel_id")) or db_by_id.get(
                    str(row.get("queue_id", "")).split("-")[-1])
                if src:
                    row["motivation_score"] = src.get("motivation_score")
                    row["motivation_tier"] = src.get("motivation_tier")
                    row["motivation_signals"] = src.get("motivation_signals")
                    row["pitch_angle"] = src.get("pitch_angle")
                    us_updated += 1
            us_re_queue.sort(key=sort_rank)
            save_json(US_RE_QUEUE, us_re_queue, backup=True)
            log(f"Synced motivation scores to {US_RE_QUEUE.name} ({us_updated} rows, tier-sorted)")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "database": str(DIALER_DB),
        "total_scored": len(targets),
        "tier_breakdown": stats,
        "queues_synced": bool(args.apply and args.sync_queues),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("  SELLER MOTIVATION SUMMARY (%s)" % report["mode"])
    print("=" * 60)
    print(f"  Scored    : {len(targets)}")
    for tier in ("VERY_HIGH", "HIGH", "MEDIUM", "LOW"):
        print(f"  {tier:<10}: {stats.get(tier, 0)}")
    print(f"  Report    : {REPORT}")
    print()
    if not args.apply:
        print("  DRY-RUN — no files changed. Re-run with --apply to write.")
    print()


if __name__ == "__main__":
    main()
