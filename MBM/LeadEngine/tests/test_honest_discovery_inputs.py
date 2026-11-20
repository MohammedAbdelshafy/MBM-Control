"""Regression tests for evidence-honest discovery adapters.

These tests protect the boundary between verified business identity and
unverified purchasing intent. Registry facts must never be inflated into
operational pain, demand, contact details, or revenue claims.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.ai_assistant_buyer_hunter import SignalHarvester
from MBM.LeadEngine.gtm.adapters import BuyerHunterAdapter


def test_missing_npi_source_does_not_create_a_fallback_clinic(tmp_path: Path) -> None:
    harvester = SignalHarvester()
    harvester.npi_path = tmp_path / "missing_npi_verified_callsheet.json"

    assert harvester._harvest_clinic_registry_signals() == []


def test_npi_registry_identity_does_not_become_invented_buyer_intent(tmp_path: Path) -> None:
    source = tmp_path / "npi_verified_callsheet.json"
    source.write_text(
        json.dumps(
            {
                "generated_at": "2026-10-30T12:00:00+00:00",
                "leads": [
                    {
                        "npi": "1568833093",
                        "company_name": "ADVANTAGE MEDICAL GROUP LLC",
                        "taxonomy": "Dentist",
                        "phone": "+17873068356",
                        "city": "Ponce",
                        "state": "PR",
                        "authorized_official_name": "ARCILIO ALVARADO",
                        "authorized_official_title": "CEO/PRESIDENT",
                        "source": "CMS NPI Registry API v2.1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    harvester = SignalHarvester()
    harvester.npi_path = source

    records = harvester._harvest_clinic_registry_signals()

    assert len(records) == 1
    record = records[0]
    assert record["id"] == "NPI-1568833093"
    assert record["company"] == "ADVANTAGE MEDICAL GROUP LLC"
    assert record["phone"] == "+17873068356"
    assert record["source"] == "CMS NPI Registry API v2.1"
    assert record["source_reference"] == "NPI-1568833093"
    assert record["source_url"].startswith("https://npiregistry.cms.hhs.gov/api/")
    for unsupported_claim in (
        "website",
        "email",
        "pain_description",
        "intent_signal",
        "post_content",
        "hiring_title",
        "tech_stack",
        "engagement_context",
    ):
        assert unsupported_claim not in record


def test_buyer_hunter_adapter_preserves_missing_evidence_as_missing() -> None:
    normalized = BuyerHunterAdapter().normalize_prospect(
        {
            "id": "BIZ-001",
            "company": "Example Dental Group",
            "source": "CMS NPI Registry API v2.1",
        }
    )

    assert normalized["pain_point"] is None
    assert normalized["intent_signal"] is None
    assert normalized["why_this_company"] is None
    assert normalized["why_now"] is None
    assert normalized["decision_maker"] is None
    assert normalized["expected_revenue"] is None
    assert normalized["signal_age_days"] is None
    assert normalized["confidence"] == 0.0
    assert normalized["qualification_status"] == "INCOMPLETE_EVIDENCE"
    assert normalized["action_eligible"] is False
    assert normalized["evidence"]["claim"] is None
    assert normalized["evidence"]["source_reference"] is None


def test_offer_price_is_not_misrepresented_as_expected_revenue() -> None:
    normalized = BuyerHunterAdapter().normalize_prospect(
        {
            "id": "BIZ-002",
            "company": "Example HVAC",
            "recommended_assistant": {
                "sku": "AI-ASSISTANT-HVAC-DISPATCH",
                "monthly_retainer": 1500.0,
            },
        }
    )

    assert normalized["recommended_assistant_sku"] == "AI-ASSISTANT-HVAC-DISPATCH"
    assert normalized["expected_revenue"] is None
    assert normalized["qualification_status"] == "INCOMPLETE_EVIDENCE"
    assert normalized["action_eligible"] is False


def test_legacy_static_social_and_hiring_examples_never_enter_discovery(tmp_path: Path) -> None:
    harvester = SignalHarvester()
    harvester.npi_path = tmp_path / "missing_npi_verified_callsheet.json"

    # Social, hiring, contractor and niche helper lists still contain old
    # examples for historical/unit-test purposes. They carry no source record
    # proof and must never be promoted into the live discovery result.
    assert harvester.harvest_all_sources() == []
