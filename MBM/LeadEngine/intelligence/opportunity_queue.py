"""
OpportunityQueue — safe, isolated storage for Intelligence Layer output (§7).

Ensures no external intelligence bypasses the human-review gate.
Opportunities are stored in a side-car JSON file, not in the canonical leads database.

States: DISCOVERED -> NORMALIZED -> SCORED -> REVIEW_REQUIRED -> APPROVED/REJECTED -> CONSUMED/EXPIRED
Invalid transitions fail closed. No silent jump to APPROVED or CONSUMED.
Provenance is mandatory (§8): missing => REVIEW_REQUIRED or REJECTED.

Storage namespace: MBM/Artifacts/intelligence/opportunities.json
Isolated from: leads_database.json, db_backups/, revision, checksums.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import Opportunity, OpportunityStatus, Provenance

OPPORTUNITIES_FILE = Path(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / "opportunities.json"
AUDIT_FILE = Path(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / "opportunity_transitions.jsonl"

# Allowed transitions — fail-closed (§7)
ALLOWED_TRANSITIONS: Dict[OpportunityStatus, List[OpportunityStatus]] = {
    OpportunityStatus.DISCOVERED: [OpportunityStatus.NORMALIZED, OpportunityStatus.REJECTED],
    OpportunityStatus.NORMALIZED: [OpportunityStatus.SCORED, OpportunityStatus.REJECTED],
    OpportunityStatus.SCORED: [OpportunityStatus.REVIEW_REQUIRED, OpportunityStatus.REJECTED],
    OpportunityStatus.REVIEW_REQUIRED: [OpportunityStatus.APPROVED, OpportunityStatus.REJECTED, OpportunityStatus.EXPIRED],
    OpportunityStatus.APPROVED: [OpportunityStatus.CONSUMED, OpportunityStatus.REJECTED],
    OpportunityStatus.REJECTED: [],
    OpportunityStatus.EXPIRED: [],
    OpportunityStatus.CONSUMED: [],
}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _serialize_opp(opp: Opportunity) -> Dict[str, Any]:
    d = opp.__dict__.copy()
    # Enum -> value
    if isinstance(d.get("status"), OpportunityStatus):
        d["status"] = d["status"].value
    # Provenance -> dict
    prov = d.get("provenance")
    if isinstance(prov, Provenance):
        pd = prov.__dict__.copy()
        d["provenance"] = pd
    return d

def _deserialize_opp(data: Dict[str, Any]) -> Opportunity:
    # status string -> enum
    status_raw = data.get("status", OpportunityStatus.DISCOVERED.value)
    try:
        status = OpportunityStatus(status_raw)
    except ValueError:
        status = OpportunityStatus.REVIEW_REQUIRED
    prov_data = data.get("provenance") or {}
    # handle both dict and already Provenance
    if isinstance(prov_data, Provenance):
        prov = prov_data
    else:
        # filter to known fields
        prov_fields = {k: v for k, v in prov_data.items() if k in Provenance.__dataclass_fields__}
        # ensure defaults for mandatory fields
        if "provider" not in prov_fields:
            prov_fields["provider"] = data.get("source_provider", "unknown")
        prov = Provenance(**prov_fields)
    # Build Opportunity, mapping legacy keys if needed
    kwargs = dict(data)
    kwargs["status"] = status
    kwargs["provenance"] = prov
    # only keep known fields
    known = Opportunity.__dataclass_fields__.keys()
    clean = {k: v for k, v in kwargs.items() if k in known}
    # required fields check
    if "opportunity_id" not in clean:
        clean["opportunity_id"] = data.get("opportunity_id") or data.get("id") or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]
    if "source_event_id" not in clean:
        clean["source_event_id"] = data.get("source_event_id", clean.get("opportunity_id", ""))
    if "source_provider" not in clean:
        clean["source_provider"] = data.get("source_provider", prov.provider)
    return Opportunity(**clean)

def _read_all() -> List[Dict[str, Any]]:
    if not OPPORTUNITIES_FILE.exists():
        return []
    try:
        data = json.loads(OPPORTUNITIES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def _write_all(records: List[Dict[str, Any]]) -> None:
    OPPORTUNITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OPPORTUNITIES_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(OPPORTUNITIES_FILE)

def _append_audit(entry: Dict[str, Any]) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

def list_opportunities(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    records = _read_all()
    if status:
        records = [r for r in records if r.get("status") == status]
    # newest first
    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return records[:limit]

def get_opportunity(opportunity_id: str) -> Optional[Dict[str, Any]]:
    for r in _read_all():
        if r.get("opportunity_id") == opportunity_id:
            return r
    return None

def write_opportunities(opportunities: List[Opportunity]) -> int:
    """
    Append opportunities to side-car store.
    Enforces provenance (§8): missing provenance => force REVIEW_REQUIRED.
    Returns count added (deduped by opportunity_id).
    """
    if not opportunities:
        return 0
    existing = _read_all()
    existing_ids = {r.get("opportunity_id") for r in existing if isinstance(r, dict)}
    added = 0
    for opp in opportunities:
        # Provenance mandatory — if incomplete, force REVIEW_REQUIRED (never APPROVED)
        if not opp.is_provenance_complete():
            if opp.status == OpportunityStatus.APPROVED:
                opp.status = OpportunityStatus.REVIEW_REQUIRED
            elif opp.status not in (OpportunityStatus.REJECTED, OpportunityStatus.REVIEW_REQUIRED):
                # For DISCOVERED/NORMALIZED/SCORED with bad provenance, push to REVIEW_REQUIRED
                # so human must inspect. This satisfies §8 "missing provenance => REVIEW_REQUIRED or REJECTED"
                if opp.status in (OpportunityStatus.DISCOVERED, OpportunityStatus.NORMALIZED, OpportunityStatus.SCORED):
                    opp.status = OpportunityStatus.REVIEW_REQUIRED
        # Prevent silent APPROVED/CONSUMED on write — must go via explicit transition
        if opp.status == OpportunityStatus.APPROVED or opp.status == OpportunityStatus.CONSUMED:
            # Only allow if provenance complete AND caller explicitly set via transition;
            # for direct writes, downgrade to REVIEW_REQUIRED.
            if not opp.is_provenance_complete():
                opp.status = OpportunityStatus.REVIEW_REQUIRED
            else:
                # Still downgrade CONSUMED on write; CONSUMED only via transition from APPROVED
                if opp.status == OpportunityStatus.CONSUMED:
                    opp.status = OpportunityStatus.REVIEW_REQUIRED
                # For APPROVED on write, require it came through proper state — downgrade to REVIEW_REQUIRED
                # unless we have audit proof. For now, downgrade.
                if opp.status == OpportunityStatus.APPROVED:
                    opp.status = OpportunityStatus.REVIEW_REQUIRED
        serialized = _serialize_opp(opp)
        if serialized["opportunity_id"] not in existing_ids:
            existing.append(serialized)
            existing_ids.add(serialized["opportunity_id"])
            added += 1
            _append_audit({
                "event": "opportunity_created",
                "opportunity_id": opp.opportunity_id,
                "status": serialized["status"],
                "at": _now(),
                "provenance_complete": opp.is_provenance_complete(),
            })
    if added:
        _write_all(existing)
    return added

def transition_opportunity(
    opportunity_id: str,
    to_status: OpportunityStatus | str,
    *,
    actor: str,
    reason: str = "",
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Explicit state transition with fail-closed enforcement.
    Records actor/timestamp/previous/new/reason/correlation_id.
    Provenance failure overrides score; policy failure would have blocked earlier.
    """
    if isinstance(to_status, str):
        try:
            to_status = OpportunityStatus(to_status)
        except ValueError:
            raise ValueError(f"Unknown status: {to_status}")

    records = _read_all()
    idx = next((i for i, r in enumerate(records) if r.get("opportunity_id") == opportunity_id), None)
    if idx is None:
        raise KeyError(f"Opportunity not found: {opportunity_id}")

    raw = records[idx]
    opp = _deserialize_opp(raw)
    from_status = opp.status

    # Validate transition
    allowed = ALLOWED_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise ValueError(f"Invalid transition {from_status.value} -> {to_status.value}. Allowed: {[s.value for s in allowed]}. Fail-closed.")

    # Guard: APPROVED requires provenance complete
    if to_status == OpportunityStatus.APPROVED and not opp.is_provenance_complete():
        raise ValueError(f"Cannot APPROVE {opportunity_id}: provenance incomplete (missing provider/object/url/type/captured/hash/lineage/confidence). Fail-closed.")

    # Guard: CONSUMED only from APPROVED (already enforced by allowed map)

    # Perform transition
    opp.status = to_status
    opp.updated_at = _now()
    records[idx] = _serialize_opp(opp)
    _write_all(records)
    entry = {
        "event": "opportunity_transition",
        "opportunity_id": opportunity_id,
        "from_status": from_status.value,
        "to_status": to_status.value,
        "actor": actor,
        "reason": reason,
        "correlation_id": correlation_id,
        "at": opp.updated_at,
    }
    _append_audit(entry)
    return entry

def purge_expired(ttl_hours: int = 72) -> int:
    """Mark REVIEW_REQUIRED older than ttl as EXPIRED (housekeeping, not auto-approve)."""
    records = _read_all()
    now = datetime.now(timezone.utc)
    changed = 0
    for r in records:
        if r.get("status") != OpportunityStatus.REVIEW_REQUIRED.value:
            continue
        try:
            created = datetime.fromisoformat(r.get("created_at", "").replace("Z", "+00:00"))
            if (now - created).total_seconds() > ttl_hours * 3600:
                opp = _deserialize_opp(r)
                opp.status = OpportunityStatus.EXPIRED
                opp.updated_at = _now()
                r.update(_serialize_opp(opp))
                changed += 1
                _append_audit({"event": "opportunity_expired", "opportunity_id": opp.opportunity_id, "at": opp.updated_at})
        except Exception:
            continue
    if changed:
        _write_all(records)
    return changed
