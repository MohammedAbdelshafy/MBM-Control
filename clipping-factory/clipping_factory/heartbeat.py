"""
Heartbeat — tracks factory runtime state.
Every scheduler run writes a heartbeat. Dead-man detection checks it.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


HEARTBEAT_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / "heartbeat.json"
LOCK_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / ".factory_lock"


def _ensure_dirs():
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)


def write_heartbeat(
    status: str = "running",
    campaigns_found: int = 0,
    clips_produced: int = 0,
    clips_rejected: int = 0,
    clips_queued: int = 0,
    clips_published: int = 0,
    publish_failures: int = 0,
    next_run: str = "",
    duration_sec: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write heartbeat file with current factory state."""
    _ensure_dirs()
    now = datetime.now(timezone.utc).isoformat()

    data: Dict[str, Any] = {
        "last_started": now,
        "status": status,
        "duration_sec": round(duration_sec, 1),
        "campaigns_found": campaigns_found,
        "clips_produced": clips_produced,
        "clips_rejected": clips_rejected,
        "clips_queued": clips_queued,
        "clips_published": clips_published,
        "publish_failures": publish_failures,
        "next_run": next_run,
        "updated_at": now,
    }

    if extra:
        data.update(extra)

    # Preserve last_completed if present
    if HEARTBEAT_FILE.exists():
        try:
            old = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
            if old.get("last_completed"):
                data["last_completed"] = old["last_completed"]
        except Exception:
            pass

    # Read existing to get last_started from previous run
    if HEARTBEAT_FILE.exists():
        try:
            old = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
            if old.get("last_started") and status != "running":
                data["last_started"] = old["last_started"]
        except Exception:
            pass

    HEARTBEAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def complete_heartbeat(
    status: str = "success",
    campaigns_found: int = 0,
    clips_produced: int = 0,
    clips_rejected: int = 0,
    clips_queued: int = 0,
    clips_published: int = 0,
    publish_failures: int = 0,
    next_run: str = "",
    duration_sec: float = 0.0,
) -> None:
    """Mark heartbeat as completed."""
    _ensure_dirs()
    now = datetime.now(timezone.utc).isoformat()

    data: Dict[str, Any] = {}
    if HEARTBEAT_FILE.exists():
        try:
            data = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    data.update({
        "status": status,
        "last_completed": now,
        "updated_at": now,
        "duration_sec": round(duration_sec, 1),
        "campaigns_found": campaigns_found,
        "clips_produced": clips_produced,
        "clips_rejected": clips_rejected,
        "clips_queued": clips_queued,
        "clips_published": clips_published,
        "publish_failures": publish_failures,
        "next_run": next_run,
    })

    HEARTBEAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_heartbeat() -> Dict[str, Any]:
    """Read current heartbeat state."""
    if not HEARTBEAT_FILE.exists():
        return {"status": "no_heartbeat", "last_completed": None}
    try:
        return json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "corrupt", "last_completed": None}


def check_dead_man(timeout_minutes: int = 360) -> Dict[str, Any]:
    """
    Dead-man detection: is the factory still alive?
    Returns health status with GREEN/YELLOW/RED.
    """
    hb = read_heartbeat()
    now = time.time()

    result = {
        "healthy": True,
        "color": "GREEN",
        "reason": "",
        "heartbeat": hb,
    }

    status = hb.get("status", "unknown")
    last_completed = hb.get("last_completed")
    last_started = hb.get("last_started")

    if status == "no_heartbeat":
        result["healthy"] = False
        result["color"] = "RED"
        result["reason"] = "No heartbeat file found — factory has never run"
        return result

    if status == "failed":
        result["healthy"] = False
        result["color"] = "RED"
        result["reason"] = f"Last run failed: {hb.get('error_message', 'unknown')}"
        return result

    if status == "running":
        result["color"] = "YELLOW"
        result["reason"] = "Factory is currently running"
        return result

    # Check how long since last completed
    if last_completed:
        try:
            from datetime import datetime as dt
            last_dt = dt.fromisoformat(last_completed.replace("Z", "+00:00"))
            elapsed_min = (now - last_dt.timestamp()) / 60

            if elapsed_min > timeout_minutes:
                result["healthy"] = False
                result["color"] = "RED"
                result["reason"] = f"No completed run in {elapsed_min:.0f}min (threshold: {timeout_minutes}min)"
            elif elapsed_min > timeout_minutes * 0.7:
                result["color"] = "YELLOW"
                result["reason"] = f"Last completed {elapsed_min:.0f}min ago (approaching threshold)"
            else:
                result["reason"] = f"Last completed {elapsed_min:.0f}min ago"
        except Exception:
            result["color"] = "YELLOW"
            result["reason"] = "Could not parse last_completed timestamp"

    return result


# ── Overlap Protection (file-based lock) ──

def acquire_run_lock(timeout_sec: int = 7200) -> bool:
    """
    Try to acquire the factory run lock.
    Returns True if lock acquired (safe to run).
    Returns False if another run is already active.
    """
    _ensure_dirs()

    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            lock_time = lock_data.get("acquired_at", "")
            if lock_time:
                from datetime import datetime as dt
                lock_dt = dt.fromisoformat(lock_time.replace("Z", "+00:00"))
                elapsed = time.time() - lock_dt.timestamp()
                if elapsed < timeout_sec:
                    return False  # Another run is still active
                # Lock expired — stale lock, proceed
        except Exception:
            pass  # Corrupt lock file, proceed

    lock_data = {
        "pid": os.getpid(),
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "machine": os.environ.get("COMPUTERNAME", "unknown"),
    }
    LOCK_FILE.write_text(json.dumps(lock_data), encoding="utf-8")
    return True


def release_run_lock() -> None:
    """Release the factory run lock."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass
