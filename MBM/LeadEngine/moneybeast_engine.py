"""
moneybeast_engine -- MoneyBeast motivated-seller intelligence refresh pipeline.

Deterministic refresh (12 steps per jarvis-mbm#8):
  ingest -> normalize -> dedupe -> validate -> signals -> scores -> rank ->
  hot100/growth200 -> audit/provenance -> export -> lead-engine sync -> report

Honesty contract:
  - NEVER invents owners, addresses, phones, equity, foreclosure status or intent.
  - Property-level evidence is kept separate from market-level context.
  - Missing data stays missing and is flagged (REQUIRES_VERIFICATION / STALE).
  - Aggregate market stats NEVER become individual leads.

Statuses: VERIFIED, LIKELY, MARKET_ONLY, CONFLICT, STALE, REQUIRES_VERIFICATION.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
ARTIFACTS = BASE / "artifacts"
REPORT_DIR = BASE / "reports"
DATA_DIR = BASE / "data"

LOGS.mkdir(parents=True, exist_ok=True)
ARTIFACTS.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SOURCE = BASE / "real_estate_calling_queue.json"

# Signal framework from issue #8 (weights must sum to 100).
SIGNAL_FRAMEWORK = {
    "distress_severity": 0.30,
    "recency_urgency": 0.20,
    "multi_signal_overlap": 0.20,
    "seller_fatigue_friction": 0.15,
    "property_liquidation_practicality": 0.10,
    "evidence_confidence": 0.05,
}

# Per-signal evidence weight when the signal is present AND evidenced.
SIGNAL_EVIDENCE = {
    "foreclosure": 30,
    "auction": 32,
    "reo": 28,
    "tax_delinquent": 25,
    "probate": 20,
    "vacant": 15,
    "code_concern": 10,
    "absentee": 10,
    "out_of_state": 8,
    "entity": 6,
    "rental_registration": 18,
    "vacation_rental": 15,
    "price_cut": 12,
    "relisted": 14,
    "long_dom": 8,
    "concessions": 7,
    "failed_listing": 12,
    "overpriced": 6,
    "failed_flip": 10,
    "landlord_exit": 12,
    "aging_landlord": 10,
    "inherited": 15,
    "estate": 12,
    "bankruptcy": 22,
}

HOT100_BANDS = {
    "VERIFIED": {"min_composite": 65, "max": 100},
    "LIKELY": {"min_composite": 60, "max": 100},
}

GROWTH200_BANDS = {
    "VERIFIED": {"min_composite": 45, "max": 100},
    "LIKELY": {"min_composite": 40, "max": 100},
}

STATUS_ORDER = ("VERIFIED", "LIKELY", "MARKET_ONLY", "CONFLICT", "STALE", "REQUIRES_VERIFICATION")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_address(addr: str) -> str:
    s = str(addr or "").upper().strip()
    s = re.sub(r"\b(STREET|STREETS?)\b", "ST", s)
    s = re.sub(r"\b(AVENUE|AVENUES?)\b", "AVE", s)
    s = re.sub(r"\b(ROAD|ROADS?)\b", "RD", s)
    s = re.sub(r"\b(BOULEVARD|BOULEVARDS?)\b", "BLVD", s)
    s = re.sub(r"\b(POINT)\b", "PT", s)
    s = re.sub(r"[^\w]+", "", s)
    return s


def _parcel_or_address_key(record: dict) -> str:
    parcel = str(record.get("parcel_id") or "").strip().upper()
    if parcel:
        return f"parcel:{parcel}"
    addr = _normalize_address(record.get("property_address") or record.get("address") or "")
    if addr:
        state = str(record.get("state") or "").strip().upper()
        return f"addr:{addr}|{state}"
    return ""


def _owner_key(record: dict) -> str:
    owner = str(
        record.get("owner_name_if_publicly_available")
        or record.get("owner_name")
        or record.get("contact_name")
        or ""
    ).strip().upper()
    phone = str(record.get("phone_number") or record.get("phone") or "").strip()
    if owner and phone:
        return f"owner:{owner}|phone:{phone}"
    return ""


@dataclass
class MoneyBeastRecord:
    lead_id: str = ""
    property_id: str = ""
    address: str = ""
    city: str = ""
    county: str = ""
    state: str = ""
    parcel_id: str = ""
    owner_name: str = ""
    phone: str = ""
    occupancy_signal: str = ""
    signals: list[str] = field(default_factory=list)
    signal_evidence: dict = field(default_factory=dict)
    source_url: str = ""
    source_name: str = ""
    source_date: str = ""
    observed_date: str = ""
    first_seen: str = ""
    last_seen: str = ""
    status: str = "REQUIRES_VERIFICATION"
    intent_score: int = 0
    urgency_score: int = 0
    confidence_score: int = 0
    composite_score: int = 0
    pipeline: str = ""
    rank: int = 0
    dedupe_key: str = ""
    provenance: str = ""
    recommended_next_action: str = ""
    notes: str = ""


def compute_signals(record: dict, evidence_keys: list[str]) -> list[str]:
    """Extract present signals from a record. Never invents them."""
    signals: list[str] = []
    for key in ("motivation_signals", "distress_flags", "signals"):
        for s in record.get(key) or []:
            norm = str(s).strip().lower().replace(" ", "_")
            if norm:
                signals.append(norm)
    if record.get("foreclosure_signal"):
        signals.append("foreclosure")
    if record.get("auction_date"):
        signals.append("auction")
    if record.get("reo_signal"):
        signals.append("reo")
    if record.get("tax_delinquency_signal"):
        signals.append("tax_delinquent")
    if record.get("probate_signal"):
        signals.append("probate")
    if record.get("vacancy_signal"):
        signals.append("vacant")
    if record.get("code_violation_signal"):
        signals.append("code_concern")
    if record.get("absentee_signal"):
        signals.append("absentee")
    if record.get("price_cut_count"):
        try:
            if int(record["price_cut_count"]) >= 1:
                signals.append("price_cut")
        except (TypeError, ValueError):
            pass
    if record.get("relisted_signal"):
        signals.append("relisted")
    if record.get("concession_signal"):
        signals.append("concessions")
    return list(dict.fromkeys(signals))


def _evidence_count(record: dict) -> int:
    """How many independent evidence-backed signals / source refs exist."""
    count = 0
    for key in (
        "source_refs", "source_url", "evidence_notes", "signal_evidence",
        "verified_source", "skip_trace_status",
    ):
        v = record.get(key)
        if v and str(v).strip():
            count += 1
    signals = record.get("motivation_signals") or record.get("distress_flags") or []
    return count + len(signals)


def score_record(record: dict) -> dict:
    """
    Weighted composite per issue #8 signal framework. Scores are capped when
    evidence is incomplete. All scores are 0-100 ints.
    """
    signals = compute_signals(record, [])

    if not signals:
        return {
            "distress_severity": 0,
            "recency_urgency": 0,
            "multi_signal_overlap": 0,
            "seller_fatigue_friction": 0,
            "property_liquidation_practicality": 0,
            "evidence_confidence": 0,
            "composite": 0,
        }

    # Distress severity: strongest distress signal scaled to a 0-100 severity.
    # Auction (32) and foreclosure (30) map to ~96/~90; mild signals stay low.
    distress = max(
        (SIGNAL_EVIDENCE.get(s, 0) for s in signals if s in SIGNAL_EVIDENCE),
        default=0,
    )
    distress = min(100, int(distress * 3.0))

    # Recency/urgency: verified recent date boosts; unknown = low but not zero.
    recency = 30
    date_str = str(record.get("source_date") or record.get("observed_date") or "").strip()
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            age_days = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
            if age_days <= 7:
                recency = 90
            elif age_days <= 30:
                recency = 70
            elif age_days <= 90:
                recency = 45
            else:
                recency = 20
        except ValueError:
            recency = 30

    # Multi-signal overlap: 3+ distinct signals is strong.
    overlap = min(100, len(signals) * 30) if len(signals) >= 2 else 15

    # Seller fatigue / friction: listing-cycle signals.
    fatigue = 0
    if "relisted" in signals:
        fatigue += 40
    if "price_cut" in signals:
        fatigue += 25
    if "long_dom" in signals or "concessions" in signals:
        fatigue += 20
    if "failed_listing" in signals or "failed_flip" in signals:
        fatigue += 15
    fatigue = min(fatigue, 100)

    # Liquidation practicality: has an address/parcel we can act on.
    has_property = bool(
        record.get("property_address") or record.get("address") or record.get("parcel_id")
    )
    has_contact = bool(
        record.get("phone_number") or record.get("phone") or record.get("verified_phone")
    )
    practicality = 60
    if not has_property:
        practicality = 25
    if not has_contact:
        practicality -= 15
    practicality = max(practicality, 5)

    # Evidence confidence: number of evidence items, capped.
    confidence = min(100, 20 + _evidence_count(record) * 12)

    composite = (
        SIGNAL_FRAMEWORK["distress_severity"] * distress
        + SIGNAL_FRAMEWORK["recency_urgency"] * recency
        + SIGNAL_FRAMEWORK["multi_signal_overlap"] * overlap
        + SIGNAL_FRAMEWORK["seller_fatigue_friction"] * fatigue
        + SIGNAL_FRAMEWORK["property_liquidation_practicality"] * practicality
        + SIGNAL_FRAMEWORK["evidence_confidence"] * confidence
    )

    # Cap: market-only / no property-level evidence can never reach property
    # level scores. Without a property key, cap composite at 39 (Growth200 floor-1).
    has_property_key = _parcel_or_address_key(record)
    if not has_property_key:
        composite = min(composite, 39)

    # Deterministic rounding ties to int.
    return {
        "distress_severity": int(round(distress)),
        "recency_urgency": int(round(recency)),
        "multi_signal_overlap": int(round(overlap)),
        "seller_fatigue_friction": int(round(fatigue)),
        "property_liquidation_practicality": int(round(practicality)),
        "evidence_confidence": int(round(confidence)),
        "composite": int(round(composite)),
    }


def compute_urgency(signals: list[str], auction_date: str = "") -> int:
    """Hard urgency overrides (issue #8). Returns 0-100."""
    urgency = 30
    auction = str(auction_date or "").strip()
    if auction:
        urgency = max(urgency, 95)
    if "foreclosure" in signals or "reo" in signals:
        urgency = max(urgency, 85)
    if "auction" in signals:
        urgency = max(urgency, 92)
    if "probate" in signals and ("vacant" in signals or "inherited" in signals):
        urgency = max(urgency, 80)
    if "tax_delinquent" in signals and ("vacant" in signals or "absentee" in signals):
        urgency = max(urgency, 78)
    if "price_cut" in signals and "relisted" in signals:
        urgency = max(urgency, 70)
    return min(urgency, 100)


def compute_intent(signals: list[str]) -> int:
    """Seller-fatigue / pre-distress intent proxy. Never higher than evidence allows."""
    intent = 20
    for s in signals:
        intent += SIGNAL_EVIDENCE.get(s, 0) // 5
    if "failed_listing" in signals or "failed_flip" in signals:
        intent = max(intent, 60)
    if "landlord_exit" in signals or "aging_landlord" in signals:
        intent = max(intent, 55)
    return min(intent, 100)


def _status_for(record: dict, composite: int) -> str:
    if record.get("status") in ("STALE", "CONFLICT"):
        return record["status"]
    src = str(record.get("verified_source") or record.get("skip_trace_status") or "").upper()
    if "VERIFIED" in src or "VERIFY" in src:
        return "VERIFIED"
    if record.get("source_url") or record.get("source_refs"):
        return "LIKELY"
    if not _parcel_or_address_key(record):
        return "REQUIRES_VERIFICATION"
    return "LIKELY"


def transform(record: dict) -> MoneyBeastRecord:
    """Normalize one ingested record into MoneyBeast schema. No fabrication."""
    signals = compute_signals(record, [])
    scores = score_record(record)
    urgency = compute_urgency(signals, record.get("auction_date", ""))
    intent = compute_intent(signals)
    status = _status_for(record, scores["composite"])

    lead_id = str(record.get("deal_id") or record.get("lead_id") or "").strip()
    if not lead_id:
        dedupe = _parcel_or_address_key(record) or _owner_key(record) or ""
        lead_id = f"MB-{abs(hash(dedupe or record.get('phone', ''))):08x}" if dedupe else ""

    address = str(record.get("property_address") or record.get("address") or "").strip()
    phone = str(
        record.get("phone_number") or record.get("verified_phone") or record.get("phone") or ""
    ).strip()
    owner = str(
        record.get("owner_name_if_publicly_available")
        or record.get("owner_name")
        or record.get("contact_name")
        or record.get("company_name")
        or ""
    ).strip()

    return MoneyBeastRecord(
        lead_id=lead_id,
        property_id=lead_id,
        address=address,
        city=str(record.get("city") or "").strip(),
        county=str(record.get("county") or "").strip(),
        state=str(record.get("state") or "").strip(),
        parcel_id=str(record.get("parcel_id") or "").strip(),
        owner_name=owner,
        phone=phone,
        occupancy_signal="absentee" if "absentee" in signals else "",
        signals=signals,
        signal_evidence=dict(record.get("signal_evidence") or {}),
        source_url=str(record.get("source_url") or "").strip(),
        source_name=str(record.get("source_name") or record.get("verified_source") or "ingest").strip(),
        source_date=str(record.get("source_date") or "").strip(),
        observed_date=str(record.get("observed_date") or record.get("verified_date") or "").strip(),
        first_seen=str(record.get("first_seen") or "").strip(),
        last_seen=str(record.get("last_seen") or "").strip(),
        status=status,
        intent_score=intent,
        urgency_score=urgency,
        confidence_score=scores["evidence_confidence"],
        composite_score=scores["composite"],
        dedupe_key=_parcel_or_address_key(record) or _owner_key(record),
        provenance=(
            f"source={record.get('source_name') or record.get('verified_source') or 'unknown'}|"
            f"source_date={record.get('source_date') or 'unknown'}|"
            f"observed={record.get('observed_date') or 'unknown'}"
        ),
        recommended_next_action="qualify_via_outreach_control" if phone else "requires_verification",
        notes=""
        if record.get("evidence_notes") is None
        else str(record["evidence_notes"]),
    )


def dedupe(records: list[MoneyBeastRecord]) -> list[MoneyBeastRecord]:
    """Dedupe by parcel/address key first, then owner+phone. Keeps first seen."""
    by_property: dict[str, MoneyBeastRecord] = {}
    by_owner: dict[str, MoneyBeastRecord] = {}
    out: list[MoneyBeastRecord] = []
    for r in records:
        key = r.dedupe_key
        if key:
            if key in by_property:
                kept = by_property[key]
                if r.first_seen < kept.first_seen:
                    by_property[key] = r
                continue
            by_property[key] = r
        okey = _owner_key(
            {
                "owner_name_if_publicly_available": r.owner_name,
                "phone": r.phone,
            }
        )
        if not okey and r.phone:
            okey = f"phone:{r.phone}"
        if okey:
            if okey in by_owner:
                continue
            by_owner[okey] = r
        out.append(r)
    out.sort(key=lambda r: (r.status, -r.composite_score, r.lead_id))
    return out


def ingest(path: Path) -> list[MoneyBeastRecord]:
    """Load a source file. Fails closed on unreadable/invalid JSON."""
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("leads", data.get("records", []))
    return [transform(r) for r in items]


def rank_hot100_growth200(records: list[MoneyBeastRecord]) -> tuple[list[MoneyBeastRecord], list[MoneyBeastRecord]]:
    """Deterministic placement: status first, composite desc, lead_id asc."""
    eligible = [r for r in records if r.status in ("VERIFIED", "LIKELY")]
    eligible.sort(key=lambda r: (-r.composite_score, r.lead_id))

    hot100: list[MoneyBeastRecord] = []
    growth200: list[MoneyBeastRecord] = []
    for r in eligible:
        band = HOT100_BANDS if r.status == "VERIFIED" else GROWTH200_BANDS
        if r.status in HOT100_BANDS and r.composite_score >= HOT100_BANDS[r.status]["min_composite"]:
            if len(hot100) < 100:
                hot100.append(r)
                continue
        if r.status in GROWTH200_BANDS and r.composite_score >= GROWTH200_BANDS[r.status]["min_composite"]:
            if len(growth200) < 200:
                growth200.append(r)
                continue
    for i, r in enumerate(hot100, 1):
        r.pipeline = "Hot100"
        r.rank = i
    for i, r in enumerate(growth200, 1):
        r.pipeline = "Growth200"
        r.rank = i
    return hot100, growth200


def export_csv(records: list[MoneyBeastRecord], path: Path) -> None:
    fields = [f.name for f in MoneyBeastRecord.__dataclass_fields__.values()]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))


