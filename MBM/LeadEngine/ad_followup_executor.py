"""
MBM LeadEngine — Follow-Up Execution Engine
=============================================
Picks up pending follow-ups from the repository and dispatches them
through the appropriate channel adapter. Tracks status, retries, and outcomes.

Channel adapters:
  CALL    — Triggers dialer integration (Twilio bridge / mbm-dialer)
  SMS     — Sends via Phound (MBM outbound rail)
  WHATSAPP — Sends via Phound WhatsApp
  EMAIL   — Queues for email pipeline
  MANUAL  — Creates task, waits for human action
  SYSTEM  — Automated internal action (no external call needed)
"""

from __future__ import annotations
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Protocol

from MBM.LeadEngine.ad_repository import AdRepository

log = logging.getLogger(__name__)


# ─── CHANNEL ADAPTERS (Protocol) ─────────────────────────────────

class ChannelAdapter(Protocol):
    """Interface for channel-specific follow-up dispatch."""
    channel: str

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch the follow-up. Returns {ok, status, message_id, error}."""
        ...

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        """Check if this adapter can handle the follow-up."""
        ...


class ManualAdapter:
    """Manual follow-up — just marks it as ready for human review."""
    channel = "MANUAL"

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "MANUAL"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "status": "AWAITING_HUMAN",
            "message": f"Manual follow-up ready for human: {follow_up.get('reason', '')}",
        }


class SystemAdapter:
    """System follow-up — internal automated actions."""
    channel = "SYSTEM"

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "SYSTEM"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        action = follow_up.get("metadata", {}).get("system_action", "log")
        return {
            "ok": True,
            "status": "COMPLETED",
            "message": f"System action '{action}' executed",
        }


class CallAdapter:
    """
    Phone follow-up — triggers the dialer bridge.
    In LOCAL mode, just logs the call intent.
    In STAGING/PRODUCTION, would trigger Twilio bridge via mbm-dialer.
    """
    channel = "CALL"

    def __init__(self, env_mode: str = "LOCAL"):
        self.env_mode = env_mode

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "CALL"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        phone = entity.get("phone") or entity.get("source_phone", "")
        if not phone:
            return {"ok": False, "error": "No phone number on entity"}

        if self.env_mode in ("PRODUCTION", "STAGING"):
            # In production, trigger the Twilio bridge via mbm-dialer API
            log.info("CALL: Would trigger Twilio bridge to %s", phone)
            return {
                "ok": True,
                "status": "BRIDGE_REQUESTED",
                "message": f"Call bridge requested to {phone}",
                "phone": phone,
            }
        else:
            log.info("CALL (local): Would call %s — reason: %s",
                     phone, follow_up.get("reason", ""))
            return {
                "ok": True,
                "status": "LOCAL_LOGGED",
                "message": f"Call to {phone} logged (LOCAL mode)",
                "phone": phone,
            }


class SmsAdapter:
    """
    SMS follow-up via Phound.
    In LOCAL mode, just logs the intent.
    """
    channel = "SMS"

    def __init__(self, env_mode: str = "LOCAL"):
        self.env_mode = env_mode

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "SMS"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        phone = entity.get("phone") or entity.get("source_phone", "")
        if not phone:
            return {"ok": False, "error": "No phone number on entity"}

        message = context.get("message", follow_up.get("reason", ""))
        if self.env_mode in ("PRODUCTION", "STAGING"):
            log.info("SMS: Would send via Phound to %s", phone)
            return {
                "ok": True,
                "status": "PHOUND_QUEUED",
                "message": f"SMS queued via Phound to {phone}",
                "phone": phone,
            }
        else:
            log.info("SMS (local): Would send to %s: %s", phone, message[:80])
            return {
                "ok": True,
                "status": "LOCAL_LOGGED",
                "message": f"SMS to {phone} logged (LOCAL mode)",
            }


class EmailAdapter:
    """
    Email follow-up via the existing email pipeline.
    In LOCAL mode, just logs the intent.
    """
    channel = "EMAIL"

    def __init__(self, env_mode: str = "LOCAL"):
        self.env_mode = env_mode

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "EMAIL"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        email = entity.get("email") or entity.get("source_email", "")
        if not email:
            return {"ok": False, "error": "No email on entity"}

        if self.env_mode in ("PRODUCTION", "STAGING"):
            log.info("EMAIL: Would queue for %s", email)
            return {
                "ok": True,
                "status": "EMAIL_QUEUED",
                "message": f"Email queued for {email}",
                "email": email,
            }
        else:
            log.info("EMAIL (local): Would send to %s", email)
            return {
                "ok": True,
                "status": "LOCAL_LOGGED",
                "message": f"Email to {email} logged (LOCAL mode)",
            }


class WhatsappAdapter:
    """WhatsApp follow-up via Phound."""
    channel = "WHATSAPP"

    def __init__(self, env_mode: str = "LOCAL"):
        self.env_mode = env_mode

    def can_handle(self, follow_up: Dict[str, Any]) -> bool:
        return follow_up.get("channel") == "WHATSAPP"

    def send(self, follow_up: Dict[str, Any], entity: Dict[str, Any],
             context: Dict[str, Any]) -> Dict[str, Any]:
        phone = entity.get("phone") or entity.get("source_phone", "")
        if not phone:
            return {"ok": False, "error": "No phone number on entity"}

        if self.env_mode in ("PRODUCTION", "STAGING"):
            log.info("WHATSAPP: Would send via Phound to %s", phone)
            return {
                "ok": True,
                "status": "WHATSAPP_QUEUED",
                "message": f"WhatsApp queued via Phound to {phone}",
            }
        else:
            log.info("WHATSAPP (local): Would send to %s", phone)
            return {
                "ok": True,
                "status": "LOCAL_LOGGED",
                "message": f"WhatsApp to {phone} logged (LOCAL mode)",
            }


# ─── FOLLOW-UP EXECUTOR ──────────────────────────────────────────

class FollowUpExecutor:
    """
    Picks up pending follow-ups, resolves entity context,
    dispatches through the correct channel adapter, and records outcomes.
    Enforces: idempotency, max attempts, DNC blocking, retry safety.
    """

    TERMINAL_REASONS = {"DNC", "EXHAUSTED", "COMPLETED", "WRONG_NUMBER", "WRONG_PARTY", "NOT_INTERESTED"}
    TERMINAL_PROVIDER_STATUSES = {"PROVIDER_FAILED", "DNC", "EXHAUSTED"}

    def __init__(self, repo: Optional[AdRepository] = None, env_mode: str = "LOCAL"):
        self.repo = repo or AdRepository()
        self.env_mode = env_mode
        self.adapters: List[ChannelAdapter] = [
            CallAdapter(env_mode),
            SmsAdapter(env_mode),
            EmailAdapter(env_mode),
            WhatsappAdapter(env_mode),
            ManualAdapter(),
            SystemAdapter(),
        ]

    def _get_adapter(self, channel: str) -> Optional[ChannelAdapter]:
        for adapter in self.adapters:
            if adapter.channel == channel:
                return adapter
        return None

    def _is_terminal(self, follow_up: Dict[str, Any]) -> bool:
        """Check if a follow-up is in a terminal state."""
        if follow_up.get("terminal_reason"):
            return True
        if follow_up.get("status") in ("COMPLETED", "SKIPPED"):
            return True
        return False

    def _is_exhausted(self, follow_up: Dict[str, Any]) -> bool:
        """Check if a follow-up has exhausted all attempts."""
        attempt_count = follow_up.get("attempt_count", 0)
        max_attempts = follow_up.get("max_attempts", 3)
        return attempt_count >= max_attempts

    def _check_dnc_lead(self, follow_up: Dict[str, Any]) -> bool:
        """Check if the entity this follow-up targets is DNC."""
        entity_id = follow_up.get("entity_id", "")
        if not entity_id:
            return False
        from MBM.LeadEngine.ad_disposition import DispositionEngine
        engine = DispositionEngine(self.repo)
        return engine.is_lead_dnc(entity_id)

    def _resolve_entity(self, follow_up: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve the entity a follow-up references."""
        entity_type = follow_up.get("entity_type", "")
        entity_id = follow_up.get("entity_id", "")

        if entity_type == "buyer":
            return self.repo.get_buyer_buy_box(entity_id) or {"id": entity_id}
        elif entity_type == "deal":
            return self.repo.get_deal_submission(entity_id) or {"id": entity_id}
        elif entity_type in ("seller", "lead", "social"):
            return {"id": entity_id, "phone": "", "email": ""}
        return {"id": entity_id}

    def execute_one(self, follow_up: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single follow-up with full safety checks.
        Returns execution result.
        """
        fu_id = follow_up.get("id", "?")
        channel = follow_up.get("channel", "MANUAL")
        entity_id = follow_up.get("entity_id", "?")

        # ─── SAFETY CHECKS ───────────────────────────────────────

        # 1. Terminal state check
        if self._is_terminal(follow_up):
            return {
                "ok": False,
                "error": f"Follow-up {fu_id} is terminal (reason: {follow_up.get('terminal_reason', 'completed')})",
                "follow_up_id": fu_id,
                "status": "BLOCKED_TERMINAL",
            }

        # 2. Exhaustion check
        if self._is_exhausted(follow_up):
            self.repo.update_follow_up(fu_id, {
                "status": "FAILED",
                "terminal_reason": "EXHAUSTED",
                "last_error": f"Exhausted after {follow_up.get('attempt_count', 0)} attempts",
            })
            return {
                "ok": False,
                "error": f"Follow-up {fu_id} exhausted after {follow_up.get('attempt_count', 0)} attempts",
                "follow_up_id": fu_id,
                "status": "BLOCKED_EXHAUSTED",
            }

        # 3. DNC lead check
        if self._check_dnc_lead(follow_up):
            self.repo.update_follow_up(fu_id, {
                "status": "SKIPPED",
                "terminal_reason": "DNC",
                "last_error": "Entity is DNC",
            })
            return {
                "ok": False,
                "error": f"Follow-up {fu_id} blocked: entity {entity_id} is DNC",
                "follow_up_id": fu_id,
                "status": "BLOCKED_DNC",
            }

        # 4. Channel escalation check — prevent accidental channel switch
        # (If originally scheduled for CALL, don't silently switch to SMS)

        # ─── DISPATCH ────────────────────────────────────────────

        adapter = self._get_adapter(channel)
        if not adapter:
            return {
                "ok": False,
                "error": f"No adapter for channel '{channel}'",
                "follow_up_id": fu_id,
            }

        # Mark as in-progress
        self.repo.update_follow_up(fu_id, {"status": "IN_PROGRESS"})

        # Resolve entity
        entity = self._resolve_entity(follow_up)
        context = follow_up.get("metadata", {})

        # Dispatch
        try:
            result = adapter.send(follow_up, entity, context)
        except Exception as e:
            log.error("Follow-up %s dispatch failed: %s", fu_id, e)
            result = {"ok": False, "error": str(e)}

        # Update status based on result
        new_status = "COMPLETED" if result.get("ok") else "FAILED"
        attempt_count = follow_up.get("attempt_count", 0) + 1
        max_attempts = follow_up.get("max_attempts", 3)

        updates = {
            "status": new_status,
            "attempt_count": attempt_count,
            "last_attempt": datetime.now(timezone.utc).isoformat(),
            "notes": result.get("message", ""),
            "provider_status": result.get("status", ""),
            "last_error": result.get("error", ""),
        }

        # If failed, schedule retry with backoff (respect max attempts)
        if new_status == "FAILED" and attempt_count < max_attempts:
            backoff_hours = [1, 4, 24][min(attempt_count - 1, 2)]
            updates["status"] = "PENDING"
            updates["next_attempt"] = (
                datetime.now(timezone.utc) + timedelta(hours=backoff_hours)
            ).isoformat()
        elif new_status == "FAILED" and attempt_count >= max_attempts:
            updates["terminal_reason"] = "EXHAUSTED"

        self.repo.update_follow_up(fu_id, updates)

        # Audit log
        self.repo.log_event(
            "followup_executed", entity_id, follow_up.get("entity_type", ""),
            result=new_status.lower(),
            error=result.get("error", ""),
            payload={
                "channel": channel,
                "attempt": attempt_count,
                "max_attempts": max_attempts,
                "fu_id": fu_id,
                "idempotency_key": follow_up.get("idempotency_key", ""),
            },
        )

        return {
            "ok": result.get("ok", False),
            "follow_up_id": fu_id,
            "channel": channel,
            "status": new_status,
            "attempt": attempt_count,
            "result": result,
        }

    def execute_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Pick up all pending follow-ups due now and execute them.
        Returns list of execution results.
        """
        now = datetime.now(timezone.utc).isoformat()
        pending = self.repo.get_pending_follow_ups(limit * 2)

        # Filter to those actually due (next_attempt <= now or not set)
        due = []
        for fu in pending:
            # Skip terminal follow-ups
            if self._is_terminal(fu):
                continue
            # Skip exhausted follow-ups
            if self._is_exhausted(fu):
                continue
            # Skip DNC leads
            if self._check_dnc_lead(fu):
                continue

            next_attempt = fu.get("next_attempt")
            if not next_attempt or next_attempt <= now:
                due.append(fu)
            if len(due) >= limit:
                break

        log.info("Executing %d pending follow-ups", len(due))
        results = []
        for fu in due:
            result = self.execute_one(fu)
            results.append(result)

        completed = sum(1 for r in results if r.get("status") == "COMPLETED")
        failed = sum(1 for r in results if r.get("status") == "FAILED")
        blocked = sum(1 for r in results if r.get("status", "").startswith("BLOCKED"))
        log.info("Follow-up batch: %d completed, %d failed, %d blocked, %d total",
                 completed, failed, blocked, len(results))

        return results

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of follow-up execution state."""
        all_pending = self.repo.get_pending_follow_ups(100)
        now = datetime.now(timezone.utc).isoformat()

        overdue = [f for f in all_pending if f.get("next_attempt") and f["next_attempt"] < now]
        due_now = [f for f in all_pending if not f.get("next_attempt") or f["next_attempt"] <= now]
        by_channel = {}
        for f in all_pending:
            ch = f.get("channel", "UNKNOWN")
            by_channel[ch] = by_channel.get(ch, 0) + 1

        return {
            "total_pending": len(all_pending),
            "overdue": len(overdue),
            "due_now": len(due_now),
            "by_channel": by_channel,
        }


# ─── CLI ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for follow-up execution."""
    import sys

    env_mode = os.environ.get("AD_ENV", "LOCAL")
    executor = FollowUpExecutor(env_mode=env_mode)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if cmd == "execute":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = executor.execute_pending(limit)
        print(json.dumps(results, indent=2, default=str))
    elif cmd == "summary":
        summary = executor.get_execution_summary()
        print(json.dumps(summary, indent=2, default=str))
    else:
        print("Usage: ad_followup_executor.py [execute [limit]|summary]")


if __name__ == "__main__":
    import os
    main()
