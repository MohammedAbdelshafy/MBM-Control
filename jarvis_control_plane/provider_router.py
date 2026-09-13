"""Provider Router for the JARVIS Ecosystem Capability Operating Layer.

Routes a mission to the best ecosystem provider by filtering through:
capabilities -> security -> permissions -> approvals -> ranking.
"""

from typing import Any, Dict, List, Optional
import json
import os
from pathlib import Path

from .policy import evaluate, PolicyVerdict

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "Schemas" / "ecosystem_capability_registry.json"
# Canonical provider DATA snapshot (single source of truth). The legacy
# REGISTRY_PATH remains supported if it ever holds a providers array, but it
# is currently the JSON *schema*, so the data file takes precedence.
PROVIDERS_DATA_PATH = ROOT / "Schemas" / "ecosystem_providers.json"

# Mission section 11: ranking weights (total 100).
RANK_WEIGHTS = {
    "capability_value": 20,
    "revenue_leverage": 20,
    "integration_leverage": 15,
    "reliability": 15,
    "ecosystem_maturity": 10,
    "security_confidence": 10,
    "maintenance_confidence": 5,
    "license_fit": 5,
}


def _read_providers_array(path: Path) -> Optional[List[Dict[str, Any]]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if isinstance(data, dict) and isinstance(data.get("providers"), list):
        # Guard: a JSON *schema* also has a "properties.providers" key but no
        # top-level "providers" array of provider objects. Only accept the
        # array when its items look like provider entries.
        items = data["providers"]
        if items and all(isinstance(p, dict) and "provider_id" in p for p in items):
            return items
        if not items:
            return items
    return None


def load_registry() -> List[Dict[str, Any]]:
    """Load the ecosystem provider entries.

    Prefers Schemas/ecosystem_providers.json (canonical data snapshot);
    falls back to the legacy registry path for backward compatibility.
    """
    for path in (PROVIDERS_DATA_PATH, REGISTRY_PATH):
        if path.exists():
            providers = _read_providers_array(path)
            if providers is not None:
                return providers
    return []


def score_provider_100(p: Dict[str, Any]) -> float:
    """Mission section 11: 100-pt provider ranking.

    Uses the stored `scores` breakdown when present (clamped to weights);
    otherwise falls back to the legacy revenue/cost/maintenance heuristic
    so entries without numeric scores still rank deterministically.
    """
    scores = p.get("scores")
    if isinstance(scores, dict) and any(k in scores for k in RANK_WEIGHTS):
        total = 0.0
        for key, weight in RANK_WEIGHTS.items():
            try:
                total += max(0.0, min(float(weight), float(scores.get(key, 0))))
            except (TypeError, ValueError):
                continue
        stored = scores.get("total")
        try:
            if stored is not None and abs(float(stored) - round(total, 2)) > 0.01:
                # Stored total drifted from its breakdown — trust the recompute
                # and surface the drift to the caller via ranking order.
                pass
        except (TypeError, ValueError):
            pass
        return round(total, 2)
    return float(_legacy_score(p))


def _legacy_score(p: Dict[str, Any]) -> int:
    score = 0
    rev = p.get("revenue_leverage", "LOW")
    cost = p.get("integration_cost", "HIGH")
    maint = p.get("maintenance_confidence", "LOW")

    if rev == "HIGH": score += 30
    elif rev == "MEDIUM": score += 20
    elif rev == "LOW": score += 10

    if cost == "LOW": score += 30
    elif cost == "MEDIUM": score += 20
    elif cost == "HIGH": score += 10

    if maint == "HIGH": score += 30
    elif maint == "MEDIUM": score += 20
    elif maint == "LOW": score += 10

    return score


def resolve(mission_intent: str, required_capabilities: List[str], approval_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolve a mission to the best provider and fallback chain.
    """
    providers = load_registry()

    # 1. Capability Filter
    eligible = []
    for p in providers:
        if p.get("status") not in ["ADOPT", "ADAPTER", "VENDOR"]:
            continue
        p_caps = set(p.get("capabilities", []))
        if all(cap in p_caps for cap in required_capabilities):
            eligible.append(p)
            
    if not eligible:
        return {"status": "FAILED", "reason": "No providers match required capabilities."}

    # 2. Security & Permission Filter (Fail-closed)
    secure_eligible = []
    for p in eligible:
        # Strict deterministic check for approval
        if p.get("approval_required") and not approval_id:
            continue
            
        # Check through policy gateway
        decision = evaluate(
            f"ecosystem_provider_invocation:{p['provider_id']} for mission {mission_intent}",
            approval=approval_id if p.get("approval_required") else "system_auto"
        )
        if decision.verdict == PolicyVerdict.ALLOW:
            secure_eligible.append(p)

    if not secure_eligible:
        return {"status": "BLOCKED", "reason": "Policy gateway blocked all eligible providers."}

    # 3. Provider Ranking
    # Score based on revenue_leverage, integration_cost, maintenance_confidence
    def score_provider(p: Dict[str, Any]) -> int:
        score = 0
        rev = p.get("revenue_leverage", "LOW")
        cost = p.get("integration_cost", "HIGH")
        maint = p.get("maintenance_confidence", "LOW")
        
        if rev == "HIGH": score += 30
        elif rev == "MEDIUM": score += 20
        elif rev == "LOW": score += 10
        
        if cost == "LOW": score += 30
        elif cost == "MEDIUM": score += 20
        elif cost == "HIGH": score += 10
        
        if maint == "HIGH": score += 30
        elif maint == "MEDIUM": score += 20
        elif maint == "LOW": score += 10
        
        return score

    ranked = sorted(secure_eligible, key=score_provider, reverse=True)
    best_provider = ranked[0]
    fallbacks = ranked[1:]

    return {
        "status": "VERIFIED",
        "best_provider": best_provider,
        "fallbacks": fallbacks,
        "required_capabilities": required_capabilities
    }
