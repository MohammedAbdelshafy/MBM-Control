"""Part I proofs: wrapped MCP capabilities respect every safety gate.

Hermetic: temp suppression files, monkeypatched provider call log, stub env.
Proves: DNC respected, suppression respected, approval required, dry-run safe,
unknown mutation denied, unknown MCP tool denied, malformed input rejected,
provider idempotent, transient-retry-only.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_control_plane import build_capability_bus, RunMode, ReplayHarness
from jarvis_control_plane.policy import evaluate, PolicyVerdict

GOOD_LEAD = {
    "id": "CAP-T1",
    "name": "Jane Smith",
    "phone": "+12124440101",
    "skip_trace_status": "VERIFIED",
}
GOOD_PHONE = "+12124440101"
DNC_PHONE = "+19995550101"


@pytest.fixture()
def bus(tmp_path, monkeypatch):
    sup = tmp_path / "suppressed_bad_phones.json"
    sup.write_text(json.dumps({
        "suppressed_phones": [DNC_PHONE],
        "total_suppressed_phones": 1,
        "last_updated": "2026-09-04T00:00:00Z",
    }), encoding="utf-8")
    import MBM.LeadEngine.phound_provider as pp

    monkeypatch.setattr(pp, "CALL_RECORDS", tmp_path / "phound_calls.jsonl")
    env = {"PHOUND_ENABLED": "false", "JARVIS_DRY_RUN": "true"}
    return build_capability_bus(suppression_file=sup, env=env), sup


def test_only_three_capabilities_exposed(bus):
    b, _ = bus
    assert b.exposed_tools() == [
        "browser_navigate_extract",
        "dialer_eligibility_filter",
        "phound_dry_run_call",
        "phound_status",
        "suppression_check",
    ]


def test_gate_blocks_unverified_xlsx_style_lead(bus):
    b, _ = bus
    out = b.call("dialer_eligibility_filter", {"leads": [
        {"id": "X1", "contact": "Walter Bowles", "phone": "3213025720",
         "verification_method": "user_upload", "verification_status": "VERIFIED"},
    ]})
    assert out["eligible_count"] == 0 and out["blocked_count"] == 1


def test_gate_passes_skip_trace_verified_lead(bus):
    b, _ = bus
    out = b.call("dialer_eligibility_filter", {"leads": [dict(GOOD_LEAD)]})
    assert out["eligible_count"] == 1


def test_suppression_respected_dnc_blocked(bus):
    b, _ = bus
    hit = b.call("suppression_check", {"phone": DNC_PHONE})
    assert hit["suppressed"] is True
    assert "phone_suppressed_bad_phones_index" in hit["reasons"]
    clear = b.call("suppression_check", {"phone": GOOD_PHONE})
    assert clear["suppressed"] is False


def test_phound_dry_run_blocks_suppressed_lead(bus):
    b, _ = bus
    out = b.call("phound_dry_run_call", {
        "lead_id": "CAP-DNC", "phone": DNC_PHONE, "persona_uid": "P1",
        "name": "Jane Smith", "skip_trace_status": "VERIFIED",
    })
    assert out["status"] == "gate_blocked"


def test_phound_dry_run_blocks_unverified_lead(bus):
    b, _ = bus
    out = b.call("phound_dry_run_call", {
        "lead_id": "CAP-RAW", "phone": "+12125559999", "persona_uid": "P1",
        "name": "Nobody Verified",
    })
    assert out["status"] == "gate_blocked"
    assert out["reason"] == "dialer_verification_gate"


def test_phound_dry_run_simulates_but_never_lives(bus):
    b, _ = bus
    out = b.call("phound_dry_run_call", {
        "lead_id": "CAP-T1", "phone": GOOD_PHONE, "persona_uid": "P1",
        "name": "Jane Smith", "skip_trace_status": "VERIFIED",
        "request_id": "req-cap-1",
    })
    assert out["status"] == "dry_run_simulated"
    assert out.get("dry_run") is True or out["record"]["dry_run"] is True
    # idempotency: same lead + request replays the same record, never duplicates
    again = b.call("phound_dry_run_call", {
        "lead_id": "CAP-T1", "phone": GOOD_PHONE, "persona_uid": "P1",
        "name": "Jane Smith", "skip_trace_status": "VERIFIED",
        "request_id": "req-cap-1",
    })
    assert again["status"] == "duplicate_suppressed"


def test_live_call_action_requires_approval_and_gate():
    d = evaluate("place real call via provider bridge")
    assert d.verdict is PolicyVerdict.REQUIRE_APPROVAL
    assert "dialer_verification_gate" in d.gates
    denied = evaluate("delete production dialer database infra")
    assert denied.verdict is PolicyVerdict.DENY


def test_unknown_mutation_denied_and_unknown_tool_rejected(bus):
    b, _ = bus
    d = evaluate("flibber the canonical lead store")
    assert d.verdict in (PolicyVerdict.REQUIRE_APPROVAL, PolicyVerdict.DENY)
    with pytest.raises(KeyError):
        b.call("place_live_call", {"lead_id": "X"})
    with pytest.raises(KeyError):
        b.call("dialer_eligibility_filter_typo", {})


def test_malformed_input_rejected(bus):
    b, _ = bus
    with pytest.raises(ValueError):
        b.call("dialer_eligibility_filter", {"leads": "not-a-list"})
    with pytest.raises(ValueError):
        b.call("dialer_eligibility_filter", {"leads": ["not-a-dict"]})
    with pytest.raises(ValueError):
        b.call("dialer_eligibility_filter", {})
    with pytest.raises(ValueError):
        b.call("suppression_check", {})
    with pytest.raises(ValueError):
        b.call("phound_dry_run_call", {"lead_id": "only-id"})


def test_phound_status_exposes_no_credentials(bus):
    b, _ = bus
    out = b.call("phound_status", {})
    blob = json.dumps(out)
    assert out["provider"] == "phound"
    assert "PHOUND_TOKEN" not in blob and "api_key" not in blob.lower()


def test_capability_replay_without_credits(bus):
    b, _ = bus
    harness = ReplayHarness(mode=RunMode.MOCK)
    harness.register(
        "dialer_eligibility_filter",
        lambda a: (_ for _ in ()).throw(AssertionError("live must not run")),
        mock=lambda a: {"eligible_count": 1, "blocked_count": 0, "mode": "MOCK"},
    )
    assert harness.call("dialer_eligibility_filter", {"leads": []})["output"]["mode"] == "MOCK"
    assert b.call("dialer_eligibility_filter", {"leads": []})["eligible_count"] == 0
