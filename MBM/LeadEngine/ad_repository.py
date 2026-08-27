"""
MBM LeadEngine — Acquisition-Disposition Repository
=====================================================
Data access layer for all AD engine persistence.
Wraps Supabase client with typed repository methods.
Domain engines never touch this directly — services wire them.

Environment modes (from AD_ENV / MBM_ENV):
  PRODUCTION  — Supabase required. Falls back = startup error.
  STAGING     — Supabase preferred. JSON fallback with warning.
  LOCAL       — JSON files, Supabase optional.
  TEST        — In-memory temp directory, no persistence beyond process.
"""

from __future__ import annotations
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Supabase client (lazy import — falls back to JSON files if unavailable)
_supabase = None
_supabase_available = None

ENV_MODES = ("PRODUCTION", "STAGING", "LOCAL", "TEST")


def _get_env_mode() -> str:
    """Determine environment mode. Fails closed in PRODUCTION."""
    raw = (os.environ.get("AD_ENV") or os.environ.get("MBM_ENV") or "LOCAL").upper()
    if raw not in ENV_MODES:
        log.warning("Unknown AD_ENV=%s, defaulting to LOCAL", raw)
        raw = "LOCAL"
    return raw


def _get_supabase():
    """Lazy-initialize Supabase client from environment."""
    global _supabase, _supabase_available
    if _supabase_available is False:
        return None
    if _supabase is not None:
        return _supabase
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            _supabase_available = False
            return None
        _supabase = create_client(url, key)
        _supabase_available = True
        return _supabase
    except Exception as e:
        log.warning("Supabase init failed: %s", e)
        _supabase_available = False
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdRepository:
    """
    Repository for Acquisition-Disposition engine persistence.
    Falls back to local JSON files when Supabase is unavailable.
    """

    def __init__(self, storage_dir: Optional[str] = None, env_mode: Optional[str] = None):
        self.env_mode = (env_mode or _get_env_mode()).upper()
        self.storage_dir = Path(storage_dir or os.path.join(
            os.path.dirname(__file__), "..", "ad_storage"
        ))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.client = _get_supabase()
        self._startup_diagnostics()

    def _startup_diagnostics(self):
        """Log backend status. Fails closed in PRODUCTION."""
        supabase_ok = self.client is not None
        mode = self.env_mode
        if mode == "PRODUCTION":
            if not supabase_ok:
                raise RuntimeError(
                    "PRODUCTION mode requires Supabase. "
                    "Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY, or switch to STAGING/LOCAL."
                )
            log.info("AD Repository: PRODUCTION mode (Supabase)")
        elif mode == "STAGING":
            if not supabase_ok:
                log.warning("AD STAGING: Supabase unavailable — falling back to JSON (data will diverge)")
            else:
                log.info("AD Repository: STAGING mode (Supabase)")
        else:
            backend = "Supabase" if supabase_ok else "JSON"
            log.info("AD Repository: %s mode (%s)", mode, backend)

    def _use_supabase(self) -> bool:
        return self.client is not None

    # ─── REVISION SUPPORT (Optimistic Concurrency) ─────────────────

    def check_and_increment_revision(self, table: str, record_id: str,
                                       expected_revision: int) -> bool:
        """
        Check that the current revision matches expected, then increment.
        Returns True if successful, False if stale.
        """
        if self._use_supabase():
            result = self.client.table(table).select("revision").eq("id", record_id).execute()
            if not result.data:
                return False
            current = result.data[0].get("revision", 1)
            if current != expected_revision:
                log.warning("Stale write on %s %s: expected rev %d, got %d",
                           table, record_id, expected_revision, current)
                return False
            self.client.table(table).update({
                "revision": current + 1
            }).eq("id", record_id).execute()
            return True
        else:
            items = self._read_json(self.storage_dir / f"{table}.json")
            for item in items:
                if item.get("id") == record_id:
                    current = item.get("revision", 1)
                    if current != expected_revision:
                        return False
                    item["revision"] = current + 1
                    self._write_json(self.storage_dir / f"{table}.json", items)
                    return True
            return False

    def get_revision(self, table: str, record_id: str) -> Optional[int]:
        """Get current revision of a record."""
        if self._use_supabase():
            result = self.client.table(table).select("revision").eq("id", record_id).execute()
            if result.data:
                return result.data[0].get("revision", 1)
            return None
        else:
            items = self._read_json(self.storage_dir / f"{table}.json")
            for item in items:
                if item.get("id") == record_id:
                    return item.get("revision", 1)
            return None

    # ─── BUYER BUY BOX ────────────────────────────────────────────

    def upsert_buyer_buy_box(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a buyer buy box."""
        data["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("buyer_buy_boxes").upsert(data, on_conflict="buyer_id").execute()
            return result.data[0] if result.data else data
        else:
            return self._local_upsert("buyer_buy_boxes.json", data, "buyer_id")

    def get_buyer_buy_box(self, buyer_id: str) -> Optional[Dict[str, Any]]:
        """Get a buyer buy box by ID."""
        if self._use_supabase():
            result = self.client.table("buyer_buy_boxes").select("*").eq("buyer_id", buyer_id).execute()
            return result.data[0] if result.data else None
        else:
            return self._local_get("buyer_buy_boxes.json", "buyer_id", buyer_id)

    def list_buyer_buy_boxes(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List buyer buy boxes with optional filters."""
        if self._use_supabase():
            query = self.client.table("buyer_buy_boxes").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.order("activity_score", desc=True).execute()
            return result.data or []
        else:
            return self._local_list("buyer_buy_boxes.json", filters)

    def get_active_buyers(self) -> List[Dict[str, Any]]:
        """Get all active/verified buyers."""
        if self._use_supabase():
            result = self.client.table("buyer_buy_boxes").select("*").in_(
                "verification_status", ["VERIFIED", "PROBABLE"]
            ).order("activity_score", desc=True).execute()
            return result.data or []
        else:
            all_buyers = self._local_list("buyer_buy_boxes.json")
            return [b for b in all_buyers if b.get("verification_status") in ("VERIFIED", "PROBABLE")]

    def get_buyers_for_segment(self, market: str, property_type: str, price_min: float, price_max: float) -> List[Dict[str, Any]]:
        """Find buyers matching a market segment."""
        all_buyers = self.get_active_buyers()
        matches = []
        for buyer in all_buyers:
            markets = buyer.get("markets", [])
            ptypes = buyer.get("property_types", [])
            if markets and market.lower() not in [m.lower() for m in markets]:
                continue
            if ptypes and property_type.upper() not in ptypes:
                continue
            bmin = buyer.get("price_min", 0) or 0
            bmax = buyer.get("price_max", 0) or 0
            if bmax > 0 and price_min > bmax:
                continue
            if bmin > 0 and price_max < bmin:
                continue
            matches.append(buyer)
        return sorted(matches, key=lambda x: -(x.get("activity_score") or 0))

    # ─── DEAL SUBMISSIONS ──────────────────────────────────────────

    def insert_deal_submission(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new deal submission."""
        data["created_at"] = _iso_now()
        data["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("deal_submissions").insert(data).execute()
            return result.data[0] if result.data else data
        else:
            return self._local_insert("deal_submissions.json", data)

    def update_deal_submission(self, deal_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a deal submission."""
        updates["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("deal_submissions").update(updates).eq("id", deal_id).execute()
            return result.data[0] if result.data else updates
        else:
            return self._local_update("deal_submissions.json", "id", deal_id, updates)

    def get_deal_submission(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get a deal submission by ID."""
        if self._use_supabase():
            result = self.client.table("deal_submissions").select("*").eq("id", deal_id).execute()
            return result.data[0] if result.data else None
        else:
            return self._local_get("deal_submissions.json", "id", deal_id)

    def list_deal_submissions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List deal submissions with optional filters."""
        if self._use_supabase():
            query = self.client.table("deal_submissions").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.order("created_at", desc=True).execute()
            return result.data or []
        else:
            return self._local_list("deal_submissions.json", filters)

    def get_active_deals(self) -> List[Dict[str, Any]]:
        """Get all deals not in terminal state."""
        terminal = {"CLOSED", "LOST", "REJECTED"}
        if self._use_supabase():
            result = self.client.table("deal_submissions").select("*").not_.in_(
                "status", list(terminal)
            ).order("created_at", desc=True).execute()
            return result.data or []
        else:
            all_deals = self._local_list("deal_submissions.json")
            return [d for d in all_deals if d.get("status") not in terminal]

    # ─── SOCIAL INTERACTIONS ───────────────────────────────────────

    def insert_social_interaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a social interaction."""
        data["created_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("social_interactions").insert(data).execute()
            return result.data[0] if result.data else data
        else:
            return self._local_insert("social_interactions.json", data)

    def list_social_interactions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List social interactions."""
        if self._use_supabase():
            query = self.client.table("social_interactions").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.order("created_at", desc=True).execute()
            return result.data or []
        else:
            return self._local_list("social_interactions.json", filters)

    # ─── NEXT BEST ACTIONS ─────────────────────────────────────────

    def upsert_next_best_action(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a next-best-action."""
        data["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("next_best_actions").upsert(
                data, on_conflict="entity_id,entity_type"
            ).execute()
            return result.data[0] if result.data else data
        else:
            return self._local_upsert("next_best_actions.json", data, "entity_id")

    def get_next_best_actions(self, status: str = "PENDING", limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending next-best-actions sorted by priority."""
        if self._use_supabase():
            result = self.client.table("next_best_actions").select("*").eq(
                "status", status
            ).order("priority", desc=False).limit(limit).execute()
            return result.data or []
        else:
            all_actions = self._local_list("next_best_actions.json")
            pending = [a for a in all_actions if a.get("status") == status]
            return sorted(pending, key=lambda x: x.get("priority", 5))[:limit]

    def update_next_best_action(self, entity_id: str, entity_type: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a next-best-action."""
        updates["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("next_best_actions").update(updates).eq(
                "entity_id", entity_id
            ).eq("entity_type", entity_type).execute()
            return result.data[0] if result.data else updates
        else:
            return self._local_update("next_best_actions.json", "entity_id", entity_id, updates)

    # ─── FOLLOW-UPS ────────────────────────────────────────────────

    def insert_follow_up(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a follow-up task."""
        data["created_at"] = _iso_now()
        data["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("follow_ups").insert(data).execute()
            return result.data[0] if result.data else data
        else:
            return self._local_insert("follow_ups.json", data)

    def get_pending_follow_ups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending follow-ups sorted by next_attempt."""
        if self._use_supabase():
            result = self.client.table("follow_ups").select("*").eq(
                "status", "PENDING"
            ).order("next_attempt", desc=False).limit(limit).execute()
            return result.data or []
        else:
            all_fups = self._local_list("follow_ups.json")
            pending = [f for f in all_fups if f.get("status") == "PENDING"]
            return sorted(pending, key=lambda x: x.get("next_attempt") or "")[:limit]

    def update_follow_up(self, follow_up_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a follow-up."""
        updates["updated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("follow_ups").update(updates).eq("id", follow_up_id).execute()
            return result.data[0] if result.data else updates
        else:
            return self._local_update("follow_ups.json", "id", follow_up_id, updates)

    # ─── DEMAND SIGNALS ────────────────────────────────────────────

    def upsert_demand_signal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a demand signal."""
        data["calculated_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("demand_signals").upsert(
                data, on_conflict="market,property_type,price_band"
            ).execute()
            return result.data[0] if result.data else data
        else:
            key = f"{data.get('market')}_{data.get('property_type')}_{data.get('price_band')}"
            data["id"] = key
            return self._local_upsert("demand_signals.json", data, "id")

    def get_demand_signals(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get demand signals, optionally filtered by market."""
        if self._use_supabase():
            query = self.client.table("demand_signals").select("*")
            if market:
                query = query.eq("market", market)
            result = query.order("calculated_at", desc=True).execute()
            return result.data or []
        else:
            signals = self._local_list("demand_signals.json")
            if market:
                signals = [s for s in signals if s.get("market") == market]
            return signals

    # ─── REVENUE EVENTS ────────────────────────────────────────────

    def insert_revenue_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a revenue event."""
        data["created_at"] = _iso_now()
        if self._use_supabase():
            result = self.client.table("revenue_events").insert(data).execute()
            return result.data[0] if result.data else data
        else:
            return self._local_insert("revenue_events.json", data)

    def get_revenue_events(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get revenue events with optional filters."""
        if self._use_supabase():
            query = self.client.table("revenue_events").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.order("occurred_at", desc=True).execute()
            return result.data or []
        else:
            return self._local_list("revenue_events.json", filters)

    # ─── AUDIT LOG ─────────────────────────────────────────────────

    def log_event(self, event_type: str, entity_id: str = "", entity_type: str = "",
                  correlation_id: str = "", source: str = "system", result: str = "success",
                  error: str = "", payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Log a structured audit event."""
        data = {
            "event_type": event_type,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "correlation_id": correlation_id,
            "source": source,
            "result": result,
            "error": error,
            "payload": payload or {},
            "created_at": _iso_now(),
        }
        if self._use_supabase():
            self.client.table("audit_log_entries").insert(data).execute()
        else:
            self._local_insert("audit_log_entries.json", data)
        return data

    # ─── LOCAL JSON FALLBACK ───────────────────────────────────────

    def _local_upsert(self, filename: str, data: Dict[str, Any], key_field: str) -> Dict[str, Any]:
        """Upsert to local JSON file."""
        filepath = self.storage_dir / filename
        items = self._read_json(filepath)
        key_val = data.get(key_field)
        found = False
        for i, item in enumerate(items):
            if item.get(key_field) == key_val:
                items[i] = data
                found = True
                break
        if not found:
            items.append(data)
        self._write_json(filepath, items)
        return data

    def _local_insert(self, filename: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert to local JSON file."""
        filepath = self.storage_dir / filename
        items = self._read_json(filepath)
        items.append(data)
        self._write_json(filepath, items)
        return data

    def _local_get(self, filename: str, key_field: str, key_val: str) -> Optional[Dict[str, Any]]:
        """Get single item from local JSON file."""
        filepath = self.storage_dir / filename
        items = self._read_json(filepath)
        for item in items:
            if item.get(key_field) == key_val:
                return item
        return None

    def _local_update(self, filename: str, key_field: str, key_val: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update item in local JSON file."""
        filepath = self.storage_dir / filename
        items = self._read_json(filepath)
        for i, item in enumerate(items):
            if item.get(key_field) == key_val:
                items[i].update(updates)
                self._write_json(filepath, items)
                return items[i]
        return updates

    def _local_list(self, filename: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List items from local JSON file."""
        filepath = self.storage_dir / filename
        items = self._read_json(filepath)
        if filters:
            items = [i for i in items if all(i.get(k) == v for k, v in filters.items())]
        return items

    def _read_json(self, filepath) -> List[Dict[str, Any]]:
        """Read JSON file safely."""
        try:
            if filepath.exists():
                return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _write_json(self, filepath, data: List[Dict[str, Any]]) -> None:
        """Write JSON file atomically."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = filepath.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(filepath)
