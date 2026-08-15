"""pipeline -- end-to-end vertical slice for jarvis-mbm#23 (data side).

  ingest -> normalize -> dedupe -> county route -> ownership verify ->
  score (opportunity + callability) -> gate (prime queue) -> rank -> artifacts.

Safe by default: no network ownership lookups and no artifact writes unless
--verify-live and --apply are passed. A dependency that is missing (e.g. no
adapter for the county, no ownership source) is reported as a blocker, not
silently replaced.

CLI:
  python pipeline.py --source FILE.json                       # offline dry-run
  python pipeline.py --source FILE.json --verify-live --apply # verify + write
  python pipeline.py --live-auction --state TX --county Dallas --max-pages 2
  python pipeline.py --history calls_history.json --apply
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .auction_freshness import load_source, rows_to_properties
from .county_registry import route_property
from .normalize import dedupe_records, normalize_record
from .ownership_verifier import apply_verification, verify_ownership
from .scoring import score_callability, score_property

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE / "artifacts"
REPORTS = BASE / "reports"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

PRIME_QUEUE_CALLABILITY = 50


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_history(path: Optional[Path]) -> list[dict]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("calls", [])


def run_pipeline(source: Path, verify_live: bool = False, history: Optional[Path] = None,
                 limit: int = 0, apply: bool = False) -> dict:
    steps: dict[str, Any] = {"ingested": 0, "normalized": 0, "deduped_removed": 0,
                             "routed": 0, "verified": 0, "prime_queue": 0, "blocked_sources": []}

    try:
        rows = load_source(source)
    except Exception as exc:  # noqa: BLE001
        steps["blocked_sources"].append({"source": str(source), "error": str(exc)})
        return _report(steps, [], [])

    steps["ingested"] = len(rows)

    norm = [normalize_record(r) for r in rows]
    norm = [n for n in norm if n.get("address") or n.get("parcel_id")]
    steps["normalized"] = len(norm)

    for n in norm:
        n["dedupe_key"] = n.get("dedupe_key") or _key(n)
    deduped = dedupe_records(norm)
    steps["deduped_removed"] = len(norm) - len(deduped)

    history_rows = load_history(history)

    records: list[dict] = []
    for rec in deduped:
        routed = route_property(rec)
        rec["county"] = routed["county"]
        rec["county_resolved"] = routed["county_resolved"]
        rec["county_source"] = routed["source"].get("authority", "") if routed["source"] else ""
        rec["county_source_url"] = (routed["source"].get("website_url") or routed["source"].get("api_url") or "") if routed["source"] else ""
        if routed["routed"]:
            steps["routed"] += 1

        verification = verify_ownership(rec, live=verify_live)
        if verification.verification_status in ("VERIFIED", "LIKELY"):
            steps["verified"] += 1
        rec = apply_verification(rec, verification)

        hist_for_rec = [
            h for h in history_rows
            if str(h.get("property_id") or h.get("address") or "").lower()
            == (rec.get("dedupe_key") or rec.get("address") or "").lower()
        ]
        rec["history"] = hist_for_rec

        opp = score_property(rec, verification.to_dict() if verification else None)
        call = score_callability(rec, verification.to_dict() if verification else None,
                                 history=hist_for_rec,
                                 phone=rec.get("phone") or rec.get("business_phone") or "")
        rec["opportunity_score"] = opp["total"]
        rec["opportunity_reasons"] = opp["reasons"]
        rec["opportunity_trace"] = opp["trace"]
        rec["callability_score"] = call["total"]
        rec["callability_reasons"] = call["reasons"]
        rec["callability_trace"] = call["trace"]
        rec["combined_rank"] = int(round(0.6 * opp["total"] + 0.4 * call["total"]))

        # Gate: prime queue only when callable + ownership known enough.
        rec["prime_queue"] = bool(
            rec.get("ownership_status") in ("VERIFIED", "LIKELY")
            and call["total"] >= PRIME_QUEUE_CALLABILITY
            and not rec.get("history")  # recycle only after clean history
        )
        if rec["prime_queue"]:
            steps["prime_queue"] += 1
        records.append(rec)

    if limit > 0:
        records = records[:limit]

    ranked = sorted(records, key=lambda r: (-r["combined_rank"], r.get("dedupe_key", "")))

    report = _report(steps, ranked, history_rows)
    report["inputs"] = {"source": str(source), "verify_live": verify_live, "limit": limit}

    if apply:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = ARTIFACTS / f"property_pipeline_{ts}.json"
        csv_path = ARTIFACTS / f"property_pipeline_{ts}.csv"
        json_path.write_text(json.dumps(ranked, indent=2, default=str), encoding="utf-8")
        if ranked:
            fields = list(ranked[0].keys())
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(ranked)
        report["artifacts"] = {"json": str(json_path), "csv": str(csv_path)}
        _write_report_md(report, ranked, ts)
    return report


def _key(rec: dict) -> str:
    from .normalize import dedupe_key
    return dedupe_key(rec.get("parcel_id", ""), rec.get("address") or rec.get("address_normalized", ""), rec.get("state", ""))


def _report(steps: dict, records: list[dict], history: list[dict]) -> dict:
    verified = sum(1 for r in records if r.get("ownership_status") in ("VERIFIED", "LIKELY"))
    return {
        "status": "success" if steps.get("normalized", 0) else "skipped",
        "inputs": {},
        "outputs": {
            "counts": steps,
            "records": len(records),
            "verified_records": verified,
            "verification_rate": round(verified / max(1, len(records)) * 100, 1),
            "top_ranked": [
                {
                    "dedupe_key": r.get("dedupe_key"),
                    "address": r.get("address"),
                    "city": r.get("city"),
                    "state": r.get("state"),
                    "county": r.get("county") or "?",
                    "owner": r.get("owner_name") or "",
                    "ownership_status": r.get("ownership_status"),
                    "opportunity": r.get("opportunity_score"),
                    "callability": r.get("callability_score"),
                    "combined": r.get("combined_rank"),
                    "prime_queue": r.get("prime_queue"),
                    "reason": "; ".join((r.get("opportunity_reasons") or [])[:3]),
                }
                for r in records[:8]
            ],
        },
        "errors": [],
        "next_action": "sync to dialer/CRM after human review" if steps.get("prime_queue") else "verify_ownership or add county source",
        "owner": "jarvis-worker-2",
        "timestamp": _iso_now(),
    }


def _write_report_md(report: dict, records: list[dict], ts: str) -> Path:
    lines = [
        "# Property Intelligence Pipeline Report",
        "",
        f"- generated_at: `{report['timestamp']}`",
        f"- status: `{report['status']}`",
        "",
        "## Counts",
        "",
    ]
    for k, v in report["outputs"]["counts"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Verification rate", ""]
    lines.append(f"- {report['outputs']['verification_rate']}% ({report['outputs']['verified_records']}/{report['outputs']['records']})")
    lines += ["", "## Top ranked", ""]
    for r in report["outputs"]["top_ranked"]:
        lines.append(
            f"- `{r['dedupe_key']}` {r['address']} {r['county']} owner={r['owner'] or 'UNKNOWN'} "
            f"[{r['ownership_status']}] opp={r['opportunity']} call={r['callability']} "
            f"prime={r['prime_queue']} :: {r['reason']}"
        )
    path = REPORTS / f"property_pipeline_report_{ts}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Property intelligence vertical slice")
    ap.add_argument("--source", type=Path, required=True, help="Pre-collected auction/listing JSON or CSV")
    ap.add_argument("--verify-live", action="store_true", help="Enable live authoritative ownership lookups")
    ap.add_argument("--history", type=Path, help="Call-outcome history JSON")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true", help="Write artifacts + report")
    args = ap.parse_args(argv)

    report = run_pipeline(args.source, verify_live=args.verify_live,
                          history=args.history, limit=args.limit, apply=args.apply)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())