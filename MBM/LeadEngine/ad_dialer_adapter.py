"""
MBM LeadEngine — Dialer Adapter
================================
Bridges the AD engine with the MBM Dialer (leads_database.json).
Reads leads from the dialer DB, converts deals to dialer-lead format,
and writes back aftercall/interaction results.

Single-writer protocol: uses the same lock file as dialerDbGateway.js
(MBM/Artifacts/.leads_database.lock) to prevent concurrent corruption.
"""

from __future__ import annotations
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
LOCK_FILE = ROOT_DIR / "MBM" / "Artifacts" / ".leads_database.lock"
STALE_LOCK_MS = 30_000


class DialerAdapter:
    """
    Read/write adapter for leads_database.json.
    Follows the same single-writer protocol as dialerDbGateway.js.
    """

    def __init__(self, dialer_db: Optional[Path] = None):
        self.dialer_db = dialer_db or DIALER_DB

    # ─── LOCK MANAGEMENT ──────────────────────────────────────────

    def _acquire_lock(self, timeout_ms: int = 15_000) -> bool:
        """Acquire exclusive lock via O_CREAT|O_EXCL (mirrors JS gateway)."""
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            try:
                fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({
                    "pid": os.getpid(),
                    "source": "python-dialer-adapter",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode())
                os.close(fd)
                return True
            except FileExistsError:
                try:
                    stat = os.stat(LOCK_FILE)
                    age_ms = (time.time() - stat.st_mtime) * 1000
                    if age_ms > STALE_LOCK_MS:
                        LOCK_FILE.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    pass
                time.sleep(0.05)
            except Exception as e:
                log.warning("Lock acquisition error: %s", e)
                return False
        return False

    def _release_lock(self):
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    # ─── READ LEADS ───────────────────────────────────────────────

    def read_leads(self) -> List[Dict[str, Any]]:
        """Read all leads from the dialer DB."""
        if not self.dialer_db.exists():
            return []
        try:
            raw = self.dialer_db.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, list) else data.get("leads", [])
        except Exception as e:
            log.error("Failed to read dialer DB: %s", e)
            return []

    def get_lead_by_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get a single lead by ID."""
        for lead in self.read_leads():
            if str(lead.get("id")) == str(lead_id):
                return lead
        return None

    def _write_leads(self, leads: List[Dict[str, Any]]) -> bool:
        """Write leads atomically under the single-writer lock."""
        ok = self._acquire_lock()
        if not ok:
            log.error("Could not acquire single-writer lock")
            return False
        try:
            self.dialer_db.parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self.dialer_db.parent),
                prefix=".leads_db_tmp_",
                suffix=".json",
            )
            try:
                os.write(tmp_fd, json.dumps(leads, indent=2, default=str).encode())
                os.close(tmp_fd)
                initial = len(leads)
                # Atomic rename (same logic as JS gateway)
                for _ in range(20):
                    try:
                        os.replace(tmp_path, str(self.dialer_db))
                        return True
                    except OSError:
                        time.sleep(0.05)
                # Fallback: copy
                import shutil
                shutil.copy2(tmp_path, str(self.dialer_db))
                os.unlink(tmp_path)
                return True
            except Exception as e:
                log.error("Write failed: %s", e)
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                return False
        finally:
            self._release_lock()

    def patch_lead(self, lead_id: str, fields: Dict[str, Any]) -> bool:
        """Patch a single lead's fields by ID."""
        leads = self.read_leads()
        patched = False
        for lead in leads:
            if str(lead.get("id")) == str(lead_id):
                lead.update(fields)
                patched = True
                break
        if patched:
            return self._write_leads(leads)
        return False

    # ─── DEAL → LEAD CONVERSION ───────────────────────────────────

    def deal_to_lead(self, deal: Dict[str, Any], score: Optional[Dict] = None,
                     matches: Optional[List] = None) -> Dict[str, Any]:
        """
        Convert an AD engine deal submission to a dialer-compatible lead dict.
        Maps AD schema → dialer schema so the dialer can display and act on it.
        """
        status_map = {
            "INTAKE": "NEW",
            "VALIDATING": "NEW",
            "UNDERWRITING": "NEW",
            "SCORED": "QUALIFIED",
            "MATCHING": "QUALIFIED",
            "BUYER_FOUND": "HOT",
            "OUTREACH_SENT": "FOLLOW_UP",
            "UNDER_CONTRACT": "CONTRACT",
            "ASSIGNED": "ASSIGNED",
            "CLOSED": "CLOSED",
            "LOST": "LOST",
            "REJECTED": "DEAD",
        }
        ad_status = deal.get("status", "INTAKE")
        dialer_status = status_map.get(ad_status, "NEW")

        score_val = 0
        if score:
            score_val = int(score.get("overall_score", 0))
        elif deal.get("deal_score"):
            score_val = int(deal["deal_score"])

        buyer_match = None
        if matches:
            buyer_match = matches[0] if matches else None
        elif deal.get("buyer_matches"):
            bm = deal["buyer_matches"]
            buyer_match = bm[0] if isinstance(bm, list) and bm else None

        lead = {
            "id": deal.get("id"),
            "contact": deal.get("source_name", ""),
            "phone": deal.get("source_phone", ""),
            "email": deal.get("source_email", ""),
            "company": deal.get("source_platform", ""),
            "address": deal.get("address", ""),
            "city": deal.get("city", ""),
            "state": deal.get("state", ""),
            "zip": deal.get("zip_code", ""),
            "property_type": deal.get("property_type", "SFR"),
            "asking_price": deal.get("asking_price", 0),
            "arv": deal.get("arv", 0),
            "estimated_repairs": deal.get("estimated_repairs", 0),
            "status": dialer_status,
            "ad_status": ad_status,
            "demand_signal": deal.get("demand_signal", "UNKNOWN"),
            "score": score_val,
            "buyer_match": buyer_match,
            "source": "ad_engine",
            "primary_offer": "WHOLESALE",
            "sales_lane": "REAL_ESTATE_WHOLESALE",
            "call_count": 0,
            "last_called_at": None,
            "disposition": ad_status,
            "created_at": deal.get("created_at", datetime.now(timezone.utc).isoformat()),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return lead

    def sync_deal_to_dialer(self, deal: Dict[str, Any], score: Optional[Dict] = None,
                            matches: Optional[List] = None) -> bool:
        """Create or update a dialer lead from an AD engine deal."""
        lead = self.deal_to_lead(deal, score, matches)
        leads = self.read_leads()

        # Find existing or append
        found = False
        for i, existing in enumerate(leads):
            if str(existing.get("id")) == str(lead["id"]):
                leads[i] = {**existing, **lead}
                found = True
                break
        if not found:
            leads.append(lead)

        return self._write_leads(leads)

    # ─── AFTERCALL → AD ENGINE ────────────────────────────────────

    def record_aftercall(self, lead_id: str, transcript: str,
                         disposition: str = "", notes: str = "",
                         phone: str = "", email: str = "") -> Dict[str, Any]:
        """
        Record an aftercall event on a dialer lead.
        Updates call_count, last_called_at, and appends to interaction_log.
        Returns the updated lead or error info.
        """
        leads = self.read_leads()
        target = None
        for lead in leads:
            if str(lead.get("id")) == str(lead_id):
                target = lead
                break

        if not target:
            return {"error": f"Lead {lead_id} not found", "ok": False}

        # Update call metadata
        target["call_count"] = (target.get("call_count") or 0) + 1
        target["last_called_at"] = datetime.now(timezone.utc).isoformat()
        if disposition:
            target["disposition"] = disposition
            target["status"] = disposition

        # Append to interaction log
        log_entry = {
            "type": "aftercall",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transcript": transcript[:2000],  # truncate for storage
            "disposition": disposition,
            "notes": notes,
            "phone": phone or target.get("phone", ""),
            "email": email or target.get("email", ""),
        }
        if "interaction_log" not in target:
            target["interaction_log"] = []
        target["interaction_log"].append(log_entry)

        ok = self._write_leads(leads)
        return {"ok": ok, "lead": target if ok else None}

    # ─── AD ENGINE FEED ───────────────────────────────────────────

    def get_seller_leads_for_ad(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Pull seller leads from the dialer that are ready for AD engine processing.
        Returns leads that have phone + valid address + haven't been scored yet.
        """
        leads = self.read_leads()
        ready = []
        for lead in leads:
            if lead.get("source") == "ad_engine":
                continue
            if not lead.get("phone"):
                continue
            if not lead.get("address"):
                continue
            if lead.get("score", 0) > 0:
                continue
            ready.append(lead)
            if len(ready) >= limit:
                break
        return ready

    def get_leads_needing_followup(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get leads with FOLLOW_UP or HOT status for the AD engine."""
        leads = self.read_leads()
        return [
            lead for lead in leads
            if lead.get("status") in ("FOLLOW_UP", "HOT")
            and lead.get("source") == "ad_engine"
        ][:limit]
