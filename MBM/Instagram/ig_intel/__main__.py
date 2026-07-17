"""MBM Instagram Intelligence — CLI entry point.

Usage:
  python -m ig_intel run --config config.example.yaml
  python -m ig_intel demo      # offline self-test (no browser)

Honors the operator's authenticated session only. See SOP.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .run import run
from .schema import Reel, render_markdown, HOOK_TYPES
from .config import Config
from . import dashboard as dashboard_mod


def _demo():
    print("[demo] offline self-test: rendering a sample reel markdown")
    r = Reel(
        reel_id="DEMO123",
        url="https://www.instagram.com/reel/DEMO123/",
        creator="@moneymachine",
        title="How I wholesaled 12 houses with AI",
        date_saved="2026-07-17",
        category="Real Estate",
        niche="Wholesaling",
        business_model="Wholesaling",
        primary_hook="I quit my job using this one AI tool",
        hook_type="Curiosity",
        hook_score=9,
        retention_score=8,
        cta="Comment AI for the free list",
        psychology_used="Curiosity Gap, Authority",
        mbm_scores={"revenue": 90, "automation": 80, "leadgen": 85,
                    "construction": 40, "ai": 95, "twists": 70, "moneybeast": 92},
        mbm_relevance_score=92,
        potential_revenue="$5k-15k per deal",
    )
    print(render_markdown(r)[:600])
    print("\n[demo] OK — hook types available:", ", ".join(HOOK_TYPES))


def main(argv=None):
    p = argparse.ArgumentParser(prog="ig_intel")
    sub = p.add_subparsers(dest="cmd")
    runp = sub.add_parser("run", help="collect + analyze (needs authenticated browser)")
    runp.add_argument("--config", default="config.example.yaml")
    sub.add_parser("demo", help="offline self-test")
    dashp = sub.add_parser("dashboard", help="build + serve local dashboard")
    dashp.add_argument("--config", default="config.example.yaml")
    dashp.add_argument("--port", type=int, default=8787)
    dashp.add_argument("--no-serve", action="store_true")
    args = p.parse_args(argv)

    if args.cmd == "demo":
        _demo()
        return 0
    if args.cmd == "run":
        res = run(args.config)
        import json
        print(json.dumps(res.to_dict(), indent=2))
        return 0 if res.status == "success" else 1
    if args.cmd == "dashboard":
        if args.no_serve:
            dashboard_mod.main(["--config", args.config, "--no-serve"])
        else:
            dashboard_mod.main(["--config", args.config, "--port", str(args.port)])
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
