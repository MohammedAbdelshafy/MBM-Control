"""county_registry tests — property -> county -> official source routing."""
from property_intel.county_registry import (
    has_arcgis_adapter,
    list_counties,
    resolve_county,
    route_property,
)


def test_resolve_county_explicit_beats_inference():
    assert resolve_county("TX", "Dallas", "Tarrant") == "Tarrant"


def test_resolve_county_from_city():
    assert resolve_county("TX", "Dallas") == "Dallas"
    assert resolve_county("TX", "Houston") == "Harris"


def test_resolve_county_unknown():
    assert resolve_county("", "") == ""
    assert resolve_county("CA", "Los Angeles") == ""


def test_route_property_dallas_has_official_source():
    r = route_property({"state": "TX", "city": "Dallas", "address": "12124 Schroeder Rd"})
    assert r["county"] == "Dallas"
    assert r["county_resolved"] is True
    assert r["routed"] is True
    assert "DCAD" in r["source"]["authority"]


def test_route_property_missing_county_reports_missing():
    r = route_property({"state": "TX"})
    assert r["county"] == ""
    assert "county" in r["missing"]
    assert r["routed"] is False


def test_has_arcgis_adapter_only_verified():
    assert has_arcgis_adapter("TX", "Dallas") is True
    assert has_arcgis_adapter("IL", "Cook") is False  # official website only


def test_list_counties_tx_nonempty():
    counties = list_counties("TX")
    assert "Dallas" in counties
    assert "Harris" in counties


def test_list_counties_all():
    all_counties = list_counties()
    assert len(all_counties) > 20