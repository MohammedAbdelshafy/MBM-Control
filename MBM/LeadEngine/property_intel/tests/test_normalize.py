"""normalize module tests — deterministic, idempotent, never fabricates."""
from property_intel import normalize


def test_normalize_address_full_line():
    assert normalize.normalize_address("12124 Schroeder Rd, Dallas, TX 75243") == "12124 SCHROEDER RD"


def test_normalize_street_expands_directionals_and_suffixes():
    assert normalize.normalize_street("123 North Main Street") == "123 N MAIN ST"


def test_normalize_street_compresses_whitespace_and_punct():
    assert normalize.normalize_street("  1510   Glen Ave,  ") == "1510 GLEN AVE"
    assert normalize.normalize_street("") == ""


def test_parse_city_state_zip_comma_form():
    assert normalize.parse_city_state_zip("DALLAS, TX 75243") == ("DALLAS", "TX", "75243")


def test_parse_city_state_zip_space_form():
    assert normalize.parse_city_state_zip("DALLAS TX 75243") == ("DALLAS", "TX", "75243")


def test_parse_city_state_zip_guards_street_suffix():
    # 'DR' must not be misread as a state or city; zip is still extracted.
    assert normalize.parse_city_state_zip("DALLAS DR 75243") == ("", "", "75243")


def test_parse_city_state_zip_zip_only():
    assert normalize.parse_city_state_zip("75243") == ("", "", "75243")


def test_split_address_parts_both_forms():
    a = normalize.split_address_parts("123 Main St, Dallas, TX 75243")
    b = normalize.split_address_parts("123 Main St Dallas TX 75243")
    assert a == b == {
        "address": "123 Main St",
        "city": "Dallas",
        "state": "TX",
        "zip_code": "75243",
    }


def test_infer_county_from_city_tx():
    assert normalize.infer_county_from_city("TX", "Dallas") == "Dallas"
    assert normalize.infer_county_from_city("TX", "Houston") == "Harris"
    assert normalize.infer_county_from_city("TX", "Unknown Town") == ""
    assert normalize.infer_county_from_city("CA", "Los Angeles") == ""


def test_dedupe_key_parcel_wins():
    assert normalize.dedupe_key("00000719884000000", "12124 Schroeder Rd", "TX") == "parcel:00000719884000000"


def test_dedupe_key_address_uses_state():
    assert normalize.dedupe_key("", "12124 Schroeder Rd", "TX") == "addr:12124 SCHROEDER RD|TX"


def test_dedupe_key_empty():
    assert normalize.dedupe_key("", "", "TX") == ""


def test_normalize_record_canonical_fields():
    rec = normalize.normalize_record({
        "property_address": "3134 Arizona Ave, Dallas, TX 75216",
        "auction_status": "pre-foreclosure",
        "opening_bid": "140000",
        "estimated_value": "280000",
        "occupancy_signal": "vacant",
    })
    assert rec["address"] == "3134 Arizona Ave"
    assert rec["address_normalized"] == "3134 ARIZONA AVE"
    assert rec["city"] == "Dallas"
    assert rec["state"] == "TX"
    assert rec["county"] == "Dallas"
    assert rec["zip_code"] == "75216"
    assert rec["auction_status"] == "pre-foreclosure"


def test_normalize_record_legacy_title_case_fields():
    rec = normalize.normalize_record({
        "Property_Address": "1510 Glen Ave, Dallas, TX 75204",
        "Status": "Foreclosure Auction",
        "County": "Dallas",
    })
    assert rec["auction_status"] == "foreclosure"
    assert rec["county"] == "Dallas"


def test_normalize_record_unknown_status():
    rec = normalize.normalize_record({"property_address": "1 Elm St, Dallas, TX", "auction_status": "zombie"})
    assert rec["auction_status"] == "unknown"


def test_dedupe_records_keeps_earliest_source_date():
    older = {"parcel_id": "P1", "address": "12124 Schroeder Rd", "state": "TX", "source_date": "2026-08-01"}
    newer = {"parcel_id": "P1", "address": "12124 Schroeder Rd", "state": "TX", "source_date": "2026-08-10"}
    out = normalize.dedupe_records([newer, older])
    assert len(out) == 1
    assert out[0]["source_date"] == "2026-08-01"