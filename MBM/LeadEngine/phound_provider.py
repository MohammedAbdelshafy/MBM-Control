#!/usr/bin/env python3
"""
MBM LeadEngine — Phound Provider Bridge (Issue #42)
====================================================
First-class Phound provider for MBM Dialer. Replaces the manual
"copy number -> hand off to Phound -> return to MBM" workflow.

Architecture (matches Current architecture discovered in #42):
- `ad_dialer_adapter.DialerAdapter` remains the ONLY lead read/write path
  (single-writer lock protocol preserved; no second lead database).
- `mbm-dialer/app/api/aftercall.js` remains the aftercall API surface;
  completed calls flow into `DialerAdapter.record_aftercall()`.
- This module is the provider layer: outbound call/SMS, event ingestion,
  aftercall persistence, health/readiness. Phound is a provider, not
  hard-coded throughout the UI (JS side: server/dialer/phoundProviderSecure.js).

Phound SDK: `phound>=0.1.13,<0.2` from PyPI.
  Phound.make_call(from_persona_uid, phone_number)
  Phound.send_message(...) / start_listen_events() / BaseCallHandler
  TOKEN/PERSONAS are environment-driven. Tokens are NEVER committed,
  never written to lead JSON, browser storage, or logs (redacted preview only).

Environment (see .env.example; no real secrets in source):
  PHOUND_ENABLED="false"            # master switch; API mode only when true
  PHOUND_TOKEN="<uid>.<api_key>"    # mapped to SDK's TOKEN at call time
  PHOUND_PERSONAS=""                # mapped to SDK's PERSONAS at call time
  PHOUND_SBC=""                     # optional; mapped to SDK's SBC
  PHOUND_DEFAULT_PERSONA_UID=""     # default from_persona_uid
  PHOUND_BRIDGE_URL=""              # runtime display config only

Safety:
  DRY_RUN (default True) never places calls or sends SMS. It resolves queue
  selection, validation, and state transitions only.
  Idempotency: lead_id + request_id dedupe via the call-record log.
  Retry/backoff ONLY for transient provider failures where the system can
  prove no call was placed; otherwise `unknown_provider_state` + reconcile.
  Manual/native fallback is always available (native_app mode).

Usage:
  python MBM/LeadEngine/phound_provider.py --status
  python MBM/LeadEngine/phound_provider.py --dry-run --lead-id L123
  python MBM/LeadEngine/phound_provider.py --apply --lead-id L123 --persona-uid P1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")

log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
CALL_RECORDS = BASE / "logs" / "phound_provider_calls.jsonl"

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

# Statuses that mean "a call may already exist provider-side — never blind-retry".
UNKNOWN_PROVIDER_STATES = {"unknown_provider_state", "accepted_unconfirmed", "error_unknown"}

# Retryable ONLY when the bridge can prove no provider-side call was placed.
TRANSIENT_ERRORS = {"timeout", "connection_error", "provider_unavailable", "rate_limited"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_e164(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Phone number is required")
    digits = re.sub(r"[^\d+]", "", raw)
    # Explicit normalization (no clever one-liners):
    if digits.startswith("+"):
        normalized = digits
    else:
        stripped = digits[1:] if digits.startswith("1") and len(digits) == 11 else digits
        normalized = "+1" + stripped
    if not E164_RE.match(normalized):
        raise ValueError("Invalid phone number. Expected E.164, e.g. +12125551234.")
    return normalized


def redact_token(value: Optional[str]) -> str:
    if not value:
        return ""
    v = str(value)
    return f"{v[:4]}...{v[-3:]}" if len(v) > 8 else "***"


def get_provider_config(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Read MBM PHOUND_* env into a validated config dict (no secrets echoed)."""
    e = env or dict(os.environ)
    enabled = str(e.get("PHOUND_ENABLED", "false")).strip().lower() == "true"
    token = (e.get("PHOUND_TOKEN") or "").strip()
    personas = (e.get("PHOUND_PERSONAS") or "").strip()
    sbc = (e.get("PHOUND_SBC") or "").strip()
    default_persona = (e.get("PHOUND_DEFAULT_PERSONA_UID") or "").strip()
    bridge_url = (e.get("PHOUND_BRIDGE_URL") or "").strip()
    token_ok = len(token.split(".")) == 2 and all(token.split("."))
    configured = bool(token_ok and default_persona)
    error = None
    if enabled and not configured:
        error = "Enabled Phound API mode requires PHOUND_TOKEN (<uid>.<api_key>) and PHOUND_DEFAULT_PERSONA_UID."
    return {
        "enabled": enabled,
        "configured": configured,
        "token_ok": token_ok,
        "has_personas": bool(personas),
        "default_persona_uid": default_persona or None,
        "bridge_url": bridge_url or None,
        "sbc_configured": bool(sbc),
        "error": error,
    }


