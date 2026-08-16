"""
GTM PRODUCTION GATE & HUMAN APPROVAL ENGINE
=============================================================================
Strict outbound gate requiring multi-point verification and human approval.

Gate Rule:
  EVIDENCE_VALID AND CONTACTABLE AND NOT_SUPPRESSED AND HIGH_CONFIDENCE
  AND CHANNEL_ALLOWED AND HUMAN_APPROVED
=============================================================================
"""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
APPROVALS_FILE = ARTIFACTS_DIR / "gtm_action_approvals.json"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HOLD = "HOLD"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ProductionGate:
    """
    Evaluates outbound safety gates and manages persistent human approval states.
    No message or call may be executed without passing all gates.
    """

    def __init__(self, approvals_file: Path = APPROVALS_FILE):
        self.approvals_file = approvals_file
        self._approvals: Dict[str, Dict[str, Any]] = self._load_approvals()

    def _load_approvals(self) -> Dict[str, Dict[str, Any]]:
        """Load stored human approval decisions from disk."""
        if self.approvals_file.exists():
            try:
                data = json.loads(self.approvals_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save_approvals(self) -> None:
        """Persist human approval decisions to disk."""
        self.approvals_file.write_text(json.dumps(self._approvals, indent=2), encoding="utf-8")

    def evaluate_gate(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate 6-point production gate for a candidate action:
        1. evidence_valid (non-empty source and claim)
        2. contactable (valid 10+ digit phone for phone, valid email for email)
        3. not_suppressed (not DNC, not suppressed, not wrong person)
        4. high_confidence (confidence >= 0.70)
        5. channel_allowed (phone/email/linkedin permitted)
        6. human_approved (explicit human sign-off)
        """
        entity_id = opportunity.get("id") or opportunity.get("entity_id") or opportunity.get("company", "UNKNOWN")
        channel = opportunity.get("recommended_channel", "PHONE").upper()

        # 1. Evidence Valid
        why_comp = (
            opportunity.get("why_this_company")
            or (opportunity.get("evidence", {}).get("claim") if isinstance(opportunity.get("evidence"), dict) else None)
            or opportunity.get("reason")
        )
        pain = opportunity.get("pain_point") or opportunity.get("pain")
        evidence_valid = bool(why_comp and pain)

        # 2. Contactable
        phone = (
            opportunity.get("phone", "")
            or (opportunity.get("contactability", {}).get("phone", "") if isinstance(opportunity.get("contactability"), dict) else "")
        )
        clean_phone = "".join(filter(str.isdigit, str(phone)))
        email = (
            opportunity.get("email", "")
            or (opportunity.get("contactability", {}).get("email", "") if isinstance(opportunity.get("contactability"), dict) else "")
        )
        
        if channel == "PHONE":
            contactable = len(clean_phone) >= 10
        elif channel == "EMAIL":
            contactable = "@" in str(email) and "." in str(email)
        else:
            contactable = True

        # 3. Not Suppressed
        identity_state = opportunity.get("identity_state", "IDENTITY_UNCONFIRMED")
        is_suppressed = bool(
            opportunity.get("is_suppressed")
            or opportunity.get("suppression_state") in {"SUPPRESSED", "DNC", "WRONG_PERSON", "WRONG_NUMBER"}
            or identity_state in {"WRONG_PERSON", "WRONG_NUMBER", "TENANT"}
        )
        not_suppressed = not is_suppressed

        # 4. High Confidence
        conf = float(opportunity.get("confidence", 0.85))
        if conf > 1.0:
            conf = conf / 100.0
        high_confidence = conf >= 0.70

        # 5. Channel Allowed
        channel_allowed = channel in {"PHONE", "EMAIL", "LINKEDIN", "SMS"}

        # 6. Human Approved
        approval_rec = self._approvals.get(entity_id, {})
        approval_status = approval_rec.get("status", ApprovalStatus.PENDING.value)
        human_approved = (approval_status == ApprovalStatus.APPROVED.value)

        # Overall gate pass
        can_execute = (
            evidence_valid
            and contactable
            and not_suppressed
            and high_confidence
            and channel_allowed
            and human_approved
        )

        return {
            "entity_id": entity_id,
            "can_execute": can_execute,
            "evidence_valid": evidence_valid,
            "contactable": contactable,
            "not_suppressed": not_suppressed,
            "high_confidence": high_confidence,
            "channel_allowed": channel_allowed,
            "human_approved": human_approved,
            "approval_status": approval_status,
            "approval_notes": approval_rec.get("notes", ""),
            "approved_by": approval_rec.get("approved_by", ""),
            "approved_at": approval_rec.get("approved_at", ""),
        }

    def set_approval(
        self,
        entity_id: str,
        status: ApprovalStatus,
        approved_by: str = "human_operator",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Record human approval decision (APPROVE, REJECT, HOLD, HUMAN_REVIEW)."""
        record = {
            "entity_id": entity_id,
            "status": status.value,
            "approved_by": approved_by,
            "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._approvals[entity_id] = record
        self._save_approvals()
        return record

    def batch_approve(self, entity_ids: List[str], approved_by: str = "human_operator") -> int:
        """Batch approve a list of verified opportunities."""
        count = 0
        for eid in entity_ids:
            self.set_approval(eid, ApprovalStatus.APPROVED, approved_by=approved_by, notes="Batch approved for production run")
            count += 1
        return count

    def get_approval_status(self, entity_id: str) -> str:
        return self._approvals.get(entity_id, {}).get("status", ApprovalStatus.PENDING.value)

    def list_approvals(self) -> Dict[str, Dict[str, Any]]:
        return self._approvals
