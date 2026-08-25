"""Hermetic reliability tests for the MBM Voice Agent Factory.

Regression coverage for incident run 32863390319 (2026-08-25):
Retell create-agent answers a NONEXISTENT voice_id with generic
HTTP 404 {"status":"error","message":"Not Found"} immediately after a
successful create-retell-llm. Verified live: valid voice + seconds-old
llm_id succeeds instantly => the 404 is permanent, not propagation.

All Retell traffic is simulated; no network access happens here.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine import agent_factory as af


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError(f"malformed JSON body: {self.text[:120]}")
        return self._payload


class FakeRetell:
    """Scripted stand-in for the `requests` session inside agent_factory."""

    def __init__(self, known_voices=None, llm_responses=None,
                 agent_responses=None, delete_response=None, get_exception=None,
                 agent_success=None):
        self.known_voices = known_voices if known_voices is not None else {"retell-Willa", "retell-Cimo"}
        self.llm_responses = list(llm_responses or [])
        self.agent_responses = list(agent_responses or [])
        self.delete_response = delete_response or FakeResponse(204)
        self.get_exception = get_exception
        # Infinite supplier used once the scripted queue is exhausted.
        self.agent_success = agent_success or (
            lambda: FakeResponse(201, payload={"agent_id": f"agent_{self.agent_calls:024d}"}))
        self.llm_calls = 0
        self.agent_calls = 0
        self.delete_calls = []
        self.created_llm_ids = []

    # -- helpers ----------------------------------------------------------
    def _next(self, queue, default_factory):
        if queue:
            item = queue.pop(0)
            return item() if callable(item) else item
        return default_factory()

    def _llm_ok(self):
        self.llm_calls += 0  # counting happens at call sites below
        llm_id = f"llm_{len(self.created_llm_ids):024d}"
        return llm_id

    # -- requests surface --------------------------------------------------
    def get(self, url, **kwargs):
        if url.endswith("/list-voices"):
            if self.get_exception is not None:
                raise self.get_exception
            return FakeResponse(200, payload=[{"voice_id": v} for v in sorted(self.known_voices)])
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, **kwargs):
        if url.endswith("/create-retell-llm"):
            resp = self._next(
                self.llm_responses,
                lambda: FakeResponse(201, payload={"llm_id": f"llm_{self.llm_calls:024d}"}),
            )
            self.llm_calls += 1
            if resp.status_code in (200, 201):
                try:
                    llm_id = resp.json().get("llm_id")
                    if llm_id:
                        self.created_llm_ids.append(llm_id)
                except ValueError:
                    pass
            return resp
        if url.endswith("/create-agent"):
            resp = self._next(self.agent_responses, self.agent_success)
            self.agent_calls += 1
            return resp
        raise AssertionError(f"unexpected POST {url}")

    def delete(self, url, **kwargs):
        self.delete_calls.append(url)
        return self.delete_response


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    """Isolated factory: temp state files, fake transport, instant sleeps."""
    monkeypatch.setattr(af, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(af, "DEPLOYED_FILE", tmp_path / "deployed_agents.json")
    monkeypatch.setattr(af, "ATTEMPTS_FILE", tmp_path / "factory_attempts.json")
    monkeypatch.setattr(af, "RETELL_API_KEY", "test-key")
    monkeypatch.setattr(af.time, "sleep", lambda *_: None)
    saved_voices = list(af.VOICE_IDS)
    yield af
    af.VOICE_IDS[:] = saved_voices


def install(factory_obj, fake):
    factory_obj.requests = fake


# ---------------------------------------------------------------------------
# Happy path / persistence / idempotency basics
# ---------------------------------------------------------------------------

def test_happy_path_deploys_and_persists(factory):
    fake = FakeRetell()
    install(factory, fake)
    rc = factory.main([])
    assert rc == 0
    deployed = json.loads((factory.DEPLOYED_FILE).read_text())
    assert len(deployed) == 1
    rec = deployed[0]
    assert rec["agent_id"].startswith("agent_")
    assert rec["llm_id"].startswith("llm_")
    assert rec["voice_id"] in ("retell-Willa", "retell-Cimo")
    assert rec["status"] == "deployed"
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "deployed" for r in ledger)
    assert not fake.delete_calls  # nothing orphaned on success


def test_batch_of_two_uses_consecutive_niches(factory):
    install(factory, FakeRetell())
    assert factory.main(["--count", "2"]) == 0
    niches = [r["niche"] for r in json.loads((factory.DEPLOYED_FILE).read_text())]
    assert len(niches) == 2
    assert niches[0] != niches[1]


def test_empty_deployment_state_is_not_required(factory):
    install(factory, FakeRetell())
    assert factory.load_deployed() == []
    assert factory.main([]) == 0


def test_corrupt_state_files_are_tolerated(factory):
    factory.DEPLOYED_FILE.write_text("{corrupt!!", encoding="utf-8")
    factory.ATTEMPTS_FILE.write_text("\x00garbage", encoding="utf-8")
    install(factory, FakeRetell())
    assert factory.main([]) == 0
    deployed = factory.load_deployed()
    assert isinstance(deployed, list) and len(deployed) == 1


def test_attempt_ledger_stays_bounded(factory):
    factory.ATTEMPTS_FILE.write_text(json.dumps([{"junk": i} for i in range(300)]), encoding="utf-8")
    install(factory, FakeRetell())
    assert factory.main([]) == 0
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert len(ledger) <= af.MAX_LEDGER_RECORDS
    assert any(r.get("status") == "deployed" for r in ledger)


def test_ledger_carries_ci_provenance(factory, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "abc1234")
    monkeypatch.setenv("GITHUB_RUN_ID", "999")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")
    install(factory, FakeRetell())
    factory.main([])
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    rec = next(r for r in ledger if r["status"] == "deployed")
    assert rec["sha"] == "abc1234"
    assert rec["run_id"] == "999"
    assert rec["attempt"] == "3"


# ---------------------------------------------------------------------------
# Deterministic cadence-window niche rotation (idempotency key)
# ---------------------------------------------------------------------------

def test_niche_rotation_is_window_deterministic(factory, monkeypatch):
    fixed = 1_800_000_000
    monkeypatch.setattr(factory.time, "time", lambda: fixed)
    slot = fixed // factory.CADENCE_SECONDS
    n = len(factory.NICHES)
    assert factory.get_next_niche(0)["name"] == factory.NICHES[slot % n]["name"]
    assert factory.get_next_niche(1)["name"] == factory.NICHES[(slot + 1) % n]["name"]
    monkeypatch.setattr(factory.time, "time", lambda: fixed + factory.CADENCE_SECONDS)
    assert factory.get_next_niche(0)["name"] == factory.NICHES[(slot + 1) % n]["name"]


# ---------------------------------------------------------------------------
# Incident contract: 404 on create-agent is PERMANENT
# ---------------------------------------------------------------------------

NOT_FOUND_BODY = '{"status":"error","message":"Not Found"}'


def test_transient_404_signature_never_retried_and_cleans_llm(factory):
    fake = FakeRetell(agent_responses=[FakeResponse(404, text=NOT_FOUND_BODY)])
    install(factory, fake)
    rc = factory.main([])
    assert rc == 1
    assert fake.agent_calls == 1, "404 must NOT be retried (permanent reference error)"
    assert len(fake.delete_calls) == 1
    assert "/delete-retell-llm/" in fake.delete_calls[0]
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    fail = next(r for r in ledger if r["status"] == "agent_failed_permanent")
    assert fail["http"] == 404
    assert fail["voice_id"] in ("retell-Willa", "retell-Cimo")
    assert fail["body"] == NOT_FOUND_BODY
    assert any(r["status"] == "orphan_llm_deleted" for r in ledger)


def test_400_class_is_permanent_too(factory):
    fake = FakeRetell(agent_responses=[FakeResponse(400, payload={"error": "bad"})])
    install(factory, fake)
    assert factory.main([]) == 1
    assert fake.agent_calls == 1


def test_429_recovers_on_later_attempt(factory):
    fake = FakeRetell(agent_responses=[
        FakeResponse(429, text="rate limited"),
        FakeResponse(429, text="rate limited"),
        lambda: FakeResponse(201, payload={"agent_id": "agent_recovered"}),
    ])
    install(factory, fake)
    assert factory.main([]) == 0
    assert fake.agent_calls == 3
    assert not fake.delete_calls


def test_5xx_exhausts_bounded_retries_then_cleans_up(factory):
    fake = FakeRetell(agent_success=lambda: FakeResponse(503, text="overloaded"))
    install(factory, fake)
    assert factory.main([]) == 1
    assert fake.agent_calls == af.AGENT_ATTEMPTS
    assert len(fake.delete_calls) == 1
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "orphan_llm_deleted" for r in ledger)


def test_network_exception_exhausts_retries_then_cleans_up(factory):
    class Flaky(FakeRetell):
        def post(self, url, **kw):
            if url.endswith("/create-agent"):
                self.agent_calls += 1
                if self.agent_calls < af.AGENT_ATTEMPTS:
                    raise ConnectionError("boom")
                return FakeResponse(201, payload={"agent_id": "agent_ok"})
            return super().post(url, **kw)

    fake = Flaky()
    install(factory, fake)
    assert factory.main([]) == 0
    assert fake.agent_calls == af.AGENT_ATTEMPTS


def test_failed_agent_creation_after_successful_llm_leaves_no_orphan(factory):
    fake = FakeRetell(agent_responses=[FakeResponse(422, text="unprocessable")])
    install(factory, fake)
    assert factory.main([]) == 1
    deleted = {u.rsplit("/", 1)[-1] for u in fake.delete_calls}
    assert deleted == set(fake.created_llm_ids), "every created llm_id must be reconciled after failure"
    assert factory.load_deployed() == []


def test_orphan_llm_quarantined_in_ledger_when_delete_fails(factory):
    fake = FakeRetell(agent_responses=[FakeResponse(404, text=NOT_FOUND_BODY)],
                      delete_response=FakeResponse(500, text="nope"))
    install(factory, fake)
    assert factory.main([]) == 1
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    q = [r for r in ledger if r["status"] == "orphan_llm_quarantined"]
    assert len(q) == 1
    assert q[0]["llm_id"].startswith("llm_")


# ---------------------------------------------------------------------------
# Malformed / missing identifiers
# ---------------------------------------------------------------------------

def test_missing_llm_id_aborts_before_create_agent(factory):
    fake = FakeRetell(llm_responses=[FakeResponse(201, payload={})])
    install(factory, fake)
    assert factory.main([]) == 1
    assert fake.agent_calls == 0


def test_malformed_llm_json_handled(factory):
    fake = FakeRetell(llm_responses=[FakeResponse(201, text="<html>gateway</html>")])
    install(factory, fake)
    assert factory.main([]) == 1
    assert fake.agent_calls == 0
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "llm_missing_id" for r in ledger)


def test_success_without_agent_id_cleans_llm(factory):
    fake = FakeRetell(agent_responses=[lambda: FakeResponse(201, payload={"foo": "bar"})])
    install(factory, fake)
    assert factory.main([]) == 1
    assert len(fake.delete_calls) == 1
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "agent_missing_id" for r in ledger)


def test_malformed_success_response_cleans_llm(factory):
    fake = FakeRetell(agent_responses=[FakeResponse(200, text="{{{not-json")])
    install(factory, fake)
    assert factory.main([]) == 1
    assert len(fake.delete_calls) == 1
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "agent_malformed_response" for r in ledger)


# ---------------------------------------------------------------------------
# Configuration gates
# ---------------------------------------------------------------------------

def test_missing_api_key_is_fatal_config_error(factory, monkeypatch):
    monkeypatch.setattr(factory, "RETELL_API_KEY", "")
    fake = FakeRetell()
    install(factory, fake)
    assert factory.main([]) == 2
    assert fake.llm_calls == 0 and fake.agent_calls == 0


def test_all_invalid_voices_blocks_production(factory):
    fake = FakeRetell(known_voices={"some-other-voice"})
    install(factory, fake)
    assert factory.main([]) == 2
    assert fake.agent_calls == 0
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    removed = {r["voice_id"] for r in ledger if r["status"] == "invalid_voice_removed"}
    assert removed == {"retell-Willa", "retell-Cimo"}


def test_invalid_voice_is_filtered_but_valid_pool_continues(factory):
    fake = FakeRetell(known_voices={"retell-Willa"})
    install(factory, fake)
    assert factory.main([]) == 0
    assert factory.VOICE_IDS == ["retell-Willa"]
    ledger = json.loads((factory.ATTEMPTS_FILE).read_text())
    assert any(r["status"] == "invalid_voice_removed" for r in ledger)


def test_catalog_probe_failure_does_not_block_production(factory):
    fake = FakeRetell(get_exception=ConnectionError("catalog down"))
    install(factory, fake)
    assert factory.main([]) == 0
    assert fake.agent_calls >= 1


# ---------------------------------------------------------------------------
# Partial batch semantics
# ---------------------------------------------------------------------------

def test_partial_batch_failure_exits_nonzero(factory):
    # First creation succeeds, second hits the incident 404.
    fake = FakeRetell(agent_responses=[
        lambda: FakeResponse(201, payload={"agent_id": "agent_first"}),
        FakeResponse(404, text=NOT_FOUND_BODY),
    ])
    install(factory, fake)
    assert factory.main(["--count", "2"]) == 1
    deployed = factory.load_deployed()
    assert len(deployed) == 1