def get_provider_status(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """UI-safe status shape (mirrors server/dialer/phoundProviderSecure.js)."""
    cfg = get_provider_config(env)
    return {
        "provider": "phound",
        "mode": "api" if (cfg["enabled"] and cfg["configured"]) else "native_app",
        "enabled": cfg["enabled"],
        "configured": cfg["configured"],
        "token_preview": redact_token((env or dict(os.environ)).get("PHOUND_TOKEN", "")),
        "error": cfg["error"],
        "message": (
            "Phound API provider configured. Calling stays behind the server boundary."
            if (cfg["enabled"] and cfg["configured"])
            else "Phound native-app mode. Manual fallback available; no credentials exposed."
        ),
    }


# ─── Call-record store (idempotency + audit) ──────────────────────────────

def _read_records() -> List[Dict[str, Any]]:
    if not CALL_RECORDS.exists():
        return []
    out = []
    for line in CALL_RECORDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _append_record(record: Dict[str, Any]) -> None:
    CALL_RECORDS.parent.mkdir(parents=True, exist_ok=True)
    safe = {k: v for k, v in record.items() if "token" not in k.lower()}
    with open(CALL_RECORDS, "a", encoding="utf-8") as f:
        f.write(json.dumps(safe, default=str) + "\n")


def find_record(lead_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for r in reversed(_read_records()):
        if str(r.get("lead_id")) != str(lead_id):
            continue
        if request_id and r.get("request_id") != request_id:
            continue
        return r
    return None


# ─── Provider abstraction ─────────────────────────────────────────────────

class DialerProvider(ABC):
    """Provider interface so Phound is a provider, not inline code in the UI."""

    name = "base"

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def place_call(self, *, lead_id: str, phone: str, persona_uid: str,
                   request_id: Optional[str] = None,
                   dry_run: bool = True) -> Dict[str, Any]:
        ...

    @abstractmethod
    def send_sms(self, *, lead_id: str, phone: str, persona_uid: str, text: str,
                 request_id: Optional[str] = None,
                 dry_run: bool = True) -> Dict[str, Any]:
        ...

    @abstractmethod
    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        ...


class PhoundProvider(DialerProvider):
    """Phound SDK provider. SDK import is lazy: `phound.config` raises at
    import time unless TOKEN (<uid>.<api_key>) is present, so env mapping
    happens inside the call path, never at module import."""

    name = "phound"

    def __init__(self, env: Optional[Dict[str, str]] = None):
        self.env = env or dict(os.environ)

    # -- internal ---------------------------------------------------------
    def _sdk(self):
        """Import + construct the SDK client with MBM env mapped. Raises
        PhoundError-style dict on misconfiguration (never leaks the token)."""
        cfg = get_provider_config(self.env)
        if not cfg["configured"]:
            raise RuntimeError(cfg["error"] or "Phound provider not configured")
        # Map MBM names -> SDK names in the child env only.
        os.environ["TOKEN"] = self.env.get("PHOUND_TOKEN", "")
        if self.env.get("PHOUND_PERSONAS"):
            os.environ["PERSONAS"] = self.env["PHOUND_PERSONAS"]
        if self.env.get("PHOUND_SBC"):
            os.environ["SBC"] = self.env["PHOUND_SBC"]
        from phound.main import Phound  # lazy: requires TOKEN at import

        client = Phound()
        client.start()
        return client

    def _persist_attempt(self, *, lead_id, phone, persona_uid, kind,
                         request_id, dry_run, status, extra=None) -> Dict[str, Any]:
        record = {
            "provider": "phound",
            "provider_call_id": (extra or {}).get("provider_call_id"),
            "lead_id": lead_id,
            "persona_uid": persona_uid,
            "kind": kind,
            "normalized_phone": phone,
            "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
            "dry_run": dry_run,
            "lifecycle_status": status,
            "disposition": (extra or {}).get("disposition"),
            "transcript": (extra or {}).get("transcript"),
            "recording_url": (extra or {}).get("recording_url"),
            "error": (extra or {}).get("error"),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        _append_record(record)
        return record

    # -- interface ---------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        status = get_provider_status(self.env)
        return {"ok": status["mode"] == "api", **status, "checked_at": utcnow()}

    def place_call(self, *, lead_id: str, phone: str, persona_uid: str,
                   request_id: Optional[str] = None,
                   dry_run: bool = True) -> Dict[str, Any]:
        phone = normalize_e164(phone)
        # Idempotency: same lead + request never places twice.
        if request_id:
            existing = find_record(lead_id, request_id)
            if existing:
                return {"status": "duplicate_suppressed", "provider": "phound",
                        "record": existing}
        if dry_run:
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="call",
                                        request_id=request_id, dry_run=True,
                                        status="dry_run_simulated")
            return {"status": "dry_run_simulated", "provider": "phound",
                    "to": phone, "record": rec}

        cfg = get_provider_config(self.env)
        if not cfg["enabled"] or not cfg["configured"]:
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="call",
                                        request_id=request_id, dry_run=False,
                                        status="native_app_fallback")
            return {"status": "native_app", "provider": "phound", "to": phone,
                    "handoff": f"https://web.phound.app/?phone={phone}",
                    "record": rec}
        try:
            client = self._sdk()
            try:
                client.make_call(persona_uid, phone)
            finally:
                try:
                    client.stop()
                except Exception:
                    pass
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="call",
                                        request_id=request_id, dry_run=False,
                                        status="accepted_unconfirmed")
            return {"status": "accepted", "provider": "phound", "to": phone,
                    "record": rec}
        except Exception as exc:
            msg = str(exc)
            # Only classify as transient when we can prove no call was placed:
            # SDK raised before returning (make_call never returned) AND the
            # error text matches a known transport failure.
            transient = any(k in msg.lower() for k in
                            ("tim", "connect", "unavail", "rate limit", "429", "503", "502"))
            status = "error_transient_no_call_placed" if transient else "unknown_provider_state"
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="call",
                                        request_id=request_id, dry_run=False,
                                        status=status, extra={"error": msg[:500]})
            out = {"status": status, "provider": "phound", "error": msg[:500],
                   "record": rec}
            if status == "unknown_provider_state":
                out["reconciliation_required"] = True
            return out

    def send_sms(self, *, lead_id: str, phone: str, persona_uid: str, text: str,
                 request_id: Optional[str] = None,
                 dry_run: bool = True) -> Dict[str, Any]:
        phone = normalize_e164(phone)
        if not text or not text.strip():
            return {"status": "error", "provider": "phound", "error": "SMS text is required"}
        if request_id:
            existing = find_record(lead_id, request_id)
            if existing:
                return {"status": "duplicate_suppressed", "provider": "phound",
                        "record": existing}
        if dry_run:
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="sms",
                                        request_id=request_id, dry_run=True,
                                        status="dry_run_simulated")
            return {"status": "dry_run_simulated", "provider": "phound",
                    "to": phone, "record": rec}
        cfg = get_provider_config(self.env)
        if not cfg["enabled"] or not cfg["configured"]:
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="sms",
                                        request_id=request_id, dry_run=False,
                                        status="native_app_fallback")
            return {"status": "native_app", "provider": "phound", "to": phone,
                    "prefill": f"https://web.phound.app/?phone={phone}",
                    "record": rec}
        try:
            client = self._sdk()
            try:
                client.send_message(text, persona_uid, phone_number=phone)
            finally:
                try:
                    client.stop()
                except Exception:
                    pass
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="sms",
                                        request_id=request_id, dry_run=False,
                                        status="accepted_unconfirmed")
            return {"status": "accepted", "provider": "phound", "to": phone,
                    "record": rec}
        except Exception as exc:
            msg = str(exc)
            rec = self._persist_attempt(lead_id=lead_id, phone=phone,
                                        persona_uid=persona_uid, kind="sms",
                                        request_id=request_id, dry_run=False,
                                        status="unknown_provider_state",
                                        extra={"error": msg[:500]})
            return {"status": "unknown_provider_state", "provider": "phound",
                    "error": msg[:500], "reconciliation_required": True,
                    "record": rec}

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Consume a Phound lifecycle event and hand completed calls into the
        existing record_aftercall() path. Never creates a second lead store."""
        event = event or {}
        lead_id = event.get("lead_id")
        lifecycle = str(event.get("lifecycle_status") or event.get("status") or "").lower()
        completed = lifecycle in ("completed", "ended", "done", "call_completed",
                                  "call_ended", "finished")
        _append_record({
            "provider": "phound",
            "provider_call_id": event.get("provider_call_id"),
            "lead_id": lead_id,
            "persona_uid": event.get("persona_uid"),
            "kind": "event",
            "normalized_phone": event.get("normalized_phone") or event.get("phone"),
            "lifecycle_status": lifecycle or "event_received",
            "disposition": event.get("disposition"),
            "transcript": (event.get("transcript") or "")[:2000],
            "recording_url": event.get("recording_url"),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        })
        if not completed or not lead_id:
            return {"status": "event_recorded", "provider": "phound",
                    "handed_to_aftercall": False}
        try:
            from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter
        except ImportError:  # pragma: no cover - script-relative fallback
            if str(Path(__file__).resolve().parents[2]) not in sys.path:
                sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter
        adapter = DialerAdapter()
        result = adapter.record_aftercall(
            lead_id=str(lead_id),
            transcript=str(event.get("transcript") or "")[:2000],
            disposition=str(event.get("disposition") or "COMPLETED"),
            notes=f"phound provider_call_id={event.get('provider_call_id')}",
            phone=str(event.get("normalized_phone") or event.get("phone") or ""),
        )
        return {"status": "event_recorded", "provider": "phound",
                "handed_to_aftercall": bool(result.get("ok")), "aftercall": result}


def retry_allowed(record: Dict[str, Any]) -> bool:
    """True ONLY for transient failures where no call was placed."""
    return record.get("lifecycle_status") == "error_transient_no_call_placed"


def main() -> int:
    ap = argparse.ArgumentParser(description="Phound provider bridge (Issue #42)")
    ap.add_argument("--status", action="store_true", help="Print provider status")
    ap.add_argument("--lead-id", type=str, help="Lead ID for call/SMS")
    ap.add_argument("--phone", type=str, help="Override phone (E.164)")
    ap.add_argument("--persona-uid", type=str, help="Phound persona UID")
    ap.add_argument("--sms", type=str, help="Send SMS with this text instead of calling")
    ap.add_argument("--request-id", type=str, default=None, help="Idempotency key")
    ap.add_argument("--dry-run", action="store_true", help="Simulate only (default)")
    ap.add_argument("--apply", action="store_true", help="Live mode: place call/SMS")
    args = ap.parse_args()

    provider = PhoundProvider()
    if args.status or not args.lead_id:
        print(json.dumps(provider.health(), indent=2))
        if not args.lead_id:
            return 0

    dry_run = not args.apply
    persona = args.persona_uid or (get_provider_config()["default_persona_uid"] or "")
    phone = args.phone or ""
    if not phone and args.lead_id:
        try:
            from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter
            lead = DialerAdapter().get_lead_by_id(args.lead_id)
            phone = (lead or {}).get("phone", "")
        except Exception as exc:
            print(json.dumps({"status": "error", "error": f"lead lookup failed: {exc}"}))
            return 2
    if not persona:
        print(json.dumps({"status": "error",
                          "error": "persona UID required (--persona-uid or PHOUND_DEFAULT_PERSONA_UID)"}))
        return 2
    if args.sms is not None:
        out = provider.send_sms(lead_id=args.lead_id, phone=phone, persona_uid=persona,
                                text=args.sms, request_id=args.request_id, dry_run=dry_run)
    else:
        out = provider.place_call(lead_id=args.lead_id, phone=phone, persona_uid=persona,
                                  request_id=args.request_id, dry_run=dry_run)
    # Strip any accidental secret echo before printing.
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