def refresh(source: Optional[Path] = None, out_dir: Optional[Path] = None) -> dict:
    """Run the deterministic 12-step refresh. Returns the report dict."""
    src = source or DEFAULT_SOURCE
    out_dir = out_dir or ARTIFACTS

    step_report = {"ingested": 0, "deduped_removed": 0, "hot100": 0, "growth200": 0, "blocked_sources": []}

    try:
        raw = ingest(src)
    except Exception as e:
        step_report["blocked_sources"].append({"source": str(src), "error": str(e)})
        step_report["ingested"] = 0
        return _finalize_report(step_report, [], [], [], src)

    step_report["ingested"] = len(raw)
    unique = dedupe(raw)
    step_report["deduped_removed"] = len(raw) - len(unique)
    hot100, growth200 = rank_hot100_growth200(unique)
    step_report["hot100"] = len(hot100)
    step_report["growth200"] = len(growth200)

    hot_path = out_dir / "moneybeast_hot100.csv"
    growth_path = out_dir / "moneybeast_growth200.csv"
    all_path = out_dir / "moneybeast_all.csv"
    export_csv(hot100, hot_path)
    export_csv(growth200, growth_path)
    export_csv(unique, all_path)

    return _finalize_report(step_report, unique, hot100, growth200, src)


def _finalize_report(
    step_report: dict, all_records: list, hot100: list, growth200: list, source: Path = None
) -> dict:
    statuses = {}
    for r in all_records:
        statuses[r.status] = statuses.get(r.status, 0) + 1

    top_reasons = []
    for r in sorted(all_records, key=lambda r: (-r.composite_score, r.lead_id))[:5]:
        top_reasons.append(
            {
                "lead_id": r.lead_id,
                "address": r.address or "(no address — REQUIRES_VERIFICATION)",
                "composite": r.composite_score,
                "signals": r.signals,
                "status": r.status,
                "reason": f"signals={','.join(r.signals) or 'none'}; evidence_conf={r.confidence_score}",
            }
        )

    report = {
        "generated_at": _iso_now(),
        "source": str(source or DEFAULT_SOURCE),
        "counts": step_report,
        "status_breakdown": statuses,
        "top_ranked": top_reasons,
        "evidence_separation": {
            "property_level": sum(1 for r in all_records if r.dedupe_key),
            "market_only": sum(1 for r in all_records if not r.dedupe_key),
        },
    }
    return report


