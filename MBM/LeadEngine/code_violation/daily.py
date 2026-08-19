"""daily.py -- daily code-violation lead pipeline CLI.

Usage:
  python MBM/LeadEngine/code_violation/daily.py [--days-back 45]
      [--enrich-limit 40] [--no-enrich] [--source dallas] [--apply]

Defaults to a DRY RUN (no dialer writes, no state, no GTM merge).
Add --apply to commit the CODE_VIOLATION_DAILY segment + artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.code_violation.pipeline import CodeViolationDailyPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily code-violation lead pipeline")
    parser.add_argument("--days-back", type=int, default=45, help="Backfill window in days")
    parser.add_argument("--enrich-limit", type=int, default=40, help="Max properties to phone-enrich")
    parser.add_argument("--no-enrich", action="store_true", help="Skip phone enrichment")
    parser.add_argument("--source", type=str, default=None, help="Restrict to one registry source")
    parser.add_argument("--apply", action="store_true", help="Commit dialer segment + state + GTM")
    args = parser.parse_args()

    pipeline = CodeViolationDailyPipeline(root_dir=ROOT)
    report = pipeline.run(
        apply=args.apply,
        days_back=args.days_back,
        enrich_limit=args.enrich_limit,
        do_enrich=not args.no_enrich,
        source_filter=args.source,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("status") in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
