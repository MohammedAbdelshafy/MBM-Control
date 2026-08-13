"""
mbm -- MBM-Social CLI entry point.

Usage:
  python mbm.py routing-dry-run     Show every queued asset and its exact
                                    destination account/channel. NO publishing.
  python mbm.py routing-audit       Audit the routing registry + queue for
                                    consistency and surface missing accounts.

Exit codes:
  0  success (dry-run: all routable; audit: no issues)
  1  failure (dry-run: any unroutable; audit: any issue)
"""
from __future__ import annotations

import argparse
import sys

from mbm_social import routing


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MBM-Social CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dry = sub.add_parser("routing-dry-run", help="Show every asset + exact destination")
    p_dry.set_defaults(func=_cmd_routing_dry_run)

    p_audit = sub.add_parser("routing-audit", help="Audit routing registry and queue")
    p_audit.set_defaults(func=_cmd_routing_audit)

    args = parser.parse_args(argv)
    return args.func(args)


def _cmd_routing_dry_run(args) -> int:
    results = routing.run_dry_run()
    errors = sum(1 for r in results if r["status"] == "ERROR")
    if errors:
        print(f"\nROUTING FAILED: {errors} asset(s) have no resolvable destination. Fix before publishing.")
        return 1
    print("\nROUTING OK: every asset has an exact destination. No publishing performed.")
    return 0


def _cmd_routing_audit(args) -> int:
    audit = routing.run_audit()
    if audit["issues"]:
        print(f"\nAUDIT FAILED: {len(audit['issues'])} issue(s) found.")
        return 1
    print("\nAUDIT OK: no routing issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())