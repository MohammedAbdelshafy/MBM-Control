"""
whop_experiments.py — Reusable A/B experiment framework (evidence-gated)
=========================================================================
- Deterministic unit assignment: sha256(experiment_id|unit_id) -> variant.
- Registry: MBM/Whop/data/experiments.json (id, hypothesis, control, variants,
  metric, start, end, sample, result, decision).
- Analysis reads the canonical event store; a verdict requires BOTH
  min_sample_per_variant AND min_days. Otherwise verdict=INCONCLUSIVE.
- Never auto-declares winners on inadequate data.

CLI:
  python MBM/Whop/whop_experiments.py list
  python MBM/Whop/whop_experiments.py assign <experiment_id> <unit_id>
  python MBM/Whop/whop_experiments.py analyze <experiment_id>
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_FILE = DATA_DIR / "experiments.json"
EVENTS_FILE = BASE_DIR / "logs" / "revenue_events.jsonl"

MIN_SAMPLE_PER_VARIANT = 100
MIN_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"experiments": {}}


def _save_registry(reg: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2), encoding="utf-8")


def create_experiment(experiment_id: str, hypothesis: str, control: str,
                      variants: list, metric: str = "cta_click_rate",
                      min_sample: int = MIN_SAMPLE_PER_VARIANT,
                      min_days: int = MIN_DAYS) -> dict:
    reg = _load_registry()
    if experiment_id in reg["experiments"]:
        raise ValueError(f"experiment '{experiment_id}' already exists")
    if control not in variants:
        variants = [control] + list(variants)
    exp = {
        "id": experiment_id,
        "hypothesis": hypothesis,
        "control": control,
        "variants": variants,
        "metric": metric,
        "min_sample_per_variant": int(min_sample),
        "min_days": int(min_days),
        "start": _utcnow().isoformat(),
        "end": None,
        "sample": {},
        "result": None,
        "decision": "RUNNING",
        "schema_version": 1,
    }
    reg["experiments"][experiment_id] = exp
    _save_registry(reg)
    return exp


def get_experiment(experiment_id: str) -> dict | None:
    return _load_registry()["experiments"].get(experiment_id)


def assign_variant(experiment_id: str, unit_id: str) -> str | None:
    """Deterministic sticky assignment (same unit always gets same variant)."""
    exp = get_experiment(experiment_id)
    if not exp:
        return None
    digest = hashlib.sha256(f"{experiment_id}|{unit_id}".encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(exp["variants"])
    variant = exp["variants"][idx]
    reg = _load_registry()
    sample = reg["experiments"][experiment_id].setdefault("sample", {})
    sample[unit_id] = {"variant": variant, "assigned_at": _utcnow().isoformat()}
    _save_registry(reg)
    return variant


def analyze_experiment(experiment_id: str, events=None, now=None) -> dict:
    """Compute per-variant metric from canonical events.

    Supported metrics:
      cta_click_rate      cta_click / landing_view per variant
      signup_rate         signup / landing_view per variant
    Verdict gates: min_sample_per_variant AND min_days else INCONCLUSIVE.
    """
    now = now or _utcnow()
    exp = get_experiment(experiment_id)
    if not exp:
        return {"verdict": "NOT_FOUND", "experiment": experiment_id}
    if events is None:
        events = []
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            continue

    # group landing views + conversions by variant attribution
    views, convs = {}, {}
    for e in events:
        attr = e.get("attribution") or {}
        variant = attr.get("landing_variant") or attr.get("offer_variant") or \
            (e.get("metadata") or {}).get("landing_variant")
        if not variant:
            continue
        name = e.get("event_name")
        if name == "landing_view":
            views[variant] = views.get(variant, 0) + 1
        elif exp["metric"] == "cta_click_rate" and name == "cta_click":
            convs[variant] = convs.get(variant, 0) + 1
        elif exp["metric"] == "signup_rate" and name == "signup":
            convs[variant] = convs.get(variant, 0) + 1

    results = {}
    for v in exp["variants"]:
        v_n, c_n = views.get(v, 0), convs.get(v, 0)
        results[v] = {
            "views": v_n,
            "conversions": c_n,
            "rate": round(c_n / v_n, 4) if v_n else None,
        }

    started = datetime.fromisoformat(exp["start"]) if isinstance(exp.get("start"), str) else None
    days_running = (now - started).days if started else 0
    adequate_sample = all(results.get(v, {}).get("views", 0) >= exp["min_sample_per_variant"]
                          for v in exp["variants"])
    adequate_time = days_running >= exp["min_days"]

    if not (adequate_sample and adequate_time):
        verdict = "INCONCLUSIVE"
        why = []
        if not adequate_sample:
            why.append(f"min {exp['min_sample_per_variant']} views/variant required")
        if not adequate_time:
            why.append(f"min {exp['min_days']} days runtime required ({days_running}d so far)")
    else:
        rates = [r["rate"] for r in results.values() if r["rate"] is not None]
        if len(rates) < len(exp["variants"]):
            verdict, why = "INCONCLUSIVE", ["a variant has zero denominator"]
        else:
            best = max(results.items(), key=lambda kv: kv[1]["rate"])
            lift = round(best[1]["rate"] - results[exp["control"]]["rate"], 4) if best[0] != exp["control"] else 0.0
            verdict = f"LEADER={best[0]}"
            why = [f"observed rate delta vs control: {lift:+} "
                   "(observational only - confirm with a proper significance test)"]

    out = {
        "experiment": experiment_id,
        "hypothesis": exp["hypothesis"],
        "metric": exp["metric"],
        "days_running": days_running,
        "results_by_variant": results,
        "verdict": verdict,
        "why": why,
        "decision_policy": f"winner declared only after >= {exp['min_sample_per_variant']} views/variant AND >= {exp['min_days']}d",
        "provenance": "DERIVED",
        "evidence": [str(EVENTS_FILE), str(REGISTRY_FILE)],
    }
    # persist latest analysis snapshot (never overwrite decision automatically)
    reg = _load_registry()
    reg["experiments"][experiment_id]["sample_counts"] = {
        v: r["views"] for v, r in results.items()}
    reg["experiments"][experiment_id]["last_analysis"] = {
        "analyzed_at": now.isoformat(), **out}
    _save_registry(reg)
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "create" and len(argv) >= 6:
        exp = create_experiment(argv[2], argv[3], argv[4], argv[5].split(","))
        print(json.dumps(exp, indent=2))
    elif cmd == "assign" and len(argv) >= 4:
        print(json.dumps({"unit": argv[3],
                          "variant": assign_variant(argv[2], argv[3])}))
    elif cmd == "analyze" and len(argv) >= 3:
        print(json.dumps(analyze_experiment(argv[2]), indent=2))
    else:
        reg = _load_registry()
        print(json.dumps({"experiments": sorted(reg["experiments"].keys())}, indent=2))


if __name__ == "__main__":
    main(sys.argv)
