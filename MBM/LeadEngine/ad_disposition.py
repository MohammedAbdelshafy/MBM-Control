"""
MBM LeadEngine — Disposition Outcomes Engine
==============================================
Tracks call dispositions with full audit trail.
Every disposition persists through the canonical repository/event path.
No fake outcomes. No random/default outcomes.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from MBM.LeadEngine.ad_repository import AdRepository

log = logging.getLogger(__name__)

# Terminal dispositions — once set, cannot be changed
TERMINAL_DISPOSITIONS = {"DNC"}

# Valid disposition outcomes
VALID_OUTCOMES = {
    "CONNECTED", "NO_ANSWER", "VOICEMAIL", "WRONG_NUMBER", "WRONG_PARTY",
    "INTERESTED", "NOT_INTERESTED", "CALLBACK", "APPOINTMENT", "DNC",
}

# Dispositions that require follow-up
FOLLOW_UP_REQUIRED = {"CONNECTED", "INTERESTED", "CALLBACK", "APPOINTMENT"}


class DispositionEngine:
    """
    Manages call dispositions with full audit trail.
    Every disposition event is persisted to the repository.
    DNC is a terminal state — once set, the lead is permanently suppressed.
    """

    def __init__(self, repo: Optional[AdRepository] = None):
        self.repo = repo or AdRepository()

    def record_disposition(self, lead_id: str, outcome: str,
                           entity_type: str = "seller", entity_id: str = "",
                           channel: str = "CALL", notes: str = "",
                           transcript: str = "", call_duration_seconds: int = 0,
                           campaign_id: str = "", content_id: str = "",
                           source_platform: str = "",
                           follow_up_channel: Optional[str] = None,
                           follow_up_scheduled_at: Optional[str] = None,
                           dnc_reason: str = "") -> Dict[str, Any]:
        """
        Record a disposition outcome. Validates the outcome, persists to
        repository, creates follow-up if required, and logs audit event.

        Returns: {ok, disposition_id, outcome, follow_up_created, errors}
        """
        errors = []

        # Validate outcome
        if outcome not in VALID_OUTCOMES:
            errors.append(f"Invalid outcome '{outcome}'. Must be one of: {sorted(VALID_OUTCOMES)}")
            return {"ok": False, "errors": errors}

        # Check for existing terminal disposition
        existing = self._get_existing_disposition(lead_id)
        if existing and existing.get("is_dnc"):
            errors.append(f"Lead {lead_id} is DNC — cannot record new disposition")
            return {"ok": False, "errors": errors, "existing_disposition": existing}

        # Build disposition record
        disposition_id = str(uuid.uuid4())
        is_dnc = outcome == "DNC"
        follow_up_required = outcome in FOLLOW_UP_REQUIRED

        data = {
            "id": disposition_id,
            "lead_id": lead_id,
            "entity_type": entity_type,
            "entity_id": entity_id or lead_id,
            "outcome": outcome,
            "channel": channel,
            "notes": notes,
            "transcript": transcript[:5000],  # truncate for storage
            "call_duration_seconds": call_duration_seconds,
            "follow_up_required": follow_up_required,
            "follow_up_channel": follow_up_channel,
            "follow_up_scheduled_at": follow_up_scheduled_at,
            "campaign_id": campaign_id,
            "content_id": content_id,
            "source_platform": source_platform,
            "is_dnc": is_dnc,
            "dnc_reason": dnc_reason if is_dnc else "",
        }

        # Persist disposition
        persisted = self._persist_disposition(data)

        # Create follow-up if required
        follow_up_created = False
        if follow_up_required:
            fu_channel = follow_up_channel or "CALL"
            from MBM.LeadEngine.ad_service import AdService
            service = AdService(self.repo)
            service.create_follow_up(
                entity_id=lead_id,
                entity_type=entity_type,
                reason=f"Follow-up after {outcome} disposition",
                priority=2 if outcome in ("INTERESTED", "APPOINTMENT") else 3,
                channel=fu_channel,
                scheduled_at=follow_up_scheduled_at,
            )
            follow_up_created = True

        # Audit log
        self.repo.log_event(
            "disposition_recorded", lead_id, entity_type,
            payload={
                "disposition_id": disposition_id,
                "outcome": outcome,
                "channel": channel,
                "is_dnc": is_dnc,
                "follow_up_required": follow_up_required,
            },
        )

        return {
            "ok": True,
            "disposition_id": disposition_id,
            "outcome": outcome,
            "is_dnc": is_dnc,
            "follow_up_created": follow_up_created,
        }

    def _get_existing_disposition(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent disposition for a lead."""
        if self.repo._use_supabase():
            try:
                result = self.repo.client.table("disposition_outcomes").select("*").eq(
                    "lead_id", lead_id
                ).order("created_at", desc=True).limit(1).execute()
                return result.data[0] if result.data else None
            except Exception:
                return None
        else:
            from pathlib import Path
            import json
            filepath = self.repo.storage_dir / "disposition_outcomes.json"
            if not filepath.exists():
                return None
            try:
                items = json.loads(filepath.read_text(encoding="utf-8"))
                matches = [i for i in items if i.get("lead_id") == lead_id]
                if matches:
                    matches.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                    return matches[0]
            except Exception:
                pass
            return None

    def _persist_disposition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist disposition to repository."""
        if self.repo._use_supabase():
            result = self.repo.client.table("disposition_outcomes").insert(data).execute()
            return result.data[0] if result.data else data
        else:
            from pathlib import Path
            import json
            filepath = self.repo.storage_dir / "disposition_outcomes.json"
            items = []
            if filepath.exists():
                try:
                    items = json.loads(filepath.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append(data)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")
            return data

    def get_lead_dispositions(self, lead_id: str) -> List[Dict[str, Any]]:
        """Get all dispositions for a lead, most recent first."""
        if self.repo._use_supabase():
            result = self.repo.client.table("disposition_outcomes").select("*").eq(
                "lead_id", lead_id
            ).order("created_at", desc=True).execute()
            return result.data or []
        else:
            from pathlib import Path
            import json
            filepath = self.repo.storage_dir / "disposition_outcomes.json"
            if not filepath.exists():
                return []
            try:
                items = json.loads(filepath.read_text(encoding="utf-8"))
                matches = [i for i in items if i.get("lead_id") == lead_id]
                matches.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return matches
            except Exception:
                return []

    def get_disposition_summary(self) -> Dict[str, Any]:
        """Get disposition statistics across all leads."""
        if self.repo._use_supabase():
            result = self.repo.client.table("disposition_outcomes").select("outcome").execute()
            outcomes = [r.get("outcome") for r in (result.data or [])]
        else:
            from pathlib import Path
            import json
            filepath = self.repo.storage_dir / "disposition_outcomes.json"
            if not filepath.exists():
                return {"total": 0, "by_outcome": {}, "dnc_count": 0}
            try:
                items = json.loads(filepath.read_text(encoding="utf-8"))
                outcomes = [i.get("outcome") for i in items]
            except Exception:
                return {"total": 0, "by_outcome": {}, "dnc_count": 0}

        from collections import Counter
        counts = Counter(outcomes)
        return {
            "total": len(outcomes),
            "by_outcome": dict(counts),
            "dnc_count": counts.get("DNC", 0),
            "follow_up_needed": sum(counts.get(o, 0) for o in FOLLOW_UP_REQUIRED),
        }

    def is_lead_dnc(self, lead_id: str) -> bool:
        """Check if a lead is in DNC terminal state."""
        existing = self._get_existing_disposition(lead_id)
        return existing is not None and existing.get("is_dnc", False)


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for disposition engine."""
    import sys
    import json

    engine = DispositionEngine()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ad_disposition.py [--summary|--recent|--record ...]"}))
        return

    cmd = sys.argv[1]

    if cmd == "--summary":
        print(json.dumps(engine.get_disposition_summary(), default=str))
    elif cmd == "--recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        if engine.repo._use_supabase():
            result = engine.repo.client.table("disposition_outcomes").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            print(json.dumps({"dispositions": result.data or []}, default=str))
        else:
            from pathlib import Path
            filepath = engine.repo.storage_dir / "disposition_outcomes.json"
            if filepath.exists():
                items = json.loads(filepath.read_text(encoding="utf-8"))
                items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                print(json.dumps({"dispositions": items[:limit]}, default=str))
            else:
                print(json.dumps({"dispositions": []}))
    elif cmd == "--record":
        args = sys.argv[2:]
        kwargs = {}
        i = 0
        while i < len(args):
            if args[i] == "--lead-id" and i + 1 < len(args):
                kwargs["lead_id"] = args[i + 1]; i += 2
            elif args[i] == "--outcome" and i + 1 < len(args):
                kwargs["outcome"] = args[i + 1]; i += 2
            elif args[i] == "--notes" and i + 1 < len(args):
                kwargs["notes"] = args[i + 1]; i += 2
            elif args[i] == "--follow-up-channel" and i + 1 < len(args):
                kwargs["follow_up_channel"] = args[i + 1]; i += 2
            elif args[i] == "--dnc-reason" and i + 1 < len(args):
                kwargs["dnc_reason"] = args[i + 1]; i += 2
            else:
                i += 1
        result = engine.record_disposition(**kwargs)
        print(json.dumps(result, default=str))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