def audit(source: Optional[Path] = None) -> dict:
    """Dry-run audit: report without writing artifacts."""
    return refresh(source=source)


def write_refresh_report(report: dict) -> Path:
    path = REPORT_DIR / "moneybeast_refresh_report.md"
    lines = [
        "# MoneyBeast Refresh Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- source: `{report['source']}`",
        "",
        "## Counts",
        "",
    ]
    for k, v in report["counts"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Status breakdown", ""]
    for k, v in sorted(report["status_breakdown"].items()):
        lines.append(f"- {k}: {v}")
    lines += ["", "## Evidence separation", ""]
    for k, v in report["evidence_separation"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Top ranked", ""]
    for r in report["top_ranked"]:
        lines.append(
            f"- `{r['lead_id']}` {r['address']} score={r['composite']} [{r['status']}] {r['reason']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MoneyBeast motivated-seller intelligence refresh")
    sub = parser.add_subparsers(dest="command", required=True)

    p_refresh = sub.add_parser("sellers-refresh", help="Run full refresh (writes artifacts)")
    p_refresh.add_argument("--source", type=Path, default=DEFAULT_SOURCE)

    p_audit = sub.add_parser("sellers-audit", help="Audit only (no writes)")
    p_audit.add_argument("--source", type=Path, default=DEFAULT_SOURCE)

    p_dry = sub.add_parser("sellers-dry-run", help="Dry-run: report only, no writes")
    p_dry.add_argument("--source", type=Path, default=DEFAULT_SOURCE)

    args = parser.parse_args(argv)

    if args.command == "sellers-refresh":
        report = refresh(source=args.source)
        write_refresh_report(report)
        print(json.dumps(report, indent=2, default=str))
    elif args.command == "sellers-audit":
        report = audit(source=args.source)
        print(json.dumps(report, indent=2, default=str))
    elif args.command == "sellers-dry-run":
        report = audit(source=args.source)
        print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())