from __future__ import annotations

import argparse
import json
import sys

from .engine import DemandFactory
from .models import DemandSignal, Opportunity


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an MBM demand opportunity safely.")
    parser.add_argument("--file", help="JSON file containing {opportunity, signals}.")
    parser.add_argument("--armed", action="store_true", help="Mark the evaluation as armed; still proposal-only.")
    args = parser.parse_args()

    if not args.file:
        parser.error("--file is required")

    try:
        with open(args.file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        opportunity = Opportunity(**payload["opportunity"])
        signals = [DemandSignal(**item) for item in payload.get("signals", [])]
        result = DemandFactory().evaluate(opportunity, signals, armed=args.armed)
        print(json.dumps({
            "status": result.status,
            "opportunity": opportunity.to_dict(),
            "decision": result.decision.to_dict() if result.decision else None,
            "diagnostics": result.diagnostics,
        }, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failure", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
