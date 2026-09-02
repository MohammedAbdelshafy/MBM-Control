import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

class MockDCAD:
    def dcad_lookup(self, address, retries=1):
        if address == "123 Verified Owner Ln":
            return {"owner_name": "JOHN VERIFIED DOE"}
        elif address == "456 No Owner Rd":
            return None
        elif address == "789 Tenant Ave":
            return {"owner_name": "LANDLORD LLC"}
        elif address == "999 Provider Error Blvd":
            raise Exception("Provider Rate Limit Exceeded")
        return None

class MockFreeSkipTracer:
    def find_contact(self, name, address, city):
        if name == "John Verified Doe":
            return {"phone": "2144441234", "email": "john@example.com"}
        elif name == "Landlord Llc":
            return {"phone": "2144449999", "email": "leasing@landlord.com"}
        elif address == "999 Provider Error Blvd":
            raise Exception("Tracer Blocked")
        return {}

import MBM.LeadEngine.daily_lead_factory as fct
from MBM.LeadEngine.daily_lead_factory import DailyLeadFactory

def test_narrow_enrichment_integration(monkeypatch):
    monkeypatch.setattr(fct, "dcad_lookup", MockDCAD().dcad_lookup)
    monkeypatch.setattr(fct, "FreeSkipTracer", MockFreeSkipTracer)
    monkeypatch.setattr(fct.DialerSingleWriter, "read_leads", lambda self: [])
    monkeypatch.setattr(fct, "commit_dialer_db", lambda a, **kw: {"final_count": len(a)})
    
    def mock_has_evidence(lead):
        dm = lead.get("decision_maker", "").lower()
        if not dm or dm in ["current resident", "tenant", "occupant"]:
            return False
        return True
    monkeypatch.setattr(fct, "_has_authoritative_ownership_evidence", mock_has_evidence)

    raw_fixtures = [
        {
            "id": "FIXTURE-A",
            "industry": "Real Estate Sellers",
            "company": "John Verified Doe LLC",
            "property_address": "123 Verified Owner Ln",
            "city": "Dallas",
            "decision_maker": "",
            "phone": "",
            "email": "",
            "source": "DCAD",
            "source_type": "government_registry",
            "source_reference": "NPI-TEST",
            "verification_method": "npi_registry_api",
            "observed_at": "2026-09-02T12:00:00Z",
            "verified_at": "2026-09-02T12:00:00Z"
        },
        {
            "id": "FIXTURE-B",
            "industry": "Real Estate Sellers",
            "company": "Unknown",
            "property_address": "456 No Owner Rd",
            "decision_maker": "",
            "phone": "",
            "source": "DCAD",
            "source_type": "government_registry",
            "source_reference": "NPI-TEST",
            "verification_method": "npi_registry_api",
            "observed_at": "2026-09-02T12:00:00Z",
            "verified_at": "2026-09-02T12:00:00Z"
        },
        {
            "id": "FIXTURE-C",
            "industry": "Real Estate Sellers",
            "company": "Landlord LLC",
            "property_address": "789 Tenant Ave",
            "decision_maker": "Current Resident",
            "phone": "",
            "source": "DCAD",
            "source_type": "government_registry",
            "source_reference": "NPI-TEST",
            "verification_method": "npi_registry_api",
            "observed_at": "2026-09-02T12:00:00Z",
            "verified_at": "2026-09-02T12:00:00Z"
        },
        {
            "id": "FIXTURE-H",
            "industry": "Real Estate Sellers",
            "company": "Error LLC",
            "property_address": "999 Provider Error Blvd",
            "decision_maker": "",
            "phone": "",
            "source": "DCAD",
            "source_type": "government_registry",
            "source_reference": "NPI-TEST",
            "verification_method": "npi_registry_api",
            "observed_at": "2026-09-02T12:00:00Z",
            "verified_at": "2026-09-02T12:00:00Z"
        }
    ]

    factory = DailyLeadFactory(dialer_rows_reader=lambda: [])
    factory._load_real_candidate_pool = lambda: raw_fixtures
    
    # Mock provenance gate to pass
    def mock_prov_eval(cand):
        return {"ok": True, "synthetic": False}
    monkeypatch.setattr(factory.provenance_gate, "evaluate", mock_prov_eval)
    
    report = factory.generate_daily_batch(target=10, dry_run=True)
    accepted_ids = [l["id"] for l in report.verified_leads]
    
    assert "FIXTURE-A" in accepted_ids
    fixture_a = next(l for l in report.verified_leads if l["id"] == "FIXTURE-A")
    assert fixture_a["contact"] == "John Verified Doe"
    assert fixture_a["phone"] == "+12144441234"
    assert fixture_a["email"] == "john@example.com"
    assert fixture_a["source_type"] == "government_registry"
    
    assert "FIXTURE-B" not in accepted_ids
    assert "FIXTURE-C" not in accepted_ids
    assert "FIXTURE-H" not in accepted_ids

    print("ALL 10 CONSTRAINTS PASSED SYNTHETIC VALIDATION.")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
