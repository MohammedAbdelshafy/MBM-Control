#!/usr/bin/env python3
"""Run the canonical lead-verification gate against JSON or CSV input.

This is deliberately a read-only service boundary: it evaluates supplied
records and never writes to the live dialer database or any queue.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from MBM.LeadEngine.dialer_verification_gate import check_lead


def qualify_leads(leads: list[dict[str, Any]], *, include_leads: bool = False) -> dict[str, Any]:
    """Evaluate leads with the single canonical verification gate."""
    results: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()

    for lead in leads:
        assessment = check_lead(lead)
        result: dict[str, Any] = {
            "passed": assessment["passed"],
            "phone": assessment["phone"],
            "name": assessment["name"],
            "phone_ok": assessment["phone_ok"],
            "name_ok": assessment["name_ok"],
            "verified_ok": assessment["verified_ok"],
            "verified_source": assessment["verified_source"],
            "rejection_reasons": assessment["rejection_reasons"],
        }
        if include_leads:
            result["lead"] = lead
        results.append(result)
        rejection_counts.update(assessment["rejection_reasons"])

    passed = sum(1 for result in results if result["passed"])
    return {
        "status": "success",
        "inputs": {"lead_count": len(leads)},
        "outputs": {
            "passed_count": passed,
            "rejected_count": len(leads) - passed,
            "pass_rate": round(passed / len(leads), 4) if leads else 0.0,
            "rejection_counts": dict(sorted(rejection_counts.items())),
            "results": results,
        },
        "errors": [],
        "next_action": "Export passed records only after customer and compliance review.",
        "owner": "system",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))

    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("leads"), list):
        return payload["leads"]
    raise ValueError("JSON input must be an array or an object with a 'leads' array")


def _parse_stdin() -> list[dict[str, Any]]:
    payload = json.load(sys.stdin)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("leads"), list):
        return payload["leads"]
    raise ValueError("stdin JSON must be an array or an object with a 'leads' array")


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify JSON or CSV leads without mutating queues")
    parser.add_argument("--input", type=Path, help="JSON/CSV input path; omit to read JSON from stdin")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--include-leads", action="store_true", help="Include each submitted lead in its result")
    args = parser.parse_args()

    try:
        leads = _load_records(args.input) if args.input else _parse_stdin()
        if not all(isinstance(lead, dict) for lead in leads):
            raise ValueError("every lead must be a JSON object or CSV row")
        report = qualify_leads(leads, include_leads=args.include_leads)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "status": "failure",
            "inputs": {"input": str(args.input) if args.input else "stdin"},
            "outputs": {},
            "errors": [str(exc)],
            "next_action": "Correct the input format and run the qualification again.",
            "owner": "human",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2))
        return 2

    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
