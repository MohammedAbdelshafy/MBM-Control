"""
lead_persistence.py — CANONICAL DIALER PERSISTENCE FOR VERIFIED PRODUCER OUTPUTS
=================================================================================
HARD SYSTEM INVARIANT: every lead that passes a producer's real verification gate
MUST reach the canonical dialer database in the SAME run, through the EXISTING
single-writer gateway (`MBM.LeadEngine.dialer_gateway.patch_dialer_db`).

This module is NOT a second write system. It is the shared mapping layer:
    producer verified lead
      -> phone normalization (existing CanonicalPhone.normalize_phone, E.164)
      -> dedupe against canonical records (stable id / normalized phone)
      -> patch_dialer_db()          [validated + locked + zero-shrink]
      -> priority refresh           [existing dialer_priority_engine]
      -> Output Contract result

FAILURE SEMANTICS: if the canonical write fails, persist_verified_leads returns
status=PERSISTENCE_FAILURE and the producing job MUST surface it instead of
reporting full success.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.canonical_lead_schema import CanonicalPhone
from MBM.LeadEngine.dialer_gateway import patch_dialer_db
from MBM.GLM.single_writer_lock import DialerSingleWriter


def normalize_phone_e164(raw: Any) -> Optional[str]:
    """Existing normalization layer. Valid US -> +1XXXXXXXXXX; ambiguous -> None."""
    return CanonicalPhone.normalize_phone(str(raw or ""))


def stable_lead_id(prefix: str, *identity_parts: Any) -> str:
    """Deterministic, stable lead id from source identity parts."""
    basis = "|".join(str(p or "").strip().lower() for p in identity_parts)
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _digits(p: Any) -> str:
    digits = "".join(ch for ch in str(p or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def map_to_canonical(lead: Dict[str, Any], source: str, id_prefix: str) -> Optional[Dict[str, Any]]:
    """Map a producer-verified lead into canonical dialer schema conventions.

    Returns None when the lead lacks a valid normalizable US phone — such a
    record must never enter the callable queue as verified.
    """
    e164 = normalize_phone_e164(lead.get("phone") or lead.get("authorized_official_phone"))
    if not e164:
        return None

    company = (lead.get("company_name") or lead.get("company")
               or lead.get("business_name") or "").strip()
    contact = (lead.get("contact") or lead.get("authorized_official_name")
               or lead.get("decision_maker") or lead.get("owner_name") or "").strip()
    if not company and not contact:
        return None  # insufficient identity

    lead_id = str(lead.get("id") or "").strip() or stable_lead_id(
        id_prefix, lead.get("npi") or "", company, _digits(e164))

    rec = {
        "id": lead_id,
        "company": company,
        "contact": contact,
        "phone": e164,
        "phone_verified": bool(lead.get("phone_verified", True)),
        "verification_status": str(lead.get("verification_status") or "VERIFIED"),
        "vertical": (lead.get("vertical_tag") or lead.get("vertical")
                     or lead.get("industry") or "Verified Leads"),
        "address": lead.get("address") or lead.get("location") or "",
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "source": lead.get("source") or source,
        "source_reference": (lead.get("source_url") or lead.get("source_reference")
                             or lead.get("source") or source),
        "created_at": lead.get("created_at")
        or datetime.now(timezone.utc).isoformat(),
        "callable": True,
        "sales_lane": lead.get("sales_lane", ""),
        "details": {
            k: lead[k] for k in (
                "taxonomy", "npi", "intent_score", "intent_tier", "line_type",
                "verified_phone", "enumeration_date", "role",
            ) if lead.get(k) not in (None, "")
        },
    }
    # Preserve any explicit seller evidence so the Tier-1 engine sees it.
    for k in ("segment", "distress_reason", "property_address", "owner_name",
              "is_real_estate", "motivation_score"):
        if lead.get(k) not in (None, ""):
            rec[k] = lead[k]
    return rec


def persist_verified_leads(
    leads: List[Dict[str, Any]],
    source: str,
    id_prefix: str,
    author: str = "lead_persistence",
    db_path: Optional[Path] = None,
    rerank: bool = True,
) -> Dict[str, Any]:
    """Persist producer-verified leads into the canonical dialer DB.

    Idempotent: records matching an existing canonical id OR normalized phone
    are treated as updates of the same record, never duplicates.
    """
    target = db_path  # None == live canonical DB (gateway default)
    writer = DialerSingleWriter(db_path=target) if target else DialerSingleWriter()
    try:
        existing = writer.read_leads()
    except Exception as e:
        return {"status": "PERSISTENCE_FAILURE", "reason": f"canonical read failed: {e}",
                "inserted": 0, "updated": 0, "skipped_invalid": 0, "errors": [str(e)]}
    original_count = len(existing)

    by_id = {str(r.get("id")): r for r in existing}
    by_phone = {_digits(r.get("phone")): r for r in existing if _digits(r.get("phone"))}

    mapped: List[Dict[str, Any]] = []
    skipped_invalid = 0
    seen_in_batch = set()
    for lead in leads or []:
        rec = map_to_canonical(lead, source=source, id_prefix=id_prefix)
        if rec is None:
            skipped_invalid += 1
            continue
        key_id = rec["id"]
        key_phone = _digits(rec["phone"])
        if key_id in seen_in_batch or key_phone in seen_in_batch:
            continue  # intra-batch duplicate
        seen_in_batch.add(key_id)
        seen_in_batch.add(key_phone)
        # Dedupe against canonical: reuse the EXISTING stable id when the
        # same lead already lives in the DB (update, never second record).
        hit = by_id.get(key_id) or by_phone.get(key_phone)
        if hit and hit.get("id"):
            rec["id"] = hit["id"]
        mapped.append(rec)

    errors: List[str] = []
    inserted = updated = 0
    persistence_ok = True
    if mapped:
        try:
            res = patch_dialer_db(
                mapped,
                reason=f"auto_persist:{source}",
                author=author,
                db_path=target,
            )
            if not res.get("ok", True):
                persistence_ok = False
                errors.append(str(res.get("error") or "gateway rejected commit"))
            else:
                inserted = int(res.get("added_count", 0) or 0)
                updated = int(res.get("updated_count", 0) or 0)
                rejected = int(res.get("rejected_count", 0) or 0)
                if rejected:
                    errors.append(f"gateway rejected {rejected} record(s)")
        except Exception as e:
            persistence_ok = False
            errors.append(f"patch_dialer_db failed: {e}")

    # Queue refresh on success (contamination guard inside the engine keeps
    # fixture/test paths from ever touching production artifacts).
    refreshed = False
    if persistence_ok and mapped and rerank:
        try:
            from MBM.LeadEngine.dialer_priority_engine import (
                DIALER_DB_PATH as CANONICAL_DB,
                refresh_dialer_priority_queue,
            )
            rr = refresh_dialer_priority_queue(
                db_path=target or CANONICAL_DB,
                dry_run=False,
                author=author,
            )
            refreshed = rr.get("status") == "SUCCESS"
        except Exception as e:
            errors.append(f"priority refresh failed: {e}")

    final_count = len(writer.read_leads()) if persistence_ok else original_count
    status = "SUCCESS" if (persistence_ok and final_count >= original_count) else "PERSISTENCE_FAILURE"
    return {
        "status": status,
        "source": source,
        "submitted": len(leads or []),
        "inserted": inserted,
        "updated": updated,
        "skipped_invalid": skipped_invalid,
        "canonical_records_before": original_count,
        "canonical_records_after": final_count,
        "queue_refreshed": refreshed,
        "zero_shrinkage": final_count >= original_count,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
