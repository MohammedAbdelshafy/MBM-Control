"""
Quality gate policy — Phase 7 configurable gate with exact failure reasons.

Every required gate is checked against a configurable threshold. A clip passes
only if ALL required gates pass. Failed clips return QUALITY_FAILED with a
structured list of failing gate -> reason (so nothing is silently dropped and
the reason is exact, per the production contract).

Gates (all 0..1 unless boolean):
  media_integrity, hook_quality, speech_accuracy, subtitle_accuracy,
  visual_framing, audio_quality, brand_fit, platform_fit,
  metadata_completeness, rights_status
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

DEFAULT_THRESHOLDS = {
    "media_integrity": 1.0,     # must be exactly pass (no corrupt/black frames)
    "hook_quality": 0.6,
    "speech_accuracy": 0.7,
    "subtitle_accuracy": 0.7,
    "visual_framing": 0.6,
    "audio_quality": 0.6,
    "brand_fit": 0.6,
    "platform_fit": 0.6,
    "metadata_completeness": 0.8,
    "rights_status": 1.0,       # source must be APPROVED
}


@dataclass
class GatePolicy:
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    required: list[str] = field(default_factory=lambda: list(DEFAULT_THRESHOLDS.keys()))

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "GatePolicy":
        if not d:
            return cls()
        return cls(
            thresholds={**DEFAULT_THRESHOLDS, **(d.get("thresholds") or {})},
            required=d.get("required") or list(DEFAULT_THRESHOLDS.keys()),
        )

    def evaluate(self, results: dict[str, Any], *, rights_approved: bool = True) -> "GateResult":
        failures: list[dict] = []
        passed = True
        for gate in self.required:
            if gate == "rights_status":
                ok = bool(rights_approved)
                val = 1.0 if ok else 0.0
                if not ok:
                    failures.append({"gate": gate, "value": 0.0,
                                     "reason": "source rights not approved (APPROVAL_REQUIRED/blocked)"})
                    passed = False
                continue
            val = results.get(gate)
            if val is None:
                failures.append({"gate": gate, "value": None, "reason": f"missing metric for '{gate}'"})
                passed = False
                continue
            thr = self.thresholds.get(gate, 0.0)
            if isinstance(val, bool):
                if not val:
                    failures.append({"gate": gate, "value": False,
                                     "reason": f"'{gate}' check returned False"})
                    passed = False
            elif float(val) < float(thr):
                failures.append({"gate": gate, "value": round(float(val), 3),
                                 "reason": f"'{gate}' {round(float(val),3)} < threshold {thr}"})
                passed = False
        return GateResult(passed=passed, failures=failures, results=results,
                          rights_approved=rights_approved)


@dataclass
class GateResult:
    passed: bool
    failures: list[dict]
    results: dict[str, Any]
    rights_approved: bool

    @property
    def status(self) -> str:
        return "PASSED" if self.passed else "QUALITY_FAILED"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "passed": self.passed,
            "failures": self.failures,
            "results": self.results,
            "rights_approved": self.rights_approved,
        }
