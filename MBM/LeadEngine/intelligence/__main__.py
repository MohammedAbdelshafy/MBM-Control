"""
CLI for the intelligence layer (additive; never touches lead DB writer).

Usage:
  python -m MBM.LeadEngine.intelligence --help
  python -m MBM.LeadEngine.intelligence discover          # World Monitor tool discovery
  python -m MBM.LeadEngine.intelligence ingest --query "ai clinics" --limit 10
  python -m MBM.LeadEngine.intelligence ingest --apply    # same but persists + scores
  python -m MBM.LeadEngine.intelligence opportunities --query "real estate" --top 10
  python -m MBM.LeadEngine.intelligence policy            # show allowlist
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MBM.LeadEngine.intelligence.config import load_flags, ProviderCredentials
from MBM.LeadEngine.intelligence.provider_policy import list_policy
from MBM.LeadEngine.intelligence.world_monitor_adapter import WorldMonitorAdapter
from MBM.LeadEngine.intelligence.intelligence_engine import IntelligenceEngine
from MBM.LeadEngine.intelligence.opportunity_engine import OpportunityEngine, ScoringConfig
from MBM.LeadEngine.intelligence.anderro_adapter import AnderroAdapter
from MBM.LeadEngine.intelligence.content_orchestrator import ContentOrchestrator

def _build_intel():
    creds = ProviderCredentials.from_env()
    wm = WorldMonitorAdapter(api_key=creds.worldmonitor_api_key, base_url=creds.worldmonitor_base_url, mcp_url=creds.worldmonitor_mcp_url)
    return IntelligenceEngine(adapter=wm)

def main(argv=None):
    p = argparse.ArgumentParser(description="MBM Intelligence Layer")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("policy", help="Show provider allowlist")

    d = sub.add_parser("discover", help="Discover World Monitor tools")
    d.add_argument("--refresh", action="store_true")

    ing = sub.add_parser("ingest", help="Fetch + normalize World Monitor events")
    ing.add_argument("--query", default="")
    ing.add_argument("--category", default="")
    ing.add_argument("--limit", type=int, default=10)
    ing.add_argument("--apply", action="store_true", help="persist to intelligence store")
    ing.add_argument("--no-persist", action="store_true")

    opp = sub.add_parser("opportunities", help="Ranked opportunities (intelligence + monetization)")
    opp.add_argument("--query", default="")
    opp.add_argument("--category", default="")
    opp.add_argument("--limit", type=int, default=12)
    opp.add_argument("--top", type=int, default=10)

    args = p.parse_args(argv)

    if args.cmd == "policy":
        print(json.dumps(list_policy(), indent=2))
        return 0

    if args.cmd == "discover":
        creds = ProviderCredentials.from_env()
        wm = WorldMonitorAdapter(api_key=creds.worldmonitor_api_key, base_url=creds.worldmonitor_base_url, mcp_url=creds.worldmonitor_mcp_url)
        tools = wm.discover_tools(force_refresh=args.refresh)
        print(json.dumps([t.__dict__ for t in tools], indent=2, default=str))
        print(f"\n{len(tools)} tools discovered")
        return 0

    if args.cmd == "ingest":
        intel = _build_intel()
        r = intel.ingest(query=args.query, category=args.category, limit=args.limit, persist=args.apply and not args.no_persist)
        print(json.dumps(r, indent=2, default=str))
        return 0 if r.get("ok") else 1

    if args.cmd == "opportunities":
        intel = _build_intel()
        eng = OpportunityEngine(ScoringConfig.from_env())
        creds = ProviderCredentials.from_env()
        anderro = AnderroAdapter(api_key=creds.anderro_api_key)
        orch = ContentOrchestrator(intel=intel, opp_engine=eng, anderro=anderro)
        r = orch.run(query=args.query, category=args.category, limit=args.limit, top_n=args.top, create_drafts=False)
        print(json.dumps(r, indent=2, default=str))
        return 0 if r.get("ok") else 1

    p.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
