"""
IntelligenceEngine — normalize → validate → dedupe → score → store (§5).

Pipeline:
  World Monitor -> Provider Adapter -> Schema Validation -> Event Normalization
               -> Deduplication -> Topic/Entity Extraction -> Opportunity Scoring
               -> Internal Intelligence Store

Provenance survives every transformation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .types import IntelligenceEvent, Provenance
from .world_monitor_adapter import WorldMonitorAdapter, ProviderError
from .observability import AuditLog

STORE_NAME = "intelligence_events.json"

def _dedup_key(evt: IntelligenceEvent) -> str:
    base = f"{evt.source}|{evt.title.lower().strip()}|{(evt.publishedAt or evt.observedAt or '')[:16]}"
    return hashlib.sha256(base.encode()).hexdigest()[:20]

class IntelligenceStore:
    """Additive file store (separate from leads_database.json)."""
    def __init__(self, path: Optional[Path] = None):
        default = Path(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / STORE_NAME
        self.path = Path(path) if path else default
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> List[Dict[str, Any]]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and isinstance(data.get("events"), list):
                    return data["events"]
        except Exception:
            pass
        return []

    def _write(self, items: List[Dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, events: List[IntelligenceEvent]) -> Dict[str, int]:
        existing = self._read()
        by_key: Dict[str, Dict[str, Any]] = {}
        for it in existing:
            k = hashlib.sha256(f"{it.get('source','')}|{str(it.get('title','')).lower().strip()}|{str(it.get('publishedAt') or it.get('observedAt',''))[:16]}".encode()).hexdigest()[:20]
            by_key[k] = it
        added = 0
        updated = 0
        for evt in events:
            k = _dedup_key(evt)
            payload = {
                "id": evt.id,
                "source": evt.source,
                "sourceUrl": evt.sourceUrl,
                "observedAt": evt.observedAt,
                "publishedAt": evt.publishedAt,
                "category": evt.category,
                "title": evt.title,
                "summary": evt.summary,
                "entities": evt.entities,
                "locations": evt.locations,
                "topics": evt.topics,
                "confidence": evt.confidence,
                "freshnessSeconds": evt.freshnessSeconds,
                "rawReference": evt.rawReference,
                "provenance": {
                    "provider": evt.provenance.provider,
                    "tool": evt.provenance.tool,
                    "retrievedAt": evt.provenance.retrievedAt,
                    "sourceUrl": evt.provenance.sourceUrl,
                    "transform": evt.provenance.transform,
                },
            }
            if k in by_key:
                # merge provenance freshness
                by_key[k] = payload
                updated += 1
            else:
                by_key[k] = payload
                added += 1
        self._write(list(by_key.values()))
        return {"added": added, "updated": updated, "total": len(by_key)}

    def list(self, *, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        items = self._read()
        if category:
            items = [x for x in items if x.get("category") == category]
        # newest first
        items.sort(key=lambda x: x.get("publishedAt") or x.get("observedAt") or "", reverse=True)
        return items[:limit]

    def count(self) -> int:
        return len(self._read())


class IntelligenceEngine:
    def __init__(self, adapter: Optional[WorldMonitorAdapter] = None, store: Optional[IntelligenceStore] = None, audit: Optional[AuditLog] = None):
        self.adapter = adapter
        self.store = store or IntelligenceStore()
        self.audit = audit or AuditLog()

    def ingest(self, *, query: str = "", category: str = "", limit: int = 20, persist: bool = True) -> Dict[str, Any]:
        """
        Full pipeline: fetch -> validate -> dedupe -> store.
        Returns report; never fabricates events on BLOCKED.
        """
        started = datetime.now(timezone.utc).isoformat()
        if self.adapter is None:
            return {"ok": False, "code": "NOT_CONFIGURED", "error": "WorldMonitorAdapter not configured (set WORLDMONITOR_API_KEY)", "events": []}

        try:
            raw_events = self.adapter.fetch_events(query=query, category=category, limit=limit)
        except ProviderError as e:
            self.audit.append("intelligence.ingest", "worldmonitor", status=f"failed:{e.code}", detail={"error": str(e)[:500]})
            return {"ok": False, "code": e.code, "error": str(e), "events": [], "retryable": e.retryable}
        except Exception as e:
            self.audit.append("intelligence.ingest", "worldmonitor", status="failed", detail={"error": str(e)[:500]})
            return {"ok": False, "code": "TRANSIENT", "error": str(e), "events": []}

        # Schema validation + dedupe (in-memory)
        seen: Set[str] = set()
        deduped: List[IntelligenceEvent] = []
        for evt in raw_events:
            # minimal schema gate
            if not evt.title or not evt.category:
                continue
            k = _dedup_key(evt)
            if k in seen:
                continue
            seen.add(k)
            deduped.append(evt)

        # provenance already set by adapter; enrich
        result: Dict[str, Any] = {
            "ok": True,
            "retrieved_at": started,
            "query": query,
            "category": category,
            "fetched": len(raw_events),
            "deduped": len(deduped),
            "events": [e.__dict__ for e in deduped],
        }

        if persist:
            stats = self.store.upsert(deduped)
            result["store"] = stats
            self.audit.append("intelligence.ingest", "worldmonitor", status="ok", detail={"fetched": len(raw_events), "deduped": len(deduped), "store": stats})

        return result

    def recent(self, *, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        return self.store.list(category=category, limit=limit)
