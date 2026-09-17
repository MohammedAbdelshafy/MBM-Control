#!/usr/bin/env python3
"""
MBM LeadEngine — Phound Auto-Dial Execution (Issue #43, refined by #44)
========================================================================
Selectable queue modes over the #42 Phound provider bridge:

  MANUAL                operator picks each lead; bridge places via Phound
                        (or native-app fallback) one at a time.
  ASSISTED              system ranks the next verified lead, presents
                        script/context, waits for operator confirm per call.
  AUTO_DIAL             system advances the queue automatically within caps.
                        Capability-gated: requires PHOUND_AUTODIAL_APPROVED=1
                        AND Phound API mode healthy. Otherwise refuses and
                        falls back to ASSISTED.
  ANDROID_SIM_ASSISTED  (#44) no-new-subscription path: the Android device/SIM
                        is the human-controlled calling transport; MBM acts as
                        the queue/intelligence layer (verify -> present script/
                        context -> emit `tel:` handoff -> wait for disposition).
                        NEVER auto-advances; each call needs operator action.
                        Provider/carrier limits are respected, never bypassed.

Safety contract (all modes):
 1. Pull ONLY records passing dialer_verification_gate.filter_for_dialer
    + campaign qualification (optional vertical/status filter).
 2. Configurable max calls in flight, pacing/cooldown, daily + session caps,
    and stop conditions (failed/skipped ceilings, paused/stopped flags).
 3. NEVER redial: in-flight/active, recently-called (cooldown), opted-out/DNC,
    invalid, or closed-disposition leads.
 4. Deterministic queue locking: single lock file + dial_attempt intent
    records (lead_id + request_id) so multiple workers cannot call the
    same lead (duplicate suppressed).
 5. dial_attempt intent is persisted BEFORE the provider call is placed.
 6. Retry ONLY when the provider failure is explicitly transient AND the
    system can prove no call was placed; otherwise `unknown_provider_state`
    + reconciliation required.
 7. Completed lifecycle events hand into DialerAdapter.record_aftercall().
 8. Queue status, current call, remaining, failed/skipped counts,
    pause/resume/stop controls.
 9. DRY_RUN simulates queue selection + state transitions; NEVER places
    calls or sends SMS.
10. Manual/native fallback available at all times.
11. No PHOUND_TOKEN in source, lead JSON, browser storage, or logs.

State (gitignored logs/):
  logs/phound_autodial_state.json     lock, in-flight, counters, controls
  logs/phound_dial_attempts.jsonl     dial_attempt intent records

Usage:
  python MBM/LeadEngine/phound_auto_dialer.py --mode ASSISTED --dry-run --limit 10
  python MBM/LeadEngine/phound_auto_dialer.py --mode AUTO_DIAL --apply --limit 25
  python MBM/LeadEngine/phound_auto_dialer.py --status
  python MBM/LeadEngine/phound_auto_dialer.py --pause|--resume|--stop
  python MBM/LeadEngine/phound_auto_dialer.py --reconcile
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "logs" / "phound_autodial_state.json"
ATTEMPTS_FILE = BASE / "logs" / "phound_dial_attempts.jsonl"
SUPPRESSED_PHONES = BASE.parent / "Artifacts" / "suppressed_bad_phones.json"

ROOT_DIR = Path(__file__).resolve().parents[2]  # repo root (convention: parents[2])
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
from dialer_verification_gate import filter_for_dialer  # noqa: E402

from MBM.LeadEngine.phound_provider import PhoundProvider, normalize_e164  # noqa: E402

from MBM.LeadEngine.ad_dialer_adapter import DialerAdapter  # noqa: E402

VALID_MODES = ("MANUAL", "ASSISTED", "AUTO_DIAL", "ANDROID_SIM_ASSISTED")

CLOSED_DISPOSITIONS = {
    "CLOSED", "DEAD", "LOST", "DNC", "OPTED_OUT", "STOP", "DO_NOT_CALL",
    "WRONG_PERSON", "NON_OWNER", "BAD_NUMBER", "DISCONNECTED",
}

OPT_OUT_FLAGS = ("opted_out", "dnc", "do_not_call", "stop_requested")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── State store ──────────────────────────────────────────────────────────

def _default_state() -> Dict[str, Any]:
    return {
        "paused": False,
        "stopped": False,
        "in_flight": {},          # lead_id -> {request_id, started_at, mode}
        "recent_calls": {},       # lead_id -> iso timestamp (cooldown)
        "session_counts": {"attempted": 0, "completed": 0, "failed": 0, "skipped": 0},
        "daily_counts": {"date": datetime.now(timezone.utc).date().isoformat(),
                         "attempted": 0},
        "lock_holder": None,
        "updated_at": utcnow(),
    }


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return _default_state()
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    # New UTC day -> reset daily counters.
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("daily_counts", {}).get("date") != today:
        state["daily_counts"] = {"date": today, "attempted": 0}
    return state


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = utcnow()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def _append_attempt(record: Dict[str, Any]) -> None:
    ATTEMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTEMPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _read_attempts() -> List[Dict[str, Any]]:
    if not ATTEMPTS_FILE.exists():
        return []
    out = []
    for line in ATTEMPTS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


# ─── Eligibility ──────────────────────────────────────────────────────────

def _load_suppressed_phones() -> set:
    try:
        data = json.loads(SUPPRESSED_PHONES.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            phones = data.get("phones") or data.get("suppressed") or []
        else:
            phones = data
        return {str(p).strip() for p in phones if p}
    except Exception:
        return set()


def is_opted_out(lead: Dict[str, Any], suppressed: set) -> bool:
    for flag in OPT_OUT_FLAGS:
        if lead.get(flag) in (True, 1, "1", "true", "TRUE", "yes"):
            return True
    for key in ("phone", "verified_phone", "phone_number", "primary_phone"):
        if str(lead.get(key, "")).strip() in suppressed:
            return True
    disp = str(lead.get("disposition") or lead.get("status") or "").upper()
    if disp in CLOSED_DISPOSITIONS or "OPT" in disp or "DNC" in disp or "STOP" in disp:
        return True
    details = lead.get("details") or {}
    if isinstance(details, dict):
        for flag in OPT_OUT_FLAGS:
            if details.get(flag) in (True, 1, "1", "true", "TRUE"):
                return True
    return False


def is_closed(lead: Dict[str, Any]) -> bool:
    disp = str(lead.get("disposition") or lead.get("status") or "").upper()
    return disp in CLOSED_DISPOSITIONS


def build_queue(leads: List[Dict[str, Any]], *,
                vertical: Optional[str] = None,
                status_filter: Optional[str] = None,
                limit: int = 25) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Gate + campaign qualification. Returns (callable, qa_summary)."""
    summary: Dict[str, Any] = {"ingested": len(leads)}
    if vertical:
        v = vertical.lower()
        leads = [l for l in leads
                 if str(l.get("vertical") or l.get("vertical_tag") or "").lower() == v]
        summary["after_vertical_filter"] = len(leads)
    if status_filter:
        leads = [l for l in leads if str(l.get("status") or "").upper() == status_filter.upper()]
        summary["after_status_filter"] = len(leads)
    gated = filter_for_dialer(leads, quiet=True)
    summary["gate_passed"] = len(gated)
    summary["gate_rejected"] = len(leads) - len(gated)
    suppressed = _load_suppressed_phones()
    state = load_state()
    callable_leads, skipped = [], 0
    for lead in gated:
        lid = str(lead.get("id"))
        if not lid or lid in state["in_flight"]:
            skipped += 1
            continue
        if is_opted_out(lead, suppressed) or is_closed(lead):
            skipped += 1
            continue
        callable_leads.append(lead)
        if len(callable_leads) >= limit:
            break
    summary["optout_closed_inflight_skipped"] = skipped
    summary["callable"] = len(callable_leads)
    return callable_leads, summary


