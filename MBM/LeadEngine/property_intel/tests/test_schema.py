"""schema tests — owner classification + money parsing."""
from property_intel.schema import (
    BusinessProspect,
    OwnershipVerification,
    PropertyRecord,
    classify_owner_type,
    money_to_float,
)


def test_classify_owner_type_entity():
    assert classify_owner_type("Harmon Property Services LLC") == "entity"
    assert classify_owner_type("BLUEBONNET GENERAL CONTRACTING LP") == "entity"


def test_classify_owner_type_trust():
    assert classify_owner_type("The Smith Family Trust") == "trust"
    assert classify_owner_type("JANE DOE TRUSTEE") == "trust"


def test_classify_owner_type_individual():
    assert classify_owner_type("Chandler Tameca") == "individual"
    assert classify_owner_type("MOSQUEDA MEREIDA I & JOSE J") == "individual"


def test_classify_owner_type_unknown():
    assert classify_owner_type("") == "unknown"
    assert classify_owner_type(None) == "unknown"


def test_money_to_float():
    assert money_to_float("$225,000") == 225000.0
    assert money_to_float("140000") == 140000.0
    assert money_to_float("") is None
    assert money_to_float(None) is None
    assert money_to_float("n/a") is None


def test_ownership_verification_evidence_roundtrip():
    from property_intel.schema import SourceRef

    src = SourceRef(source="DCAD", source_url="https://dallascad.org", verification_status="VERIFIED")
    ov = OwnershipVerification(
        property_key="addr:12124 SCHROEDER RD|TX",
        owner_name="Chandler Tameca",
        owner_type="individual",
        parcel_id="00000719884000000",
        verification_status="VERIFIED",
        confidence=0.95,
        evidence=[src],
    )
    d = ov.to_dict()
    assert d["owner_name"] == "Chandler Tameca"
    assert d["evidence"][0]["source"] == "DCAD"
    assert d["confidence"] == 0.95


def test_property_record_requires_provenance_fields():
    rec = PropertyRecord(address="1 Main St", state="TX", source="auction.com", source_url="https://auction.com")
    d = rec.to_dict()
    assert d["source"] == "auction.com"
    assert "retrieved_at" in d


def test_business_prospect_never_invents_owner():
    p = BusinessProspect(company_name="X Roofing")
    assert p.owner_name == ""
    assert p.verification_status == "UNVERIFIED"