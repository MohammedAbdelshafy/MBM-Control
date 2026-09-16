    d = P.evaluate("delete production database infra")
    assert d.action_class is P.ActionClass.HIGH_IMPACT
    assert d.verdict is P.PolicyVerdict.DENY


def test_policy_unknown_mutation_fails_closed():
    d = P.evaluate("flibber the wobble store")
    assert d.verdict in (P.PolicyVerdict.REQUIRE_APPROVAL, P.PolicyVerdict.DENY)


def test_policy_redaction_removes_secrets_and_phones():
    dirty = {
        "api_key": "REDACTION_TEST_API_KEY",
        "auth": {"token": "REDACTION_TEST_TOKEN"},
        "phone": "+1 (555) 123-4567",
        "note": "call PHOUND_TOKEN=uid.secretkey now",
        "safe": "hello world",
    }
    clean = P.redact(dirty)
    blob = json.dumps(clean)
    assert "REDACTION_TEST_API_KEY" not in blob
    assert "REDACTION_TEST_TOKEN" not in blob
    assert "555" not in blob or "[REDACTED]" in blob
    assert "secretkey" not in blob
    assert clean["safe"] == "hello world"


def test_policy_retry_only_transient_without_side_effect():
    assert P.retry_allowed("timeout", True) is True
    assert P.retry_allowed("timeout", False) is False
    assert P.retry_allowed("unknown_provider_state", True) is False


# -- registry ------------------------------------------------------------------
def test_registry_builds_and_has_contract_fields():
    reg = R.build_registry()
    assert "jarvis.decider" in reg and "policy.gateway" in reg and "workflow.engine" in reg
    assert len(reg) > 10  # native + wrapped GLM roles
    for spec in reg.values():
        assert spec.agent_id and spec.name and spec.responsibility
        assert spec.fallback, f"{spec.agent_id} missing fallback"
        assert isinstance(spec.protocol, R.AgentProtocol)


def test_registry_capability_discovery_and_routing():
    assert R.list_by_capability("dialer"), "expected dialer-capable specialist"
    routed = R.route("dialer verification queue provider")
    assert routed, "router returned nothing for dialer intent"
    with pytest.raises(KeyError):
        R.get("no.such.agent")


# -- record / replay -------------------------------------------------------------
def test_recorder_redacts_secrets(tmp_path):
    rec = RR.RunRecorder(tmp_path / "runs.jsonl")
    rec.record(RR.RunEvent(run_id="r1", tool_called="send email",
                           tool_arguments_redacted={"token": "REDACTION_TEST_GH_TOKEN"},
                           output={"phone": "+15551234567"}))
    blob = (tmp_path / "runs.jsonl").read_text(encoding="utf-8")
    assert "REDACTION_TEST_GH_TOKEN" not in blob and "5551234567" not in blob
    assert "[REDACTED]" in blob


def test_replay_modes_deterministic(tmp_path):