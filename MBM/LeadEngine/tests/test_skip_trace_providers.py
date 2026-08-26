"""Tests for SkipTraceProvider abstraction + benchmark cohort builder (P0 P2/P4)."""
import json

import pytest

from MBM.LeadEngine.skip_trace_provider import (
    InternalHistoryProvider,
    NullProvider,
    PROVIDER_REGISTRY,
    SkipTraceResult,
    first_available_provider,
    get_provider,
    normalize,
)
from MBM.LeadEngine.seller_benchmark_cohort import (
    build_cohort,
    evaluation_status,
)


def seller(**kw):
    base = {
        "id": "Real Estate Sellers-1", "segment": "DISTRESSED_SELLER",
        "phone": "+12147360101", "source": "Dallas County Appraisal District (DCAD)",
        "address": "123 Main St, Dallas, TX 75201",
        "owner_verification_status": "VERIFIED_OWNER",
        "details": {"county_parcel_verified": True,
                    "skip_trace_source": "none"},
    }
    base.update(kw)
    return base


class TestNormalize:
    def test_formats(self):
        assert normalize("(214) 736-0101") == "+12147360101"
        assert normalize("12147360101") == "+12147360101"
        assert normalize("") == ""
        assert normalize("12345") == ""


class TestProviders:
    def test_null_provider_unavailable_and_returns_nothing(self):
        p = NullProvider()
        assert p.available() is False
        assert p.trace(seller()) == []

    def test_registry_has_internal_first_available(self):
        assert "internal_history" in PROVIDER_REGISTRY
        p = first_available_provider()
        assert p is not None and p.name == "internal_history"

    def test_get_unknown_provider_raises(self):
        with pytest.raises(KeyError):
            get_provider("propstream")  # not registered until credentials exist

    def test_internal_history_returns_primary_with_provenance(self):
        res = InternalHistoryProvider().trace(seller())
        assert len(res) == 1
        r = res[0]
        assert isinstance(r, SkipTraceResult)
        assert r.candidate_phone == "+12147360101"
        assert r.provider == "internal_history"
        assert r.raw_reference.startswith("lead:")
        # owner verified on lead -> MATCH; never UNKNOWN->MATCH fabrication
        assert r.owner_match in ("MATCH", "UNKNOWN")

    def test_internal_history_owner_match_requires_verification(self):
        s = seller(owner_verification_status="")
        res = InternalHistoryProvider().trace(s)
        assert res[0].owner_match == "UNKNOWN"

    def test_alternate_phones_included(self):
        s = seller(alternate_phones=[{"phone": "+19725550188", "ts": "2026-08-24"}])
        res = InternalHistoryProvider().trace(s)
        phones = [r.candidate_phone for r in res]
        assert "+12147360101" in phones and "+19725550188" in phones

    def test_dnc_lead_marked(self):
        res = InternalHistoryProvider().trace(seller(dnc=True))
        assert res[0].dnc_status == "DNC"

    def test_result_to_phone_candidate(self):
        r = InternalHistoryProvider().trace(seller())[0]
        cand = r.to_phone_candidate()
        assert cand.phone == "+12147360101"
        assert cand.sources == ["provider:internal_history"]
        assert cand.owner_match == 1.0  # verified owner on fixture


class TestCohort:
    def test_known_bad_from_quarantine_event(self):
        s = seller(quarantined_phones=[{"phone": "+12147360101", "status": "BAD"}])
        status, reason = evaluation_status(s)
        assert status == "KNOWN_BAD" and "quarantine" in reason

    def test_known_bad_from_feedback(self):
        s = seller(details={"call_feedback": [{"outcome": "WRONG_NUMBER"}]})
        assert evaluation_status(s)[0] == "KNOWN_BAD"

    def test_known_good_requires_identity_evidence(self):
        s = seller(details={"owner_phone_evidence": "TITLED_OWNER_DIRECT"})
        assert evaluation_status(s)[0] == "KNOWN_GOOD"

    def test_unknown_when_no_ground_truth(self):
        assert evaluation_status(seller())[0] == "UNKNOWN"

    def test_cohort_size_and_statuses_honest(self):
        pop = [seller(id=f"S-{i}") for i in range(120)]
        bad = [seller(id=f"B-{i}",
                      quarantined_phones=[{"phone": "+12147360101", "status": "BAD"}])
               for i in range(6)]
        cohort = build_cohort(pop + bad, size=100)
        assert cohort["size"] == 100
        assert cohort["population"] == 126
        # all KNOWN_BAD preserved (never diluted by sampling)
        assert cohort["status_counts"]["KNOWN_BAD"] == 6
        recs = {r["lead_id"]: r for r in cohort["records"]}
        for i in range(6):
            assert recs[f"B-{i}"]["evaluation_status"] == "KNOWN_BAD"
        assert all(r["evaluation_status"] in ("KNOWN_BAD", "UNKNOWN")
                   for r in cohort["records"])

    def test_stratification_fields_present(self):
        cohort = build_cohort([seller(), seller(id="S-2")], size=2)
        row = cohort["records"][0]
        for key in ("source", "geo", "age_bucket", "value_tier",
                    "evaluation_status"):
            assert key in row


@pytest.fixture()
def tmp_db(tmp_path):
    def make(leads):
        p = tmp_path / "db.json"
        p.write_text(json.dumps({"leads": leads}), encoding="utf-8")
        return str(p)
    return make


def test_benchmark_runner_blocked_honest(tmp_db, tmp_path):
    from MBM.LeadEngine.run_provider_benchmark import run
    db = tmp_db([seller(id="S-1"), seller(id="S-2")])
    out = tmp_path / "bench.json"
    report = run(db_path=db, out_path=str(out))
    # internal_history IS available -> status OK, but null stays blocked
    assert report["status"] == "OK"
    assert "null" in report["providers_blocked"]
    assert "internal_history" in report["providers_tested"]
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["cohort"]["size"] == 2
