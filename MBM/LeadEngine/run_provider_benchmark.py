"""run_provider_benchmark - Phase 3 executor over the benchmark cohort.

For every AVAILABLE provider: run trace() across cohort records, score
candidates against known evaluation status, and emit the metrics matrix.

Honesty law: if no paid provider is connected, this prints BLOCKED and exits 0
with a machine-readable report saying so. It never fabricates results.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from MBM.LeadEngine.skip_trace_provider import (
    PROVIDER_REGISTRY,
    get_provider,
)
from MBM.LeadEngine.seller_benchmark_cohort import load_sellers, build_cohort


def _load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run(db_path: str = "mbm-dialer/app/public/leads_database.json",
        out_path: str = "MBM/Artifacts/GTM/seller_benchmark/provider_benchmark_results.json",
        cohort_size: int = 100) -> dict:
    sellers = load_sellers(db_path)
    cohort = build_cohort(sellers, size=cohort_size)
    by_id = {s.get("id"): s for s in sellers}

    providers = [get_provider(n) for n in PROVIDER_REGISTRY]
    available = [p for p in providers if p.available()]
    report = {
        "benchmark_id": "SELLER-BENCH-001",
        "timestamp": None,
        "cohort": {"size": cohort["size"], "statuses": cohort["status_counts"]},
        "providers_tested": [p.name for p in available],
        "providers_blocked": [p.name for p in providers if not p.available()],
        "status": "OK" if available else "BLOCKED",
        "block_reason": (None if available else
                         "no authorized skip-trace provider connected "
                         "(PropStream/DealMachine/etc. credentials required)"),
        "results": {},
    }

    from datetime import datetime, timezone
    report["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for prov in available:
        m = defaultdict(float)
        latencies: list[float] = []
        for rec in cohort["records"]:
            lead = by_id.get(rec["lead_id"]) or {}
            t0 = time.perf_counter()
            try:
                results = prov.trace(lead) if rec["evaluation_status"] != "KNOWN_BAD" \
                    else prov.trace(lead)
            except Exception as exc:  # adapter failure is a metric, not a crash
                m["adapter_errors"] += 1
                continue
            latencies.append((time.perf_counter() - t0) * 1000)
            if not results:
                m["no_match"] += 1
                continue
            phones = {r.candidate_phone for r in results}
            truth_phone = (lead.get("phone") or "")
            m["returned"] += 1
            if rec["evaluation_status"] == "KNOWN_BAD" and truth_phone in phones:
                m["bad_phone_returned"] += 1
            if rec["evaluation_status"] == "KNOWN_GOOD":
                owner_matches = [r for r in results if r.owner_match == "MATCH"]
                if owner_matches:
                    m["owner_match"] += 1
                else:
                    m["known_good_missed"] += 1
        n = max(1, len(cohort["records"]))
        report["results"][prov.name] = {
            "metrics": dict(m),
            "coverage_pct": round(100.0 * m["returned"] / n, 1),
            "latency_ms_p50": round(sorted(latencies)[len(latencies) // 2], 1)
            if latencies else None,
            "cost_per_record_usd": prov.cost_per_record_usd,
        }

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "providers_tested": report["providers_tested"],
                      "providers_blocked": report["providers_blocked"],
                      "out": str(p)}, indent=2))
    return report


if __name__ == "__main__":
    run()
