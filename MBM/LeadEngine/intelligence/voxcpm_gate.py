"""
VoxCPM gate — strictly gated voice clone (§10).

Uses ONLY canonical VoxCPM project. voxcpm.net is BLOCKED by provider_policy.
VoxCPM is OFF by default, self-hosted, behind authz + consent + audit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .provider_policy import assert_allowed

@dataclass
class VoiceConsent:
    consentVerified: bool
    subjectAuthorized: bool
    intendedUse: str
    provenanceAvailable: bool
    subjectId: Optional[str] = None
    consentRecordId: Optional[str] = None

def voice_clone_allowed(c: VoiceConsent) -> tuple[bool, str]:
    if (os.environ.get("VOXCPM_ENABLED", "") or "").strip().lower() not in ("1", "true", "yes", "on"):
        return False, "VOXCPM_ENABLED != true (kill switch)"
    # policy gate — voxcpm_official is gated
    try:
        assert_allowed("voxcpm_official", purpose="production")
    except Exception as e:
        return False, str(e)
    if not c.consentVerified:
        return False, "consentVerified == false"
    if not c.subjectAuthorized:
        return False, "subjectAuthorized == false"
    if not c.provenanceAvailable:
        return False, "provenanceAvailable == false"
    if not c.intendedUse or len(c.intendedUse.strip()) < 5:
        return False, "intendedUse missing/too short"
    # hard bans
    banned = {"impersonate", "public figure", "celebrity", "politician", "deceive", "misattribute"}
    low = c.intendedUse.lower()
    for tok in banned:
        if tok in low:
            return False, f"intendedUse contains banned concept: {tok}"
    return True, "allowed"

def gated_synth(*, consent: VoiceConsent, text: str, **kwargs) -> Dict[str, Any]:
    ok, reason = voice_clone_allowed(consent)
    if not ok:
        return {"ok": False, "blocked": True, "reason": reason}
    # Placeholder: real self-hosted VoxCPM call would go here.
    # We never impersonate; this path is intentionally not wired to auto-publish.
    return {"ok": False, "blocked": True, "reason": "VoxCPM self-hosted runtime not provisioned (stub gate). Wire local inference behind this gate."}
