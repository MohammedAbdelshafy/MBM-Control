import os
from MBM.LeadEngine.intelligence.voxcpm_gate import VoiceConsent, voice_clone_allowed, gated_synth

def test_voxcpm_off_by_default():
    os.environ.pop("VOXCPM_ENABLED", None)
    ok, _ = voice_clone_allowed(VoiceConsent(True, True, "podcast intro", True))
    assert ok is False

def test_voxcpm_requires_all_consents():
    os.environ["VOXCPM_ENABLED"] = "true"
    try:
        # missing consent
        ok, reason = voice_clone_allowed(VoiceConsent(False, True, "podcast intro", True))
        assert not ok
        assert "consentVerified" in reason
        # missing subjectAuthorized
        ok, reason = voice_clone_allowed(VoiceConsent(True, False, "podcast intro", True))
        assert not ok
        # banned intent
        ok, reason = voice_clone_allowed(VoiceConsent(True, True, "impersonate a public figure", True))
        assert not ok
        # valid passes gate (but synth still stub-blocked without runtime)
        ok, reason = voice_clone_allowed(VoiceConsent(True, True, "internal training", True))
        assert ok is True
        r = gated_synth(consent=VoiceConsent(True, True, "internal training", True), text="hello")
        assert r["blocked"] is True  # stub has no runtime
    finally:
        os.environ.pop("VOXCPM_ENABLED", None)
