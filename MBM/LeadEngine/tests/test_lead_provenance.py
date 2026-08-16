"""
REGRESSION TESTS: LEAD PROVENANCE GATE (ZERO SYNTHETIC LEADS)
=============================================================================
Guards that fabricated/fixture records can NEVER enter production:
1. test_synthetic_leads_rejected      - GEN-NEW fabricated leads rejected
2. test_generated_contacts_rejected   - persona first+last pool rejected
3. test_missing_provenance_rejected   - missing source fields rejected
4. test_fake_domain_rejected          - email slug-matches-company rejected
5. test_sequential_registry_fixture_rejected - /entity/0000771 refs rejected
6. test_real_source_required          - real NPI record passes the gate
7. test_production_synthetic_count    - aggregate zero-synthetic assertion
=============================================================================
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.lead_provenance import (
    LeadProvenanceGate,
    SyntheticLeadDetector,
    build_provenance_fields,
    production_synthetic_count,
    is_generated_domain,
    is_template_company,
    is_persona_contact,
    is_sequential_registry_ref,
)

REAL_NPI = {
    "id": "NPI-1568833093",
    "company": "ADVANTAGE MEDICAL GROUP LLC",
    "contact": "ARCILIO ALVARADO",
    "phone": "+17873068356",
    "email": "",
    "source": "CMS NPI Registry API v2.1",
    "source_reference": "NPI-1568833093",
    "source_type": "government_registry",
    "observed_at": "2026-08-15T12:51:50Z",
    "verified_at": "2026-08-15T12:51:50Z",
    "verification_method": "npi_registry_api",
}

SYNTHETIC = {
    "id": "GEN-NEW-07053",
    "company": "Chattanooga Civil Enterprises",
    "contact": "Ashley Mercer",
    "phone": "+14235712699",
    "email": "ashley@chattanoogacivilenterprises.com",
    "source": "TN State Commercial Licensing Board",
    "source_reference": "https://license.tn.gov/entity/004773",
    "verification_method": "state licensing",
}


def test_synthetic_leads_rejected():
    gate = LeadProvenanceGate()
    result = gate.evaluate(SYNTHETIC)
    assert result["ok"] is False
    assert result["synthetic"] is True


def test_generated_contacts_rejected():
    assert is_persona_contact("Ashley Mercer") is True
    assert is_persona_contact("ARCILIO ALVARADO") is False


def test_missing_provenance_rejected():
    gate = LeadProvenanceGate()
    missing = dict(REAL_NPI)
    del missing["source_type"]
    result = gate.evaluate(missing)
    assert result["ok"] is False
    assert "source_type" in result["missing_fields"]


def test_fake_domain_rejected():
    assert is_generated_domain("ashley@chattanoogacivilenterprises.com", "Chattanooga Civil Enterprises") is True


def test_sequential_registry_fixture_rejected():
    assert is_sequential_registry_ref("https://license.tn.gov/entity/004773") is True
    assert is_sequential_registry_ref("NPI-1568833093") is False


def test_real_source_required():
    gate = LeadProvenanceGate()
    result = gate.evaluate(REAL_NPI)
    assert result["ok"] is True
    assert result["synthetic"] is False
    assert result["provenance_complete"] is True


def test_production_synthetic_count():
    assert production_synthetic_count([REAL_NPI]) == 0
    assert production_synthetic_count([SYNTHETIC]) == 1
    assert production_synthetic_count([REAL_NPI, SYNTHETIC, dict(REAL_NPI)]) == 1


def test_build_provenance_fields_roundtrip():
    fields = build_provenance_fields(
        source="CMS NPI Registry API v2.1",
        source_reference="NPI-1568833093",
        source_type="government_registry",
        verification_method="npi_registry_api",
    )
    assert set(fields.keys()) >= {"source", "source_reference", "source_type", "observed_at", "verified_at", "verification_method"}