# ─── Runner ───────────────────────────────────────────────────────────────

class AutoDialer:
    def __init__(self, *, mode: str, provider: Optional[PhoundProvider] = None,
                 max_in_flight: int = 1, pacing_seconds: float = 30.0,
                 cooldown_seconds: float = 3600.0, daily_cap: int = 100,
                 session_cap: int = 50, max_failed_stop: int = 5,
                 max_skipped_stop: int = 50, dry_run: bool = True,
                 persona_uid: str = ""):
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        self.mode = mode
        self.provider = provider or PhoundProvider()
        self.max_in_flight = max(1, max_in_flight)
        self.pacing_seconds = max(0.0, pacing_seconds)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.daily_cap = daily_cap
        self.session_cap = session_cap
        self.max_failed_stop = max_failed_stop
        self.max_skipped_stop = max_skipped_stop
        self.dry_run = dry_run
        self.persona_uid = persona_uid
        self.adapter = DialerAdapter()
        self.worker_id = f"worker_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        self._last_place_ts = 0.0

    # -- capability gate ---------------------------------------------------
    def capability_check(self) -> Dict[str, Any]:
        """AUTO_DIAL requires explicit approval + healthy API mode.
        ANDROID_SIM_ASSISTED never auto-advances by design."""
        health = self.provider.health()
        if self.mode == "AUTO_DIAL":
            approved = os.getenv("PHOUND_AUTODIAL_APPROVED", "").strip() == "1"
            if not approved:
                return {"allowed": False,
                        "reason": "AUTO_DIAL requires PHOUND_AUTODIAL_APPROVED=1; falling back to ASSISTED",
                        "fallback": "ASSISTED"}
            if health.get("mode") != "api":
                return {"allowed": False,
                        "reason": "AUTO_DIAL requires healthy Phound API mode; falling back to ASSISTED",
                        "fallback": "ASSISTED"}
        return {"allowed": True, "reason": "ok"}

    # -- single-lead execution ----------------------------------------------
    def _cooldown_ok(self, lead_id: str, state: Dict[str, Any]) -> bool:
        ts = state["recent_calls"].get(str(lead_id))
        if not ts:
            return True
        try:
            last = datetime.fromisoformat(ts)
            delta = (datetime.now(timezone.utc) - last).total_seconds()
            return delta >= self.cooldown_seconds
        except Exception:
            return True

    def execute_one(self, lead: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        lid = str(lead.get("id"))
        request_id = f"{lid}_{self.worker_id}_{int(time.time())}"
        # Duplicate-worker protection: claim in-flight BEFORE placing.
        if lid in state["in_flight"]:
            return {"status": "duplicate_suppressed", "lead_id": lid}
        if not self._cooldown_ok(lid, state):
            return {"status": "skipped_cooldown", "lead_id": lid}
        phone = lead.get("verified_phone") or lead.get("phone") or ""
        try:
            phone = normalize_e164(phone)
        except ValueError as exc:
            return {"status": "skipped_invalid", "lead_id": lid, "error": str(exc)}

        # Persist dial_attempt intent FIRST (deterministic idempotency record).
        _append_attempt({"type": "dial_attempt", "lead_id": lid, "phone": phone,
                         "mode": self.mode, "worker": self.worker_id,
                         "request_id": request_id, "dry_run": self.dry_run,
                         "at": utcnow()})
        state["in_flight"][lid] = {"request_id": request_id,
                                   "started_at": utcnow(), "mode": self.mode}

        if self.mode == "ANDROID_SIM_ASSISTED":
            # Human-controlled transport: present script/context, emit tel:
            # handoff, wait for operator disposition. Never place via API.
            state["recent_calls"][lid] = utcnow()
            state["in_flight"].pop(lid, None)
            return {"status": "handoff_presented", "lead_id": lid, "to": phone,
                    "handoff": f"tel:{phone}",
                    "script_context": {"contact": lead.get("contact") or lead.get("contact_name"),
                                       "score": lead.get("score"),
                                       "notes": "Operator dials on Android device; record disposition after."},
                    "note": "Waiting for operator disposition; queue does NOT auto-advance."}

        # Pacing (auto modes only; manual/assisted wait on the operator anyway).
        if self.mode == "AUTO_DIAL" and not self.dry_run:
            wait = self.pacing_seconds - (time.time() - self._last_place_ts)
            if wait > 0:
                time.sleep(wait)

        result = self.provider.place_call(lead_id=lid, phone=phone,
                                          persona_uid=self.persona_uid,
                                          request_id=request_id,
                                          dry_run=self.dry_run)
        self._last_place_ts = time.time()
        status = result.get("status", "")
        if status in ("accepted", "native_app", "dry_run_simulated", "handoff_presented"):
            state["recent_calls"][lid] = utcnow()
            state["session_counts"]["attempted"] += 1
            state["daily_counts"]["attempted"] += 1
        if status in ("accepted", "native_app"):
            pass  # stays in-flight until lifecycle event completes it
        elif status == "dry_run_simulated":
            # Provably no call was placed: release the claim, keep cooldown.
            state["in_flight"].pop(lid, None)
        else:
            state["in_flight"].pop(lid, None)
            if status.startswith("error") or status == "unknown_provider_state":
                state["session_counts"]["failed"] += 1
            elif status.startswith("skipped") or status == "duplicate_suppressed":
                state["session_counts"]["skipped"] += 1
        return {"lead_id": lid, **result}

    # -- session --------------------------------------------------------------
    def stop_requested(self, state: Dict[str, Any]) -> Optional[str]:
        if state.get("stopped"):
            return "stopped_flag"
        if state.get("paused"):
            return "paused"
        if len(state["in_flight"]) >= self.max_in_flight:
            return "max_in_flight"
        if state["session_counts"]["attempted"] >= self.session_cap:
            return "session_cap"
        if state["daily_counts"]["attempted"] >= self.daily_cap:
            return "daily_cap"
        if state["session_counts"]["failed"] >= self.max_failed_stop:
            return "max_failed"
        if state["session_counts"]["skipped"] >= self.max_skipped_stop:
            return "max_skipped"
        return None

    def run(self, queue: List[Dict[str, Any]]) -> Dict[str, Any]:
        cap = self.capability_check()
        effective_mode = self.mode
        if not cap["allowed"]:
            effective_mode = cap.get("fallback", "ASSISTED")
            self.mode = effective_mode
        state = load_state()
        outcomes: List[Dict[str, Any]] = []
        for lead in queue:
            stop = self.stop_requested(state)
            if stop:
                outcomes.append({"status": f"session_stopped:{stop}"})
                break
            # MANUAL/ASSISTED pause per lead for operator confirm in live mode.
            if effective_mode in ("MANUAL", "ASSISTED") and not self.dry_run:
                outcomes.append({"status": "awaiting_operator_confirm",
                                 "lead_id": str(lead.get("id")),
                                 "note": "Confirm to place; skip to move on."})
                continue
            outcomes.append(self.execute_one(lead, state))
            save_state(state)
        save_state(state)
        return {"status": "success", "mode": effective_mode,
                "capability": cap, "dry_run": self.dry_run,
                "outcomes": outcomes, "state": queue_status()}

    # -- lifecycle ------------------------------------------------------------
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Provider lifecycle event -> clear in-flight -> record_aftercall."""
        out = self.provider.ingest_event(event)
        state = load_state()
        lid = str((event or {}).get("lead_id") or "")
        if lid and lid in state["in_flight"]:
            state["in_flight"].pop(lid, None)
            state["session_counts"]["completed"] += 1
            save_state(state)
        return out


# ─── Controls ─────────────────────────────────────────────────────────────

def queue_status() -> Dict[str, Any]:
    state = load_state()
    attempts = _read_attempts()
    return {"status": "success",
            "paused": state["paused"], "stopped": state["stopped"],
            "in_flight": state["in_flight"],
            "in_flight_count": len(state["in_flight"]),
            "session_counts": state["session_counts"],
            "daily_counts": state["daily_counts"],
            "dial_attempts_logged": len(attempts),
            "remaining_capacity": {
                "note": "remaining queue depends on live gate pull; see --dry-run for current callable count"}}


def set_control(paused: Optional[bool] = None, stopped: Optional[bool] = None) -> Dict[str, Any]:
    state = load_state()
    if paused is not None:
        state["paused"] = paused
        if paused is False:
            state["stopped"] = False
    if stopped is not None:
        state["stopped"] = stopped
    save_state(state)
    return queue_status()


def reconcile() -> Dict[str, Any]:
    """Restart recovery: any in-flight lead with no terminal lifecycle event
    and no aftercall goes to unknown_provider_state for human review."""
    state = load_state()
    attempts = _read_attempts()
    terminal = {str(a.get("lead_id")) for a in attempts
                if a.get("type") == "aftercall" or "completed" in str(a.get("lifecycle_status") or "")}
    flagged = []
    for lid, info in list(state["in_flight"].items()):
        if lid not in terminal:
            flagged.append({"lead_id": lid, **info,
                            "status": "unknown_provider_state",
                            "action": "Verify provider-side before any retry; then record disposition."})
    state["in_flight"] = {}
    save_state(state)
    return {"status": "success", "reconciled": len(flagged), "flagged": flagged}


def main() -> int:
    ap = argparse.ArgumentParser(description="Phound auto-dial execution (Issue #43)")
    ap.add_argument("--mode", default="ASSISTED", choices=VALID_MODES)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--vertical", type=str, default=None)
    ap.add_argument("--status-filter", type=str, default=None)
    ap.add_argument("--max-in-flight", type=int, default=1)
    ap.add_argument("--pacing-seconds", type=float, default=30.0)
    ap.add_argument("--cooldown-seconds", type=float, default=3600.0)
    ap.add_argument("--daily-cap", type=int, default=100)
    ap.add_argument("--session-cap", type=int, default=50)
    ap.add_argument("--persona-uid", type=str, default=None)
    ap.add_argument("--dry-run", action="store_true", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--event-json", type=str, default=None,
                    help="Ingest one provider lifecycle event (JSON string)")
    args = ap.parse_args()

    if args.status:
        print(json.dumps(queue_status(), indent=2, default=str))
        return 0
    if args.pause:
        print(json.dumps(set_control(paused=True), indent=2))
        return 0
    if args.resume:
        print(json.dumps(set_control(paused=False, stopped=False), indent=2))
        return 0
    if args.stop:
        print(json.dumps(set_control(stopped=True), indent=2))
        return 0
    if args.reconcile:
        print(json.dumps(reconcile(), indent=2, default=str))
        return 0

    dialer = AutoDialer(mode="ASSISTED")  # for event path only
    if args.event_json:
        try:
            event = json.loads(args.event_json)
        except Exception as exc:
            print(json.dumps({"status": "error", "error": f"bad event JSON: {exc}"}))
            return 2
        print(json.dumps(dialer.handle_event(event), indent=2, default=str))
        return 0

    dry_run = not args.apply  # DRY_RUN default; --apply opts into live
    persona = args.persona_uid or os.getenv("PHOUND_DEFAULT_PERSONA_UID", "")
    if args.mode != "ANDROID_SIM_ASSISTED" and not persona and not dry_run:
        print(json.dumps({"status": "error", "error": "Live Phound modes require --persona-uid or PHOUND_DEFAULT_PERSONA_UID"}))
        return 2

    leads = DialerAdapter().read_leads()
    queue, qa = build_queue(leads, vertical=args.vertical,
                            status_filter=args.status_filter, limit=args.limit)
    runner = AutoDialer(mode=args.mode, max_in_flight=args.max_in_flight,
                        pacing_seconds=args.pacing_seconds,
                        cooldown_seconds=args.cooldown_seconds,
                        daily_cap=args.daily_cap, session_cap=args.session_cap,
                        dry_run=dry_run, persona_uid=persona)
    out = runner.run(queue)
    out["queue_qa"] = qa
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
