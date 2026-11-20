from __future__ import annotations

from types import SimpleNamespace

import pytest

from MBM.LeadEngine.agency_prospector import (
    AgencyProspector,
    ProspectSourceNotConfigured,
    ProviderNotConfigured,
)


def valid_prospect(**overrides):
    row = {
        "company": "Northstar Creative",
        "industry": "Podcast production agency",
        "contact_name": "Casey",
        "source": "customer-supplied-prospect-file",
        "source_url": "https://northstar.example/about",
        "retrieved_at": "2026-10-30T12:00:00Z",
    }
    row.update(overrides)
    return row


class FakeSource:
    def __init__(self, rows):
        self.rows = rows

    def find_prospects(self, niche):
        return self.rows


class FakeClient:
    def __init__(self):
        self.prompt = None
        self.models = self

    def generate_content(self, model, contents):
        self.prompt = contents
        return SimpleNamespace(text="A reviewed draft asking about their current workflow.")


def test_default_prospector_does_not_return_mock_prospects():
    prospector = AgencyProspector()

    with pytest.raises(ProspectSourceNotConfigured):
        prospector.find_prospects()


def test_source_records_require_company_provenance_and_retrieval_time():
    prospector = AgencyProspector(source=FakeSource([
        {"company": "Unverified Example", "email": "owner@example.com"},
    ]))

    with pytest.raises(ValueError, match="source|provenance|retrieved_at"):
        prospector.find_prospects()


def test_valid_source_records_keep_their_provenance():
    prospect = valid_prospect()
    prospector = AgencyProspector(source=FakeSource([prospect]))

    results = prospector.find_prospects(niche="Podcast agencies")

    assert results == [prospect]
    assert results[0]["source_url"] == "https://northstar.example/about"
    assert results[0]["retrieved_at"] == "2026-10-30T12:00:00Z"


def test_missing_model_configuration_fails_closed():
    prospect = valid_prospect()
    prospector = AgencyProspector(source=FakeSource([prospect]), api_key="")

    with pytest.raises(ProviderNotConfigured):
        prospector.draft_pitch(prospect)


def test_pitch_without_completed_work_evidence_cannot_claim_it_was_done():
    client = FakeClient()
    prospect = valid_prospect()
    prospector = AgencyProspector(source=FakeSource([prospect]), client=client)

    draft = prospector.draft_pitch(prospect)

    assert draft == "A reviewed draft asking about their current workflow."
    assert client.prompt is not None
    prompt = client.prompt.lower()
    assert "do not claim" in prompt
    assert "already analyzed" in prompt
    assert "attached clip" in prompt


def test_completed_work_claim_requires_source_linked_analysis_and_artifact():
    client = FakeClient()
    prospect = valid_prospect(completed_work_evidence={
        "source_url": "https://northstar.example/episode/12",
        "analysis_reference": "analysis:episode-12",
        "artifact_reference": "artifact:clip-12",
        "completed_at": "2026-10-30T12:30:00Z",
    })
    prospector = AgencyProspector(source=FakeSource([prospect]), client=client)

    prospector.draft_pitch(prospect)

    assert "source-linked completed work evidence is present" in client.prompt.lower()
    assert "analysis:episode-12" in client.prompt
    assert "artifact:clip-12" in client.prompt
