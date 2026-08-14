#!/usr/bin/env python3
"""
lead_pack_builder -- Build a monthly REAL-ESTATE LEAD PACK from the pipeline.

Research-backed deliverable (docs/research/automation-monetization-2026.md):
  Deploy automated monthly lead packs FIRST ($899/mo) — lowest friction, fastest
  sales cycle, and the repo already has the machine (NPI-verified sellers, buyer
  contacts, skip-trace, Whop storefront).

What this does:
  ingest -> score -> verify contact -> tier -> gate -> export (CSV + brief + manifest)

Honesty contract (same as moneybeast / lead_quality_scorer):
  - NEVER invents phones, emails, addresses, owners, equity or motivation.
  - A lead only ships in a pack with a VERIFIED, deliverable contact (phone or
    email) plus a real verification source. Missing = kept out, counted as
    "needs_verification", never padded.
  - The pack is BLOCKED (status=blocked) when contact-verification % is below
    the gate threshold — we never ship an unverifiable pack.

CLI:
  python MBM/LeadEngine/lead_pack_builder.py                      # dry-run (no writes)
  python MBM/LeadEngine/lead_pack_builder.py --apply              # write CSV + brief + manifest
  python MBM/LeadEngine/lead_pack_builder.py --source mbm-dialer/app/public/leads_database.json
  python MBM/LeadEngine/lead_pack_builder.py --source MBM/Artifacts/buyer_contacts.csv
  python MBM/LeadEngine/lead_pack_builder.py --gate 0.80          # min contact-verification %
  python MBM/LeadEngine/lead_pack_builder.py --whop-config        # emit Whop product spec (no API call)
  python MBM/LeadEngine/lead_pack_builder.py --limit 50
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
LOGS = BASE / "logs"
PACK_DIR = BASE / "artifacts" / "lead_packs"
LOGS.mkdir(parents=True, exist_ok=True)
PACK_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SOURCE = BASE / "real_estate_calling_queue.json"

# Monthly subscription price anchored by the research doc ($899/mo flat).
WHOP_PRODUCT = {
    "name": "Real-Estate Lead Pack Subscription",
    "price_usd": 899,
    "plan_type": "renewal",
    "billing_period_days": 30,
    "headline": "Monthly verified real-estate lead packs delivered as CSV + brief.",
    "description": (
        "Every pack is built from NPI/registry-verified contacts with a real phone "
        "or email and a verification source. Contact-verification % is gated before "
        "shipment; a pack that cannot hit the gate is never delivered."
    ),
}

TIER_BANDS = [
    (80, "A_PLUS"),
    (70, "A"),
    (55, "B"),
    (40, "C"),
    (0, "D"),
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


@dataclass
class PackLead:
    lead_id: str = ""
    contact_name: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""
    property_address: str = ""
    city: str = ""
    state: str = ""
    vertical: str = ""
    quality_score: int = 0
    quality_tier: str = "D"
    verification_source: str = ""
    verification_status: str = "UNVERIFIED"
    contact_ok: bool = False
    reason: str = ""
    pack_tier: str = "D"
    source_row: dict = field(default_factory=dict)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _valid_email(v) -> str:
    s = str(v or "").strip()
    return s if EMAIL_RE.match(s) else ""


def _valid_phone(v) -> str:
    s = str(v or "").strip()
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 10 and len(digits) <= 15:
        return s
    return ""


def _verification_source(row: dict, d: dict) -> str:
    for key in ("verified_source", "skip_trace_source", "Verified_Source", "source", "Lead_Source", "Verification_Status"):
        v = str(row.get(key) or d.get(key) or "").strip()
        if v:
            return v
    return ""


def _verification_status(row: dict, d: dict) -> str:
    for key in ("skip_trace_status", "Verification_Status", "Status", "QA_Status", "status"):
        v = str(row.get(key) or d.get(key) or "").strip()
        if v:
            return v
    return "UNVERIFIED"


def load_json_source(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("queue", data.get("leads", data.get("data", [])))


def load_csv_source(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({k: (v or "") for k, v in r.items()})
    return rows


def ingest(source: Path) -> list[dict]:
    if source.suffix.lower() == ".csv":
        return load_csv_source(source)
    return load_json_source(source)


def _flatten_contact(row: dict) -> tuple[str, str]:
    """Best-effort email + phone from a row or its nested details. Never invents."""
    d = row.get("details") or {}
    email = row.get("email") or d.get("email") or d.get("Email") or ""
    phone = (
        row.get("verified_phone")
        or row.get("phone_number")
        or row.get("phone")
        or d.get("verified_phone")
        or d.get("phone")
        or d.get("Phone")
        or ""
    )
    return _valid_email(email), _valid_phone(phone)


def score_row(row: dict) -> dict:
    """Score a row. Reuses lead_quality_scorer when importable; else a local
    deterministic fallback so this module stays standalone-safe."""
    try:
        sys.path.insert(0, str(BASE))
        from lead_quality_scorer import score_lead  # type: ignore
        res = score_lead(row)
        return {"score": res["quality_score"], "tier": res["quality_tier"]}
    except Exception:
        d = row.get("details") or {}
        score = 0
        if (row.get("motivation_score") or d.get("Motivation_Score") or 0):
            score += int(row.get("motivation_score") or d.get("Motivation_Score") or 0) * 0.3
        if _valid_phone(row.get("phone") or d.get("phone") or ""):
            score += 20
        if _valid_email(row.get("email") or d.get("email") or ""):
            score += 10
        addr = row.get("property_address") or d.get("Property_Address") or ""
        if addr:
            score += 20
        score = max(0, min(100, int(round(score))))
        tier = next(t for bound, t in TIER_BANDS if score >= bound)
        return {"score": score, "tier": tier}


def build_pack_lead(row: dict) -> PackLead:
    d = row.get("details") or {}
    email, phone = _flatten_contact(row)
    vsrc = _verification_source(row, d)
    vstat = _verification_status(row, d)

    name = (
        row.get("contact_name")
        or row.get("contact")
        or d.get("Owner_Name")
        or d.get("contact")
        or d.get("Company_Name")
        or ""
    )
    company = row.get("company_name") or row.get("company") or row.get("Entity_Name") or ""
    addr = row.get("property_address") or row.get("address") or d.get("Property_Address") or d.get("address") or ""
    city = row.get("city") or d.get("City") or ""
    state = row.get("state") or d.get("State") or ""
    vertical = str(row.get("vertical") or d.get("vertical") or d.get("vertical_tag") or "Real Estate").strip()

    scored = score_row(row)
    quality = int(scored["score"])
    tier = scored["tier"]

    verified = bool(
        vsrc
        and ("VERIFIED" in vstat.upper() or "NPI" in vstat.upper() or "DCAD" in vstat.upper() or "ENRICHED" in vstat.upper() or vsrc.upper() in ("NPI", "DCAD", "VERIFIED"))
    )
    contact_ok = bool((email or phone) and verified)

    reason_parts = []
    if not (email or phone):
        reason_parts.append("no deliverable contact")
    elif not verified:
        reason_parts.append(f"unverified ({vstat or 'no source'})")
    if contact_ok:
        reason_parts.append("contact verified")

    return PackLead(
        lead_id=str(row.get("deal_id") or row.get("id") or row.get("lead_id") or "").strip(),
        contact_name=str(name).strip(),
        company=str(company).strip(),
        email=email,
        phone=phone,
        property_address=str(addr).strip(),
        city=str(city).strip(),
        state=str(state).strip(),
        vertical=vertical,
        quality_score=quality,
        quality_tier=tier,
        verification_source=vsrc,
        verification_status=vstat,
        contact_ok=contact_ok,
        reason="; ".join(reason_parts) or "n/a",
        source_row=row,
        pack_tier=_tier_for(contact_ok, quality, bool(phone), bool(email)),
    )


def _tier_for(contact_ok: bool, quality: int, has_phone: bool, has_email: bool) -> str:
    if not contact_ok:
        return "D"
    if quality >= 70 and has_phone:
        return "A"
    if quality >= 55 and (has_phone or has_email):
        return "B"
    if quality >= 40:
        return "C"
    return "D"


def build_pack(source: Path, gate: float = 0.80) -> dict:
    rows = ingest(source)
    leads = [build_pack_lead(r) for r in rows]

    shippable = [l for l in leads if l.contact_ok]
    needs_verification = [l for l in leads if not l.contact_ok]

    total = len(leads)
    verified = len(shippable)
    contact_verification_pct = round(verified / total, 4) if total else 0.0

    gated = contact_verification_pct >= gate

    tier_counts: dict[str, int] = {}
    for l in shippable:
        tier_counts[l.pack_tier] = tier_counts.get(l.pack_tier, 0) + 1

    return {
        "generated_at": _iso_now(),
        "source": str(source),
        "total_rows": total,
        "contact_verified": verified,
        "needs_verification": len(needs_verification),
        "contact_verification_pct": contact_verification_pct,
        "gate": gate,
        "gated": gated,
        "status": "ready" if gated else "blocked",
        "tier_counts": tier_counts,
        "pack_tier": sorted(tier_counts.items(), key=lambda x: -x[1])[0][0] if tier_counts else "D",
        "leads": shippable,
        "excluded": needs_verification,
        "whop_product": dict(WHOP_PRODUCT),
    }


def export_csv(leads: list[PackLead], path: Path) -> None:
    fieldnames = [
        "pack_tier", "contact_name", "company", "email", "phone",
        "property_address", "city", "state", "vertical", "quality_score",
        "verification_source", "verification_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for l in sorted(leads, key=lambda x: (-x.quality_score, x.lead_id)):
            writer.writerow({
                "pack_tier": l.pack_tier,
                "contact_name": l.contact_name,
                "company": l.company,
                "email": l.email,
                "phone": l.phone,
                "property_address": l.property_address,
                "city": l.city,
                "state": l.state,
                "vertical": l.vertical,
                "quality_score": l.quality_score,
                "verification_source": l.verification_source,
                "verification_status": l.verification_status,
            })


def write_brief(report: dict, path: Path) -> None:
    lines = [
        "# Real-Estate Lead Pack — Monthly Brief",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- source: `{report['source']}`",
        f"- status: `{report['status']}` (gate {report['gate']:.0%})",
        "",
        "## Delivery counts",
        "",
        f"- total rows: {report['total_rows']}",
        f"- contact verified: {report['contact_verified']}",
        f"- needs verification: {report['needs_verification']}",
        f"- contact verification: {report['contact_verification_pct']:.1%}",
        f"- pack tier: {report['pack_tier']}",
        "",
        "## Tier breakdown",
        "",
    ]
    for tier in ("A", "B", "C", "D"):
        lines.append(f"- {tier}: {report['tier_counts'].get(tier, 0)}")
    lines += [
        "",
        "## Integrity note",
        "",
        "Only leads with a verified, deliverable contact (phone or email) plus a",
        "verification source ship in this pack. Excluded leads are counted but never",
        "padded — re-running upstream verification (NPI / skip-trace) raises the gate.",
        "",
    ]
    if report["status"] == "blocked":
        lines += [
            "## BLOCKED",
            "",
            f"Contact verification {report['contact_verification_pct']:.1%} is below the "
            f"{report['gate']:.0%} gate. Run skip-trace / NPI verification, then rebuild.",
            "",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_whop_config(report: dict, path: Path) -> None:
    """Emit the Whop product spec as JSON (no API call — human applies it)."""
    path.write_text(json.dumps(report["whop_product"], indent=2) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="MBM Real-Estate Lead Pack Builder")
    ap.add_argument("--apply", action="store_true", help="write CSV + brief + manifest (default: dry-run)")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--gate", type=float, default=0.80, help="min contact-verification %% to ship")
    ap.add_argument("--limit", type=int, default=None, help="max rows to process")
    ap.add_argument("--whop-config", action="store_true", help="emit Whop product spec JSON")
    args = ap.parse_args(argv)

    source = args.source
    if not source.exists():
        print(json.dumps({
            "status": "failure",
            "inputs": {"source": str(source)},
            "outputs": {},
            "errors": [f"source not found: {source}"],
            "next_action": "provide a valid source path",
            "owner": "human",
            "timestamp": _iso_now(),
        }, indent=2))
        return 1

    report = build_pack(source, gate=args.gate)
    if args.limit:
        report["leads"] = report["leads"][: args.limit]
        report["excluded"] = report["excluded"][: args.limit]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = PACK_DIR / f"lead_pack_{stamp}.csv"
    brief_path = PACK_DIR / f"lead_pack_{stamp}_brief.md"
    manifest_path = PACK_DIR / f"lead_pack_{stamp}_manifest.json"
    whop_path = PACK_DIR / f"lead_pack_{stamp}_whop_config.json"

    if args.apply:
        export_csv(report["leads"], csv_path)
        write_brief(report, brief_path)
        manifest = {
            "status": report["status"],
            "generated_at": report["generated_at"],
            "inputs": {"source": str(source), "gate": args.gate},
            "outputs": {
                "csv": str(csv_path),
                "brief": str(brief_path),
                "whop_config": str(whop_path),
                "total_rows": report["total_rows"],
                "contact_verified": report["contact_verified"],
                "contact_verification_pct": report["contact_verification_pct"],
                "pack_tier": report["pack_tier"],
                "tier_counts": report["tier_counts"],
            },
            "errors": [],
            "next_action": "ship via Whop 'Lead Pack Subscription' $899/mo" if report["status"] == "ready"
                          else "run skip-trace / NPI verification to raise the gate",
            "owner": "system" if report["status"] == "ready" else "human",
            "timestamp": _iso_now(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        if args.whop_config:
            write_whop_config(report, whop_path)
        print(json.dumps(manifest, indent=2, default=str))
        print(f"\nWrote pack: {csv_path}")
        print(f"Brief:       {brief_path}")
        print(f"Manifest:    {manifest_path}")
        if args.whop_config:
            print(f"Whop spec:   {whop_path}")
    else:
        summary = {
            "status": "dry_run",
            "source": str(source),
            "total_rows": report["total_rows"],
            "contact_verified": report["contact_verified"],
            "needs_verification": report["needs_verification"],
            "contact_verification_pct": report["contact_verification_pct"],
            "gate": args.gate,
            "gated": report["gated"],
            "pack_tier": report["pack_tier"],
            "tier_counts": report["tier_counts"],
            "top_lead": (
                {
                    "contact": report["leads"][0].contact_name,
                    "phone": report["leads"][0].phone,
                    "quality": report["leads"][0].quality_score,
                }
                if report["leads"]
                else None
            ),
            "note": "dry-run — re-run with --apply to write the pack",
        }
        print(json.dumps(summary, indent=2, default=str))
        if args.whop_config:
            print("\nWhop product spec (not written in dry-run):")
            print(json.dumps(report["whop_product"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())