"""Configuration: scoring weights, approval thresholds, store locations.
All money/spend gates are configurable; nothing is hardcoded in logic."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
ARTIFACTS_ROOT = Path(os.environ.get(
    "CONTEC_RADAR_ARTIFACTS", REPO_ROOT / "MBM" / "Artifacts" / "ContecRadar"))

DEFAULT_WEIGHTS = {
    # factor -> weight (sums to 100). Directive §6 defaults.
    "demand": 20,
    "time_to_first_revenue": 15,
    "automation_potential": 15,
    "existing_asset_reuse": 15,
    "gross_margin_potential": 10,
    "recurring_revenue": 10,
    "competition_inverse": 5,
    "startup_cost_inverse": 5,
    "execution_ease": 5,
}

DEFAULT_CONFIG = {
    "weights": DEFAULT_WEIGHTS,
    "decision_thresholds": {"build_now": 75, "experiment": 55},
    "human_approval_required_usd": 250.0,   # spend above this needs operator sign-off
    "max_auto_experiment_budget_usd": 100.0,
    "velocity_min_signals": 2,
}


def load_config() -> Dict[str, Any]:
    path = ARTIFACTS_ROOT / "radar_config.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> Path:
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_ROOT / "radar_config.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def set_weights(weights: Dict[str, int]) -> Path:
    cfg = load_config()
    cfg["weights"] = weights
    return save_config(cfg)
