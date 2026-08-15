"""ownership_verifier tests — hermetic (arcgis_query mocked), ambiguity-safe.

The core integrity contract: an owner is asserted only when the source returned
it AND the match is unambiguous. Multiple distinct owners at the same site
address must yield CONFLICT with NO owner name, never a guess.
"""
import pytest

from property_intel.normalize import dedupe_key, normalize_record
from property_intel.ownership_verifier import (
    ArcGisAssessorAdapter,
    CountyRoutedVerifier,
    _address_match_score,
    apply_verification,
    build_registry_from_sources,
    verify_ownership,
)

DCAD = {
    "name": "Dallas Central Appraisal District (DCAD)",
    "endpoint": "https://maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4",
    "fields": {
        "address": "SITEADDRESS",
        "owner1": "OWNERNME1",
        "owner2": "OWNERNME2",
        "mailing": "PSTLADDRESS",
        "parcel": "PARCELID",
    },
}

DCAD_REC = normalize_record({
    "property_address": "12124 Schroeder Rd, Dallas, TX 75243",
    "parcel_id": "00000719884000000",
})
DCAD_REC["dedupe_key"] = dedupe_key("00000719884000000", DCAD_REC["address"], DCAD_REC["state"])

SCHROEDER_ROW = {
    "SITEADDRESS": "12124 SCHROEDER RD",
    "OWNERNME1": "CHANDLER TAMECA",
    "PARCELID": "00000719884000000",
    "PSTLADDRESS": "12124 SCHROEDER RD",
}


def make_dcad_adapter():
    return ArcGisAssessorAdapter(DCAD["name"], DCAD["endpoint"], DCAD["fields"])


# ── match scoring ─────────────────────────────────────────────────────────
def test_address_match_score_exact():
    assert _address_match_score("12124 SCHROEDER RD", "12124", "Schroeder", "12124 Schroeder Rd") == 5.0


def test_address_match_score_number_and_first_word():
    assert _address_match_score("1300 MAIN", "1300", "Main", "1300 Main St") >= 4.0


def test_address_match_score_weak_number_mismatch():
    assert _address_match_score("1400 OAK AVE", "1300", "Main", "1300 Main St") < 2.0


# ── verify: unique single owner -> VERIFIED ──────────────────────────────
def test_verify_unique_owner_verified(monkeypatch):
    adapter = make_dcad_adapter()

    def fake_query(endpoint, where, out_fields, **kw):
        return [SCHROEDER_ROW]

    monkeypatch.setattr("property_intel.ownership_verifier.arcgis_query", fake_query)
    v = adapter.verify(DCAD_REC)
    assert v.verification_status == "VERIFIED"
    assert v.owner_name == "CHANDLER TAMECA"
    assert v.parcel_id == "00000719884000000"
    assert v.confidence >= 0.85


# ── verify: parcel (APN) lookup -> VERIFIED even if address weak ─────────
def test_verify_parcel_lookup_exact(monkeypatch):
    adapter = make_dcad_adapter()

    def fake_query(endpoint, where, out_fields, **kw):
        return [SCHROEDER_ROW]

    monkeypatch.setattr("property_intel.ownership_verifier.arcgis_query", fake_query)
    v = adapter.verify(DCAD_REC)  # rec carries parcel_id -> parcel-first
    assert v.verification_status == "VERIFIED"
    assert v.owner_name == "CHANDLER TAMECA"


# ── ambiguity: multiple distinct owners -> CONFLICT, no owner asserted ───
def test_verify_ambiguous_owners_conflict(monkeypatch):
    adapter = make_dcad_adapter()
    owners = ["MOSQUEDA MEREIDA I & JOSE J", "ARMSTRONG DAVID & ELIZABETH",
              "IGLESIA MISIONMERA BIBLICA", "LA GRANGE ACQUISTION LP", "SSRB LLC"]

    def fake_query(endpoint, where, out_fields, **kw):
        return [{"SITEADDRESS": "1300 MAIN", "OWNERNME1": o, "PARCELID": f"P{i}"}
                for i, o in enumerate(owners)]

    monkeypatch.setattr("property_intel.ownership_verifier.arcgis_query", fake_query)
    v = adapter.verify(normalize_record({"property_address": "1300 Main St, Houston, TX"}))
    assert v.verification_status == "CONFLICT"
    assert v.owner_name == ""
    assert v.confidence < 0.5


# ── _build parcel ambiguity directly ─────────────────────────────────────
def test_build_parcel_multiple_owners_conflict():
    adapter = make_dcad_adapter()
    feats = [
        {"SITEADDRESS": "12124 SCHROEDER RD", "OWNERNME1": "PERSON A", "PARCELID": "00000719884000000"},
        {"SITEADDRESS": "12124 SCHROEDER RD", "OWNERNME1": "PERSON B", "PARCELID": "00000719884000000"},
    ]
    v = adapter._build(DCAD_REC, feats, parcel_lookup=True)
    assert v.verification_status == "CONFLICT"
    assert v.owner_name == ""


# ── no candidates -> NOT_FOUND ───────────────────────────────────────────
def test_verify_no_candidates_not_found(monkeypatch):
    adapter = make_dcad_adapter()

    def fake_query(endpoint, where, out_fields, **kw):
        return []

    monkeypatch.setattr("property_intel.ownership_verifier.arcgis_query", fake_query)
    v = adapter.verify(normalize_record({"property_address": "999 Unknown Ln, Dallas, TX"}))
    assert v.verification_status == "NOT_FOUND"
    assert v.owner_name == ""
    assert v.confidence == 0.0


def test_verify_empty_address_not_found():
    adapter = make_dcad_adapter()
    v = adapter.verify({})
    assert v.verification_status == "NOT_FOUND"


# ── offline convenience ──────────────────────────────────────────────────
def test_verify_ownership_offline_no_network():
    v = verify_ownership(DCAD_REC, live=False)
    assert v.verification_status == "NOT_FOUND"
    assert v.source == "offline"


def test_verify_ownership_live_routes_to_dcad(monkeypatch):
    def fake_query(endpoint, where, out_fields, **kw):
        return [SCHROEDER_ROW]

    monkeypatch.setattr("property_intel.ownership_verifier.arcgis_query", fake_query)
    v = verify_ownership(DCAD_REC, live=True)
    assert v.verification_status == "VERIFIED"
    assert v.owner_name == "CHANDLER TAMECA"


def test_build_registry_from_sources_contains_dallas():
    registry = build_registry_from_sources()
    assert ("TX", "Dallas") in registry


def test_county_routed_no_adapter_not_found():
    verifier = CountyRoutedVerifier({})
    v = verifier.verify({"state": "IL", "county": "Cook", "address": "1 Main St", "dedupe_key": "x"})
    assert v.verification_status == "NOT_FOUND"


# ── apply_verification annotates without mutating truth ──────────────────
def test_apply_verification_annotates():
    v = verify_ownership(DCAD_REC, live=False)
    out = apply_verification(DCAD_REC, v)
    assert out["ownership_status"] == "NOT_FOUND"
    assert out["ownership_source"] == "offline"
    assert out["ownership_evidence"][0]["source"] == "offline"
    assert "owner_name" in out