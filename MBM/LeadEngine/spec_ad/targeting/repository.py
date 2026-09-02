"""
repository.py — explicit, idempotent, conflict-aware store for TargetAccount (Step 9).

Does NOT:
- call CRM APIs
- send outreach
- generate videos
- create decision makers
- run external prospecting automatically

Is additive and isolated from leads_database.json.

Production backing is Supabase `spec_ad_target_accounts` (00020). For hermetic
tests and local Phase 2 usage, this class provides a file-backed side-car that
mirrors the Supabase contract: idempotent upsert on canonical_domain, conflict
detection, provenance preservation.

The store file defaults to MBM/Artifacts/spec_ad/target_accounts.json (ignored via
.gitignore PII patterns if needed, but spec_ad is non-PII business metadata).
Tests pass an explicit tmp path for isolation.

All writes are explicit and must be called by the caller; no implicit prospecting.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .dedup import canonicalize_domain, detect_conflicting_identity, dedup_key, extract_canonical_domain
from .scoring import build_target_account

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[4] / "MBM" / "Artifacts" / "spec_ad" / "target_accounts.json"
AUDIT_PATH = Path(__file__).resolve().parents[4] / "MBM" / "Artifacts" / "spec_ad" / "target_account_transitions.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_store(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("accounts"), list):
            return data["accounts"]
    except Exception:
        pass
    return []


def _write_store(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def _append_audit(entry: Dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


class TargetAccountRepository:
    """
    Explicit store. Caller must provide store_path for tests; production may
    later swap to Supabase implementation behind same method names.
    """

    def __init__(self, store_path: Optional[Path] = None, audit_path: Optional[Path] = None):
        self.store_path = Path(store_path) if store_path else DEFAULT_STORE_PATH
        self.audit_path = Path(audit_path) if audit_path else AUDIT_PATH

    # ---- reads ----

    def list(self, *, status: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        records = _read_store(self.store_path)
        if status:
            records = [r for r in records if r.get("account_status") == status]
        records.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return records[:limit]

    def get(self, account_id: str) -> Optional[Dict[str, Any]]:
        for r in _read_store(self.store_path):
            if str(r.get("id")) == str(account_id):
                return r
        return None

    def find_by_domain(self, domain_or_url: str) -> Optional[Dict[str, Any]]:
        canon = canonicalize_domain(domain_or_url)
        if not canon:
            return None
        for r in _read_store(self.store_path):
            if (r.get("canonical_domain") or "").lower() == canon:
                return r
        return None

    def find_by_dedup_key(self, dedup_key_val: str) -> Optional[Dict[str, Any]]:
        for r in _read_store(self.store_path):
            acct = {"canonical_domain": r.get("canonical_domain"), "company_name": r.get("company_name"), "id": r.get("id")}
            if dedup_key(acct) == dedup_key_val:
                return r
        return None

    # ---- writes (explicit, idempotent, conflict-aware) ----

    def create_target_account(self, raw: Dict[str, Any], config: Any, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Create a single TargetAccount from raw dict + config.
        Idempotent on canonical_domain: if domain exists, returns existing and
        appends audit instead of duplicating. Use upsert for conflict-aware merge.
        """
        built = build_target_account(raw, config, context or {})
        # ensure id
        if not built.get("id"):
            built["id"] = str(uuid.uuid4())
        built["created_at"] = built.get("created_at") or _now()
        built["updated_at"] = _now()
        built["last_evaluated_at"] = _now()

        records = _read_store(self.store_path)
        domain = (built.get("canonical_domain") or "").lower() if built.get("canonical_domain") else None
        if domain:
            for r in records:
                if (r.get("canonical_domain") or "").lower() == domain:
                    # idempotent: already exists
                    _append_audit(
                        {
                            "event": "create_idempotent_hit",
                            "canonical_domain": domain,
                            "existing_id": r.get("id"),
                            "attempted_id": built.get("id"),
                            "at": _now(),
                        },
                        self.audit_path,
                    )
                    return r

        records.append(built)
        _write_store(self.store_path, records)
        _append_audit(
            {"event": "target_account_created", "id": built["id"], "canonical_domain": built.get("canonical_domain"), "status": built.get("account_status"), "at": built["updated_at"]},
            self.audit_path,
        )
        return built

    def upsert_target_account(
        self, raw: Dict[str, Any], config: Any, context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Idempotent upsert on canonical_domain.
        - If no domain, falls back to dedup_key; if no key, creates new.
        - If domain exists and incoming has conflicting identity, marks conflict
          (account_status=DISQUALIFIED, exclusion_reason=conflicting_identity) and
          preserves provenance from both, never silently overwrites company_name.
        - If domain exists and no conflict, merges provenance (append) and re-evaluates
          scores/status via build_target_account, preserving created_at.
        """
        incoming_built = build_target_account(raw, config, context or {})
        incoming_domain = (incoming_built.get("canonical_domain") or "").lower() if incoming_built.get("canonical_domain") else None

        records = _read_store(self.store_path)

        # find existing by domain
        existing_idx: Optional[int] = None
        if incoming_domain:
            for idx, r in enumerate(records):
                if (r.get("canonical_domain") or "").lower() == incoming_domain:
                    existing_idx = idx
                    break
        else:
            # fallback to dedup_key match (name-based)
            incoming_key = dedup_key(raw)
            if incoming_key:
                for idx, r in enumerate(records):
                    existing_acct = {"canonical_domain": r.get("canonical_domain"), "company_name": r.get("company_name"), "id": r.get("id")}
                    if dedup_key(existing_acct) == incoming_key:
                        existing_idx = idx
                        break

        if existing_idx is None:
            # create
            if not incoming_built.get("id"):
                incoming_built["id"] = str(uuid.uuid4())
            incoming_built["created_at"] = incoming_built.get("created_at") or _now()
            incoming_built["updated_at"] = _now()
            incoming_built["last_evaluated_at"] = _now()
            records.append(incoming_built)
            _write_store(self.store_path, records)
            _append_audit(
                {"event": "target_account_upsert_created", "id": incoming_built["id"], "canonical_domain": incoming_domain, "at": incoming_built["updated_at"]},
                self.audit_path,
            )
            return incoming_built

        # existing exists — conflict check
        existing = records[existing_idx]
        if detect_conflicting_identity(existing, incoming_built):
            # mark conflict, preserve existing company_name, append provenance
            merged_provenance = list(existing.get("provenance") or []) + list(incoming_built.get("provenance") or [])
            # de-dupe provenance by source+retrieved_at
            seen = set()
            deduped = []
            for p in merged_provenance:
                key = f"{p.get('source')}|{p.get('retrieved_at')}"
                if key not in seen:
                    seen.add(key)
                    deduped.append(p)
            existing["provenance"] = deduped
            existing["account_status"] = "DISQUALIFIED"
            existing["exclusion_reason"] = "conflicting_identity"
            existing["updated_at"] = _now()
            existing["last_evaluated_at"] = _now()
            records[existing_idx] = existing
            _write_store(self.store_path, records)
            _append_audit(
                {
                    "event": "target_account_conflict",
                    "id": existing["id"],
                    "canonical_domain": incoming_domain,
                    "incoming_company": incoming_built.get("company_name"),
                    "existing_company": existing.get("company_name"),
                    "at": existing["updated_at"],
                },
                self.audit_path,
            )
            return existing

        # no conflict — merge provenance and re-evaluate, preserve created_at and id
        merged_provenance = list(existing.get("provenance") or []) + list(incoming_built.get("provenance") or [])
        seen = set()
        deduped = []
        for p in merged_provenance:
            key = f"{p.get('source')}|{p.get('retrieved_at')}"
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        # build re-evaluated, but keep original provenance merged
        reeval_raw = dict(raw)
        reeval_raw["provenance"] = deduped
        # preserve existing id and created_at for stability
        reeval_raw["id"] = existing.get("id")
        reeval_raw["created_at"] = existing.get("created_at")
        reevaluated = build_target_account(reeval_raw, config, context or {})
        reevaluated["id"] = existing.get("id")
        reevaluated["created_at"] = existing.get("created_at")
        reevaluated["provenance"] = deduped
        reevaluated["updated_at"] = _now()
        reevaluated["last_evaluated_at"] = _now()
        records[existing_idx] = reevaluated
        _write_store(self.store_path, records)
        _append_audit(
            {"event": "target_account_upsert_merged", "id": reevaluated["id"], "canonical_domain": incoming_domain, "at": reevaluated["updated_at"]},
            self.audit_path,
        )
        return reevaluated

    def update_evaluation(self, account_id: str, raw_patch: Dict[str, Any], config: Any) -> Dict[str, Any]:
        """Re-evaluate an existing account with a patch (explicit)."""
        records = _read_store(self.store_path)
        idx = next((i for i, r in enumerate(records) if str(r.get("id")) == str(account_id)), None)
        if idx is None:
            raise KeyError(f"TargetAccount not found: {account_id}")
        existing = records[idx]
        # merge patch onto existing raw, rebuild
        merged = dict(existing)
        merged.update(raw_patch)
        # keep provenance append
        if raw_patch.get("provenance"):
            merged["provenance"] = list(existing.get("provenance") or []) + (
                raw_patch["provenance"] if isinstance(raw_patch["provenance"], list) else [raw_patch["provenance"]]
            )
        rebuilt = build_target_account(merged, config, {})
        rebuilt["id"] = existing.get("id")
        rebuilt["created_at"] = existing.get("created_at")
        rebuilt["updated_at"] = _now()
        rebuilt["last_evaluated_at"] = _now()
        records[idx] = rebuilt
        _write_store(self.store_path, records)
        _append_audit({"event": "target_account_revaluated", "id": account_id, "at": rebuilt["updated_at"]}, self.audit_path)
        return rebuilt

    def suppress_account(self, account_id: str, *, reason: str = "manual_suppression", actor: str = "system") -> Dict[str, Any]:
        """Explicit suppression — terminal, mirrors dialer HARD_SUPPRESSION."""
        records = _read_store(self.store_path)
        idx = next((i for i, r in enumerate(records) if str(r.get("id")) == str(account_id)), None)
        if idx is None:
            raise KeyError(f"TargetAccount not found: {account_id}")
        existing = records[idx]
        existing["account_status"] = "SUPPRESSED"
        existing["exclusion_reason"] = reason
        existing["updated_at"] = _now()
        existing["last_evaluated_at"] = _now()
        records[idx] = existing
        _write_store(self.store_path, records)
        _append_audit(
            {"event": "target_account_suppressed", "id": account_id, "reason": reason, "actor": actor, "at": existing["updated_at"]},
            self.audit_path,
        )
        return existing
