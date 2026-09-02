"""
Provider-level metrics + audit log (§17).
Never logs secrets or auth headers.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# In-memory counters (process-local). For persistence use AuditLog below.
_counters: Counter = Counter()
_latencies: Dict[str, list] = defaultdict(list)


def record(provider: str, metric: str, value: int = 1, latency_ms: Optional[float] = None) -> None:
    _counters[f"{provider}.{metric}"] += value
    if latency_ms is not None:
        _latencies[provider].append(latency_ms)
        # cap per provider
        if len(_latencies[provider]) > 500:
            _latencies[provider] = _latencies[provider][-500:]


def snapshot() -> Dict[str, Any]:
    out: Dict[str, Any] = {"counters": dict(_counters), "latency": {}}
    for prov, vals in _latencies.items():
        if not vals:
            continue
        s = sorted(vals)
        n = len(s)
        out["latency"][prov] = {
            "p50": s[n // 2],
            "p95": s[int(n * 0.95)] if n >= 20 else s[-1],
            "avg": sum(s) / n,
            "count": n,
        }
    return out


class AuditLog:
    """Append-only audit for intelligence/content ops (additive, not lead DB)."""
    def __init__(self, path: Optional[Path] = None):
        default = Path(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / "audit.jsonl"
        self.path = Path(path) if path else default
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: str, provider: str, *, status: str = "ok", detail: Optional[Dict[str, Any]] = None, correlation_id: str = "") -> None:
        # strip any secret-looking keys
        safe_detail = {}
        if detail:
            for k, v in detail.items():
                lk = k.lower()
                if any(s in lk for s in ("key", "token", "secret", "password", "auth", "bearer")):
                    safe_detail[k] = "***REDACTED***"
                else:
                    safe_detail[k] = v
        entry = {
            "at": _now(),
            "event": event,
            "provider": provider,
            "status": status,
            "correlation_id": correlation_id,
            "detail": safe_detail,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
