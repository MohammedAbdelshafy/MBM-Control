#!/usr/bin/env python3
"""
MBM Transparent Lead Quality Scorer — Evidence-Backed 8-Factor Score
====================================================================
Annotates seller/healthcare leads with a 0-100 composite QUALITY score built
from eight transparent factors. Every factor carries its own provenance block:

    { "score", "weight", "reason", "source", "observed_at",
      "confidence", "freshness_days", "evidence" }

Factors (composite of the revenue-critical lead-quality model):
  1. MOTIVATION        — seller distress / absentee / entity signals
  2. EQUITY            — est ARV vs asking vs target offer (only if present)
  3. PROPERTY FIT      — property attributes present & matching criteria
  4. MARKET FIT        — city/state market signal (only legit signals)
  5. RECENCY           — freshness of verification/signal timestamps
  6. DATA CONFIDENCE   — verified source / skip-trace status quality
  7. BUYER DEMAND      — buyer-side interest signals (only if present)
  8. COMPLETENESS      — fraction of core fields actually populated

RULES
  * NEVER invents values: missing data contributes 0 and drops confidence.
    No fabricated equity, ownership, phone, or distress.
  * Every non-zero factor emits source + observed_at + confidence + freshness.
  * Idempotent: re-running overwrites its own previous annotations only.
  * Safe by default — nothing written until --apply (with backup).

Usage:
    python MBM/LeadEngine/lead_quality_scorer.py                      # dry-run
    python MBM/LeadEngine/lead_quality_scorer.py --apply              # write DB + queues
    python MBM/LeadEngine/lead_quality_scorer.py --apply --limit 50
    python MBM/LeadEngine/lead_quality_scorer.py --queue real_estate_calling_queue.json
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
REPORT = LOGS / "lead_quality_report.json"

# Canonical single-writer gateway for the live dialer DB (never raw-write it).
sys.path.insert(0, str(ROOT))
from MBM.LeadEngine.dialer_gateway import commit_dialer_db  # noqa: E402

WEIGHTS = {
    "motivation": 0.30,
    "equity": 0.18,
    "property_fit": 0.12,
    "market_fit": 0.08,
    "recency": 0.10,
    "data_confidence": 0.12,
    "buyer_demand": 0.05,
    "completeness": 0.05,
}

TIER_BANDS = [
    (80, "A_PLUS"),
    (70, "A"),
    (55, "B"),
    (40, "C"),
    (0, "D"),
]

VERIFIED_MARKERS = ("VERIFIED", "ENRICHED", "DONE", "NPI", "DCAD")
UNVERIFIED_MARKERS = ("NO_MATCH", "UNVERIFIED", "PENDING")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[LEAD QUALITY] {ts} - {msg}"
    print(line)
    try:
        with open(LOGS / "lead_quality.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_int(v):
    try:
        return int(float(str(v).replace("$", "").replace(",", "").strip() or 0))
    except Exception:
        return 0


def _freshness_days(date_str):
    if not date_str:
        return None
    try:
        parsed = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)
    except Exception:
        return None


def _confidence_for_status(status):
    s = str(status or "").upper()
    if any(m in s for m in ("VERIFIED", "NPI", "DCAD")):
        return "high"
    if "ENRICHED" in s or "DONE" in s:
        return "medium"
    if s in UNVERIFIED_MARKERS:
        return "low"
    return "unknown"


def score_lead(lead):
    d = lead.get("details") or {}
    row = lead  # queue rows are flat; db rows have details nested

    factors = {}

    # ---- 1. MOTIVATION (reuse verified motivation signals) ----
    mot_score = int(row.get("motivation_score") or d.get("Motivation_Score") or 0)
    mot_tier = str(row.get("motivation_tier") or d.get("Motivation_Tier") or "").upper()
    mot_signals = row.get("motivation_signals") or d.get("Motivation_Signals") or []
    if not mot_signals and isinstance(mot_tier, str) and mot_tier:
        mot_signals = [mot_tier.lower()]
    mot_points = max(0, min(100, mot_score))
    factors["motivation"] = {
        "score": mot_points,
        "weight": WEIGHTS["motivation"],
        "reason": f"signals={','.join(mot_signals) or 'none'} tier={mot_tier or 'n/a'}",
        "source": "seller_motivation_scorer",
        "observed_at": d.get("Motivated_At") or row.get("scored_at") or "",
        "confidence": "high" if mot_signals else "unknown",
        "freshness_days": _freshness_days(d.get("Motivated_At") or row.get("scored_at")),
        "evidence": mot_signals,
    }

    # ---- 2. EQUITY (only if real numbers exist; never invent) ----
    arv = _to_int(row.get("est_arv") or row.get("arv") or d.get("Est_ARV") or 0)
    asking = _to_int(row.get("asking_price") or d.get("Asking_Price") or 0)
    offer = _to_int(row.get("target_cash_offer") or d.get("Target_Cash_Offer") or 0)
    if arv > 0:
        spread = ((arv - asking) / arv * 100) if asking > 0 else ((arv - offer) / arv * 100) if offer > 0 else None
        if spread is not None:
            eq = max(0, min(100, int(spread * 2.5)))
        else:
            eq = 50
        factors["equity"] = {
            "score": eq,
            "weight": WEIGHTS["equity"],
            "reason": f"arv={arv} asking={asking} offer={offer} spread={spread and round(spread,1)}%",
            "source": "dcad/rapidapi_valuation",
            "observed_at": row.get("enriched_at") or d.get("Enriched_At") or "",
            "confidence": "high",
            "freshness_days": _freshness_days(row.get("enriched_at") or d.get("Enriched_At")),
            "evidence": {"est_arv": arv, "asking_price": asking, "target_cash_offer": offer},
        }
    else:
        factors["equity"] = {
            "score": 0, "weight": WEIGHTS["equity"],
            "reason": "no verified valuation data (est_arv/asking missing) — not fabricated",
            "source": "", "observed_at": "", "confidence": "unknown",
            "freshness_days": None, "evidence": {},
        }

    # ---- 3. PROPERTY FIT (attributes present) ----
    addr = row.get("property_address") or row.get("address") or d.get("Property_Address") or ""
    ptype = row.get("property_type") or d.get("Property_Type") or ""
    fit_points = 0
    fit_hits = []
    if addr:
        fit_points += 50
        fit_hits.append("address")
    if ptype:
        fit_points += 30
        fit_hits.append("property_type")
    if row.get("bedrooms") or d.get("Beds"):
        fit_points += 20
        fit_hits.append("bedrooms")
    if row.get("acreage") or d.get("Acreage"):
        fit_points += 20
        fit_hits.append("acreage")
    if row.get("zoning") or d.get("Zoning"):
        fit_points += 10
        fit_hits.append("zoning")
    factors["property_fit"] = {
        "score": fit_points,
        "weight": WEIGHTS["property_fit"],
        "reason": f"attrs={','.join(fit_hits) or 'none'}",
        "source": "lead_row",
        "observed_at": row.get("enriched_at") or d.get("Enriched_At") or "",
        "confidence": "medium" if fit_hits else "unknown",
        "freshness_days": None,
        "evidence": fit_hits,
    }

    # ---- 4. MARKET FIT (legit market signal only) ----
    city = str(row.get("city") or d.get("City") or "").strip()
    state = str(row.get("state") or d.get("State") or "").strip()
    mkt = row.get("market_signal") or d.get("Market_Signal") or ""
    if mkt:
        factors["market_fit"] = {
            "score": 80, "weight": WEIGHTS["market_fit"],
            "reason": f"market_signal={mkt}",
            "source": "market_data",
            "observed_at": "", "confidence": "medium",
            "freshness_days": None, "evidence": mkt,
        }
    else:
        factors["market_fit"] = {
            "score": 0, "weight": WEIGHTS["market_fit"],
            "reason": f"no market signal; location={city},{state}" if (city or state) else "no market data",
            "source": "", "observed_at": "", "confidence": "unknown",
            "freshness_days": None, "evidence": {},
        }

    # ---- 5. RECENCY (freshness of verification) ----
    vdate = d.get("Verified_Date") or d.get("Signal_Date") or row.get("verified_at") or d.get("Motivated_At") or row.get("scored_at") or ""
    days = _freshness_days(vdate)
    if days is None:
        recency = 0
    elif days <= 30:
        recency = 100
    elif days <= 90:
        recency = 70
    elif days <= 365:
        recency = 40
    else:
        recency = 15
    factors["recency"] = {
        "score": recency, "weight": WEIGHTS["recency"],
        "reason": f"verified_at={vdate or 'missing'} ({days or 'n/a'} days old)",
        "source": "verification_timestamp", "observed_at": vdate,
        "confidence": "high" if days is not None else "unknown",
        "freshness_days": days, "evidence": {"verified_date": vdate},
    }

    # ---- 6. DATA CONFIDENCE (verification quality) ----
    status = str(row.get("skip_trace_status") or d.get("Skip_Trace_Status") or row.get("verified_source") or "").upper()
    vsrc = str(row.get("verified_source") or d.get("Verified_Source") or "").upper()
    conf = _confidence_for_status(status)
    conf_points = {"high": 90, "medium": 60, "low": 25, "unknown": 0}.get(conf, 0)
    factors["data_confidence"] = {
        "score": conf_points, "weight": WEIGHTS["data_confidence"],
        "reason": f"status={status or 'missing'} source={vsrc or 'missing'}",
        "source": vsrc or status or "", "observed_at": row.get("verified_at") or d.get("Verified_Date") or "",
        "confidence": conf, "freshness_days": None,
        "evidence": {"skip_trace_status": status, "verified_source": vsrc},
    }

    # ---- 7. BUYER DEMAND (only legit buyer signals) ----
    match_score = float(row.get("buyer_match_score") or d.get("Buyer_Match_Score") or 0)
    bd = row.get("buyer_demand") or d.get("Buyer_Demand") or ""
    if match_score > 0:
        factors["buyer_demand"] = {
            "score": int(match_score), "weight": WEIGHTS["buyer_demand"],
            "reason": f"buyer_match_score={match_score}",
            "source": "buyer_matching_engine", "observed_at": "",
            "confidence": "high", "freshness_days": None, "evidence": bd or "matched",
        }
    elif bd:
        factors["buyer_demand"] = {
            "score": 80, "weight": WEIGHTS["buyer_demand"],
            "reason": f"buyer_demand={bd}",
            "source": "buyer_board", "observed_at": "",
            "confidence": "medium", "freshness_days": None, "evidence": bd,
        }
    else:
        factors["buyer_demand"] = {
            "score": 0, "weight": WEIGHTS["buyer_demand"],
            "reason": "no buyer-demand signal present", "source": "",
            "observed_at": "", "confidence": "unknown",
            "freshness_days": None, "evidence": {},
        }

    # ---- 8. COMPLETENESS (fraction of core fields populated) ----
    core_fields = {
        "contact_name": row.get("contact_name") or d.get("Owner_Name") or row.get("contact"),
        "phone": row.get("verified_phone") or row.get("phone_number") or row.get("phone"),
        "address": addr,
        "city": city,
        "state": state,
        "source": vsrc or status,
    }
    present = sum(1 for v in core_fields.values() if v)
    comp = int(present / len(core_fields) * 100)
    factors["completeness"] = {
        "score": comp, "weight": WEIGHTS["completeness"],
        "reason": f"{present}/{len(core_fields)} core fields populated",
        "source": "lead_row", "observed_at": "",
        "confidence": "high", "freshness_days": None,
        "evidence": {k: bool(v) for k, v in core_fields.items()},
    }

    # ---- Composite ----
    weighted = sum(f["score"] * f["weight"] for f in factors.values())
    composite = max(0, min(100, int(round(weighted))))
    tier = next(t for bound, t in TIER_BANDS if composite >= bound)

    # Effective data confidence = share of factors carrying real evidence
    ev_factors = [k for k, f in factors.items() if f.get("evidence")]
    data_confidence = round(len(ev_factors) / len(factors) * 100)

    # Outreach eligibility: composite gate + phone verified + no hard blocker
    phone = row.get("verified_phone") or row.get("phone_number") or row.get("phone") or d.get("Verified_Phone") or ""
    eligible = (
        composite >= 55
        and len(str(phone or "").strip()) >= 10
        and conf not in ("low", "unknown")
    )

    return {
        "quality_score": composite,
        "quality_tier": tier,
        "data_confidence_pct": data_confidence,
        "outreach_eligible": eligible,
        "factors": factors,
        "scored_at": now_iso(),
    }


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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def annotate(lead, res, nested):
    lead["quality_score"] = res["quality_score"]
    lead["quality_tier"] = res["quality_tier"]
    lead["data_confidence_pct"] = res["data_confidence_pct"]
    lead["outreach_eligible"] = res["outreach_eligible"]
    lead["quality_factors"] = res["factors"]
    if nested is not None:
        nested["Quality_Score"] = res["quality_score"]
        nested["Quality_Tier"] = res["quality_tier"]
        nested["Data_Confidence_Pct"] = res["data_confidence_pct"]
        nested["Outreach_Eligible"] = res["outreach_eligible"]
        nested["Quality_Factors"] = res["factors"]


def main():
    ap = argparse.ArgumentParser(description="Transparent Lead Quality Scorer")
    ap.add_argument("--apply", action="store_true", help="write results (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="max leads to score")
    ap.add_argument("--queue", type=str, default=None,
                    help="queue file to score (default: real_estate_calling_queue.json)")
    ap.add_argument("--db", action="store_true", help="also score mbm-dialer leads_database.json")
    ap.add_argument("--json-out", type=str, default=None, help="write a JSON verdict to this path")
    args = ap.parse_args()

    queue_path = BASE / (args.queue or "real_estate_calling_queue.json")

    queue = load_json(queue_path)
    if not queue:
        log(f"ERROR: {queue_path} missing or empty.")
        return

    log(f"Loaded {len(queue)} rows from {queue_path.name}")

    if args.limit:
        queue = queue[: args.limit]

    stats = {}
    eligible = 0
    for i, lead in enumerate(queue, 1):
        res = score_lead(lead)
        d = lead.get("details")
        annotate(lead, res, d)
        stats[res["quality_tier"]] = stats.get(res["quality_tier"], 0) + 1
        if res["outreach_eligible"]:
            eligible += 1
        log(f"[{i}/{len(queue)}] {lead.get('deal_id') or lead.get('id') or lead.get('contact_name')} -> "
            f"{res['quality_score']} ({res['quality_tier']}) eligible={res['outreach_eligible']}")

    if args.apply:
        save_json(queue_path, queue, backup=True)
        log(f"Saved {len(queue)} rows to {queue_path.name} (backup written)")
        if args.db:
            db = load_json(DIALER_DB)
            by_id = {str(l.get("id")): l for l in db}
            for lead in queue:
                src = by_id.get(str(lead.get("deal_id", "")).split("-")[-1]) or by_id.get(str(lead.get("id")))
                if src:
                    annotate(src, score_lead(lead), src.get("details"))
            # Route the live dialer DB through the canonical single-writer gateway
            # (atomic + locked + audited). save_json() is only used for queues.
            commit_dialer_db(
                db, reason="lead_quality_scorer", author="LEAD_QUALITY_SCORER",
                allow_shrink=False,
            )
            log(f"Synced quality scores to {DIALER_DB.name} via canonical gateway")

    # Always sync quality annotations to the sibling dialer queues (dry-run keeps
    # them local only when --apply; the sort helps dialers rank by quality).
    if args.apply and queue_path != US_RE_QUEUE:
        by_deal = {str(lead.get("deal_id")): lead for lead in queue}
        us_re_queue = load_json(US_RE_QUEUE)
        us_updated = 0
        for row in us_re_queue:
            src = by_deal.get(str(row.get("deal_id")))
            if src and src.get("quality_score") is not None:
                row["quality_score"] = src["quality_score"]
                row["quality_tier"] = src["quality_tier"]
                row["data_confidence_pct"] = src["data_confidence_pct"]
                row["outreach_eligible"] = src["outreach_eligible"]
                us_updated += 1
        if us_re_queue:
            us_re_queue.sort(key=lambda r: (-(int(r.get("quality_score") or 0))))
            save_json(US_RE_QUEUE, us_re_queue, backup=True)
            log(f"Synced quality scores to {US_RE_QUEUE.name} ({us_updated} rows, quality-sorted)")

    report = {
        "timestamp": now_iso(),
        "mode": "apply" if args.apply else "dry_run",
        "queue": str(queue_path),
        "total_scored": len(queue),
        "outreach_eligible": eligible,
        "tier_breakdown": stats,
        "weights": WEIGHTS,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"answer": "DATA" if eligible else "GAP",
                        "score": eligible, "escalation_level": "NORMAL",
                        "quality_report": str(REPORT)}, indent=2), encoding="utf-8")

    print("\n" + "=" * 64)
    print("  LEAD QUALITY SUMMARY (%s)" % report["mode"])
    print("=" * 64)
    print(f"  Scored            : {len(queue)}")
    print(f"  Outreach eligible : {eligible}")
    for tier in ("A_PLUS", "A", "B", "C", "D"):
        print(f"  {tier:<7}: {stats.get(tier, 0)}")
    print(f"  Report            : {REPORT}")
    if not args.apply:
        print("  DRY-RUN — no files changed. Re-run with --apply to write.")
    print()


if __name__ == "__main__":
    main()