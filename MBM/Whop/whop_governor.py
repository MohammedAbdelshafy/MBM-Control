"""
whop_governor.py — Automation Governor + Human Override
========================================================
Explicit safety model for every automated commercial action:

  LEVEL 0 = OBSERVE (read-only)
  LEVEL 1 = RECOMMEND (human reads, decides)
  LEVEL 2 = PREPARE (artifact/draft created, nothing sent)
  LEVEL 3 = EXECUTE WITH APPROVAL (queued until a human approves)
  LEVEL 4 = AUTONOMOUS EXECUTION

Default levels are CONSERVATIVE. Sensitive kinds (price changes, payment
changes, mass campaigns, customer deletion, large discounts, production
schema changes) can never run below LEVEL 3.

State: MBM/Whop/data/action_queue.jsonl   (proposed actions + decisions log)
Human overrides: approve | reject | pause | resume | disable — each stores
decision, actor, timestamp, reason (auditable).

CLI:
  python MBM/Whop/whop_governor.py propose <kind> '<payload_json>'
  python MBM/Whop/whop_governor.py queue
  python MBM/Whop/whop_governor.py approve <action_id> --actor me --reason "..."
  python MBM/Whop/whop_governor.py reject  <action_id> --actor me --reason "..."
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = DATA_DIR / "action_queue.jsonl"

LEVELS = {0: "OBSERVE", 1: "RECOMMEND", 2: "PREPARE",
          3: "EXECUTE_WITH_APPROVAL", 4: "AUTONOMOUS"}

# kind -> minimum allowed level (floor). Anything sensitive is floored at L3.
SENSITIVE_FLOOR = {
    "price_change": 3,
    "payment_change": 3,
    "mass_campaign": 3,
    "customer_delete": 4,
    "large_discount": 3,
    "production_schema_change": 4,
}
DEFAULT_FLOOR = {
    "send_email": 2,
    "upsell_flow": 2,
    "winback_flow": 2,
    "recovery_flow": 2,
    "experiment_conclude": 3,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(entry: dict) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, default=str) + "\n")


def _load_all() -> list:
    if not QUEUE_FILE.exists():
        return []
    out = []
    with open(QUEUE_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def level_for(kind: str) -> int:
    floor = SENSITIVE_FLOOR.get(kind, DEFAULT_FLOOR.get(kind, 3))
    return floor


def propose(kind: str, payload: dict, requested_level=None, note="") -> dict:
    """Queue an action at the correct safety level. Never auto-executes."""
    floor = level_for(kind)
    level = int(requested_level) if requested_level is not None else floor
    if level < floor:
        level = floor
        note = f"[level raised to floor] {note}".strip()
    entry = {
        "action_id": f"act_{uuid.uuid4().hex[:12]}",
        "kind": kind,
        "level": level,
        "level_name": LEVELS[level],
        "status": "proposed" if level >= 3 else ("prepared" if level == 2 else "logged"),
        "payload": payload,
        "note": note,
        "proposed_at": _utcnow(),
        "decisions": [],
    }
    _append(entry)
    return entry


def _latest_action(action_id: str) -> dict | None:
    """Return a merged view of the action across all its queue records."""
    merged = None
    for rec in _load_all():
        if rec.get("action_id") != action_id:
            continue
        if merged is None:
            merged = dict(rec)
        merged.update({k: v for k, v in rec.items() if v is not None})
        merged["decisions"] = [*(merged.get("decisions") or []), *rec.get("decisions", [])]
    return merged


def override(action_id: str, decision: str, actor: str, reason: str,
             executed_payload_ref=None) -> dict:
    """approve|reject|pause|resume|disable — appends an auditable decision."""
    assert decision in ("approve", "reject", "pause", "resume", "disable"), \
        f"invalid decision '{decision}'"
    target = _latest_action(action_id)
    record = {
        "action_id": action_id,
        "decision": decision,
        "actor": actor,
        "reason": reason,
        "timestamp": _utcnow(),
        "kind": target.get("kind") if target else None,
        "executed_result": executed_payload_ref,
    }
    _append({"action_id": action_id, "override": record})
    return record


def mark_executed(action_id: str, result: dict) -> dict:
    """Record execution outcome AFTER approval (audit trail)."""
    return override(action_id, "approve", actor="system_executor",
                    reason="approved action executed",
                    executed_payload_ref=result)


def queue_snapshot() -> list:
    """Latest status per action id."""
    latest = {}
    for rec in _load_all():
        aid = rec.get("action_id")
        cur = latest.setdefault(aid, {"decisions": []})
        if "override" in rec and rec["override"]:
            cur["decisions"].append(rec["override"])
            last_dec = rec["override"]["decision"]
            mapping = {"approve": "approved_executable", "reject": "rejected",
                       "pause": "paused", "resume": "proposed", "disable": "disabled"}
            cur["status"] = mapping[last_dec] if last_dec != "approve" else cur.get("status")
        elif "kind" in rec:
            cur.update({k: v for k, v in rec.items() if k != "decisions"})
    return list(latest.values())


def is_execution_approved(action_id: str) -> bool:
    """An action may execute only when its latest human decision is 'approve'
    AND it has not been disabled/paused afterwards."""
    decisions = []
    for rec in _load_all():
        if rec.get("action_id") == action_id and rec.get("override"):
            decisions.append(rec["override"])
    if not any(d["decision"] == "approve" for d in decisions):
        return False
    ordered = sorted(decisions, key=lambda d: d["timestamp"])
    return ordered[-1]["decision"] in ("approve", "resume")


def main(argv):
    parser = argparse.ArgumentParser(description="Whop automation governor")
    sub = parser.add_subparsers(dest="cmd")

    p_propose = sub.add_parser("propose")
    p_propose.add_argument("kind")
    p_propose.add_argument("payload", help="JSON string")
    p_propose.add_argument("--level", type=int, default=None)

    sub.add_parser("queue")

    for name in ("approve", "reject", "pause", "resume", "disable"):
        p = sub.add_parser(name)
        p.add_argument("action_id")
        p.add_argument("--actor", default="human")
        p.add_argument("--reason", default="")

    args = parser.parse_args(argv[1:])
    if args.cmd == "propose":
        print(json.dumps(propose(args.kind, json.loads(args.payload),
                                 requested_level=args.level), indent=2))
    elif args.cmd == "queue":
        print(json.dumps(queue_snapshot(), indent=2))
    elif args.cmd in ("approve", "reject", "pause", "resume", "disable"):
        print(json.dumps(override(args.action_id, args.cmd, args.actor,
                                  args.reason), indent=2))
    else:
        print(json.dumps({"levels": LEVELS,
                          "sensitive_floors": SENSITIVE_FLOOR}))


if __name__ == "__main__":
    main(sys.argv)
