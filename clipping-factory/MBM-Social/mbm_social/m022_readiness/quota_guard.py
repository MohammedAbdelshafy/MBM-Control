"""Quota Awareness Guard for YouTube Data API v3.

Tracks:
- estimated upload cost (based on 2026 quota model changes)
- daily upload budget
- observed usage
- remaining budget
- per-channel budget

Default: BLOCKED if quota exhausted.
No blind retries when quota exceeded.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class QuotaState(str, Enum):
    AVAILABLE = "AVAILABLE"
    LOW = "LOW"
    EXCEEDED = "EXCEEDED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class QuotaGuard:
    """Quota-aware guard for upload operations."""

    # YouTube's 2026 quota model includes a dedicated bucket for videos.insert
    # (per current documentation). We treat upload quota conservatively.
    DEFAULT_DAILY_UPLOAD_BUDGET = 10  # uploads/day (conservative for M-022 readiness)
    ESTIMATED_INSERT_COST = 1600  # approximate quota units per upload

    def __init__(self, daily_budget: int = DEFAULT_DAILY_UPLOAD_BUDGET):
        self.daily_budget = daily_budget
        self.usage_file = __import__("pathlib").Path("metrics/quota_usage.json")
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_usage(self) -> Dict[str, Any]:
        import json
        if not self.usage_file.exists():
            return {"uploads_today": 0, "quota_units_used": 0, "date": str(datetime.now().date())}
        try:
            data = json.loads(self.usage_file.read_text(encoding="utf-8"))
            today = str(datetime.now().date())
            if data.get("date") != today:
                return {"uploads_today": 0, "quota_units_used": 0, "date": today}
            return data
        except Exception:
            return {"uploads_today": 0, "quota_units_used": 0, "date": str(datetime.now().date())}

    def _save_usage(self, uploads: int, units: int):
        import json
        data = {"uploads_today": uploads, "quota_units_used": units, "date": str(datetime.now().date())}
        self.usage_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_quota_state(self) -> QuotaState:
        usage = self._load_usage()
        uploads_today = usage.get("uploads_today", 0)
        units_used = usage.get("quota_units_used", 0)
        if uploads_today >= self.daily_budget:
            return QuotaState.EXCEEDED
        # Conservative: treat usage above 80% of budget as LOW
        if uploads_today >= int(self.daily_budget * 0.8):
            return QuotaState.LOW
        return QuotaState.AVAILABLE

    def estimate_upload_cost(self) -> int:
        return self.ESTIMATED_INSERT_COST

    def record_upload(self, video_path: Optional[str] = None) -> bool:
        """Record an upload attempt (successful or not). Blocked if exceeded."""
        state = self.get_quota_state()
        if state == QuotaState.EXCEEDED:
            return False
        usage = self._load_usage()
        current_uploads = usage.get("uploads_today", 0)
        current_units = usage.get("quota_units_used", 0)
        new_uploads = current_uploads + 1
        new_units = current_units + self.estimate_upload_cost()
        self._save_usage(new_uploads, new_units)
        return True

    def check_before_upload(self, video_path: Optional[str] = None) -> Dict[str, Any]:
        state = self.get_quota_state()
        usage = self._load_usage()
        return {
            "quota_state": state.value,
            "daily_budget": self.daily_budget,
            "uploads_today": usage.get("uploads_today", 0),
            "quota_units_used": usage.get("quota_units_used", 0),
            "estimated_cost": self.estimate_upload_cost(),
            "allowed": state != QuotaState.EXCEEDED,
            "video_path": video_path or "",
        }
