#!/usr/bin/env python3
"""
lead_pack_builder.py — Build a deliverable monthly Real-Estate Lead Pack from the
MBM Lead Engine pipeline, ready to ship to a Whop subscriber.

Outputs (Output Contract):
  status: success | failure | skipped
  inputs: { source, month, tier_filters }
  outputs: { pack_path, csv_path, count, verified_count, verification_rate, gate }
  errors: [ ... ]
  next_action: string
  owner: "system"
  timestamp: ISO8601

Wires into: leadPipeline.py (source), revenue_tracker.py (gate), Whop subscription.
Gate: a pack is "ship-ready" only when contact-verification >= REQUIRED_VERIFICATION_RATE.
"""
import base64
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

QUEUE_FILE = BASE_DIR / "cold_calling_queue.json"
RE_LIST_FILE = BASE_DIR / "real_estate_calling_queue.json"
ENRICHED_FILE = BASE_DIR / "enriched_global_leads.json"
OUT_DIR = BASE_DIR / "lead_packs"
OUT_DIR.mkdir(exist_ok=True)

REQUIRED_VERIFICATION_RATE = 0.75   # 75% of rows must have a valid phone+email
LEAD_TIERS = ("Tier A+", "Tier A")  # highest-intent tiers sold first
MAX_ROWS = 100                      # per pack


def _load_json(path, default=None):
    if default is None:
        default = []
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _contract(status, inputs, outputs, errors, next_action, owner="system"):
    return {
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "errors": errors,
        "next_action": next_action,
        "owner": owner,
        "timestamp": _stamp(),
    }


def _norm(v):
    v = (v or "").strip()
    return v


def _is_verified_phone(v):
    digits = "".join(c for c in _norm(v) if c.isdigit())
    return len(digits) >= 10


def _is_verified_email(v):
    v = _norm(v)
    return "@" in v and "." in v.split("@")[-1]


def _row_from_re(item):
    """Normalise a real-estate calling queue entry (buyer/seller deal leads)."""
    return {
        "contact_name": _norm(item.get("contact_name") or item.get("company_name")),
        "title": _norm(item.get("role_type")),
        "entity": _norm(item.get("company_name")) or _norm(item.get("contact_name")),
        "phone": _norm(item.get("phone_number") or item.get("phone")),
        "email": _norm(item.get("email") or item.get("agent_email")),
        "address": _norm(item.get("property_address")),
        "city": _norm(item.get("city")),
        "state": _norm(item.get("state")),
        "priority_score": _norm(item.get("antigravity_score") or item.get("priority_score")),
        "tier": _norm(item.get("tier")) or "Tier A",
        "deal_id": _norm(item.get("deal_id")),
        "est_arv": _norm(item.get("est_arv")),
        "asking_price": _norm(item.get("asking_price")),
        "target_cash_offer": _norm(item.get("target_cash_offer")),
        "est_assignment_profit": _norm(item.get("est_assignment_profit")),
        "distress_signal": _norm(item.get("distress_signal")),
        "source": "real estate",
    }


def _row_from_queue(item):
    """Normalise a cold-calling/outreach queue entry into a pack row."""
    tier = _norm(item.get("tier") or item.get("priority_tier"))
    return {
        "contact_name": _norm(item.get("contact_name") or item.get("name")),
        "title": _norm(item.get("title")),
        "entity": _norm(item.get("entity") or item.get("company") or item.get("agent")),
        "phone": _norm(item.get("phone") or item.get("agent_phone")),
        "email": _norm(item.get("email") or item.get("agent_email")),
        "address": _norm(item.get("address")),
        "city": _norm(item.get("city")),
        "state": _norm(item.get("state") or item.get("country")),
        "priority_score": _norm(item.get("priority_score")),
        "tier": tier or "Tier A",
        "source": "outreach",
    }


def _collect_rows(source=None):
    """source: 'real_estate' | 'outreach' | None (all). Cash-buyer/seller first."""
    rows = []
    if source in (None, "real_estate") and RE_LIST_FILE.exists():
        data = _load_json(RE_LIST_FILE, [])
        seq = data.get("queue", data) if isinstance(data, dict) else data
        if isinstance(seq, list):
            for item in seq:
                if isinstance(item, dict):
                    rows.append(_row_from_re(item))
    if source in (None, "outreach") and QUEUE_FILE.exists():
        data = _load_json(QUEUE_FILE, [])
        seq = data.get("queue", data) if isinstance(data, dict) else data
        if isinstance(seq, list):
            for item in seq:
                if isinstance(item, dict):
                    rows.append(_row_from_queue(item))
    if source in (None, "lead engine"):
        rows += _rows_from_enriched()
    return rows


def _rows_from_enriched():
    """Complement queue rows with verified real-estate buyer/seller leads."""
    leads = _load_json(ENRICHED_FILE, [])
    rows = []
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        status = _norm(lead.get("verification_status"))
        if "INVALID" in status.upper():
            continue
        rows.append({
            "contact_name": _norm(lead.get("agent") or lead.get("contact")),
            "title": "Agent" if ("agent" in lead and lead.get("agent")) else "Seller",
            "entity": _norm(lead.get("entity")) or _norm(lead.get("address")),
            "phone": _norm(lead.get("verified_phone") or lead.get("phone") or lead.get("agent_phone")),
            "email": _norm(lead.get("email") or lead.get("agent_email")),
            "address": _norm(lead.get("address")),
            "city": _norm(lead.get("city")),
            "state": _norm(lead.get("state")),
            "priority_score": str(lead.get("lead_score") or ""),
            "tier": _norm(lead.get("tier")) or "Tier A",
            "source": "lead engine",
        })
    return rows


def _score_row(row):
    """0..100 contact-verification + intent score."""
    score = 0
    if _is_verified_phone(row["phone"]):
        score += 45
    if _is_verified_email(row["email"]):
        score += 35
    if row.get("tier") in ("Tier A+", "Tier A"):
        score += 10
    if row.get("priority_score"):
        try:
            if int(str(row["priority_score"]).rstrip("%")) >= 70:
                score += 10
        except Exception:
            pass
    return min(score, 100)


def _build_pack(month, tier_filter, limit, source=None):
    rows = _collect_rows(source)
    if tier_filter:
        rows = [r for r in rows if r["tier"] in tier_filter]
    for r in rows:
        r["_score"] = _score_row(r)
    rows.sort(key=lambda r: r["_score"], reverse=True)
    pack = rows[:limit]
    for r in pack:
        r["verified"] = _is_verified_phone(r["phone"]) and _is_verified_email(r["email"])
    verified = sum(1 for r in pack if r["verified"])
    rate = (verified / len(pack)) if pack else 0.0
    return pack, verified, rate


def _write_deliverables(pack, month):
    safe_month = month.replace("-", "")
    csv_path = OUT_DIR / f"lead_pack_{safe_month}.csv"
    manifest_path = OUT_DIR / f"manifest_{safe_month}.json"

    # Strip internal scoring keys for the deliverable.
    deliver = []
    for r in pack:
        deliver.append({
            k: v for k, v in r.items() if not k.startswith("_")
        })

    fields = ["contact_name", "title", "entity", "phone", "email",
              "address", "city", "state", "priority_score", "tier",
              "deal_id", "est_arv", "asking_price", "target_cash_offer",
              "est_assignment_profit", "distress_signal", "source"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deliver)

    manifest = {
        "month": month,
        "generated_at": _stamp(),
        "count": len(deliver),
        "verified_count": sum(1 for r in pack if r["verified"]),
        "verification_rate": round(len(deliver) and sum(1 for r in pack if r["verified"]) / len(deliver), 3),
        "tiers": sorted({r["tier"] for r in deliver}),
        "csv_path": str(csv_path),
        "sample_hashes": [hashlib.sha1(f"{r['phone']}|{r['email']}".encode()).hexdigest()[:12] for r in deliver[:5]],
    }
    _save_json(manifest_path, manifest)
    return csv_path, manifest_path


def cmd_build(month=None, tier_filter=None, limit=MAX_ROWS, source=None):
    month = month or datetime.now().strftime("%Y-%m")
    pack, verified, rate = _build_pack(month, tier_filter, limit, source)
    csv_path, manifest_path = _write_deliverables(pack, month)

    gate = rate >= REQUIRED_VERIFICATION_RATE
    outputs = {
        "month": month,
        "count": len(pack),
        "verified_count": verified,
        "verification_rate": round(rate, 3),
        "gate_passed": gate,
        "csv_path": str(csv_path),
        "manifest_path": str(manifest_path),
    }
    errors = []
    if not pack:
        errors.append("no leads matched the tier filter")
        return _contract("failure", {"month": month}, outputs, errors, "check_pipeline_harvest")

    next_action = "ship_to_whop" if gate else "fix_contact_verification"
    owner = "system"
    _save_json(LOGS_DIR / "lead_pack_builder_log.json", outputs)
    return _contract("success", {"month": month, "tier_filter": tier_filter, "source": source}, outputs, errors, next_action, owner)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build a deliverable Real-Estate Lead Pack.")
    parser.add_argument("--month", default=None)
    parser.add_argument("--tiers", nargs="*", default=["Tier A+", "Tier A"], help="Tiers to include")
    parser.add_argument("--limit", type=int, default=MAX_ROWS)
    parser.add_argument("--source", default="real_estate", help="real_estate | outreach | lead engine | '' (all)")
    args = parser.parse_args()
    result = cmd_build(args.month, args.tiers, args.limit, args.source)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)